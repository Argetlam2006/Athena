import google.generativeai as genai

from shared.config.settings import settings

genai.configure(api_key=settings.GEMINI_API_KEY)
supported_models = [
    m.name
    for m in genai.list_models()
    if "generateContent" in m.supported_generation_methods
]


def select_model(models):
    # 1. Configured model
    configured = settings.GEMINI_MODEL
    if configured:
        for m in models:
            if m == configured or m == f"models/{configured}":
                return m

    # Filter for standard flash
    flash_models = [
        m
        for m in models
        if "flash" in m.lower()
        and "lite" not in m.lower()
        and "preview" not in m.lower()
        and "image" not in m.lower()
        and "tts" not in m.lower()
        and "omni" not in m.lower()
    ]
    if flash_models:
        # Reverse sort to get highest version number, e.g. gemini-3.5-flash > gemini-2.5-flash
        return sorted(flash_models, reverse=True)[0]

    pro_models = [
        m
        for m in models
        if "pro" in m.lower()
        and "preview" not in m.lower()
        and "image" not in m.lower()
        and "tts" not in m.lower()
        and "banana" not in m.lower()
        and "deep-research" not in m.lower()
    ]
    if pro_models:
        return sorted(pro_models, reverse=True)[0]

    # If standard didn't match, just take ANY flash
    any_flash = [m for m in models if "flash" in m.lower()]
    if any_flash:
        return sorted(any_flash, reverse=True)[0]

    any_pro = [m for m in models if "pro" in m.lower()]
    if any_pro:
        return sorted(any_pro, reverse=True)[0]

    return None


print(f"Selected: {select_model(supported_models)}")
