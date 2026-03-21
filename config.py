import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
DART_API_KEY = os.getenv("DART_API_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
BOK_API_KEY = os.getenv("BOK_API_KEY", "")

# Database
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "stock_agent.db")

# LLM Settings
LLM_MODEL = "claude-sonnet-4-6"
LLM_MAX_TOKENS = 4096

# Cache Settings
CACHE_DIR = os.path.join(os.path.dirname(__file__), "data", "cache")
CACHE_EXPIRY_HOURS = 6

# Default currency
BASE_CURRENCY = "KRW"
