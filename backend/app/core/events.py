"""
Redis Event Bus - Pub/Sub for Real-time SSE Streaming

WHY THIS EXISTS:
The previous SSE implementation used database polling, which held DB connections
open indefinitely while waiting for updates. This caused QueuePool exhaustion:

    sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 20 reached

This module replaces polling with Redis Pub/Sub:
1. Writers publish events to Redis channels (fire-and-forget)
2. Readers subscribe to channels and yield events (no DB connection)
3. DB connections are only used for initial data fetch, then released

Architecture:
    [Agent writes log] → DB.commit() → redis.publish("task:{id}", event)
                                                    ↓
    [SSE endpoint] ← redis.subscribe("task:{id}") ←┘
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator

import redis.asyncio as redis
import structlog

from backend.app.config import settings

logger = structlog.get_logger(__name__)


# =============================================================================
# Event Types
# =============================================================================


@dataclass
class Event:
    """Represents a pub/sub event."""

    channel: str
    event_type: str
    data: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps({
            "event_type": self.event_type,
            "data": self.data,
        })

    @classmethod
    def from_json(cls, channel: str, raw: bytes | str) -> "Event":
        parsed = json.loads(raw)
        return cls(
            channel=channel,
            event_type=parsed.get("event_type", "unknown"),
            data=parsed.get("data", {}),
        )


# =============================================================================
# Channel Naming Convention
# =============================================================================


def task_channel(task_id: str) -> str:
    """Get the Redis channel name for a task."""
    return f"task:{task_id}"


def global_channel() -> str:
    """Get the Redis channel for global events."""
    return "global:events"


# =============================================================================
# Redis Event Bus
# =============================================================================


class RedisEventBus:
    """
    Redis-based event bus for real-time pub/sub.

    CRITICAL: This class enables zero-DB SSE streaming.
    Write operations publish events to Redis.
    Read operations subscribe to Redis channels.
    No database connections are held open during streaming.

    Usage:
        # Publishing (fire-and-forget)
        await event_bus.publish(task_channel(task_id), "agent_log", {...})

        # Subscribing (yields events forever)
        async for event in event_bus.subscribe(task_channel(task_id)):
            yield event.data
    """

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or settings.redis_url
        self._pool: redis.ConnectionPool | None = None
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        """Initialize Redis connection pool."""
        if self._pool is None:
            self._pool = redis.ConnectionPool.from_url(
                self.redis_url,
                decode_responses=True,
                max_connections=50,
            )
            self._client = redis.Redis(connection_pool=self._pool)

            # Test connection
            try:
                await self._client.ping()
                logger.info("redis_event_bus_connected", url=self.redis_url[:20] + "...")
            except redis.ConnectionError as e:
                logger.error("redis_connection_failed", error=str(e))
                raise

    async def disconnect(self) -> None:
        """Close Redis connection pool."""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._pool:
            await self._pool.disconnect()
            self._pool = None
        logger.info("redis_event_bus_disconnected")

    @asynccontextmanager
    async def get_client(self) -> AsyncGenerator[redis.Redis, None]:
        """Get a Redis client, auto-connecting if needed."""
        if self._client is None:
            await self.connect()
        yield self._client

    # =========================================================================
    # Publishing (Write Side)
    # =========================================================================

    async def publish(
        self,
        channel: str,
        event_type: str,
        data: dict[str, Any],
    ) -> int:
        """
        Publish an event to a Redis channel.

        This is fire-and-forget - returns immediately after publish.
        Does NOT hold any database connections.

        Args:
            channel: The Redis channel (e.g., "task:{id}")
            event_type: Event type (e.g., "agent_log", "status", "complete")
            data: Event payload

        Returns:
            Number of subscribers that received the message
        """
        event = Event(channel=channel, event_type=event_type, data=data)

        async with self.get_client() as client:
            num_subscribers = await client.publish(channel, event.to_json())

        logger.debug(
            "event_published",
            channel=channel,
            event_type=event_type,
            subscribers=num_subscribers,
        )

        return num_subscribers

    async def publish_task_event(
        self,
        task_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """
        Convenience method to publish a task-specific event.

        Publishes to both the task-specific channel and global channel.
        """
        # Task-specific channel
        await self.publish(task_channel(task_id), event_type, data)

        # Global channel (for dashboards watching all activity)
        await self.publish(global_channel(), event_type, {**data, "task_id": task_id})

    # =========================================================================
    # Subscribing (Read Side)
    # =========================================================================

    async def subscribe(
        self,
        channel: str,
        timeout_seconds: float = 0,
    ) -> AsyncGenerator[Event, None]:
        """
        Subscribe to a Redis channel and yield events.

        CRITICAL: This generator does NOT hold any database connections.
        It only maintains a Redis subscription, which is lightweight.

        Args:
            channel: The Redis channel to subscribe to
            timeout_seconds: Max time to wait for events (0 = forever)

        Yields:
            Event objects as they arrive
        """
        async with self.get_client() as client:
            pubsub = client.pubsub()
            await pubsub.subscribe(channel)

            logger.info("redis_subscribed", channel=channel)

            try:
                start_time = asyncio.get_event_loop().time()

                while True:
                    # Check timeout
                    if timeout_seconds > 0:
                        elapsed = asyncio.get_event_loop().time() - start_time
                        if elapsed > timeout_seconds:
                            logger.info("subscription_timeout", channel=channel)
                            break

                    # Get message with short timeout (allows checking for cancellation)
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )

                    if message and message["type"] == "message":
                        try:
                            event = Event.from_json(channel, message["data"])
                            yield event
                        except json.JSONDecodeError as e:
                            logger.warning(
                                "invalid_event_json",
                                channel=channel,
                                error=str(e),
                            )

            except asyncio.CancelledError:
                logger.info("subscription_cancelled", channel=channel)
                raise
            finally:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()

    async def subscribe_multiple(
        self,
        channels: list[str],
    ) -> AsyncGenerator[Event, None]:
        """Subscribe to multiple channels and yield events from all."""
        async with self.get_client() as client:
            pubsub = client.pubsub()

            for channel in channels:
                await pubsub.subscribe(channel)

            logger.info("redis_subscribed_multiple", channels=channels)

            try:
                while True:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )

                    if message and message["type"] == "message":
                        try:
                            event = Event.from_json(
                                message["channel"],
                                message["data"],
                            )
                            yield event
                        except json.JSONDecodeError:
                            pass

            except asyncio.CancelledError:
                raise
            finally:
                for channel in channels:
                    await pubsub.unsubscribe(channel)
                await pubsub.aclose()


# =============================================================================
# Global Instance
# =============================================================================

# Singleton event bus instance
_event_bus: RedisEventBus | None = None


def get_event_bus() -> RedisEventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = RedisEventBus()
    return _event_bus


async def init_event_bus() -> RedisEventBus:
    """Initialize and return the global event bus."""
    bus = get_event_bus()
    await bus.connect()
    return bus


async def shutdown_event_bus() -> None:
    """Shutdown the global event bus."""
    global _event_bus
    if _event_bus:
        await _event_bus.disconnect()
        _event_bus = None
