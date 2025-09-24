import redis.asyncio as redis
import json
from typing import List
import zlib
import time
import asyncio
import hashlib
import pickle

REDIS_HOST = "redis-server"
REDIS_PORT = 6379

class RedisService:
    def __init__(self):
        print("Init Redis Service...")
        self.redis_client = None
        self._load_client()
        
    def _load_client(self):
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=False
            )  # decode=False for binary (compressed)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Redis: {str(e)}")
    
    ############################################## CLUSTER
    async def add_dislike_label(self, user_id: str, label: int):
        """Thêm 1 label vào danh sách dislike của user."""
        await self.redis_client.sadd(f"cluster:{user_id}", label)

    async def get_dislike_labels(self, user_id: str) -> list[int]:
        """Lấy toàn bộ labels mà user đã dislike."""
        labels = await self.redis_client.smembers(f"cluster:{user_id}")
        return [int(l) for l in labels]

    async def remove_dislike_label(self, user_id: str, label: int):
        """Bỏ dislike 1 label."""
        await self.redis_client.srem(f"cluster:{user_id}", label)

    async def clear_dislike_labels(self, user_id: str):
        """Xoá toàn bộ dislike của user."""
        await self.redis_client.delete(f"cluster:{user_id}")
        
    async def flush_user_dislike_labels(self, user_id: str):
        """
        Xoá toàn bộ cache của user (cluster:{user_id}*)
        """
        for pattern in [f"cluster:{user_id}*"]:
            cursor = b"0"
            while cursor:
                cursor, keys = await self.redis_client.scan(cursor=cursor, match=pattern, count=1000)
                if keys:
                    await self.redis_client.delete(*keys)
        
    async def flush_all_user_dislike_labels(self):
        """
        Xoá toàn bộ cache của tất cả user (cluster:*)
        """
        for pattern in ["cluster:*"]:
            cursor = b"0"
            while cursor:
                cursor, keys = await self.redis_client.scan(cursor=cursor, match=pattern, count=1000)
                if keys:
                    await self.redis_client.delete(*keys)
        
    ###################################################### SUBMISSION
    async def set_submission(self, image_key: str, status: str):
        """Set status for a submission (global shared)."""
        await self.redis_client.hset("image_submissions", image_key, status)

    async def remove_submission(self, image_key: str):
        """Remove one submission from Redis (global shared)."""
        await self.redis_client.hdel("image_submissions", image_key)

    async def get_submissions(self) -> dict:
        """Get all submissions (global shared)."""
        data = await self.redis_client.hgetall("image_submissions")
        return {k.decode(): v.decode() for k, v in data.items()}

    async def clear_submissions(self):
        """Clear all submissions."""
        await self.redis_client.delete("image_submissions")
    
    ###################################################### CACHE USER
    async def flush_user_cache(self, user_id: str):
        """
        Xoá toàn bộ cache có prefix 'search_cache:{user_id}:*' và 'q:{user_id}' 
        """
        pattern = f"search_cache:{user_id}:*"
        cursor = b"0"
        keys_deleted = 0

        while cursor:
            cursor, keys = await self.redis_client.scan(cursor=cursor, match=pattern, count=1000)
            if keys:
                await self.redis_client.delete(*keys)
                keys_deleted += len(keys)
                
        pattern = f"q:{user_id}:*"
        cursor = b"0"
        keys_deleted = 0

        while cursor:
            cursor, keys = await self.redis_client.scan(cursor=cursor, match=pattern, count=1000)
            if keys:
                await self.redis_client.delete(*keys)
                keys_deleted += len(keys)
                
    async def flush_all_user_cache(self):
        """
        Xoá toàn bộ cache của tất cả user (search_cache:* và q:*)
        """
        for pattern in ["search_cache:*", "q:*"]:
            cursor = b"0"
            while cursor:
                cursor, keys = await self.redis_client.scan(cursor=cursor, match=pattern, count=1000)
                if keys:
                    await self.redis_client.delete(*keys)
