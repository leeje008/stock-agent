import pandas as pd
import io
from datetime import datetime


CATEGORY_KEYWORDS = {
    "식비": ["식당", "음식", "배달", "요기요", "배민", "쿠팡이츠", "맥도날드", "버거킹", "편의점", "GS25", "CU", "세븐일레븐", "이마트", "홈플러스", "롯데마트"],
    "카페/음료": ["스타벅스", "카페", "이디야", "커피", "투썸", "메가커피", "컴포즈"],
    "교통": ["택시", "카카오T", "주유", "주차", "교통", "버스", "지하철", "고속버스", "KTX", "SRT"],
    "쇼핑": ["쿠팡", "11번가", "G마켓", "옥션", "네이버쇼핑", "무신사", "올리브영", "다이소"],
    "통신": ["SKT", "KT", "LG유플러스", "통신", "알뜰폰"],
    "구독서비스": ["넷플릭스", "유튜브", "스포티파이", "왓챠", "디즈니", "애플", "구글"],
    "의료/건강": ["병원", "약국", "의원", "치과", "한의원", "안과", "헬스", "필라테스"],
    "교육": ["학원", "교육", "인강", "클래스", "학교"],
    "주거/관리비": ["관리비", "월세", "전세", "공과금", "전기", "가스", "수도"],
    "보험": ["보험", "삼성생명", "한화생명", "교보"],
    "여가/문화": ["영화", "CGV", "메가박스", "롯데시네마", "여행", "호텔", "펜션"],
}


class BankCSVParser:
    """은행/카드 거래내역 CSV 파서"""

    BANK_FORMATS = {
        "국민은행": {
            "date_col": "거래일시",
            "amount_col": "거래금액",
            "description_col": "적요",
            "type_detection": "sign",
            "date_format": "%Y.%m.%d",
            "encoding": "cp949",
        },
        "신한은행": {
            "date_col": "거래일",
            "deposit_col": "입금",
            "withdraw_col": "출금",
            "description_col": "거래내용",
            "type_detection": "separate_columns",
            "date_format": "%Y-%m-%d",
            "encoding": "cp949",
        },
        "카카오뱅크": {
            "date_col": "거래일시",
            "amount_col": "거래금액",
            "type_col": "구분",
            "description_col": "내용",
            "date_format": "%Y.%m.%d",
            "encoding": "utf-8",
        },
        "신한카드": {
            "date_col": "이용일",
            "amount_col": "이용금액",
            "description_col": "이용가맹점",
            "type_detection": "all_expense",
            "date_format": "%Y.%m.%d",
            "encoding": "cp949",
        },
        "삼성카드": {
            "date_col": "이용일",
            "amount_col": "이용금액",
            "description_col": "가맹점",
            "type_detection": "all_expense",
            "date_format": "%Y.%m.%d",
            "encoding": "cp949",
        },
        "KB카드": {
            "date_col": "이용일",
            "amount_col": "이용금액",
            "description_col": "가맹점명",
            "type_detection": "all_expense",
            "date_format": "%Y.%m.%d",
            "encoding": "cp949",
        },
        "범용": {
            "date_col": "날짜",
            "amount_col": "금액",
            "type_col": "구분",
            "category_col": "카테고리",
            "description_col": "내용",
            "date_format": "%Y-%m-%d",
            "encoding": "utf-8",
        },
    }

    @classmethod
    def detect_bank(cls, file_data: bytes, filename: str) -> str:
        """CSV 컬럼명으로 은행/카드 자동 감지"""
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
            return "범용"

        columns = set(str(c).strip() for c in df.columns)
        best_bank = "범용"
        best_score = 0

        for bank_name, fmt in cls.BANK_FORMATS.items():
            score = sum(1 for v in fmt.values() if isinstance(v, str) and v in columns)
            if score > best_score:
                best_score = score
                best_bank = bank_name

        return best_bank

    def parse(self, file_data: bytes, filename: str, bank: str | None = None) -> list[dict]:
        """CSV/Excel 파싱하여 수입/지출 내역 리스트 반환

        Returns: [{"date", "amount", "type", "category", "description"}]
        """
        if bank is None:
            bank = self.detect_bank(file_data, filename)

        fmt = self.BANK_FORMATS.get(bank, self.BANK_FORMATS["범용"])
        enc = fmt.get("encoding", "utf-8")

        # Read file
        df = None
        if filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_data))
        else:
            for try_enc in [enc, "utf-8", "cp949", "euc-kr"]:
                try:
                    df = pd.read_csv(io.BytesIO(file_data), encoding=try_enc)
                    break
                except Exception:
                    continue

        if df is None or df.empty:
            return []

        entries = []
        for _, row in df.iterrows():
            try:
                entry = self._parse_row(row, fmt)
                if entry:
                    entries.append(entry)
            except Exception:
                continue

        return entries

    def _parse_row(self, row, fmt: dict) -> dict | None:
        """한 행을 파싱"""
        # Date
        date_col = fmt.get("date_col", "날짜")
        date_val = row.get(date_col)
        if pd.isna(date_val):
            return None
        date_str = self._parse_date(date_val, fmt.get("date_format", "%Y-%m-%d"))

        # Description
        desc_col = fmt.get("description_col", "내용")
        description = str(row.get(desc_col, "")).strip() if not pd.isna(row.get(desc_col)) else ""

        # Amount and type
        type_detection = fmt.get("type_detection", "sign")

        if type_detection == "separate_columns":
            deposit = self._parse_number(row.get(fmt.get("deposit_col", "입금"), 0))
            withdraw = self._parse_number(row.get(fmt.get("withdraw_col", "출금"), 0))
            if deposit > 0:
                amount = deposit
                entry_type = "income"
            elif withdraw > 0:
                amount = withdraw
                entry_type = "expense"
            else:
                return None
        elif type_detection == "all_expense":
            amount = abs(self._parse_number(row.get(fmt.get("amount_col", "금액"), 0)))
            entry_type = "expense"
        elif fmt.get("type_col"):
            amount = abs(self._parse_number(row.get(fmt.get("amount_col", "금액"), 0)))
            type_val = str(row.get(fmt["type_col"], "")).strip()
            if "입금" in type_val or "수입" in type_val:
                entry_type = "income"
            else:
                entry_type = "expense"
        else:  # sign-based
            raw_amount = self._parse_number(row.get(fmt.get("amount_col", "금액"), 0))
            if raw_amount > 0:
                amount = raw_amount
                entry_type = "income"
            elif raw_amount < 0:
                amount = abs(raw_amount)
                entry_type = "expense"
            else:
                return None

        if amount <= 0:
            return None

        # Category
        category_col = fmt.get("category_col")
        if category_col and not pd.isna(row.get(category_col)):
            category = str(row[category_col]).strip()
        else:
            category = self._auto_categorize(description)

        return {
            "date": date_str,
            "amount": float(amount),
            "type": entry_type,
            "category": category,
            "description": description,
            "source": "csv",
        }

    @staticmethod
    def _auto_categorize(description: str) -> str:
        """가맹점명/적요에서 카테고리 자동 분류"""
        desc_upper = description.upper()
        for category, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw.upper() in desc_upper:
                    return category
        return "기타지출"

    def _parse_date(self, value, date_format: str) -> str:
        if isinstance(value, (datetime, pd.Timestamp)):
            return value.strftime("%Y-%m-%d")
        s = str(value).strip()
        for fmt in [date_format, "%Y%m%d", "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"]:
            try:
                return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return s[:10]

    @staticmethod
    def _parse_number(value) -> float:
        if pd.isna(value):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip().replace(",", "").replace(" ", "")
        try:
            return float(s)
        except ValueError:
            return 0.0

    @staticmethod
    def get_bank_list() -> list[str]:
        return list(BankCSVParser.BANK_FORMATS.keys())

    @staticmethod
    def generate_template() -> pd.DataFrame:
        return pd.DataFrame({
            "날짜": ["2024-01-15", "2024-01-15", "2024-01-25"],
            "금액": [3500000, 45000, 120000],
            "구분": ["수입", "지출", "지출"],
            "카테고리": ["급여", "식비", "쇼핑"],
            "내용": ["1월 급여", "점심 식사", "쿠팡 주문"],
        })
