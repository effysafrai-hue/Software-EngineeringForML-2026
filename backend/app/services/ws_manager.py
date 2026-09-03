import asyncio
import logging
from typing import Dict, List, Optional
from fastapi import WebSocket

logger = logging.getLogger("ws_manager")


class ConnectionManager:
    """Manages active WebSocket connections keyed by user_id."""

    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Record the loop the sockets live on.

        A WebSocket may only be written from the loop that accepted it. Both the
        APScheduler thread and the sync route handlers (FastAPI runs `def`
        endpoints in a worker thread) are off that loop, so they need a handle
        to hand work back to it. Called once from the app lifespan.
        """
        self._loop = loop

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

    async def broadcast(self, data: dict, exclude_user_id: Optional[int] = None):
        """Fan a payload out to every connected user.

        Used for public forum activity (new post, new comment, changed reaction
        counts) so open feeds update without polling. Never use it for anything
        addressed to specific people — direct messages go through send_to_user.
        """
        for user_id in list(self.active_connections.keys()):
            if exclude_user_id is not None and user_id == exclude_user_id:
                continue
            await self.send_to_user(user_id, data)

    def send_to_user_sync(self, user_id: int, data: dict):
        """Push to one user from outside the event loop (scheduler or sync route)."""
        self._dispatch(self.send_to_user(user_id, data))

    def broadcast_sync(self, data: dict, exclude_user_id: Optional[int] = None):
        """Fan out from outside the event loop."""
        self._dispatch(self.broadcast(data, exclude_user_id=exclude_user_id))

    def _dispatch(self, coro) -> None:
        """Run a send coroutine on the socket-owning loop, from any thread.

        Best-effort by design: a websocket push that fails must never turn a
        successful post or message into an error response. The durable record is
        the Notification row, which the client can still fetch over HTTP.
        """
        loop = self._loop
        if loop is not None and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(coro, loop)
                return
            except Exception as e:
                logger.warning(f"WebSocket dispatch to bound loop failed: {e}")

        # No bound loop (unit tests, scripts). If we happen to already be on a
        # running loop, schedule there; otherwise drop the push and close the
        # coroutine so it does not raise "never awaited".
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        if running is not None:
            asyncio.ensure_future(coro)
            return

        coro.close()


# Singleton instance
manager = ConnectionManager()
