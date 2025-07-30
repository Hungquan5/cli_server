from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from db import get_connection
from model import Keyframe

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NEW BATCH ENDPOINTS FOR INFINITE SCROLLING

@app.get("/keyframes/batch-next", response_model=list[Keyframe])
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
    conn.close()
    
    if not rows:
        raise HTTPException(status_code=404, detail="No more keyframes found in this direction")
    
    return [Keyframe(video_id=row[0], frame_index=row[1], filename=row[2]) for row in rows]

@app.get("/keyframes/batch-prev", response_model=list[Keyframe])
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
    conn.close()
    
    if not rows:
        raise HTTPException(status_code=404, detail="No more keyframes found in this direction")
    
    # Reverse the order to return frames in ascending order by frame_id
    # (since we fetched them in DESC order to get the closest ones first)
    rows.reverse()
    
    return [Keyframe(video_id=row[0], frame_index=row[1], filename=row[2]) for row in rows]

@app.get("/keyframes/batch-around", response_model=list[Keyframe])
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
    conn.close()
    
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

# OPTIONAL: Get keyframes with pagination support
@app.get("/keyframes/paginated", response_model=dict)
def get_keyframes_paginated(
    video_id: str = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100)
):
    """Get keyframes with pagination support"""
    conn = get_connection()
    cur = conn.cursor()
    
    # Get total count
    cur.execute("""
        SELECT COUNT(*) FROM keyframes WHERE video_id = %s;
    """, (video_id,))
    total_count = cur.fetchone()[0]
    
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Get paginated results
    cur.execute("""
        SELECT video_id, frame_id, frame_name
        FROM keyframes
        WHERE video_id = %s
        ORDER BY frame_id ASC
        LIMIT %s OFFSET %s;
    """, (video_id, page_size, offset))
    
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    keyframes = [Keyframe(video_id=row[0], frame_index=row[1], filename=row[2]) for row in rows]
    
    total_pages = (total_count + page_size - 1) // page_size  # Ceiling division
    
    return {
        "keyframes": keyframes,
        "pagination": {
            "current_page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "total_count": total_count,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }