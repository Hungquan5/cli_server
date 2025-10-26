from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from db import get_async_connection
from services.redis_service import RedisService
from utils import get_redis_service
from model import Keyframe
from fastapi import APIRouter, Depends
import asyncio
from typing import List, Optional

router = APIRouter()

# ========== TRULY ASYNC DATABASE FUNCTIONS ==========

async def fetch_keyframes_by_direction(
    video_id: str, 
    frame_index: int, 
    batch_size: int, 
    direction: str = "next"
) -> Optional[List[Keyframe]]:
    """
    Truly async function to fetch keyframes in any direction.
    No blocking, no threadpool needed!
    """
    async with get_async_connection() as conn:
        if direction == "next":
            rows = await conn.fetch("""
                SELECT video_id, frame_id, frame_name
                FROM keyframes
                WHERE video_id = $1 AND frame_id > $2
                ORDER BY frame_id ASC
                LIMIT $3;
            """, video_id, frame_index, batch_size)
            
        elif direction == "prev":
            rows = await conn.fetch("""
                SELECT video_id, frame_id, frame_name
                FROM keyframes
                WHERE video_id = $1 AND frame_id < $2
                ORDER BY frame_id DESC
                LIMIT $3;
            """, video_id, frame_index, batch_size)
            # Reverse to get ascending order
            rows = list(reversed(rows))
            
        elif direction == "around":
            half_batch = batch_size // 2
            
            # Single optimized query with UNION
            rows = await conn.fetch("""
                (
                    SELECT video_id, frame_id, frame_name
                    FROM keyframes
                    WHERE video_id = $1 AND frame_id < $2
                    ORDER BY frame_id DESC
                    LIMIT $3
                )
                UNION ALL
                (
                    SELECT video_id, frame_id, frame_name
                    FROM keyframes
                    WHERE video_id = $1 AND frame_id = $2
                )
                UNION ALL
                (
                    SELECT video_id, frame_id, frame_name
                    FROM keyframes
                    WHERE video_id = $1 AND frame_id > $2
                    ORDER BY frame_id ASC
                    LIMIT $4
                )
                ORDER BY frame_id ASC;
            """, video_id, frame_index, half_batch, batch_size - half_batch - 1)
        
        else:
            raise ValueError(f"Invalid direction: {direction}")
        
        if not rows:
            return None
        
        return [Keyframe(video_id=row['video_id'], frame_index=row['frame_id'], filename=row['frame_name']) for row in rows]


async def fetch_cluster_label(video_id: str, frame_index: int) -> Optional[int]:
    """Truly async function to fetch cluster label"""
    async with get_async_connection() as conn:
        row = await conn.fetchrow("""
            SELECT label
            FROM cluster
            WHERE video_id = $1 AND frame_id = $2
        """, video_id, frame_index)
        
        return row['label'] if row else None


async def fetch_nearest_keyframe(video_id: str, frame_index: int) -> Optional[dict]:
    """Truly async function to fetch nearest keyframe"""
    async with get_async_connection() as conn:
        result = await conn.fetchrow("""
            SELECT video_id, frame_id, frame_name,
                   ABS(frame_id - $1) as distance
            FROM keyframes
            WHERE video_id = $2
            ORDER BY distance ASC, frame_id ASC
            LIMIT 1;
        """, frame_index, video_id)
        
        return result


# ========== ASYNC ENDPOINTS (NO MORE THREADPOOL!) ==========

@router.get("/batch-next", response_model=List[Keyframe])
async def get_batch_next_keyframes(
    video_id: str = Query(...),
    frame_index: int = Query(...),
    batch_size: int = Query(default=10, ge=1, le=50)
):
    """Get next keyframes - truly non-blocking"""
    result = await fetch_keyframes_by_direction(
        video_id=video_id,
        frame_index=frame_index,
        batch_size=batch_size,
        direction="next"
    )
    
    if result is None:
        raise HTTPException(status_code=404, detail="No more keyframes found")
    
    return result


@router.get("/batch-prev", response_model=List[Keyframe])
async def get_batch_prev_keyframes(
    video_id: str = Query(...),
    frame_index: int = Query(...),
    batch_size: int = Query(default=10, ge=1, le=50)
):
    """Get previous keyframes - truly non-blocking"""
    result = await fetch_keyframes_by_direction(
        video_id=video_id,
        frame_index=frame_index,
        batch_size=batch_size,
        direction="prev"
    )
    
    if result is None:
        raise HTTPException(status_code=404, detail="No more keyframes found")
    
    return result


@router.get("/batch-around", response_model=List[Keyframe])
async def get_batch_keyframes_around(
    video_id: str = Query(...),
    frame_index: int = Query(...),
    batch_size: int = Query(default=20, ge=2, le=100)
):
    """Get keyframes around frame - single optimized query"""
    result = await fetch_keyframes_by_direction(
        video_id=video_id,
        frame_index=frame_index,
        batch_size=batch_size,
        direction="around"
    )
    
    if result is None:
        raise HTTPException(status_code=404, detail="No keyframes found")
    
    return result


@router.get("/nearest", response_model=Keyframe)
async def get_nearest_keyframe(
    video_id: str = Query(...),
    frame_index: int = Query(...),
):
    """Get nearest keyframe - truly non-blocking"""
    result = await fetch_nearest_keyframe(video_id, frame_index)
    
    if not result:
        raise HTTPException(status_code=404, detail="No keyframes found")
    
    return Keyframe(
        video_id=result['video_id'],
        frame_index=result['frame_id'],
        filename=result['frame_name']
    )


@router.get("/dislike_cluster")
async def dislike_cluster(
    video_id: str = Query(...),
    frame_index: int = Query(...),
    redis_service: RedisService = Depends(get_redis_service),
    user_id: str = "anonymous"
):
    """Dislike cluster - all operations in parallel"""
    label = await fetch_cluster_label(video_id, frame_index)
    
    if label is None:
        raise HTTPException(status_code=404, detail="Label not found")
    
    # Run Redis operations in parallel
    await asyncio.gather(
        redis_service.add_dislike_label(user_id=user_id, label=label),
        redis_service.flush_user_cache(user_id=user_id)
    )
    
    return {"message": f"User {user_id} disliked cluster {label}"}


@router.get("/un_dislike_cluster")
async def un_dislike_cluster(
    video_id: str = Query(...),
    frame_index: int = Query(...),
    redis_service: RedisService = Depends(get_redis_service),
    user_id: str = "anonymous"
):
    """Remove dislike - all operations in parallel"""
    label = await fetch_cluster_label(video_id, frame_index)
    
    if label is None:
        raise HTTPException(status_code=404, detail="Label not found")
    
    # Run Redis operations in parallel
    await asyncio.gather(
        redis_service.remove_dislike_label(user_id=user_id, label=label),
        redis_service.flush_user_cache(user_id=user_id)
    )
    
    return {"message": f"User {user_id} removed dislike from cluster {label}"}