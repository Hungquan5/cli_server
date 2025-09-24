from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from db import get_connection, release_connection
from services.redis_service import RedisService
from services.client_service import OpenAIService
from utils import get_redis_service, get_openai_service
from model import Keyframe
from fastapi import APIRouter, Depends
from typing import List

router = APIRouter()


@router.post("/paraphrase", response_model=List[str])
async def paraphrase(
    text: str,
    openai_service: OpenAIService = Depends(get_openai_service),
    user_id: str = "anonymous"
):
    """User dislike cluster label của một keyframe"""
    list_paraphrase = openai_service.paraphrase(text=text)
    return list_paraphrase

@router.post("/question", response_model=str)
async def question(
    text: str,
    openai_service: OpenAIService = Depends(get_openai_service),
    user_id: str = "anonymous"
):
    """User dislike cluster label của một keyframe"""
    answer = openai_service.question(text=text)
    return answer