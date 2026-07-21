"""CSV 파싱 공통 유틸.

broker/csv_parser.py 와 budget/csv_parser.py 가 공유하는 인코딩 폴백 읽기,
날짜/숫자 파싱 로직을 한곳에 모은다. 동작은 기존 각 파서와 동일하다.
"""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd

from utils.logger import get_logger

logger = get_logger("utils.csv_utils")

DEFAULT_ENCODINGS: tuple[str, ...] = ("utf-8", "cp949", "euc-kr")


def read_csv_with_fallback(
    file_data: bytes,
    encodings: list[str] | tuple[str, ...] = DEFAULT_ENCODINGS,
    **read_csv_kwargs,
) -> pd.DataFrame | None:
    """여러 인코딩을 순서대로 시도해 CSV를 읽는다.

    file_data: 원본 바이트
    encodings: 시도할 인코딩 순서 (앞에서부터)
    read_csv_kwargs: pandas.read_csv 로 전달할 추가 인자 (skiprows, nrows 등)

    Returns: 첫 성공 DataFrame, 모두 실패하면 None.
    """
    last_error: Exception | None = None
    for enc in encodings:
        try:
            return pd.read_csv(io.BytesIO(file_data), encoding=enc, **read_csv_kwargs)
        except Exception as e:
            last_error = e
            logger.debug(f"CSV 읽기 실패 (encoding={enc}): {e}")
            continue
    if last_error is not None:
        logger.warning(
            f"모든 인코딩({', '.join(encodings)})으로 CSV를 읽지 못했습니다: {last_error}"
        )
    return None


def parse_date(value, date_format: str = "%Y-%m-%d") -> str:
    """다양한 날짜 표현을 YYYY-MM-DD 문자열로 변환한다."""
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    for fmt in [date_format, "%Y%m%d", "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"]:
        try:
            return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s[:10]


def parse_number(value) -> float:
    """문자열/숫자를 float로 변환한다 (쉼표·공백 제거, 실패 시 0.0)."""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return 0.0
