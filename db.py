import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import asyncpg
from typing import Optional

load_dotenv()

# Global connection pool
_async_pool: Optional[asyncpg.Pool] = None


async def init_async_pool():
    """Initialize the async connection pool (call this at app startup)"""
    global _async_pool
    if _async_pool is None:
        _async_pool = await asyncpg.create_pool(
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            min_size=10,        # Minimum connections
            max_size=100,       # Maximum connections (increased from 50)
            max_queries=50000,  # Max queries per connection before recycling
            max_inactive_connection_lifetime=300,  # 5 minutes
            command_timeout=60  # Query timeout in seconds
        )
    return _async_pool


async def close_async_pool():
    """Close the async connection pool (call this at app shutdown)"""
    global _async_pool
    if _async_pool is not None:
        await _async_pool.close()
        _async_pool = None


@asynccontextmanager
async def get_async_connection():
    """
    Get an async database connection from the pool.
    Usage:
        async with get_async_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT ...")
    """
    if _async_pool is None:
        await init_async_pool()
    
    async with _async_pool.acquire() as connection:
        yield connection


# ============================================
# KEEP YOUR EXISTING SYNC CODE FOR COMPATIBILITY
# ============================================

from psycopg2 import pool
import threading

_connection_pool = None
_pool_lock = threading.Lock()


def get_pool():
    """Sync connection pool (for backward compatibility)"""
    global _connection_pool
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                _connection_pool = pool.SimpleConnectionPool(
                    1, 50,
                    dbname=os.getenv("DB_NAME"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    host=os.getenv("DB_HOST"),
                    port=os.getenv("DB_PORT")
                )
    return _connection_pool


def get_connection():
    """Sync connection (for backward compatibility)"""
    return get_pool().getconn()


def release_connection(conn):
    """Release sync connection (for backward compatibility)"""
    get_pool().putconn(conn)