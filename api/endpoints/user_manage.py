# session_routes.py
from fastapi import APIRouter, Depends, HTTPException
from utils import get_redis_service
import json

router = APIRouter()

@router.post("/connect/{username}", tags=["Session Management"])
async def connect_user(username: str, redis_service = Depends(get_redis_service)):
    """
    Handles user connection by storing their information in Redis.
    A session ID is created based on the username.
    """
    session_id = f"session:{username}"
    
    await redis_service.redis_client.set(session_id, json.dumps({
        "username": username, 
        "status": "active",
        "websocket_status": "disconnected"
    }))
    return {"message": f"User {username} connected and session created."}

@router.delete("/disconnect/{username}", tags=["Session Management"])
async def disconnect_user(username: str, redis_service = Depends(get_redis_service)):
    """
    Handles user disconnection by removing their session data from Redis.
    This endpoint should be called when the user leaves the web application.
    """
    session_id = f"session:{username}"
    history_id = f"history:{username}"
    
    # Check if session exists
    session_data = await redis_service.redis_client.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail=f"Session for user {username} not found")
    
    # Delete the session and history
    await  redis_service.redis_client.delete(session_id)
    await redis_service.redis_client.delete(history_id)
    await redis_service.flush_user_dislike_labels(user_id=username)
    
    return {"message": f"User {username} disconnected and session data cleared."}
