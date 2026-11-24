import os
import warnings

# Suppress LangChain deprecation notices for clean terminal logs
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*LangChainDeprecationWarning.*")

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOpenAI

load_dotenv()

AVAILABLE_PROVIDERS = {
    "gemini": {
        "name": "Google Gemini (Free Tier)",
        "models": {
            "gemini-3.5-flash-lite": "Gemini 3.5 Flash Lite (Fastest & Most Efficient)",
            "gemini-3.1-flash-lite": "Gemini 3.1 Flash Lite (Ultra-Fast & Detailed)",
            "gemini-3.8-flash": "Gemini 3.8 Flash (Multimodal / Standard)",
        },
        "default_model": "gemini-3.5-flash-lite",
        "key_env": "GOOGLE_API_KEY",
        "key_hint": "Free key from https://aistudio.google.com",
    },
    "groq": {
        "name": "Groq Cloud (100% Free - High Speed)",
        "models": {
            "openai/gpt-oss-120b": "OpenAI GPT-OSS 120B (Best for Legal Contracts)",
            "openai/gpt-oss-20b": "OpenAI GPT-OSS 20B (Fast Reasoning)",
            "qwen/qwen3.8-27b": "Qwen 3.8 27B (Multimodal Reasoning)",
            "llama-3.1-8b-instant": "Llama 3.1 8B (Instant)",
            "allam-2-7b": "Allam 2 7B",
        },
        "default_model": "openai/gpt-oss-120b",
        "key_env": "GROQ_API_KEY",
        "key_hint": "100% free key (no credit card) from https://console.groq.com",
    },
}

_active_provider = os.getenv("LLM_PROVIDER", "gemini")
if _active_provider not in AVAILABLE_PROVIDERS:
    _active_provider = "gemini"

_active_model_name = os.getenv(
    "GEMINI_MODEL" if _active_provider == "gemini" else "GROQ_MODEL",
    AVAILABLE_PROVIDERS[_active_provider]["default_model"]
)


def _create_llm(provider, model_name, custom_key=None):
    if provider == "gemini":
        key = custom_key or os.getenv("GOOGLE_API_KEY")
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=key,
            transport="rest",
            temperature=0,
        )
    elif provider == "groq":
        key = custom_key or os.getenv("GROQ_API_KEY")
        if not key:
            raise ValueError("GROQ_API_KEY is not set. Please add it to your .env file or enter it in the sidebar.")
        return ChatOpenAI(
            openai_api_key=key,
            openai_api_base="https://api.groq.com/openai/v1",
            model_name=model_name,
            temperature=0,
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")


# Initialize default LLM
llm = _create_llm(_active_provider, _active_model_name)


def set_active_model(model_name, provider=None, custom_key=None):
    global llm, _active_provider, _active_model_name
    target_provider = provider or _active_provider
    if target_provider in AVAILABLE_PROVIDERS:
        models = get_available_models(target_provider, api_key=custom_key)
        if model_name in models or target_provider == "groq":
            _active_provider = target_provider
            _active_model_name = model_name
            llm = _create_llm(target_provider, model_name, custom_key)
            label = models.get(model_name, model_name)
            return True, f"Successfully activated {label}"
        else:
            return False, f"Model {model_name} not found in provider {target_provider}."
    return False, f"Provider {target_provider} is invalid."


def get_active_model():
    return _active_model_name


def get_active_provider():
    return _active_provider


def get_available_providers():
    return AVAILABLE_PROVIDERS


def fetch_live_groq_models(api_key):
    if not api_key:
        return None
    try:
        import requests
        resp = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key.strip()}"},
            timeout=3,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            priority = [
                "openai/gpt-oss-120b",
                "openai/gpt-oss-20b",
                "qwen/qwen3.8-27b",
                "llama-3.1-8b-instant",
                "allam-2-7b",
            ]
            collected = []
            for item in data:
                mid = item.get("id", "")
                if not mid:
                    continue
                lower = mid.lower()
                if any(x in lower for x in ["whisper", "guard", "canopy", "orpheus", "tts", "audio", "embed", "vision", "rerank", "bge"]):
                    continue
                collected.append(mid)

            def sort_key(m):
                m_low = m.lower()
                for i, p in enumerate(priority):
                    if p in m_low:
                        return (i, m_low)
                return (100, m_low)

            collected.sort(key=sort_key)
            valid_models = {m: m for m in collected}
            if valid_models:
                return valid_models
    except Exception:
        pass
    return None


def get_available_models(provider=None, api_key=None):
    p = provider or _active_provider
    if p == "groq":
        k = api_key or os.getenv("GROQ_API_KEY")
        if k:
            live = fetch_live_groq_models(k)
            if live:
                return live
    if p in AVAILABLE_PROVIDERS:
        return AVAILABLE_PROVIDERS[p]["models"]
    return AVAILABLE_PROVIDERS["gemini"]["models"]


def invoke_llm(prompt):
    """
    Safely invoke the active LLM and normalize the response into a clean string,
    regardless of whether the model returns a string, an AIMessage, or a list of blocks.
    """
    response = llm.invoke(prompt)
    if hasattr(response, "content"):
        raw = response.content
    else:
        raw = response

    if isinstance(raw, list):
        return "".join([part if isinstance(part, str) else part.get("text", "") for part in raw]).strip()
    return str(raw).strip()


def explain_contract(text):
    prompt = f"""
You are a legal assistant.

Explain the following contract in simple English so that a non-lawyer can understand it.

Document:

{text}

Provide:
1. Summary
2. Key obligations
3. Important clauses
4. Potential concerns
"""

    try:
        return invoke_llm(prompt)
    except Exception as e:
        return f"""
❌ Unable to generate explanation.

Reason:

{str(e)}

Please check your API key / model settings or wait a moment and try again.
"""
