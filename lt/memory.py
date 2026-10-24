"""Conversation Memory Manager for the AI Office Assistant.

Handles three layers of memory:
1. Recent conversation history (short-term, in-memory)
2. Persistent context saved to JSON file (cross-session)
3. Project state (ingested sources, generated materials, output locations)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Path for persistent memory
MEMORY_DIR = Path.home() / ".learning-tools"
MEMORY_FILE = MEMORY_DIR / "memory.json"


class ConversationMemory:
    """Manages conversation history and persistent context.

    Attributes:
        max_recent: Maximum number of exchange pairs to keep in recent history
        recent: List of (role, content) tuples representing the conversation history
        persistent: Dictionary of persistent key-value preferences
    """

    def __init__(self, max_recent: int = 20):
        """Initialize the memory manager.

        Args:
            max_recent: Maximum number of user/assistant exchange pairs to retain
        """
        self.max_recent = max_recent
        self.recent: List[Tuple[str, str]] = []  # List of (role, content) tuples
        self.persistent: Dict[str, Any] = {}

        # Load persistent memory from file if it exists
        self._load_persistent()

    def _load_persistent(self) -> None:
        """Load persistent memory from JSON file if it exists."""
        if MEMORY_FILE.exists():
            try:
                with open(MEMORY_FILE, "r", encoding="utf8") as f:
                    data = json.load(f)
                self.persistent = data.get("persistent", {})
                # Merge with recent history if present
                recent = data.get("recent", [])
                # Convert old format if needed
                self.recent = [
                    (entry.get("role", "user"), entry.get("content", ""))
                    for entry in recent
                ]
            except (json.JSONDecodeError, KeyError, IOError):
                # Start fresh if file is corrupted
                self.persistent = {}
                self.recent = []

    def _save_persistent(self) -> None:
        """Save persistent memory to JSON file."""
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "persistent": self.persistent,
            "recent": [
                {"role": role, "content": content}
                for role, content in self.recent
            ],
        }
        try:
            with open(MEMORY_FILE, "w", encoding="utf8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError:
            logger.warning(f"Could not save memory to {MEMORY_FILE}")

    def add(self, role: str, content: str) -> None:
        """Add an exchange to the conversation history.

        Args:
            role: Either "user" or "assistant"
            content: The text content of the exchange
        """
        self.recent.append((role, content))

        # Trim to max_recent (keep pairs, so remove 2 at a time)
        while len(self.recent) > self.max_recent * 2:
            self.recent.pop(0)
            # Also remove old persistent data if needed (not implemented here)

        # Save after adding
        self._save_persistent()

    def get_recent(self, n: Optional[int] = None) -> List[Tuple[str, str]]:
        """Get the recent conversation history.

        Args:
            n: Number of recent exchanges to return. If None, returns all.

        Returns:
            List of (role, content) tuples, most recent first
        """
        if n is None:
            return self.recent[:]
        # Return the last n entries (most recent), accounting for (role, content) pairs
        pair_count = n * 2
        return self.recent[-pair_count:]

    def set_context(self, key: str, value: Any) -> None:
        """Set a persistent context value.

        Args:
            key: The context key (e.g., "preferred_style", "favorite_format")
            value: The value to persist
        """
        self.persistent[key] = value
        self._save_persistent()

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a persistent context value.

        Args:
            key: The context key to look up
            default: Value to return if key not found

        Returns:
            The stored value or default
        """
        return self.persistent.get(key, default)

    def clear_context(self) -> None:
        """Clear all persistent context (except recently used preferences)."""
        self.persistent = {}
        self._save_persistent()

    def get_context_summary(self) -> str:
        """Get a string summary of all persistent context.

        Returns:
            Formatted string of key-value pairs
        """
        if not self.persistent:
            return "No persistent context set."
        parts = ["**Persistent Context:**"]
        for key, value in self.persistent.items():
            parts.append(f"- {key}: {value}")
        return "\n".join(parts)


# Global memory instance (can be imported and used directly)
# This allows other modules to access memory without creating new instances
_memory_instance: Optional[ConversationMemory] = None


def get_memory() -> ConversationMemory:
    """Get the global memory instance.

    Returns:
        The single ConversationMemory instance
    """
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = ConversationMemory()
    return _memory_instance


def reset_memory() -> None:
    """Reset the global memory instance (useful for testing)."""
    global _memory_instance
    _memory_instance = None