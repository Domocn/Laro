"""
Remote Access Router - Laro Cloud Remote Access (similar to Home Assistant Cloud)

Allows users to:
1. Link their self-hosted Laro instance to a Laro Cloud account
2. Access their home instance from anywhere through the cloud relay
3. No port forwarding or dynamic DNS needed
"""
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import secrets
import uuid
import asyncio
import logging

from dependencies import get_current_user
from database.connection import get_db, dict_from_row, rows_to_dicts

router = APIRouter(prefix="/remote", tags=["remote-access"])
logger = logging.getLogger(__name__)

# In-memory store for active relay connections
# In production, this would use Redis for multi-instance support
active_relays: dict[str, WebSocket] = {}  # instance_id -> WebSocket connection


class CreateInstanceRequest(BaseModel):
    instance_name: str


class LinkInstanceRequest(BaseModel):
    linking_code: str


class InstanceResponse(BaseModel):
    id: str
    instance_name: str
    instance_id: str
    is_connected: bool
    last_connected_at: Optional[str]
    local_url: Optional[str]
    created_at: str


class LinkingCodeResponse(BaseModel):
    linking_code: str
    expires_at: str
    instance_id: str


# ============== Cloud Account Endpoints ==============

@router.post("/instances", response_model=InstanceResponse)
async def create_remote_instance(
    request: CreateInstanceRequest,
    user: dict = Depends(get_current_user)
):
    """Create a new remote instance entry for linking a self-hosted Laro"""
    pool = await get_db()

    instance_id = f"mise_{secrets.token_hex(8)}"
    record_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO remote_instances (id, user_id, instance_name, instance_id, created_at)
            VALUES ($1, $2, $3, $4, $5)
        """, record_id, user["id"], request.instance_name, instance_id, now)

        row = await conn.fetchrow("""
            SELECT * FROM remote_instances WHERE id = $1
        """, record_id)

    instance = dict_from_row(row)
    return InstanceResponse(
        id=instance["id"],
        instance_name=instance["instance_name"],
        instance_id=instance["instance_id"],
        is_connected=instance["is_connected"],
        last_connected_at=instance["last_connected_at"].isoformat() if instance["last_connected_at"] else None,
        local_url=instance["local_url"],
        created_at=instance["created_at"].isoformat()
    )


@router.get("/instances")
async def list_remote_instances(user: dict = Depends(get_current_user)):
    """List all remote instances linked to the user's cloud account"""
    pool = await get_db()

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM remote_instances WHERE user_id = $1 ORDER BY created_at DESC
        """, user["id"])

    instances = rows_to_dicts(rows)
    return {
        "instances": [
            {
                "id": i["id"],
                "instance_name": i["instance_name"],
                "instance_id": i["instance_id"],
                "is_connected": i["instance_id"] in active_relays,
                "last_connected_at": i["last_connected_at"].isoformat() if i["last_connected_at"] else None,
                "local_url": i["local_url"],
                "created_at": i["created_at"].isoformat()
            }
            for i in instances
        ]
    }


@router.post("/instances/{instance_id}/linking-code", response_model=LinkingCodeResponse)
async def generate_linking_code(
    instance_id: str,
    user: dict = Depends(get_current_user)
):
    """Generate a linking code for a self-hosted instance to connect"""
    pool = await get_db()

    # Generate a short, easy-to-type code
    linking_code = f"{secrets.token_hex(2)}-{secrets.token_hex(2)}".upper()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    async with pool.acquire() as conn:
        # Verify ownership
        row = await conn.fetchrow("""
            SELECT * FROM remote_instances WHERE instance_id = $1 AND user_id = $2
        """, instance_id, user["id"])

        if not row:
            raise HTTPException(status_code=404, detail="Instance not found")

        # Update with new linking code
        await conn.execute("""
            UPDATE remote_instances
            SET linking_code = $1, linking_code_expires = $2
            WHERE instance_id = $3
        """, linking_code, expires_at, instance_id)

    return LinkingCodeResponse(
        linking_code=linking_code,
        expires_at=expires_at.isoformat(),
        instance_id=instance_id
    )


@router.delete("/instances/{instance_id}")
async def delete_remote_instance(
    instance_id: str,
    user: dict = Depends(get_current_user)
):
    """Unlink and delete a remote instance"""
    pool = await get_db()

    async with pool.acquire() as conn:
        result = await conn.execute("""
            DELETE FROM remote_instances WHERE instance_id = $1 AND user_id = $2
        """, instance_id, user["id"])

    # Disconnect active relay if exists
    if instance_id in active_relays:
        try:
            await active_relays[instance_id].close()
        except:
            pass
        del active_relays[instance_id]

    return {"message": "Instance unlinked"}


# ============== Self-Hosted Instance Endpoints ==============

@router.post("/link")
async def link_to_cloud(request: LinkInstanceRequest):
    """
    Called by self-hosted Laro to link to a cloud account using a linking code.
    Returns connection credentials for the relay.
    """
    pool = await get_db()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        # Find instance by linking code
        row = await conn.fetchrow("""
            SELECT * FROM remote_instances
            WHERE linking_code = $1 AND linking_code_expires > $2
        """, request.linking_code.upper(), now)

        if not row:
            raise HTTPException(status_code=400, detail="Invalid or expired linking code")

        instance = dict_from_row(row)

        # Generate webhook ID for this instance
        webhook_id = secrets.token_urlsafe(32)

        # Clear the linking code and set webhook_id
        await conn.execute("""
            UPDATE remote_instances
            SET linking_code = NULL, linking_code_expires = NULL, webhook_id = $1
            WHERE id = $2
        """, webhook_id, instance["id"])

    return {
        "instance_id": instance["instance_id"],
        "webhook_id": webhook_id,
        "cloud_url": "wss://web-production-b3fb4.up.railway.app/api/v1/remote/relay",
        "message": "Successfully linked to Laro Cloud"
    }


@router.get("/connection-info")
async def get_connection_info():
    """Get cloud relay connection info for self-hosted instances"""
    return {
        "relay_url": "wss://web-production-b3fb4.up.railway.app/api/v1/remote/relay",
        "api_version": "v1"
    }


# ============== WebSocket Relay ==============

@router.websocket("/relay")
async def relay_websocket(websocket: WebSocket, instance_id: str, webhook_id: str):
    """
    WebSocket relay endpoint for self-hosted instances.
    Self-hosted Laro connects here to establish a persistent tunnel.
    """
    pool = await get_db()

    # Verify instance credentials
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM remote_instances
            WHERE instance_id = $1 AND webhook_id = $2
        """, instance_id, webhook_id)

        if not row:
            await websocket.close(code=4001)
            return

    await websocket.accept()
    logger.info(f"Remote instance connected: {instance_id}")

    # Register active relay
    active_relays[instance_id] = websocket

    # Update connection status
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE remote_instances
            SET is_connected = TRUE, last_connected_at = $1
            WHERE instance_id = $2
        """, now, instance_id)

    try:
        # Keep connection alive and handle messages
        while True:
            try:
                # Receive messages from self-hosted instance
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30)

                # Handle ping/pong for keep-alive
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

                # Handle relay responses (forwarded back to mobile app)
                elif data.get("type") == "response":
                    # Response handling would go here
                    pass

            except asyncio.TimeoutError:
                # Send ping to check connection
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        logger.info(f"Remote instance disconnected: {instance_id}")
    except Exception as e:
        logger.error(f"Relay error for {instance_id}: {e}")
    finally:
        # Cleanup
        if instance_id in active_relays:
            del active_relays[instance_id]

        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE remote_instances SET is_connected = FALSE WHERE instance_id = $1
            """, instance_id)


@router.websocket("/client")
async def client_relay(websocket: WebSocket, instance_id: str, token: str):
    """
    WebSocket endpoint for mobile apps to connect to their remote instance.
    Relays messages between mobile app and self-hosted instance through the cloud.
    """
    import jwt
    from config import settings

    # Verify user token
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("user_id")
    except:
        await websocket.close(code=4001)
        return

    pool = await get_db()

    # Verify user owns this instance
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM remote_instances
            WHERE instance_id = $1 AND user_id = $2
        """, instance_id, user_id)

        if not row:
            await websocket.close(code=4003)
            return

    # Check if instance is connected
    if instance_id not in active_relays:
        await websocket.close(code=4004)  # Instance offline
        return

    await websocket.accept()
    logger.info(f"Client connected to relay for instance: {instance_id}")

    instance_ws = active_relays[instance_id]

    try:
        while True:
            # Receive request from mobile app
            data = await websocket.receive_json()

            # Forward to self-hosted instance
            await instance_ws.send_json({
                "type": "request",
                "data": data
            })

            # Wait for response from instance
            response = await instance_ws.receive_json()

            # Forward response back to mobile app
            await websocket.send_json(response.get("data", response))

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from instance: {instance_id}")
    except Exception as e:
        logger.error(f"Client relay error: {e}")


# ============== HTTP Relay (for REST API calls) ==============

@router.api_route("/proxy/{instance_id}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_request(
    instance_id: str,
    path: str,
    user: dict = Depends(get_current_user)
):
    """
    HTTP proxy for REST API calls to remote instances.
    Forwards requests through the WebSocket relay.
    """
    pool = await get_db()

    # Verify user owns this instance
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM remote_instances
            WHERE instance_id = $1 AND user_id = $2
        """, instance_id, user["id"])

        if not row:
            raise HTTPException(status_code=404, detail="Instance not found")

    # Check if instance is connected
    if instance_id not in active_relays:
        raise HTTPException(status_code=503, detail="Instance is offline")

    # For now, return that the instance is available
    # Full implementation would forward the request through WebSocket
    return {
        "status": "connected",
        "instance_id": instance_id,
        "message": "Use WebSocket relay for real-time communication"
    }
