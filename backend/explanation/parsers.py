"""
backend/explanation/parsers.py - Natural Language Parsers

Uses the LLM to deterministically extract structured constraints from natural language.
"""

import json

from backend.explanation.prompt_builder import PromptPackage
from backend.explanation.providers.openai_provider import OpenAIProvider


def parse_natural_language_scouting(query: str) -> dict:
    """
    Parses a natural language scouting query into structured criteria.
    Returns a dictionary matching the schema:
    {
        "position": str | None,
        "playing_style": str | None,
        "traits": list[str],
        "confidence": str
    }
    """
    provider = OpenAIProvider(model_name="meta/llama-3.1-8b-instruct", temperature=0.0)

    system_prompt = """You are Athena, a deterministic football analytics engine.
Your task is to extract structural scouting constraints from natural language queries.
Do NOT hallucinate players or attempt to answer the query. Only parse the intent.

Return ONLY a valid JSON object matching this schema exactly:
{
    "position": "Forward" | "Midfielder" | "Defender" | "Goalkeeper" | null,
    "playing_style": string | null,
    "traits": ["Goalscoring", "Chance Creation", "Progressive Passing", "Ball Carrying", "Press Resistance", "Defensive Work", "Ball Retention", "Aerial Ability"],
    "confidence": "High" | "Medium" | "Low"
}

Playing Styles to choose from (pick the closest one, or null):
- Forward: "Elite Goal Scorer", "Target Man", "Complete Forward", "Direct Winger", "Creative Forward", "Creative Playmaker", "Creative Winger"
- Midfielder: "Deep-Lying Playmaker", "Box-to-Box Engine", "Press-Resistant Anchor", "Midfield Destroyer", "Creative Playmaker"
- Defender: "Ball-Playing Defender", "Progressive Fullback", "Traditional Defender", "Defensive Fullback"
- Goalkeeper: "Goalkeeper"

Map natural language words to the traits listed above. E.g. "creative" -> "Chance Creation". "possession-dominant" -> "Ball Retention", "Progressive Passing".
Make sure output is ONLY JSON.
"""

    prompt = PromptPackage(
        system_prompt=system_prompt,
        user_prompt=query,
        serialized_context="",
        prompt_version="v1",
        metadata={},
    )

    try:
        response = provider.generate(prompt)
        response_text = response.generated_text
        # Clean markdown code block if present
        if response_text.startswith("```json"):
            response_text = (
                response_text.replace("```json", "").replace("```", "").strip()
            )
        elif response_text.startswith("```"):
            response_text = response_text.replace("```", "").strip()

        parsed = json.loads(response_text)
        return parsed
    except Exception as e:
        return {
            "position": None,
            "playing_style": None,
            "traits": [],
            "confidence": "Low",
            "error": str(e),
        }
