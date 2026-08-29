import asyncio
import json
import logging
from typing import Dict, List
from fastapi import WebSocket

logger = logging.getLogger("ws_manager")


class ConnectionManager:
    """Manages active WebSocket connections keyed by user_id."""

    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"WebSocket connected: user_id={user_id} (total: {len(self.active_connections[user_id])})")

    def disconnect(self, user_id: int, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id] = [
                ws for ws in self.active_connections[user_id] if ws is not websocket
            ]
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"WebSocket disconnected: user_id={user_id}")

    async def send_to_user(self, user_id: int, data: dict):
        """Send a JSON payload to all active connections for a user."""
        if user_id not in self.active_connections:
            return
        dead = []
        for ws in self.active_connections[user_id]:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    def send_to_user_sync(self, user_id: int, data: dict):
        """Synchronous wrapper to push a notification (called from APScheduler thread)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.send_to_user(user_id, data))
            else:
                loop.run_until_complete(self.send_to_user(user_id, data))
        except RuntimeError:
            # No running event loop; create one
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.send_to_user(user_id, data))
            except Exception:
                pass


# Singleton instance
manager = ConnectionManager()
