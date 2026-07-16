from backend.explanation.prompt_builder import SystemPromptBuilder
from backend.explanation.engine import ExplanationContextEngine

def validate_hallucination_safety():
    print("\n--- Validating Hallucination Safety ---")
    
    # 1. Check System Prompt for Dataset Transparency
    prompt = SystemPromptBuilder.build()
    
    if "StatsBomb dataset" in prompt or "StatsBomb" in prompt:
        print("[PASS] System prompt enforces Dataset Transparency.")
    else:
        print("[FAIL] System prompt missing Dataset Transparency clause.")
        
    if "NEVER invent" in prompt or "NEVER substitute unsupported LLM knowledge" in prompt:
        print("[PASS] System prompt enforces Hallucination Safety.")
    else:
        print("[FAIL] System prompt missing Hallucination Safety clauses.")

if __name__ == "__main__":
    validate_hallucination_safety()
