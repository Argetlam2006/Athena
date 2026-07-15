"""
backend/explanation/prompt_builder.py — Prompt Pipeline for the Explanation Layer.

Transforms ExplanationContexts and User Queries into standard PromptPackages
for consumption by Provider models.
"""

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PromptPackage:
    """
    Standardized prompt package.
    Providers must only consume this object to generate their API requests.
    """

    system_prompt: str
    user_prompt: str
    serialized_context: str
    prompt_version: str
    metadata: dict[str, Any]


class SystemPromptBuilder:
    """Builds the canonical Athena system prompt."""

    VERSION = "v1.0.0"

    @staticmethod
    def build() -> str:
        return """You are Athena, an elite, AI-powered Football Decision Intelligence Analyst.
Your core philosophy is "Evidence before AI."

CRITICAL INSTRUCTIONS:
1. NEVER invent, hallucinate, or estimate statistics.
2. ONLY use the verified evidence provided in the EXPLANATION CONTEXT block.
3. If the evidence required to answer the user's prompt is missing, EXPLICITLY state that you do not have the data.
4. NEVER contradict the supplied Explanation Context.
5. Always explain your reasoning using the supplied evidence packets.
6. Maintain a professional, objective, and analytical football analyst tone. Do not use overly enthusiastic or flowery language.

When responding:
- Reference the 'confidence' metrics if they are notably high or low.
- Highlight 'trade-offs' when comparing options.
- If asked a general football question not covered by the context, decline respectfully, reminding the user that you only analyze the supplied proprietary data.
"""


class ContextFormatter:
    """Serializes ExplanationContext into JSON for the LLM."""

    @staticmethod
    def format(context: Any) -> str:
        """
        Converts the strongly typed context (which is a dataclass) into a JSON string.
        """
        # If it's already a dict, just dump it. Otherwise, assume it's a dataclass.
        if isinstance(context, dict):
            ctx_dict = context
        else:
            ctx_dict = asdict(context)

        return json.dumps(ctx_dict, indent=2)


class UserPromptBuilder:
    """Builds the structured user prompt."""

    @staticmethod
    def build(user_query: str, serialized_context: str) -> str:
        return f"""<EXPLANATION_CONTEXT>
{serialized_context}
</EXPLANATION_CONTEXT>

Based strictly on the EXPLANATION CONTEXT provided above, answer the following query:

<USER_QUERY>
{user_query}
</USER_QUERY>
"""


class PromptBuilder:
    """
    Assembles the final PromptPackage.
    """

    def build(self, user_query: str, context: Any, context_type: str) -> PromptPackage:
        serialized_ctx = ContextFormatter.format(context)
        sys_prompt = SystemPromptBuilder.build()
        user_prompt = UserPromptBuilder.build(user_query, serialized_ctx)

        return PromptPackage(
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            serialized_context=serialized_ctx,
            prompt_version=SystemPromptBuilder.VERSION,
            metadata={
                "context_type": context_type,
                "context_size_bytes": len(serialized_ctx),
            },
        )
