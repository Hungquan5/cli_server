from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from db import get_connection, release_connection
from services.redis_service import RedisService
from utils import get_redis_service
from model import Keyframe
from fastapi import APIRouter, Depends

router = APIRouter()

# NEW BATCH ENDPOINTS FOR INFINITE SCROLLING

@router.get("/dislike_cluster")
async def dislike_cluster(
    video_id: str = Query(...),
    frame_index: int = Query(...),
    redis_service: RedisService = Depends(get_redis_service),
    user_id: str = "anonymous"
):
    """User dislike cluster label của một keyframe"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT label
        FROM cluster
        WHERE video_id = %s AND frame_id = %s
    """, (video_id, frame_index))
    
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    print("row: ", row)
    label = row[0]
    if label == None:
        raise HTTPException(status_code=404, detail="Label not found")

    # Lưu vào Redis
    await redis_service.add_dislike_label(user_id=user_id, label=label)
    # Xóa các cache kết quả trên redis của user
    await redis_service.flush_user_cache(user_id=user_id)
    return {"message": f"User {user_id} disliked cluster {label}"}

@router.get("/un_dislike_cluster")
async def dislike_cluster(
    video_id: str = Query(...),
    frame_index: int = Query(...),
    redis_service: RedisService = Depends(get_redis_service),
    user_id: str = "anonymous"
):
    """User dislike cluster label của một keyframe"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT label
        FROM cluster
        WHERE video_id = %s AND frame_id = %s
    """, (video_id, frame_index))
    
    row = cur.fetchone()
    cur.close()
    release_connection(conn)

    label = row[0]
    if label == None:
        raise HTTPException(status_code=404, detail="Label not found")

    # Lưu vào Redis
    await redis_service.remove_dislike_label(user_id=user_id, label=label)
    # Xóa các cache kết quả trên redis của user
    await redis_service.flush_user_cache(user_id=user_id)
    return {"message": f"User {user_id} disliked cluster {label}"}
    

@router.get("/batch-next", response_model=list[Keyframe])
def get_batch_next_keyframes(
    video_id: str = Query(...),
    frame_index: int = Query(...),
    batch_size: int = Query(default=10, ge=1, le=50)
):
    """Get a batch of keyframes after the specified frame_index"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT video_id, frame_id, frame_name
        FROM keyframes
        WHERE video_id = %s AND frame_id > %s
        ORDER BY frame_id ASC
        LIMIT %s;
    """, (video_id, frame_index, batch_size))
    
    rows = cur.fetchall()
    cur.close()
    # conn.close()
    release_connection(conn)
    
    if not rows:
        raise HTTPException(status_code=404, detail="No more keyframes found in this direction")
    
    return [Keyframe(video_id=row[0], frame_index=row[1], filename=row[2]) for row in rows]

@router.get("/batch-prev", response_model=list[Keyframe])
def get_batch_prev_keyframes(
    video_id: str = Query(...),
    frame_index: int = Query(...),
    batch_size: int = Query(default=10, ge=1, le=50)
):
    """Get a batch of keyframes before the specified frame_index"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT video_id, frame_id, frame_name
        FROM keyframes
        WHERE video_id = %s AND frame_id < %s
        ORDER BY frame_id DESC
        LIMIT %s;
    """, (video_id, frame_index, batch_size))
    
    rows = cur.fetchall()
    cur.close()
    # conn.close()
    release_connection(conn)
    
    if not rows:
        raise HTTPException(status_code=404, detail="No more keyframes found in this direction")
    
    # Reverse the order to return frames in ascending order by frame_id
    # (since we fetched them in DESC order to get the closest ones first)
    rows.reverse()
    
    return [Keyframe(video_id=row[0], frame_index=row[1], filename=row[2]) for row in rows]

@router.get("/batch-around", response_model=list[Keyframe])
def get_batch_keyframes_around(
    video_id: str = Query(...),
    frame_index: int = Query(...),
    batch_size: int = Query(default=20, ge=2, le=100)
):
    """Get a batch of keyframes around the specified frame_index (half before, half after)"""
    conn = get_connection()
    cur = conn.cursor()
    
    # Calculate how many frames to get on each side
    half_batch = batch_size // 2
    
    # Get frames before current frame
    cur.execute("""
        SELECT video_id, frame_id, frame_name
        FROM keyframes
        WHERE video_id = %s AND frame_id < %s
        ORDER BY frame_id DESC
        LIMIT %s;
    """, (video_id, frame_index, half_batch))
    before_rows = cur.fetchall()
    
    # Get current frame
    cur.execute("""
        SELECT video_id, frame_id, frame_name
        FROM keyframes
        WHERE video_id = %s AND frame_id = %s;
    """, (video_id, frame_index))
    current_row = cur.fetchone()
    
    # Get frames after current frame
    # If we have current frame, get fewer after frames to maintain batch_size
    remaining_slots = batch_size - len(before_rows) - (1 if current_row else 0)
    cur.execute("""
        SELECT video_id, frame_id, frame_name
        FROM keyframes
        WHERE video_id = %s AND frame_id > %s
        ORDER BY frame_id ASC
        LIMIT %s;
    """, (video_id, frame_index, remaining_slots))
    after_rows = cur.fetchall()
    
    cur.close()
    # conn.close()
    release_connection(conn)
    
    # Combine results in correct order
    all_rows = []
    # Add before frames (reverse order since we got them DESC)
    all_rows.extend(reversed(before_rows))
    # Add current frame if it exists
    if current_row:
        all_rows.append(current_row)
    # Add after frames
    all_rows.extend(after_rows)
    
    if not all_rows:
        raise HTTPException(status_code=404, detail="No keyframes found around the specified frame")
    
    return [Keyframe(video_id=row[0], frame_index=row[1], filename=row[2]) for row in all_rows]

@router.get("/nearest", response_model=Keyframe)
def get_nearest_keyframe(
    video_id: str = Query(...),
    frame_index: int = Query(...),
):
    """Get the nearest keyframe to an approximate frame_index"""
    conn = get_connection()
    cur = conn.cursor()

    # Method 1: Single query approach (most efficient)
    cur.execute("""
        SELECT video_id, frame_id, frame_name,
               ABS(frame_id - %s) as distance
        FROM keyframes
        WHERE video_id = %s
        ORDER BY distance ASC, frame_id ASC
        LIMIT 1;
    """, (frame_index, video_id))
    
    result = cur.fetchone()
    cur.close()
    release_connection(conn)
    
    if not result:
        raise HTTPException(status_code=404, detail="No keyframes found for this video")
    
    return Keyframe(
        video_id=result[0], 
        frame_index=result[1], 
        filename=result[2]
    )