# utils.py
from fastapi import WebSocket
from services.redis_service import RedisService
from services.client_service import OpenAIService
import threading
from typing import List
import json
import logging
from redis.asyncio import Redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accepts and adds a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New WebSocket connection. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Removes a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_to_all(self, message: str):
        """Sends a message to all active connections."""
        connections_to_remove = []
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending message to connection: {e}")
                connections_to_remove.append(connection)
        for connection in connections_to_remove:
            self.disconnect(connection)

    async def subscribe_broadcasts(self, redis: Redis, channel_name: str = "broadcast"):
        """Listens to Redis pub/sub channel and relays messages to WebSocket clients."""
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel_name)
        logger.info(f"Subscribed to Redis channel '{channel_name}'")

        async for message in pubsub.listen():
            if message["type"] == "message":
                await self.send_to_all(message["data"].decode())
            # elif message["type"] == ""
    
    async def broadcast(self, message: str):
        """Sends a message to all active connections."""
        if self.active_connections:
            # Create a copy of the list to avoid issues with concurrent modifications
            connections_to_remove = []
            
            for connection in self.active_connections[:]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error sending message to connection: {e}")
                    connections_to_remove.append(connection)
            
            # Remove failed connections
            for connection in connections_to_remove:
                self.disconnect(connection)

# Create a single instance of the ConnectionManager
manager = ConnectionManager()

class ServiceManager:
    def __init__(self):
        self.redis_service = RedisService()
        self.openai_service = OpenAIService()

    def get_redis_service(self):
        return self.redis_service
    
    def get_openai_service(self):
        return self.openai_service

service_manager = ServiceManager()

def get_redis_service() -> RedisService:
    return service_manager.get_redis_service()

def get_openai_service() -> OpenAIService:
    return service_manager.get_openai_service()
