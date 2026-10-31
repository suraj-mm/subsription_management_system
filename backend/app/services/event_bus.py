import asyncio
import json
import logging
from typing import Set, Dict, Any, Optional

logger = logging.getLogger("brightloop.event_bus")


class EventBus:
    def __init__(self):
        self._subscribers: Set[asyncio.Queue] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Records the running asyncio event loop for threadsafe cross-thread dispatch."""
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        """Registers a new SSE listener queue."""
        q = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """Removes a disconnected client queue."""
        self._subscribers.discard(q)

    def publish(self, event_type: str, payload: Dict[str, Any]):
        """
        Broadcasts an event message to all connected SSE clients.
        Handles both async context and threadpool worker contexts thread-safely.
        """
        message = {
            "event": event_type,
            "data": payload
        }

        # Format as SSE message string
        raw_msg = f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"

        if not self._subscribers:
            return

        def _dispatch():
            for q in list(self._subscribers):
                try:
                    q.put_nowait(raw_msg)
                except Exception as e:
                    logger.warning("Error pushing to subscriber queue: %s", e)

        # If we have an established event loop and we're in another thread
        if self._loop and self._loop.is_running():
            try:
                running = asyncio.get_running_loop()
                if running == self._loop:
                    _dispatch()
                else:
                    self._loop.call_soon_threadsafe(_dispatch)
            except RuntimeError:
                # No running loop in current thread -> use stored loop
                self._loop.call_soon_threadsafe(_dispatch)
        else:
            try:
                loop = asyncio.get_running_loop()
                _dispatch()
            except RuntimeError:
                pass


event_bus = EventBus()
