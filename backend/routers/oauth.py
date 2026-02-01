"""
OAuth Router - Google and GitHub OAuth authentication
Configure via environment variables:
- GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
- GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET
- OAUTH_REDIRECT_BASE_URL (e.g., http://localhost:3001)
"""
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from pydantic import BaseModel
from typing import Optional
from dependencies import create_token, get_current_user, user_repository, oauth_account_repository, oauth_state_repository
from utils.activity_logger import log_action, log_user_activity
from datetime import datetime, timezone
import uuid
import os
import httpx

router = APIRouter(prefix="/oauth", tags=["OAuth"])

# =============================================================================
# CONFIGURATION
# =============================================================================

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
OAUTH_REDIRECT_BASE_URL = os.environ.get("OAUTH_REDIRECT_BASE_URL", "http://localhost:3001")

# =============================================================================
# MODELS
# =============================================================================

class OAuthCallback(BaseModel):
    code: str
    state: Optional[str] = None

class OAuthLinkRequest(BaseModel):
    code: str
    provider: str

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def is_oauth_enabled(provider: str) -> bool:
    """Check if OAuth provider is configured"""
    if provider == "google":
        return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    elif provider == "github":
        return bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET)
    return False

# =============================================================================
# STATUS ENDPOINT
# =============================================================================

@router.get("/status")
async def get_oauth_status():
    """Get which OAuth providers are enabled"""
    return {
        "google": is_oauth_enabled("google"),
        "github": is_oauth_enabled("github")
    }

# =============================================================================
# GOOGLE OAUTH
# =============================================================================

@router.get("/google/auth-url")
async def get_google_auth_url(redirect_uri: str = Query(None)):
    """Get Google OAuth authorization URL"""
    if not is_oauth_enabled("google"):
        raise HTTPException(status_code=400, detail="Google OAuth is not configured")

    if not redirect_uri:
        redirect_uri = f"{OAUTH_REDIRECT_BASE_URL}/oauth/callback/google"

    state = uuid.uuid4().hex

    await oauth_state_repository.create({
        "id": str(uuid.uuid4()),
        "state": state,
        "provider": "google",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "consent"
    }

    query = "&".join(f"{k}={v}" for k, v in params.items())
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{query}"

    return {"auth_url": auth_url, "state": state}

@router.post("/google/callback")
async def google_callback(data: OAuthCallback):
    """Handle Google OAuth callback"""
    if not is_oauth_enabled("google"):
        raise HTTPException(status_code=400, detail="Google OAuth is not configured")

    if data.state:
        state_doc = await oauth_state_repository.find_and_delete(data.state)
        if not state_doc:
            raise HTTPException(status_code=400, detail="Invalid state parameter")

    redirect_uri = f"{OAUTH_REDIRECT_BASE_URL}/oauth/callback/google"

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": data.code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri
            }
        )

        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code for token")

        tokens = token_response.json()
        access_token = tokens.get("access_token")

        userinfo_response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if userinfo_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")

        userinfo = userinfo_response.json()

    google_id = userinfo.get("id")
    email = userinfo.get("email")

    if not email:
        raise HTTPException(status_code=400, detail="Could not retrieve email from Google")

    name = userinfo.get("name") or email.split("@")[0]

    oauth_link = await oauth_account_repository.find_by_provider("google", google_id)

    if oauth_link:
        user = await user_repository.find_by_id(oauth_link["user_id"])
        if not user:
            raise HTTPException(status_code=400, detail="User account not found")

        if user.get("status") == "suspended":
            raise HTTPException(status_code=403, detail="Account is suspended")

        await user_repository.update(user["id"], {
            "last_login": datetime.now(timezone.utc).isoformat()
        })

        # Log Google OAuth login
        await log_user_activity(
            user_id=user["id"],
            user_email=user.get("email", email),
            action="oauth_login",
            details={"provider": "google"}
        )

        token = create_token(user["id"])
        user.pop("password", None)
        return {"token": token, "user": user, "is_new": False}

    existing_user = await user_repository.find_by_email(email)

    if existing_user:
        await oauth_account_repository.create({
            "id": str(uuid.uuid4()),
            "user_id": existing_user["id"],
            "provider": "google",
            "provider_id": google_id,
            "provider_email": email,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        # Log Google account link
        await log_user_activity(
            user_id=existing_user["id"],
            user_email=existing_user.get("email", email),
            action="oauth_account_linked",
            details={"provider": "google"}
        )

        token = create_token(existing_user["id"])
        user_data = {k: v for k, v in existing_user.items() if k != "password"}
        return {"token": token, "user": user_data, "is_new": False}

    user_id = str(uuid.uuid4())
    user_count = await user_repository.count()
    role = "admin" if user_count == 0 else "user"

    user_doc = {
        "id": user_id,
        "email": email,
        "password": "",
        "name": name,
        "role": role,
        "status": "active",
        "household_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "oauth_only": True
    }

    await user_repository.create(user_doc)

    await oauth_account_repository.create({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "provider": "google",
        "provider_id": google_id,
        "provider_email": email,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    # Log new user registration via Google
    await log_user_activity(
        user_id=user_id,
        user_email=email,
        action="oauth_register",
        details={"provider": "google", "role": role}
    )

    token = create_token(user_id)
    user_data = {k: v for k, v in user_doc.items() if k != "password"}

    return {"token": token, "user": user_data, "is_new": True}

# =============================================================================
# GITHUB OAUTH
# =============================================================================

@router.get("/github/auth-url")
async def get_github_auth_url(redirect_uri: str = Query(None)):
    """Get GitHub OAuth authorization URL"""
    if not is_oauth_enabled("github"):
        raise HTTPException(status_code=400, detail="GitHub OAuth is not configured")

    if not redirect_uri:
        redirect_uri = f"{OAUTH_REDIRECT_BASE_URL}/oauth/callback/github"

    state = uuid.uuid4().hex

    await oauth_state_repository.create({
        "id": str(uuid.uuid4()),
        "state": state,
        "provider": "github",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "user:email",
        "state": state
    }

    query = "&".join(f"{k}={v}" for k, v in params.items())
    auth_url = f"https://github.com/login/oauth/authorize?{query}"

    return {"auth_url": auth_url, "state": state}

@router.post("/github/callback")
async def github_callback(data: OAuthCallback):
    """Handle GitHub OAuth callback"""
    if not is_oauth_enabled("github"):
        raise HTTPException(status_code=400, detail="GitHub OAuth is not configured")

    if data.state:
        state_doc = await oauth_state_repository.find_and_delete(data.state)
        if not state_doc:
            raise HTTPException(status_code=400, detail="Invalid state parameter")

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": data.code
            }
        )

        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code for token")

        tokens = token_response.json()
        access_token = tokens.get("access_token")

        if not access_token:
            raise HTTPException(status_code=400, detail=tokens.get("error_description", "OAuth failed"))

        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
        )

        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")

        github_user = user_response.json()

        email = github_user.get("email")
        if not email:
            email_response = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json"
                }
            )
            if email_response.status_code == 200:
                emails = email_response.json()
                primary = next((e for e in emails if e.get("primary")), None)
                if primary:
                    email = primary["email"]

    if not email:
        raise HTTPException(status_code=400, detail="Could not retrieve email from GitHub")

    github_id = str(github_user.get("id"))
    name = github_user.get("name") or github_user.get("login", email.split("@")[0])

    oauth_link = await oauth_account_repository.find_by_provider("github", github_id)

    if oauth_link:
        user = await user_repository.find_by_id(oauth_link["user_id"])
        if not user:
            raise HTTPException(status_code=400, detail="User account not found")

        if user.get("status") == "suspended":
            raise HTTPException(status_code=403, detail="Account is suspended")

        await user_repository.update(user["id"], {
            "last_login": datetime.now(timezone.utc).isoformat()
        })

        # Log GitHub OAuth login
        await log_user_activity(
            user_id=user["id"],
            user_email=user.get("email", email),
            action="oauth_login",
            details={"provider": "github"}
        )

        token = create_token(user["id"])
        user.pop("password", None)
        return {"token": token, "user": user, "is_new": False}

    existing_user = await user_repository.find_by_email(email)

    if existing_user:
        await oauth_account_repository.create({
            "id": str(uuid.uuid4()),
            "user_id": existing_user["id"],
            "provider": "github",
            "provider_id": github_id,
            "provider_email": email,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        # Log GitHub account link
        await log_user_activity(
            user_id=existing_user["id"],
            user_email=existing_user.get("email", email),
            action="oauth_account_linked",
            details={"provider": "github"}
        )

        token = create_token(existing_user["id"])
        user_data = {k: v for k, v in existing_user.items() if k != "password"}
        return {"token": token, "user": user_data, "is_new": False}

    user_id = str(uuid.uuid4())
    user_count = await user_repository.count()
    role = "admin" if user_count == 0 else "user"

    user_doc = {
        "id": user_id,
        "email": email,
        "password": "",
        "name": name,
        "role": role,
        "status": "active",
        "household_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "oauth_only": True
    }

    await user_repository.create(user_doc)

    await oauth_account_repository.create({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "provider": "github",
        "provider_id": github_id,
        "provider_email": email,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    # Log new user registration via GitHub
    await log_user_activity(
        user_id=user_id,
        user_email=email,
        action="oauth_register",
        details={"provider": "github", "role": role}
    )

    token = create_token(user_id)
    user_data = {k: v for k, v in user_doc.items() if k != "password"}

    return {"token": token, "user": user_data, "is_new": True}

# =============================================================================
# ACCOUNT LINKING
# =============================================================================

@router.get("/linked-accounts")
async def get_linked_accounts(user: dict = Depends(get_current_user)):
    """Get OAuth accounts linked to current user"""
    accounts = await oauth_account_repository.find_by_user(user["id"])
    return {"accounts": accounts}

@router.delete("/linked-accounts/{provider}")
async def unlink_account(provider: str, request: Request, user: dict = Depends(get_current_user)):
    """Unlink an OAuth account"""
    db_user = await user_repository.find_by_id(user["id"])
    if db_user.get("oauth_only") and not db_user.get("password"):
        oauth_count = await oauth_account_repository.count_by_user(user["id"])
        if oauth_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot unlink last OAuth account without setting a password first"
            )

    deleted = await oauth_account_repository.delete_by_user_and_provider(user["id"], provider)

    if not deleted:
        raise HTTPException(status_code=404, detail="OAuth account not found")

    # Log account unlink
    await log_action(
        user, "oauth_account_unlinked", request,
        details={"provider": provider}
    )

    return {"message": f"{provider.title()} account unlinked"}
