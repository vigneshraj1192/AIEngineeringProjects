"""Real-time event streaming bus connecting agents, logs, state, and TUI."""

from typing import Callable, Dict, List, Any
import threading
import queue

class EventType:
    ISSUE_LIST_UPDATED = "issue_list_updated"
    TASK_STATE_CHANGED = "task_state_changed"
    AGENT_LOG = "agent_log"
    HITL_PROMPT = "hitl_prompt"
    HITL_RESOLVED = "hitl_resolved"

class EventBus:
    """Thread-safe publish/subscribe event bus."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        self._lock = threading.Lock()
        self._event_queue: queue.Queue = queue.Queue()

    def subscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for an event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Remove a callback for an event type."""
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [cb for cb in self._subscribers[event_type] if cb != callback]

    def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish an event to all subscribers."""
        with self._lock:
            callbacks = list(self._subscribers.get(event_type, []))
        
        for callback in callbacks:
            try:
                callback(data)
            except Exception as e:
                # Do not let callback errors break execution
                pass

    def log(self, agent_name: str, message: str, level: str = "INFO", tool_call: str | None = None) -> None:
        """Helper to stream agent log events."""
        self.emit(EventType.AGENT_LOG, {
            "agent": agent_name,
            "message": message,
            "level": level,
            "tool_call": tool_call,
        })

# Global singleton event bus
event_bus = EventBus()
