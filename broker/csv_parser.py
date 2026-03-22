import pandas as pd
import io
from datetime import datetime


class BrokerCSVParser:
    """증권사 거래내역 CSV/Excel 파서"""

    BROKER_FORMATS = {
        "신한투자증권": {
            "date_col": "거래일자",
            "ticker_col": "종목코드",
            "name_col": "종목명",
            "action_col": "매매구분",
            "quantity_col": "수량",
            "price_col": "단가",
            "amount_col": "거래금액",
            "fee_col": "수수료",
            "tax_col": "세금",
            "buy_keywords": ["매수", "buy"],
            "sell_keywords": ["매도", "sell"],
            "date_format": "%Y%m%d",
            "encoding": "cp949",
            "skiprows": 0,
        },
        "KB증권": {
            "date_col": "거래일",
            "ticker_col": "종목코드",
            "name_col": "종목명",
            "action_col": "거래구분",
            "quantity_col": "거래수량",
            "price_col": "거래단가",
            "amount_col": "거래금액",
            "fee_col": "수수료",
            "tax_col": "제세금",
            "buy_keywords": ["매수", "buy"],
            "sell_keywords": ["매도", "sell"],
            "date_format": "%Y.%m.%d",
            "encoding": "cp949",
            "skiprows": 0,
        },
        "범용 (직접입력)": {
            "date_col": "거래일자",
            "ticker_col": "종목코드",
            "name_col": "종목명",
            "action_col": "매매구분",
            "quantity_col": "수량",
            "price_col": "단가",
            "amount_col": "거래금액",
            "fee_col": "수수료",
            "tax_col": "세금",
            "buy_keywords": ["매수", "buy", "BUY"],
            "sell_keywords": ["매도", "sell", "SELL"],
            "date_format": "%Y-%m-%d",
            "encoding": "utf-8",
            "skiprows": 0,
        },
    }

    def parse(
        self,
        file_data: bytes,
        filename: str,
        broker: str,
        encoding: str | None = None,
    ) -> list[dict]:
        """CSV/Excel 파일을 파싱하여 거래 내역 리스트로 변환

        Returns: [
            {
                "date": "2024-01-15",
                "ticker": "005930",
                "name": "삼성전자",
                "action": "BUY",
                "quantity": 10,
                "price": 72000.0,
                "amount": 720000.0,
                "fee": 0.0,
                "tax": 0.0,
            },
            ...
        ]
        """
        fmt = self.BROKER_FORMATS.get(broker, self.BROKER_FORMATS["범용 (직접입력)"])
        enc = encoding or fmt["encoding"]

        # Read file
        if filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_data), skiprows=fmt["skiprows"])
        else:
            # Try specified encoding, fallback to utf-8, then cp949
            for try_enc in [enc, "utf-8", "cp949", "euc-kr"]:
                try:
                    df = pd.read_csv(
                        io.BytesIO(file_data),
                        encoding=try_enc,
                        skiprows=fmt["skiprows"],
                    )
                    break
                except (UnicodeDecodeError, pd.errors.ParserError):
                    continue
            else:
                raise ValueError("파일 인코딩을 인식할 수 없습니다.")

        # Auto-detect columns if exact match not found
        col_mapping = self._detect_columns(df, fmt)

        transactions = []
        for _, row in df.iterrows():
            try:
                # Parse date
                date_val = row.get(col_mapping.get("date"))
                if pd.isna(date_val):
                    continue
                date_str = self._parse_date(date_val, fmt["date_format"])

                # Parse action
                action_val = str(row.get(col_mapping.get("action"), "")).strip()
                if any(kw in action_val for kw in fmt["buy_keywords"]):
                    action = "BUY"
                elif any(kw in action_val for kw in fmt["sell_keywords"]):
                    action = "SELL"
                else:
                    continue  # Skip unknown actions (dividends, etc.)

                # Parse ticker - remove leading zeros for display, keep 6-digit format
                ticker = str(row.get(col_mapping.get("ticker"), "")).strip()
                # Remove common prefixes like 'A' that some brokers add
                if ticker.startswith("A") and ticker[1:].isdigit():
                    ticker = ticker[1:]
                ticker = ticker.zfill(6) if ticker.isdigit() and len(ticker) < 6 else ticker

                # Parse name
                name = str(row.get(col_mapping.get("name"), "")).strip()

                # Parse numeric values
                quantity = self._parse_number(row.get(col_mapping.get("quantity"), 0))
                price = self._parse_number(row.get(col_mapping.get("price"), 0))
                amount = self._parse_number(row.get(col_mapping.get("amount"), 0))
                fee = self._parse_number(row.get(col_mapping.get("fee"), 0))
                tax = self._parse_number(row.get(col_mapping.get("tax"), 0))

                if quantity <= 0:
                    continue

                transactions.append({
                    "date": date_str,
                    "ticker": ticker,
                    "name": name,
                    "action": action,
                    "quantity": int(quantity),
                    "price": float(price),
                    "amount": float(amount) if amount else float(price * quantity),
                    "fee": float(fee),
                    "tax": float(tax),
                })
            except Exception:
                continue

        return transactions

    def _detect_columns(self, df: pd.DataFrame, fmt: dict) -> dict:
        """컬럼명을 자동 감지하여 매핑"""
        mapping = {}
        col_keys = {
            "date": fmt["date_col"],
            "ticker": fmt["ticker_col"],
            "name": fmt["name_col"],
            "action": fmt["action_col"],
            "quantity": fmt["quantity_col"],
            "price": fmt["price_col"],
            "amount": fmt["amount_col"],
            "fee": fmt["fee_col"],
            "tax": fmt["tax_col"],
        }

        for key, expected_col in col_keys.items():
            if expected_col in df.columns:
                mapping[key] = expected_col
            else:
                # Fuzzy match: find column containing the keyword
                for col in df.columns:
                    col_stripped = str(col).strip()
                    # Check various partial matches
                    if key == "date" and any(kw in col_stripped for kw in ["일자", "일시", "날짜", "date", "거래일"]):
                        mapping[key] = col
                        break
                    elif key == "ticker" and any(kw in col_stripped for kw in ["종목코드", "코드", "ticker", "symbol"]):
                        mapping[key] = col
                        break
                    elif key == "name" and any(kw in col_stripped for kw in ["종목명", "종목", "name"]):
                        mapping[key] = col
                        break
                    elif key == "action" and any(kw in col_stripped for kw in ["매매", "구분", "거래구분", "type", "action"]):
                        mapping[key] = col
                        break
                    elif key == "quantity" and any(kw in col_stripped for kw in ["수량", "qty", "quantity"]):
                        mapping[key] = col
                        break
                    elif key == "price" and any(kw in col_stripped for kw in ["단가", "가격", "price"]):
                        mapping[key] = col
                        break
                    elif key == "amount" and any(kw in col_stripped for kw in ["금액", "거래금액", "amount"]):
                        mapping[key] = col
                        break
                    elif key == "fee" and any(kw in col_stripped for kw in ["수수료", "fee", "commission"]):
                        mapping[key] = col
                        break
                    elif key == "tax" and any(kw in col_stripped for kw in ["세금", "제세금", "tax"]):
                        mapping[key] = col
                        break

        return mapping

    def _parse_date(self, value, date_format: str) -> str:
        """다양한 날짜 형식을 YYYY-MM-DD로 변환"""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, pd.Timestamp):
            return value.strftime("%Y-%m-%d")

        s = str(value).strip()
        # Try the specified format first
        for fmt in [date_format, "%Y%m%d", "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"]:
            try:
                return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return s[:10]

    @staticmethod
    def _parse_number(value) -> float:
        """문자열/숫자를 float로 변환 (쉼표 제거 등)"""
        if pd.isna(value):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip().replace(",", "").replace(" ", "")
        try:
            return float(s)
        except ValueError:
            return 0.0

    @classmethod
    def detect_broker(cls, file_data: bytes, filename: str) -> str:
        """CSV 컬럼명으로 증권사 자동 감지"""
        # Try reading with multiple encodings to get column names
        import io
        df = None
        for enc in ["utf-8", "cp949", "euc-kr"]:
            try:
                if filename.endswith((".xlsx", ".xls")):
                    df = pd.read_excel(io.BytesIO(file_data), nrows=0)
                else:
                    df = pd.read_csv(io.BytesIO(file_data), encoding=enc, nrows=0)
                break
            except Exception:
                continue

        if df is None:
            return "범용 (직접입력)"

        columns = set(str(c).strip() for c in df.columns)

        best_broker = "범용 (직접입력)"
        best_score = 0

        for broker_name, fmt in cls.BROKER_FORMATS.items():
            score = 0
            for key in ["date_col", "ticker_col", "name_col", "action_col", "quantity_col", "price_col"]:
                if fmt.get(key) in columns:
                    score += 1
            if score > best_score:
                best_score = score
                best_broker = broker_name

        return best_broker

    @staticmethod
    def get_broker_list() -> list[str]:
        return list(BrokerCSVParser.BROKER_FORMATS.keys())

    @staticmethod
    def generate_template() -> pd.DataFrame:
        """범용 CSV 템플릿 생성"""
        return pd.DataFrame({
            "거래일자": ["2024-01-15", "2024-02-15", "2024-03-15"],
            "종목코드": ["133690", "133690", "360750"],
            "종목명": ["TIGER 미국나스닥100", "TIGER 미국나스닥100", "TIGER 미국S&P500"],
            "매매구분": ["매수", "매수", "매수"],
            "수량": [5, 5, 10],
            "단가": [80000, 82000, 16000],
            "거래금액": [400000, 410000, 160000],
            "수수료": [0, 0, 0],
            "세금": [0, 0, 0],
        })
