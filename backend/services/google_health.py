"""
Google Health API — OAuth link + nutrition-log sync.

Uses Restricted scope googlehealth.nutrition.writeonly.
Tokens are Fernet-encrypted at rest (key derived from JWT_SECRET).
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

from config import settings
from database.connection import get_db
from utils.recipe_fields import columns_to_nutrition

logger = logging.getLogger(__name__)

NUTRITION_SCOPE = "https://www.googleapis.com/auth/googlehealth.nutrition.writeonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
HEALTH_BASE = "https://health.googleapis.com/v4"
DATA_TYPE = "nutrition-log"


def client_id() -> str:
    return (
        os.environ.get("GOOGLE_HEALTH_CLIENT_ID")
        or os.environ.get("GOOGLE_CLIENT_ID")
        or ""
    ).strip()


def client_secret() -> str:
    return (
        os.environ.get("GOOGLE_HEALTH_CLIENT_SECRET")
        or os.environ.get("GOOGLE_CLIENT_SECRET")
        or ""
    ).strip()


def is_configured() -> bool:
    return bool(client_id() and client_secret())


def oauth_redirect_base() -> str:
    return (
        os.environ.get("OAUTH_REDIRECT_BASE_URL")
        or settings.oauth_redirect_base_url
        or "http://localhost:3001"
    ).rstrip("/")


def allowed_redirect_uris() -> set[str]:
    base = oauth_redirect_base()
    return {
        f"{base}/oauth/callback/google-health",
        "laro://oauth/callback/google-health",
    }


def validate_redirect_uri(redirect_uri: str) -> str:
    allowed = allowed_redirect_uris()
    if redirect_uri not in allowed:
        raise ValueError("Invalid redirect_uri")
    return redirect_uri


def _fernet() -> Fernet:
    raw = (os.environ.get("GOOGLE_HEALTH_TOKEN_KEY") or settings.jwt_secret or "").encode()
    digest = hashlib.sha256(raw).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_token(cipher: str) -> str:
    try:
        return _fernet().decrypt(cipher.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt Google Health token") from exc


def build_auth_url(state: str, redirect_uri: str) -> str:
    params = {
        "client_id": client_id(),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": NUTRITION_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, redirect_uri: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id(),
                "client_secret": client_secret(),
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        logger.warning("Google Health token exchange failed: %s %s", resp.status_code, resp.text[:300])
        raise ValueError("Failed to exchange authorization code")
    return resp.json()


async def refresh_access_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": client_id(),
                "client_secret": client_secret(),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code != 200:
        logger.warning("Google Health token refresh failed: %s %s", resp.status_code, resp.text[:300])
        raise ValueError("Failed to refresh Google Health token")
    return resp.json()


def _parse_expires_at(tokens: dict) -> Optional[datetime]:
    expires_in = tokens.get("expires_in")
    if expires_in is None:
        return None
    try:
        return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=int(expires_in))
    except (TypeError, ValueError):
        return None


async def get_link(user_id: str) -> Optional[dict]:
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM google_health_links WHERE user_id = $1",
            user_id,
        )
    return dict(row) if row else None


async def upsert_link(
    user_id: str,
    tokens: dict,
    google_sub: Optional[str] = None,
) -> dict:
    access = tokens.get("access_token")
    refresh = tokens.get("refresh_token")
    if not access:
        raise ValueError("Missing access_token")

    existing = await get_link(user_id)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires_at = _parse_expires_at(tokens)
    scopes = tokens.get("scope") or NUTRITION_SCOPE

    pool = await get_db()
    async with pool.acquire() as conn:
        if existing:
            # Keep prior refresh token if Google omits it on re-consent
            refresh_enc = (
                encrypt_token(refresh)
                if refresh
                else existing["refresh_token_enc"]
            )
            await conn.execute(
                """
                UPDATE google_health_links SET
                    access_token_enc = $1,
                    refresh_token_enc = $2,
                    token_expires_at = $3,
                    scopes = $4,
                    google_sub = COALESCE($5, google_sub),
                    updated_at = $6
                WHERE user_id = $7
                """,
                encrypt_token(access),
                refresh_enc,
                expires_at,
                scopes,
                google_sub,
                now,
                user_id,
            )
            link_id = existing["id"]
        else:
            if not refresh:
                raise ValueError("Missing refresh_token — reconnect with consent prompt")
            link_id = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO google_health_links (
                    id, user_id, google_sub, access_token_enc, refresh_token_enc,
                    token_expires_at, scopes, sync_on_cook, linked_at, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,TRUE,$8,$8)
                """,
                link_id,
                user_id,
                google_sub,
                encrypt_token(access),
                encrypt_token(refresh),
                expires_at,
                scopes,
                now,
            )
    return await get_link(user_id)  # type: ignore[return-value]


async def delete_link(user_id: str) -> bool:
    pool = await get_db()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM google_health_links WHERE user_id = $1",
            user_id,
        )
    return result.endswith("1")


async def set_sync_on_cook(user_id: str, enabled: bool) -> Optional[dict]:
    pool = await get_db()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE google_health_links
            SET sync_on_cook = $1, updated_at = $2
            WHERE user_id = $3
            """,
            enabled,
            now,
            user_id,
        )
    return await get_link(user_id)


async def _valid_access_token(link: dict) -> str:
    access = decrypt_token(link["access_token_enc"])
    expires_at = link.get("token_expires_at")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    needs_refresh = False
    if expires_at is None:
        needs_refresh = False  # try current token first
    elif isinstance(expires_at, datetime):
        # refresh 2 minutes early
        needs_refresh = expires_at <= (now + timedelta(minutes=2))
    if not needs_refresh:
        return access

    refresh = decrypt_token(link["refresh_token_enc"])
    tokens = await refresh_access_token(refresh)
    await upsert_link(link["user_id"], tokens, google_sub=link.get("google_sub"))
    return tokens["access_token"]


def _meal_type_for_time(when: datetime) -> str:
    """Map local/UTC hour to a Google Health MealType enum value."""
    hour = when.astimezone(timezone.utc).hour if when.tzinfo else when.hour
    if 5 <= hour < 11:
        return "BREAKFAST"
    if 11 <= hour < 15:
        return "LUNCH"
    if 17 <= hour < 22:
        return "DINNER"
    return "SNACK"


def _nutrition_payload(
    title: str,
    nutrition: dict,
    servings: float = 1.0,
    when: Optional[datetime] = None,
) -> dict:
    when = when or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    start = when - timedelta(minutes=30)
    end = when

    def _num(key: str) -> float:
        raw = nutrition.get(key)
        if raw is None:
            return 0.0
        try:
            return float(raw) * float(servings)
        except (TypeError, ValueError):
            return 0.0

    calories = _num("calories")
    protein = _num("protein")
    carbs = _num("carbs")
    fat = _num("fat")
    fiber = _num("fiber")
    sugar = _num("sugar")
    sodium_mg = _num("sodium")  # stored as mg in Laro

    nutrients: list[dict] = []
    if protein > 0:
        nutrients.append({"nutrient": "PROTEIN", "quantity": {"grams": round(protein, 2)}})
    if fiber > 0:
        nutrients.append({"nutrient": "FIBER", "quantity": {"grams": round(fiber, 2)}})
    if sugar > 0:
        nutrients.append({"nutrient": "SUGAR", "quantity": {"grams": round(sugar, 2)}})
    if sodium_mg > 0:
        nutrients.append(
            {"nutrient": "SODIUM", "quantity": {"grams": round(sodium_mg / 1000.0, 4)}}
        )

    body: dict[str, Any] = {
        "nutritionLog": {
            "interval": {
                "startTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "endTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "foodDisplayName": (title or "Recipe")[:200],
            # Google Health accepts BREAKFAST|LUNCH|DINNER|SNACK only (not UNKNOWN).
            "mealType": _meal_type_for_time(when),
            "serving": {"amount": float(servings)},
        }
    }
    nl = body["nutritionLog"]
    if calories > 0:
        nl["energy"] = {"kcal": round(calories, 1)}
    if carbs > 0:
        nl["totalCarbohydrate"] = {"grams": round(carbs, 2)}
    if fat > 0:
        nl["totalFat"] = {"grams": round(fat, 2)}
    if nutrients:
        nl["nutrients"] = nutrients
    return body


def _extract_data_point_name(payload: dict) -> Optional[str]:
    if not payload:
        return None
    if payload.get("name") and "/dataPoints/" in str(payload.get("name")):
        return payload["name"]
    resp = payload.get("response") or {}
    if isinstance(resp, dict) and resp.get("name"):
        return resp["name"]
    return None


async def create_nutrition_log(
    access_token: str,
    title: str,
    nutrition: dict,
    servings: float = 1.0,
    when: Optional[datetime] = None,
) -> str:
    body = _nutrition_payload(title, nutrition, servings=servings, when=when)
    url = f"{HEALTH_BASE}/users/me/dataTypes/{DATA_TYPE}/dataPoints"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
    if resp.status_code not in (200, 201):
        logger.warning(
            "Google Health nutrition create failed: %s %s",
            resp.status_code,
            resp.text[:400],
        )
        raise ValueError(f"Google Health API error ({resp.status_code})")

    data = resp.json()
    name = _extract_data_point_name(data)
    if not name and data.get("done") is False and data.get("name"):
        # Long-running op — poll once
        op_name = data["name"]
        async with httpx.AsyncClient(timeout=30.0) as client:
            for _ in range(5):
                op = await client.get(
                    f"https://health.googleapis.com/v4/{op_name}",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if op.status_code != 200:
                    break
                op_data = op.json()
                if op_data.get("done"):
                    name = _extract_data_point_name(op_data)
                    break
    if not name:
        raise ValueError("Google Health create returned no data point name")
    return name


async def batch_delete_nutrition_logs(access_token: str, names: list[str]) -> None:
    if not names:
        return
    url = f"{HEALTH_BASE}/users/me/dataTypes/{DATA_TYPE}/dataPoints:batchDelete"
    last_error = None
    async with httpx.AsyncClient(timeout=60.0) as client:
        for attempt in range(3):
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={"names": names},
            )
            if resp.status_code in (200, 201):
                return
            # Transient Google outages are common on batchDelete
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                import asyncio
                await asyncio.sleep(1.5 * (attempt + 1))
                last_error = resp
                continue
            logger.warning(
                "Google Health batchDelete failed: %s %s",
                resp.status_code,
                resp.text[:400],
            )
            raise ValueError(f"Google Health delete error ({resp.status_code})")
    if last_error is not None:
        raise ValueError(f"Google Health delete error ({last_error.status_code})")


async def list_nutrition_logs(user_id: str, limit: int = 20) -> list[dict]:
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, recipe_id, cook_session_id, food_display_name, calories,
                   created_at, deleted_at
            FROM google_health_nutrition_logs
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
    out = []
    for row in rows:
        item = dict(row)
        for key in ("created_at", "deleted_at"):
            if item.get(key) is not None and hasattr(item[key], "isoformat"):
                item[key] = item[key].isoformat()
        out.append(item)
    return out


async def record_local_log(
    user_id: str,
    recipe_id: Optional[str],
    cook_session_id: Optional[str],
    data_point_name: str,
    food_display_name: str,
    calories: Optional[int],
) -> dict:
    pool = await get_db()
    log_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO google_health_nutrition_logs (
                id, user_id, recipe_id, cook_session_id, data_point_name,
                food_display_name, calories, created_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            """,
            log_id,
            user_id,
            recipe_id,
            cook_session_id,
            data_point_name,
            food_display_name,
            calories,
            now,
        )
    return {
        "id": log_id,
        "data_point_name": data_point_name,
        "food_display_name": food_display_name,
        "calories": calories,
    }


async def sync_recipe_to_google_health(
    user_id: str,
    recipe: dict,
    cook_session_id: Optional[str] = None,
    servings: float = 1.0,
) -> Optional[dict]:
    """
    Best-effort sync. Returns log metadata on success, None if skipped,
    raises on hard API failure after link exists.
    """
    link = await get_link(user_id)
    if not link:
        return None
    if not link.get("sync_on_cook", True):
        return None

    nutrition = columns_to_nutrition(recipe) or {}
    if not any(nutrition.get(k) for k in ("calories", "protein", "carbs", "fat")):
        return None

    title = recipe.get("title") or "Recipe"
    access = await _valid_access_token(link)
    name = await create_nutrition_log(
        access_token=access,
        title=title,
        nutrition=nutrition,
        servings=servings,
    )
    cal = nutrition.get("calories")
    try:
        cal_i = int(round(float(cal) * servings)) if cal is not None else None
    except (TypeError, ValueError):
        cal_i = None
    return await record_local_log(
        user_id=user_id,
        recipe_id=recipe.get("id"),
        cook_session_id=cook_session_id,
        data_point_name=name,
        food_display_name=title,
        calories=cal_i,
    )


async def delete_nutrition_log_for_user(user_id: str, log_id: str) -> bool:
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM google_health_nutrition_logs
            WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
            """,
            log_id,
            user_id,
        )
    if not row:
        return False

    link = await get_link(user_id)
    if not link:
        raise ValueError("Google Health not linked")

    access = await _valid_access_token(link)
    await batch_delete_nutrition_logs(access, [row["data_point_name"]])

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE google_health_nutrition_logs SET deleted_at = $1 WHERE id = $2",
            now,
            log_id,
        )
    return True


async def create_oauth_state(user_id: str, redirect_uri: str) -> str:
    state = uuid.uuid4().hex
    pool = await get_db()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO google_health_oauth_states (id, state, user_id, redirect_uri, created_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            str(uuid.uuid4()),
            state,
            user_id,
            redirect_uri,
            now,
        )
    return state


async def consume_oauth_state(state: str, user_id: str) -> dict:
    if not state:
        raise ValueError("Missing state")
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM google_health_oauth_states WHERE state = $1",
            state,
        )
        if not row:
            raise ValueError("Invalid or expired state")
        await conn.execute(
            "DELETE FROM google_health_oauth_states WHERE state = $1",
            state,
        )
    data = dict(row)
    if data["user_id"] != user_id:
        raise ValueError("State does not match user")
    created = data.get("created_at")
    if isinstance(created, datetime):
        age = datetime.now(timezone.utc).replace(tzinfo=None) - (
            created.replace(tzinfo=None) if created.tzinfo else created
        )
        if age > timedelta(minutes=15):
            raise ValueError("OAuth state expired")
    return data
