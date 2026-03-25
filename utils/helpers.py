import os
import json
import hashlib
import time
from datetime import datetime, timedelta
from functools import wraps

from config import CACHE_DIR, CACHE_EXPIRY_HOURS


def get_cache_path(key: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    hashed = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{hashed}.json")


def read_cache(key: str) -> dict | None:
    path = get_cache_path(key)
    if not os.path.exists(path):
        return None
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    if datetime.now() - mtime > timedelta(hours=CACHE_EXPIRY_HOURS):
        os.remove(path)
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        os.remove(path)
        return None


def write_cache(key: str, data: dict):
    path = get_cache_path(key)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)


def format_currency(value: float, currency: str = "KRW") -> str:
    if currency == "KRW":
        return f"{value:,.0f}원"
    return f"${value:,.2f}"


def format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """API 호출 재시도 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(delay * (backoff ** attempt))
        return wrapper
    return decorator
