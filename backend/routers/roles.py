"""
Roles Router - Custom user roles management
Supports custom roles beyond admin/user with granular permissions
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from dependencies import get_current_user, custom_role_repository, user_repository, audit_log_repository
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/roles", tags=["Roles"])

# =============================================================================
# DEFAULT PERMISSIONS
# =============================================================================

# User permissions - full control of own data within household
DEFAULT_PERMISSIONS = {
    "recipes": {
        "create": True,
        "read": True,
        "update_own": True,
        "update_any": False,  # Can't edit other households' recipes
        "delete_own": True,
        "delete_any": False,
    },
    "meal_plans": {
        "create": True,
        "read": True,
        "update": True,
        "delete": True,
    },
    "shopping_lists": {
        "create": True,
        "read": True,
        "update": True,
        "delete": True,
    },
    "household": {
        "view_members": True,
        "invite_members": True,  # Users can invite to their household
        "remove_members": False,  # Only owner can remove
        "manage_settings": False,
    },
    "admin": {
        "view_users": False,
        "manage_users": False,
        "view_settings": False,
        "manage_settings": False,
        "view_audit_log": False,
        "manage_backups": False,
    },
    "data": {
        "export_own": True,  # GDPR - can export own data
        "delete_own": True,  # GDPR - can delete own account
    }
}

# Household owner permissions - full control of their household
OWNER_PERMISSIONS = {
    "recipes": {
        "create": True,
        "read": True,
        "update_own": True,
        "update_any": True,  # Can edit any recipe in their household
        "delete_own": True,
        "delete_any": True,  # Can delete any recipe in their household
    },
    "meal_plans": {
        "create": True,
        "read": True,
        "update": True,
        "delete": True,
    },
    "shopping_lists": {
        "create": True,
        "read": True,
        "update": True,
        "delete": True,
    },
    "household": {
        "view_members": True,
        "invite_members": True,
        "remove_members": True,  # Owner can remove members
        "manage_settings": True,  # Owner can manage household settings
    },
    "admin": {
        "view_users": False,
        "manage_users": False,
        "view_settings": False,
        "manage_settings": False,
        "view_audit_log": False,
        "manage_backups": False,
    },
    "data": {
        "export_own": True,
        "delete_own": True,
    }
}

# Admin permissions - manages their own household with some admin access
ADMIN_PERMISSIONS = {
    "recipes": {
        "create": True,
        "read": True,
        "update_own": True,
        "update_any": True,
        "delete_own": True,
        "delete_any": True,
    },
    "meal_plans": {
        "create": True,
        "read": True,
        "update": True,
        "delete": True,
    },
    "shopping_lists": {
        "create": True,
        "read": True,
        "update": True,
        "delete": True,
    },
    "household": {
        "view_members": True,
        "invite_members": True,
        "remove_members": True,
        "manage_settings": True,
    },
    "admin": {
        "view_users": True,
        "manage_users": True,
        "view_settings": True,
        "manage_settings": True,
        "view_audit_log": True,
        "manage_backups": True,
    },
    "data": {
        "export_own": True,
        "delete_own": True,
    }
}

# Super Admin permissions - App owner, can see/manage ALL users across ALL households
SUPER_ADMIN_PERMISSIONS = {
    "recipes": {
        "create": True,
        "read": True,
        "read_all": True,  # Can read any user's recipes
        "update_own": True,
        "update_any": True,
        "delete_own": True,
        "delete_any": True,
    },
    "meal_plans": {
        "create": True,
        "read": True,
        "read_all": True,
        "update": True,
        "delete": True,
    },
    "shopping_lists": {
        "create": True,
        "read": True,
        "read_all": True,
        "update": True,
        "delete": True,
    },
    "household": {
        "view_members": True,
        "view_all_households": True,  # Can see all households
        "invite_members": True,
        "remove_members": True,
        "manage_settings": True,
        "manage_any_household": True,  # Can manage any household
    },
    "admin": {
        "view_users": True,
        "manage_users": True,
        "view_all_users": True,  # Can see all users
        "manage_any_user": True,  # Can manage any user
        "view_settings": True,
        "manage_settings": True,
        "view_audit_log": True,
        "manage_backups": True,
        "manage_subscriptions": True,  # Can grant/revoke subscriptions
        "view_system_health": True,
    },
    "data": {
        "export_own": True,
        "export_any": True,  # Can export any user's data (support)
        "delete_own": True,
        "delete_any": True,  # Can delete any user (GDPR requests)
    }
}

# =============================================================================
# MODELS
# =============================================================================

class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    color: Optional[str] = "#6C5CE7"  # Brand purple
    permissions: Optional[dict] = None

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    permissions: Optional[dict] = None

class AssignRole(BaseModel):
    user_id: str
    role_id: str

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def get_user_permissions(user_id: str, household_id: str = None) -> dict:
    """
    Get effective permissions for a user based on their role.
    Also checks if user is household owner for elevated permissions.
    """
    from dependencies import household_repository

    user = await user_repository.find_by_id(user_id)
    if not user:
        return DEFAULT_PERMISSIONS

    role = user.get("role", "user")

    # Built-in roles (highest to lowest priority)
    if role == "super_admin":
        return SUPER_ADMIN_PERMISSIONS
    elif role == "admin":
        return ADMIN_PERMISSIONS

    # Check if user is household owner (gets owner permissions)
    user_household_id = household_id or user.get("household_id")
    if user_household_id:
        household = await household_repository.find_by_id(user_household_id)
        if household and household.get("owner_id") == user_id:
            return OWNER_PERMISSIONS

    # Standard user or custom role
    if role == "user":
        return DEFAULT_PERMISSIONS

    # Custom role
    custom_role = await custom_role_repository.find_by_id(role)
    if custom_role:
        return custom_role.get("permissions", DEFAULT_PERMISSIONS)

    return DEFAULT_PERMISSIONS


def is_super_admin(user: dict) -> bool:
    """Check if user is the app super admin"""
    return user.get("role") == "super_admin"


async def is_household_owner(user: dict) -> bool:
    """Check if user owns their household"""
    from dependencies import household_repository

    household_id = user.get("household_id")
    if not household_id:
        return True  # Solo users own their own data

    household = await household_repository.find_by_id(household_id)
    return household and household.get("owner_id") == user["id"]

async def check_permission(user: dict, category: str, action: str) -> bool:
    """Check if user has a specific permission"""
    permissions = await get_user_permissions(user["id"])
    return permissions.get(category, {}).get(action, False)

# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("")
async def list_roles(user: dict = Depends(get_current_user)):
    """List all custom roles"""
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    roles = await custom_role_repository.list_all()

    # Add built-in roles
    built_in = [
        {
            "id": "super_admin",
            "name": "Super Admin",
            "description": "App owner - full access to all users and households",
            "color": "#FF6B6B",
            "is_builtin": True,
            "permissions": SUPER_ADMIN_PERMISSIONS
        },
        {
            "id": "admin",
            "name": "Administrator",
            "description": "Full access within own household",
            "color": "#6C5CE7",
            "is_builtin": True,
            "permissions": ADMIN_PERMISSIONS
        },
        {
            "id": "owner",
            "name": "Household Owner",
            "description": "Full control of their household (auto-assigned)",
            "color": "#4ECDC4",
            "is_builtin": True,
            "is_auto": True,  # Automatically assigned based on household ownership
            "permissions": OWNER_PERMISSIONS
        },
        {
            "id": "user",
            "name": "User",
            "description": "Standard user - full access to own data",
            "color": "#00D2D3",
            "is_builtin": True,
            "permissions": DEFAULT_PERMISSIONS
        }
    ]

    return {"roles": built_in + roles}

@router.post("")
async def create_role(data: RoleCreate, user: dict = Depends(get_current_user)):
    """Create a custom role"""
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Check for duplicate name
    existing = await custom_role_repository.find_by_name(data.name)
    if existing:
        raise HTTPException(status_code=400, detail="Role name already exists")

    role_id = str(uuid.uuid4())
    role_doc = {
        "id": role_id,
        "name": data.name,
        "description": data.description,
        "color": data.color,
        "permissions": data.permissions or DEFAULT_PERMISSIONS,
        "is_builtin": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user["id"]
    }

    await custom_role_repository.create(role_doc)

    # Log action
    await audit_log_repository.create({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_email": user.get("email"),
        "action": "role_created",
        "details": {"role_name": data.name, "role_id": role_id},
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return role_doc

@router.get("/{role_id}")
async def get_role(role_id: str, user: dict = Depends(get_current_user)):
    """Get a specific role"""
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Check built-in roles first
    if role_id == "super_admin":
        return {
            "id": "super_admin",
            "name": "Super Admin",
            "description": "App owner - full access to all users and households",
            "color": "#FF6B6B",
            "is_builtin": True,
            "permissions": SUPER_ADMIN_PERMISSIONS
        }
    elif role_id == "admin":
        return {
            "id": "admin",
            "name": "Administrator",
            "description": "Full access within own household",
            "color": "#6C5CE7",
            "is_builtin": True,
            "permissions": ADMIN_PERMISSIONS
        }
    elif role_id == "owner":
        return {
            "id": "owner",
            "name": "Household Owner",
            "description": "Full control of their household (auto-assigned)",
            "color": "#4ECDC4",
            "is_builtin": True,
            "is_auto": True,
            "permissions": OWNER_PERMISSIONS
        }
    elif role_id == "user":
        return {
            "id": "user",
            "name": "User",
            "description": "Standard user - full access to own data",
            "color": "#00D2D3",
            "is_builtin": True,
            "permissions": DEFAULT_PERMISSIONS
        }

    role = await custom_role_repository.find_by_id(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    return role

@router.put("/{role_id}")
async def update_role(role_id: str, data: RoleUpdate, user: dict = Depends(get_current_user)):
    """Update a custom role"""
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Can't update built-in roles
    if role_id in ["admin", "user", "super_admin", "owner"]:
        raise HTTPException(status_code=400, detail="Cannot modify built-in roles")

    role = await custom_role_repository.find_by_id(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await custom_role_repository.update_role(role_id, update_data)

    return {"message": "Role updated"}

@router.delete("/{role_id}")
async def delete_role(role_id: str, user: dict = Depends(get_current_user)):
    """Delete a custom role"""
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Can't delete built-in roles
    if role_id in ["admin", "user", "super_admin", "owner"]:
        raise HTTPException(status_code=400, detail="Cannot delete built-in roles")

    # Check if any users have this role
    users_with_role = await user_repository.count({"role": role_id})
    if users_with_role > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete role: {users_with_role} user(s) still have this role"
        )

    result = await custom_role_repository.delete_role(role_id)
    if result == 0:
        raise HTTPException(status_code=404, detail="Role not found")

    return {"message": "Role deleted"}

@router.post("/assign")
async def assign_role(data: AssignRole, user: dict = Depends(get_current_user)):
    """Assign a role to a user"""
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Only super_admin can assign super_admin role
    if data.role_id == "super_admin" and user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admin can assign super admin role")

    # Verify role exists (owner is auto-assigned, not manually assignable)
    if data.role_id not in ["admin", "user", "super_admin"]:
        role = await custom_role_repository.find_by_id(data.role_id)
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")

    # Update user's role
    result = await user_repository.update_user(data.user_id, {"role": data.role_id})

    if result == 0:
        raise HTTPException(status_code=404, detail="User not found")

    # Log action
    await audit_log_repository.create({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_email": user.get("email"),
        "action": "role_assigned",
        "details": {"target_user_id": data.user_id, "role_id": data.role_id},
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return {"message": "Role assigned"}

@router.get("/permissions/default")
async def get_default_permissions(user: dict = Depends(get_current_user)):
    """Get the default permission template"""
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    return {"permissions": DEFAULT_PERMISSIONS}


@router.get("/my-permissions")
async def get_my_permissions(user: dict = Depends(get_current_user)):
    """Get current user's effective permissions"""
    permissions = await get_user_permissions(user["id"], user.get("household_id"))
    is_owner = await is_household_owner(user)

    return {
        "role": user.get("role", "user"),
        "is_household_owner": is_owner,
        "permissions": permissions
    }
