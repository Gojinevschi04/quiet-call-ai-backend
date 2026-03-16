from datetime import datetime

from app.modules.calls.models import LogLine
from app.modules.calls.schema import Speaker


class ConversationManager:
    """Manages dialog turns, noise retries, and conversation history."""

    def __init__(self, max_turns: int, max_noise_retries: int) -> None:
        self.history: list[dict[str, str]] = []
        self.log_lines: list[LogLine] = []
        self.max_turns = max_turns
        self.max_noise_retries = max_noise_retries
        self.noise_retries = 0

    def add_agent_message(self, text: str, session_id: int) -> None:
        self.history.append({"role": "assistant", "content": text})
        self.log_lines.append(self._create_log_line(session_id, Speaker.AGENT, text))

    def add_interlocutor_message(self, text: str, intent: str | None, session_id: int) -> None:
        self.history.append({"role": "user", "content": text})
        self.log_lines.append(
            self._create_log_line(session_id, Speaker.INTERLOCUTOR, text, intent)
        )

    def is_complete(self, agent_reply: str) -> bool:
        return "[OBJECTIVE_ACHIEVED]" in agent_reply or "[OBJECTIVE_FAILED]" in agent_reply

    def format_history(self) -> str:
        lines = []
        for msg in self.history:
            role = "Agent" if msg["role"] == "assistant" else "Interlocutor"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)

    def has_objective_achieved(self) -> bool:
        return any(
            "[OBJECTIVE_ACHIEVED]" in msg.get("content", "")
            for msg in self.history
            if msg["role"] == "assistant"
        )

    def _create_log_line(
        self,
        session_id: int,
        speaker: Speaker,
        text: str,
        detected_intent: str | None = None,
    ) -> LogLine:
        return LogLine(
            session_id=session_id,
            timestamp=datetime.now(),
            speaker=speaker,
            text=text,
            detected_intent=detected_intent,
        )
