import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
DART_API_KEY = os.getenv("DART_API_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
BOK_API_KEY = os.getenv("BOK_API_KEY", "")

# Database
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "stock_agent.db")

# LLM Settings (Ollama - 100% 로컬, 과금 없음)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
LLM_MODEL_LIGHT = os.getenv("LLM_MODEL_LIGHT", "llama3.1:8b")
LLM_MODEL_HEAVY = os.getenv("LLM_MODEL_HEAVY", "qwen3.5:27b")
LLM_MAX_TOKENS = 4096

# Cache Settings
CACHE_DIR = os.path.join(os.path.dirname(__file__), "data", "cache")
CACHE_EXPIRY_HOURS = 6

# Default currency
BASE_CURRENCY = "KRW"
