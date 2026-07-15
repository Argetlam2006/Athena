"""
backend/explanation/conversation.py — Conversation Manager.

Maintains session history and detects context changes to inject system memory
while preserving continuity.
"""

from dataclasses import dataclass, field


@dataclass
class ConversationMessage:
    role: str  # "user" or "assistant"
    content: str
    context_type: str | None = None


@dataclass
class ConversationState:
    messages: list[ConversationMessage] = field(default_factory=list)
    last_player_id: int | None = None
    last_team_id: int | None = None
    last_workspace: str | None = None


class ConversationManager:
    """
    Manages the conversational history and context transitions.
    """

    def __init__(self):
        self.state = ConversationState()

    def add_user_message(self, content: str, context_type: str | None = None) -> None:
        self.state.messages.append(
            ConversationMessage(role="user", content=content, context_type=context_type)
        )

    def add_assistant_message(self, content: str) -> None:
        self.state.messages.append(
            ConversationMessage(role="assistant", content=content)
        )

    def detect_and_handle_context_change(
        self,
        current_player_id: int | None,
        current_team_id: int | None,
        current_workspace: str | None,
    ) -> bool:
        """
        Detects if the context has fundamentally changed since the last interaction.
        Injects a lightweight system note if it has. Returns True if a change occurred.
        """
        changed = False
        updates = []

        if self.state.last_workspace != current_workspace:
            updates.append(f"Workspace changed to {current_workspace}")
            self.state.last_workspace = current_workspace
            changed = True

        if self.state.last_player_id != current_player_id:
            updates.append("Focus player changed")
            self.state.last_player_id = current_player_id
            changed = True

        if self.state.last_team_id != current_team_id:
            updates.append("Focus team changed")
            self.state.last_team_id = current_team_id
            changed = True

        if changed and self.state.messages:
            # Inject a silent system transition message to keep LLM aware of the shift
            # without wiping the entire history.
            transition = f"[System Note: Context changed. {' | '.join(updates)}. Please align future answers to the new context.]"
            # We don't want to expose this to the user, so we mark it specifically
            self.state.messages.append(
                ConversationMessage(role="system", content=transition)
            )

        return changed

    def get_history(self) -> list[dict[str, str]]:
        """Returns the history formatted for provider consumption."""
        return [
            {"role": msg.role, "content": msg.content} for msg in self.state.messages
        ]

    def clear(self) -> None:
        """Wipes the conversation history."""
        self.state.messages = []
