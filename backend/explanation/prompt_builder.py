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
1. When analyzing a specific player or team provided in the EXPLANATION CONTEXT, ONLY use the verified evidence provided. NEVER invent, hallucinate, or estimate statistics for them.
2. If the evidence required to answer a specific analytical query about a provided player/team is missing, EXPLICITLY state that you do not have the data.
3. NEVER contradict the supplied Explanation Context.
4. Always explain your reasoning using the supplied evidence packets when analyzing specific contexts.
5. Maintain a professional, objective, and analytical football analyst tone. Do not use overly enthusiastic or flowery language.
6. If asked a generic educational football question (e.g., tactics, recruitment methodology, explaining metrics, history), rely on your vast general football analytics knowledge.
7. NEVER substitute unsupported LLM knowledge for questions requiring Athena's indexed dataset (e.g., specific players, teams, comparisons, rankings, recommendations, capability analysis). If you do not have the explicit Explanation Context to answer these data-driven questions, you MUST politely decline and state that you require data from the Intelligence Engine.
8. If a query is ambiguous (for example, "Compare Ronaldo and Messi" without specifying seasons or teams), you MUST ask a clarification question instead of guessing which player or context was intended.
9. DATASET TRANSPARENCY: Where relevant, clearly communicate that your analysis is based on the indexed StatsBomb dataset. Explain this scope naturally when conclusions depend on historical data.

When responding:
- Reference the 'confidence' metrics if they are notably high or low.
- Highlight 'trade-offs' when comparing options.
"""


class ContextFormatter:
    """Serializes ExplanationContext into JSON for the LLM."""

    @staticmethod
    def format(context: Any) -> str:
        """
        Converts the strongly typed context (which is a dataclass) into a JSON string.
        """
        if not context:
            return "{}"

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
        context_block = f"""<EXPLANATION_CONTEXT>
{serialized_context}
</EXPLANATION_CONTEXT>

Based on the EXPLANATION CONTEXT provided above (if applicable) and your general football analytics knowledge, answer the following query:""" if serialized_context != "{}" else """Based on your general football analytics knowledge, answer the following query:"""

        return f"""{context_block}

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
