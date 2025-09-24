from api.endpoints.user_manage import router as user_manage_router
from api.endpoints.websocket import router as websocket_router
from api.endpoints.related_keyframes import router as related_keyframes_router
from api.endpoints.client import router as client_router

from fastapi import FastAPI

app = FastAPI()
app.include_router(user_manage_router, prefix="/user", tags=["User Management"])
app.include_router(websocket_router, prefix="/ws", tags=["WebSocket"])
app.include_router(related_keyframes_router, prefix="/keyframes", tags=["Keyframes"])
app.include_router(client_router, prefix="/client", tags=["OpenAI Service"])