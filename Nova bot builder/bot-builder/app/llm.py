import os

from langchain_openai import ChatOpenAI

try:
    from .config import OPENROUTER_API_KEY, OPENROUTER_MODEL
except ImportError:
    from config import OPENROUTER_API_KEY, OPENROUTER_MODEL


# Read configuration
API_KEY = (
    OPENROUTER_API_KEY
    or os.getenv("OPENAI_API_KEY")
    or ""
).strip()

MODEL = (
    OPENROUTER_MODEL
    or ""
).strip()

BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL",
    "https://openrouter.ai/api/v1",
).strip()


# Validate configuration before making requests
if not API_KEY:
    raise RuntimeError(
        "کلید دسترسی OpenRouter تنظیم نشده است."
    )

if not MODEL:
    raise RuntimeError(
        "مدل زبانی در تنظیمات پروژه مشخص نشده است."
    )


llm = ChatOpenAI(
    model=MODEL,
    api_key=API_KEY,
    base_url=BASE_URL,
    temperature=0,
    timeout=45,
    max_retries=0,
    max_tokens=2000,
)