# websocket_routes.py - Updated with new message types
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from utils import manager, get_redis_service
from services.redis_service import RedisService
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

async def broadcast_submissions_status(redis_service: RedisService):
    """Helper function to broadcast the current submission statuses to everyone."""
    submissions = await redis_service.get_submissions()
    await redis_service.redis_client.publish("broadcast", json.dumps({
        "type": "submission_status_update",
        "payload": submissions
    }))

@router.websocket("/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str, redis_service: RedisService = Depends(get_redis_service)):
    """
    Enhanced WebSocket handler supporting:
    - Image broadcasting
    - Video sharing
    - Event frame management
    - DRES submissions
    - Submission tracking
    """
    session_id = f"session:{username}"
    if not await redis_service.redis_client.exists(session_id):
        await websocket.close(code=1008, reason="User session not found")
        return

    await manager.connect(websocket)
    logger.info(f"User {username} connected to WebSocket")

    # Send current submission status to newly connected user
    await broadcast_submissions_status(redis_service)

    # Notify all users of connection
    await redis_service.redis_client.publish("broadcast", json.dumps({
        "type": "user_status",
        "payload": {"message": f"User {username} has connected."}
    }))

    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                message_data = json.loads(data_text)
                message_type = message_data.get("type")
                logger.info(f"Received message type: {message_type} from {username}")

                if message_type == "broadcast_image":
                    await handle_broadcast_image(message_data, redis_service)

                elif message_type == "broadcast_video":
                    await handle_broadcast_video(message_data, redis_service, username)

                elif message_type == "event_frame_added":
                    await handle_event_frame_added(message_data, redis_service, username)

                elif message_type == "dres_submission":
                    await handle_dres_submission(message_data, redis_service, username)

                elif message_type == "submission_result":
                    await handle_submission_result(message_data, redis_service)

                elif message_type == "remove_broadcast":
                    await handle_remove_broadcast(message_data, redis_service, username)

                else:
                    # Forward unknown message types
                    logger.info(f"Forwarding unknown message type: {message_type}")
                    await redis_service.redis_client.publish("broadcast", json.dumps(message_data))

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error from {username}: {e}")
                await redis_service.redis_client.publish("broadcast", json.dumps({
                    "type": "error",
                    "payload": {"message": "Invalid JSON format received."}
                }))
            except Exception as e:
                logger.error(f"Error processing message from {username}: {e}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"User {username} disconnected from WebSocket")
        await redis_service.redis_client.publish("broadcast", json.dumps({
            "type": "user_status",
            "payload": {"message": f"User {username} has disconnected."}
        }))
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket for {username}: {e}")
        manager.disconnect(websocket)

# Message Handlers

async def handle_broadcast_image(message_data, redis_service):
    """Handle image broadcast messages"""
    payload = message_data.get("payload", {})
    image_key = payload.get("thumbnail")

    if image_key:
        # Save submission as PENDING in Redis
        await redis_service.set_submission(image_key=image_key, status="PENDING")
        # Broadcast updated status
        await broadcast_submissions_status(redis_service)

    # Forward original message
    await redis_service.redis_client.publish("broadcast", json.dumps(message_data))

async def handle_broadcast_video(message_data, redis_service, username):
    """Handle video sharing messages"""
    payload = message_data.get("payload", {})
    
    # Log video sharing event
    logger.info(f"User {username} shared video: {payload.get('videoId')} at timestamp {payload.get('timestamp')}")
    
    # Store video sharing event in Redis (optional, for analytics)
    video_share_key = f"video_shares:{payload.get('videoId')}:{int(payload.get('timestamp', 0))}"
    await redis_service.redis_client.hset(video_share_key, mapping={
        "shared_by": username,
        "timestamp": payload.get('timestamp', 0),
        "shared_at": json.dumps({"time": "now"})  # You might want to use actual timestamp
    })
    await redis_service.redis_client.expire(video_share_key, 3600)  # Expire after 1 hour
    
    # Forward message to all users
    await redis_service.redis_client.publish("broadcast", json.dumps(message_data))

async def handle_event_frame_added(message_data, redis_service, username):
    """Handle event frame addition messages"""
    payload = message_data.get("payload", {})
    event_id = payload.get("eventId")
    frame = payload.get("frame", {})
    
    # Store event frame in Redis
    if event_id and frame:
        event_key = f"event_frames:{event_id}:{username}"
        frame_data = json.dumps(frame)
        await redis_service.redis_client.lpush(event_key, frame_data)
        await redis_service.redis_client.expire(event_key, 7200)  # Expire after 2 hours
        
        logger.info(f"Added frame to {event_id} by {username}: {frame.get('id')}")
    
    # Forward message to all users
    await redis_service.redis_client.publish("broadcast", json.dumps(message_data))

async def handle_dres_submission(message_data, redis_service, username):
    """Handle DRES submission messages"""
    payload = message_data.get("payload", {})
    event_id = payload.get("eventId")
    frames = payload.get("frames", [])
    
    # Store DRES submission
    if event_id and frames:
        submission_key = f"dres_submissions:{event_id}:{username}:{payload.get('timestamp')}"
        submission_data = {
            "event_id": event_id,
            "frame_count": len(frames),
            "frames": json.dumps(frames),
            "submitted_by": username,
            "submitted_at": payload.get('timestamp')
        }
        await redis_service.redis_client.hset(submission_key, mapping=submission_data)
        await redis_service.redis_client.expire(submission_key, 86400)  # Expire after 24 hours
        
        # Clear the event frames after submission
        event_key = f"event_frames:{event_id}:{username}"
        await redis_service.redis_client.delete(event_key)
        
        logger.info(f"DRES submission from {username}: {event_id} with {len(frames)} frames")
    
    # Forward message to all users
    await redis_service.redis_client.publish("broadcast", json.dumps(message_data))

async def handle_submission_result(message_data, redis_service):
    """Handle submission result messages"""
    payload = message_data.get("payload", {})
    item_id = payload.get("itemId")  # thumbnail URL
    submission_status = payload.get("submission")

    if item_id:
        if submission_status == "CORRECT":
            # Remove item from Redis
            await redis_service.remove_submission(image_key=item_id)
            # Clear all caches on correct submission
            await redis_service.clear_submissions()
            await redis_service.flush_all_user_cache()
            await redis_service.flush_all_user_dislike_labels()
            
        elif submission_status in ["WRONG", "DUPLICATE"]:
            await redis_service.set_submission(image_key=item_id, status="WRONG")
            
        elif submission_status == 'ERROR':
            await redis_service.clear_submissions()

        # Broadcast updated submission status
        await broadcast_submissions_status(redis_service)

    # Forward the original message
    await redis_service.redis_client.publish("broadcast", json.dumps(message_data))

async def handle_remove_broadcast(message_data, redis_service, username):
    """Handle broadcast message removal"""
    message_id = message_data.get("messageId")
    
    if message_id:
        logger.info(f"User {username} removed broadcast message: {message_id}")
    
    # Forward message to all users
    await redis_service.redis_client.publish("broadcast", json.dumps(message_data))