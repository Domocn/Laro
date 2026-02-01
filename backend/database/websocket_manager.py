"""
WebSocket Manager for Live Refresh
Handles real-time updates for shopping lists, recipes, meal plans, etc.
Supports Redis Pub/Sub for multi-instance deployments.
"""
import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from fastapi import WebSocket, WebSocketDisconnect
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of real-time events"""
    # Shopping list events
    SHOPPING_LIST_CREATED = "shopping_list:created"
    SHOPPING_LIST_UPDATED = "shopping_list:updated"
    SHOPPING_LIST_DELETED = "shopping_list:deleted"
    SHOPPING_LIST_ITEM_CHECKED = "shopping_list:item_checked"

    # Recipe events
    RECIPE_CREATED = "recipe:created"
    RECIPE_UPDATED = "recipe:updated"
    RECIPE_DELETED = "recipe:deleted"
    RECIPE_FAVORITED = "recipe:favorited"

    # Meal plan events
    MEAL_PLAN_CREATED = "meal_plan:created"
    MEAL_PLAN_UPDATED = "meal_plan:updated"
    MEAL_PLAN_DELETED = "meal_plan:deleted"

    # Household events
    HOUSEHOLD_MEMBER_JOINED = "household:member_joined"
    HOUSEHOLD_MEMBER_LEFT = "household:member_left"
    HOUSEHOLD_UPDATED = "household:updated"
    HOUSEHOLD_DELETED = "household:deleted"

    # Cook session events
    COOK_SESSION_STARTED = "cook_session:started"
    COOK_SESSION_COMPLETED = "cook_session:completed"

    # General events
    DATA_SYNC = "data:sync"
    PING = "ping"
    PONG = "pong"


@dataclass
class WebSocketConnection:
    """Represents a WebSocket connection with metadata"""
    websocket: WebSocket
    user_id: str
    household_id: Optional[str] = None
    subscriptions: Set[str] = field(default_factory=set)


class WebSocketManager:
    """
    Manages WebSocket connections and broadcasts real-time updates.
    Supports room-based subscriptions (user, household) for targeted updates.
    Supports Redis Pub/Sub for multi-instance deployments.
    """

    def __init__(self):
        # Map of connection_id -> WebSocketConnection
        self._connections: Dict[str, WebSocketConnection] = {}
        # Map of user_id -> set of connection_ids
        self._user_connections: Dict[str, Set[str]] = {}
        # Map of household_id -> set of connection_ids
        self._household_connections: Dict[str, Set[str]] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        # Connection counter for unique IDs
        self._counter = 0

        # Redis Pub/Sub support
        self._redis_client: Optional[redis.Redis] = None
        self._redis_pubsub: Optional[redis.client.PubSub] = None
        self._redis_enabled = False
        self._redis_listener_task: Optional[asyncio.Task] = None

    async def initialize_redis(self, redis_url: str):
        """
        Initialize Redis client for Pub/Sub.
        Call this at application startup.
        """
        try:
            self._redis_client = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self._redis_client.ping()
            self._redis_enabled = True
            logger.info(f"Redis Pub/Sub initialized: {redis_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            logger.warning("Running without Redis Pub/Sub (single-instance mode)")
            self._redis_enabled = False

    async def start_redis_listener(self):
        """
        Start the Redis Pub/Sub listener.
        Subscribes to all household and user channels.
        """
        if not self._redis_enabled or not self._redis_client:
            logger.info("Redis Pub/Sub disabled - running in single-instance mode")
            return

        try:
            self._redis_pubsub = self._redis_client.pubsub()
            # Subscribe to all household and user channels using pattern subscription
            await self._redis_pubsub.psubscribe("household:*", "user:*", "broadcast:*")

            logger.info("Redis Pub/Sub listener started")

            # Start background task to listen for messages
            self._redis_listener_task = asyncio.create_task(self._redis_listener_loop())
        except Exception as e:
            logger.error(f"Failed to start Redis listener: {e}")
            self._redis_enabled = False

    async def _redis_listener_loop(self):
        """
        Background task that listens for Redis Pub/Sub messages
        and forwards them to local WebSocket connections.
        """
        if not self._redis_pubsub:
            return

        try:
            async for message in self._redis_pubsub.listen():
                try:
                    if message["type"] == "pmessage":
                        await self._handle_redis_message(message)
                except Exception as e:
                    logger.error(f"Error handling Redis message: {e}")
                    # Continue processing other messages
                    continue
        except asyncio.CancelledError:
            logger.info("Redis listener task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in Redis listener loop: {e}", exc_info=True)
            # Don't attempt to reconnect to avoid crash loops
            # Just disable Redis and continue in single-instance mode
            self._redis_enabled = False
            logger.warning("Redis Pub/Sub disabled after error - continuing in single-instance mode")

    async def _handle_redis_message(self, message: dict):
        """
        Handle incoming Redis Pub/Sub messages and broadcast to local connections.
        """
        try:
            channel = message["channel"]
            data = json.loads(message["data"])

            event_type = data.get("type")
            event_data = data.get("data")

            # Parse channel to determine target
            if channel.startswith("household:"):
                household_id = channel.split(":", 1)[1]
                await self._broadcast_local_household(household_id, event_type, event_data)
            elif channel.startswith("user:"):
                user_id = channel.split(":", 1)[1]
                await self._broadcast_local_user(user_id, event_type, event_data)
            elif channel.startswith("broadcast:all"):
                await self._broadcast_local_all(event_type, event_data)

        except Exception as e:
            logger.error(f"Error handling Redis message: {e}")

    async def _broadcast_local_household(self, household_id: str, event_type: str, data: Any):
        """Broadcast to local connections in a household only (called by Redis listener)"""
        connection_ids = self._household_connections.get(household_id, set()).copy()
        for conn_id in connection_ids:
            await self.send_to_connection(conn_id, event_type, data)

    async def _broadcast_local_user(self, user_id: str, event_type: str, data: Any):
        """Broadcast to local connections for a user only (called by Redis listener)"""
        connection_ids = self._user_connections.get(user_id, set()).copy()
        for conn_id in connection_ids:
            await self.send_to_connection(conn_id, event_type, data)

    async def _broadcast_local_all(self, event_type: str, data: Any):
        """Broadcast to all local connections (called by Redis listener)"""
        for conn_id in list(self._connections.keys()):
            await self.send_to_connection(conn_id, event_type, data)

    async def _publish_to_redis(self, channel: str, event_type: EventType, data: Any):
        """Publish message to Redis Pub/Sub channel"""
        if not self._redis_enabled or not self._redis_client:
            return

        try:
            message = json.dumps({
                "type": event_type.value if isinstance(event_type, EventType) else event_type,
                "data": data
            })
            await self._redis_client.publish(channel, message)
        except Exception as e:
            logger.error(f"Failed to publish to Redis channel {channel}: {e}")

    async def shutdown(self):
        """Shutdown Redis connections gracefully"""
        try:
            if self._redis_listener_task:
                self._redis_listener_task.cancel()
                try:
                    await self._redis_listener_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error cancelling Redis listener task: {e}")

            if self._redis_pubsub:
                try:
                    await self._redis_pubsub.unsubscribe()
                    await self._redis_pubsub.close()
                except Exception as e:
                    logger.error(f"Error closing Redis pubsub: {e}")

            if self._redis_client:
                try:
                    await self._redis_client.close()
                except Exception as e:
                    logger.error(f"Error closing Redis client: {e}")

            logger.info("Redis connections closed")
        except Exception as e:
            logger.error(f"Error during Redis shutdown: {e}", exc_info=True)

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        household_id: Optional[str] = None
    ) -> str:
        """
        Accept a new WebSocket connection and register it.
        Returns the connection ID.
        """
        await websocket.accept()

        async with self._lock:
            self._counter += 1
            connection_id = f"conn_{user_id}_{self._counter}"

            connection = WebSocketConnection(
                websocket=websocket,
                user_id=user_id,
                household_id=household_id
            )

            self._connections[connection_id] = connection

            # Add to user connections
            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(connection_id)

            # Add to household connections
            if household_id:
                if household_id not in self._household_connections:
                    self._household_connections[household_id] = set()
                self._household_connections[household_id].add(connection_id)

            logger.info(f"WebSocket connected: {connection_id} (user={user_id}, household={household_id})")
            return connection_id

    async def disconnect(self, connection_id: str):
        """Remove a WebSocket connection"""
        async with self._lock:
            if connection_id not in self._connections:
                return

            connection = self._connections[connection_id]

            # Remove from user connections
            if connection.user_id in self._user_connections:
                self._user_connections[connection.user_id].discard(connection_id)
                if not self._user_connections[connection.user_id]:
                    del self._user_connections[connection.user_id]

            # Remove from household connections
            if connection.household_id and connection.household_id in self._household_connections:
                self._household_connections[connection.household_id].discard(connection_id)
                if not self._household_connections[connection.household_id]:
                    del self._household_connections[connection.household_id]

            del self._connections[connection_id]
            logger.info(f"WebSocket disconnected: {connection_id}")

    async def update_household(self, connection_id: str, household_id: Optional[str]):
        """Update the household association for a connection"""
        async with self._lock:
            if connection_id not in self._connections:
                return

            connection = self._connections[connection_id]
            old_household = connection.household_id

            # Remove from old household
            if old_household and old_household in self._household_connections:
                self._household_connections[old_household].discard(connection_id)
                if not self._household_connections[old_household]:
                    del self._household_connections[old_household]

            # Add to new household
            connection.household_id = household_id
            if household_id:
                if household_id not in self._household_connections:
                    self._household_connections[household_id] = set()
                self._household_connections[household_id].add(connection_id)

    async def send_to_connection(
        self,
        connection_id: str,
        event_type: EventType,
        data: Any
    ):
        """Send a message to a specific connection"""
        if connection_id not in self._connections:
            return

        connection = self._connections[connection_id]
        try:
            message = {
                "type": event_type.value if isinstance(event_type, EventType) else event_type,
                "data": data,
            }
            await connection.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending to {connection_id}: {e}")
            await self.disconnect(connection_id)

    async def broadcast_to_user(
        self,
        user_id: str,
        event_type: EventType,
        data: Any,
        exclude_connection: Optional[str] = None
    ):
        """Broadcast a message to all connections for a specific user"""
        # Broadcast to local connections
        connection_ids = self._user_connections.get(user_id, set()).copy()

        for conn_id in connection_ids:
            if conn_id != exclude_connection:
                await self.send_to_connection(conn_id, event_type, data)

        # Publish to Redis for other instances
        await self._publish_to_redis(f"user:{user_id}", event_type, data)

    async def broadcast_to_household(
        self,
        household_id: str,
        event_type: EventType,
        data: Any,
        exclude_connection: Optional[str] = None
    ):
        """Broadcast a message to all connections in a household"""
        # Broadcast to local connections
        connection_ids = self._household_connections.get(household_id, set()).copy()

        for conn_id in connection_ids:
            if conn_id != exclude_connection:
                await self.send_to_connection(conn_id, event_type, data)

        # Publish to Redis for other instances
        await self._publish_to_redis(f"household:{household_id}", event_type, data)

    async def broadcast_to_household_or_user(
        self,
        user_id: str,
        household_id: Optional[str],
        event_type: EventType,
        data: Any,
        exclude_connection: Optional[str] = None
    ):
        """
        Broadcast to household if user is in one, otherwise to user only.
        This is the main method for data updates that should be shared within households.
        """
        if household_id:
            await self.broadcast_to_household(household_id, event_type, data, exclude_connection)
        else:
            await self.broadcast_to_user(user_id, event_type, data, exclude_connection)

    async def broadcast_all(
        self,
        event_type: EventType,
        data: Any,
        exclude_connection: Optional[str] = None
    ):
        """Broadcast a message to all connected clients"""
        # Broadcast to local connections
        for conn_id in list(self._connections.keys()):
            if conn_id != exclude_connection:
                await self.send_to_connection(conn_id, event_type, data)

        # Publish to Redis for other instances
        await self._publish_to_redis("broadcast:all", event_type, data)

    async def handle_client_message(
        self,
        connection_id: str,
        message: dict
    ):
        """Handle incoming messages from clients"""
        msg_type = message.get("type", "")

        if msg_type == "ping":
            await self.send_to_connection(connection_id, EventType.PONG, {"timestamp": message.get("timestamp")})
        elif msg_type == "subscribe":
            # Handle subscription requests
            subscription = message.get("subscription")
            if subscription and connection_id in self._connections:
                self._connections[connection_id].subscriptions.add(subscription)
        elif msg_type == "unsubscribe":
            subscription = message.get("subscription")
            if subscription and connection_id in self._connections:
                self._connections[connection_id].subscriptions.discard(subscription)

    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return len(self._connections)

    def get_user_connection_count(self, user_id: str) -> int:
        """Get number of connections for a specific user"""
        return len(self._user_connections.get(user_id, set()))

    def get_household_connection_count(self, household_id: str) -> int:
        """Get number of connections in a household"""
        return len(self._household_connections.get(household_id, set()))

    def is_redis_enabled(self) -> bool:
        """Check if Redis Pub/Sub is enabled and connected"""
        return self._redis_enabled

    async def get_redis_health(self) -> dict:
        """Get Redis connection health status"""
        if not self._redis_enabled or not self._redis_client:
            return {
                "enabled": False,
                "connected": False,
                "mode": "single-instance"
            }

        try:
            # Use a timeout to prevent hanging
            await asyncio.wait_for(self._redis_client.ping(), timeout=2.0)
            return {
                "enabled": True,
                "connected": True,
                "mode": "multi-instance",
                "listener_running": self._redis_listener_task is not None and not self._redis_listener_task.done()
            }
        except asyncio.TimeoutError:
            logger.warning("Redis health check timed out")
            return {
                "enabled": True,
                "connected": False,
                "mode": "multi-instance",
                "error": "Connection timeout"
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "enabled": True,
                "connected": False,
                "mode": "multi-instance",
                "error": str(e)
            }


# Global WebSocket manager instance
ws_manager = WebSocketManager()


# Convenience functions for broadcasting events
async def broadcast_shopping_list_update(
    household_id: str,
    user_id: str,
    event_type: EventType,
    data: dict
):
    """Broadcast shopping list changes to household members"""
    await ws_manager.broadcast_to_household_or_user(
        user_id=user_id,
        household_id=household_id,
        event_type=event_type,
        data=data
    )


async def broadcast_recipe_update(
    household_id: Optional[str],
    user_id: str,
    event_type: EventType,
    data: dict
):
    """Broadcast recipe changes"""
    await ws_manager.broadcast_to_household_or_user(
        user_id=user_id,
        household_id=household_id,
        event_type=event_type,
        data=data
    )


async def broadcast_meal_plan_update(
    household_id: str,
    user_id: str,
    event_type: EventType,
    data: dict
):
    """Broadcast meal plan changes to household members"""
    await ws_manager.broadcast_to_household_or_user(
        user_id=user_id,
        household_id=household_id,
        event_type=event_type,
        data=data
    )


async def broadcast_household_update(
    household_id: str,
    event_type: EventType,
    data: dict
):
    """Broadcast household changes to all members"""
    await ws_manager.broadcast_to_household(
        household_id=household_id,
        event_type=event_type,
        data=data
    )
