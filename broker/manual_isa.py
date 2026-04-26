"""ISA 적립식 수동 입력용 단순 CSV 파서.

증권사 양식과 별개로, 사용자가 직접 작성하는 미니멀 양식.
컬럼: date, ticker, name, quantity, price, contribution_amount(optional)
"""
import io
from datetime import datetime

import pandas as pd


REQUIRED_COLS = ["date", "ticker", "name", "quantity", "price"]
OPTIONAL_COLS = ["contribution_amount", "currency", "market", "note"]


def template() -> pd.DataFrame:
    """사용자가 채워서 다시 업로드할 빈 템플릿."""
    return pd.DataFrame({
        "date": ["2026-04-26", "2026-04-26"],
        "ticker": ["360750", "133690"],
        "name": ["TIGER 미국S&P500", "TIGER 미국나스닥100"],
        "quantity": [30, 10],
        "price": [16500, 80000],
        "contribution_amount": [495000, 800000],
        "currency": ["KRW", "KRW"],
        "market": ["KR", "KR"],
        "note": ["월 적립", "월 적립"],
    })


def parse(file_data: bytes, filename: str) -> list[dict]:
    """미니멀 ISA 양식 → 거래내역 리스트로 정규화.

    Returns: [{date, ticker, name, action='BUY', quantity, price, amount,
               currency, market, fee=0, tax=0, contribution_amount, note}]
    """
    df = _read(file_data, filename)
    df.columns = [str(c).strip().lower() for c in df.columns]

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    rows: list[dict] = []
    for _, r in df.iterrows():
        try:
            date_str = _normalize_date(r["date"])
            ticker = str(r["ticker"]).strip()
            if ticker.startswith("A") and ticker[1:].isdigit():
                ticker = ticker[1:]
            if ticker.isdigit() and len(ticker) < 6:
                ticker = ticker.zfill(6)
            qty = _num(r["quantity"])
            price = _num(r["price"])
            if qty <= 0 or price <= 0:
                continue
            amount = qty * price
            market = _infer_market(ticker, r.get("market"))
            currency = str(r.get("currency") or ("KRW" if market == "KR" else "USD")).strip().upper()
            contribution = _num(r.get("contribution_amount") or 0)
            rows.append({
                "date": date_str,
                "ticker": ticker,
                "name": str(r["name"]).strip(),
                "action": "BUY",
                "quantity": int(qty),
                "price": float(price),
                "amount": float(amount),
                "fee": 0.0,
                "tax": 0.0,
                "currency": currency,
                "market": market,
                "contribution_amount": float(contribution) if contribution else float(amount),
                "note": str(r.get("note") or "").strip(),
            })
        except Exception:
            continue
    return rows


def _read(file_data: bytes, filename: str) -> pd.DataFrame:
    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(file_data))
    for enc in ["utf-8-sig", "utf-8", "cp949", "euc-kr"]:
        try:
            return pd.read_csv(io.BytesIO(file_data), encoding=enc)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    raise ValueError("파일 인코딩을 인식할 수 없습니다.")


def _normalize_date(value) -> str:
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s[:10]


def _num(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _infer_market(ticker: str, override) -> str:
    if override:
        m = str(override).strip().upper()
        if m in ("KR", "US", "ETF"):
            return m
    if ticker.isdigit() and len(ticker) == 6:
        return "KR"
    return "US"
