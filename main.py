from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from db import init_async_pool, close_async_pool
from utils import manager, get_redis_service
import asyncio
from api.endpoints.user_manage import router as user_manage_router
from api.endpoints.websocket import router as websocket_router
from api.endpoints.related_keyframes import router as related_keyframes_router
from api.endpoints.client import router as client_router

from fastapi import FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    print("🚀 Initializing async database pool...")
    await init_async_pool()
    
    print("🚀 Starting Redis broadcast subscription...")
    redis_service = get_redis_service()
    asyncio.create_task(manager.subscribe_broadcasts(redis_service.redis_client))
    
    print("✅ Application startup complete!")
    
    yield  # Application runs here
    
    # Shutdown
    print("🛑 Closing async database pool...")
    await close_async_pool()
    print("✅ Application shutdown complete!")

app = FastAPI(lifespan=lifespan)
app.include_router(user_manage_router, prefix="/user", tags=["User Management"])
app.include_router(websocket_router, prefix="/ws", tags=["WebSocket"])
app.include_router(related_keyframes_router, prefix="/keyframes", tags=["Keyframes"])
app.include_router(client_router, prefix="/client", tags=["OpenAI Service"])

# Create app with lifespan

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API is running"}