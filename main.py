from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from db import get_connection
from model import Keyframe
from api.api import app

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from utils import manager, get_redis_service
import asyncio

@app.on_event("startup")
async def startup_event():
    redis_service = get_redis_service()
    asyncio.create_task(manager.subscribe_broadcasts(redis_service.redis_client))
