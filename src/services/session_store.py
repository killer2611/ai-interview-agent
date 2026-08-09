"""Session Store — in-memory interview state management."""

from __future__ import annotations

from src.models.interview import InterviewState


class SessionStore:
    """In-memory store for interview sessions keyed by sessionId."""

    def __init__(self) -> None:
        self._sessions: dict[str, InterviewState] = {}

    def create(self, state: InterviewState) -> None:
        """Store a new interview session.

        Raises:
            ValueError: If a session with this ID already exists.
        """
        if state.session_id in self._sessions:
            raise ValueError(f"Session already exists: {state.session_id}")
        self._sessions[state.session_id] = state

    def get(self, session_id: str) -> InterviewState | None:
        """Retrieve an interview session by ID."""
        return self._sessions.get(session_id)

    def update(self, state: InterviewState) -> None:
        """Update an existing interview session.

        Raises:
            ValueError: If the session does not exist.
        """
        if state.session_id not in self._sessions:
            raise ValueError(f"Session not found: {state.session_id}")
        self._sessions[state.session_id] = state

    def exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        return session_id in self._sessions

    def delete(self, session_id: str) -> None:
        """Remove a session."""
        self._sessions.pop(session_id, None)

    @property
    def count(self) -> int:
        """Number of active sessions."""
        return len(self._sessions)
