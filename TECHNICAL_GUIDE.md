# Stock Agent 기술 상세 가이드

## 1. 시스템 개요

### 1.1 전체 아키텍처 설명

Stock Agent는 **Streamlit 기반 웹 애플리케이션**으로, 개인 투자자를 위한 포트폴리오 관리 및 AI 기반 투자 분석 시스템이다. 시스템은 크게 7개 모듈 계층으로 구성된다:

```
┌─────────────────────────────────────────────────────────────┐
│                    app.py (Streamlit UI)                      │
│   Tab1: 현황 | Tab2: 최적화 | Tab3: 뉴스 | Tab4: 매수가이드  │
│   Tab5: 기술분석 | Tab6: 백테스팅 | Tab7: AI 토론             │
├─────────────┬───────────────┬────────────────┬──────────────┤
│  agent/     │  portfolio/   │  analysis/     │  broker/     │
│  LLM 에이전트│  포트폴리오    │  분석 엔진     │  증권사 연동  │
│  - llm_client│  - manager   │  - technical   │  - csv_parser│
│  - news_anal│  - optimizer  │  - backtest    │  - aggregator│
│  - market_an│  - allocator  │                │              │
│  - fundament│  - tracker    │                │              │
│  - views_gen│               │                │              │
│  - debate   │               │                │              │
│  - report_ge│               │                │              │
├─────────────┴───────────────┴────────────────┴──────────────┤
│                      data/                                   │
│   fetcher.py | news_fetcher.py | economic_data.py            │
│   market_data.py                                             │
├──────────────────────────────────────────────────────────────┤
│          db/ (SQLite)          │       utils/                 │
│   database.py | models.py     │  fx.py | helpers.py          │
│                                │  constants.py               │
├──────────────────────────────────────────────────────────────┤
│                    config.py (.env)                           │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 데이터 흐름도

```
사용자 입력 (종목 추가 / CSV 업로드)
        │
        ▼
  PortfolioManager (SQLite CRUD)
        │
        ├──▶ StockDataFetcher (yfinance / pykrx)
        │         │
        │         ▼
        ├──▶ PortfolioOptimizer (pypfopt)
        │         │
        │         ├── Mean-Variance 최적화
        │         ├── Black-Litterman 최적화
        │         └── 이산 배분 (Discrete Allocation)
        │
        ├──▶ NewsFetcher (Google News RSS)
        │         │
        │         ▼
        │    NewsAnalystAgent (LLM 감성 분석)
        │
        ├──▶ EconomicDataFetcher (FRED API)
        │
        ├──▶ TechnicalAnalyzer (RSI, MACD, BB, MA)
        │
        ├──▶ Backtester (Walk-forward 백테스트)
        │
        ├──▶ DebateAgent (Bull vs Bear 토론)
        │
        └──▶ PortfolioManagerAgent (종합 리포트)
                  │
                  ▼
            ReportGenerator (SQLite 저장)
```

### 1.3 모듈 간 의존성 관계

| 모듈 | 의존하는 모듈 |
|------|-------------|
| `app.py` | 모든 모듈 |
| `agent/llm_client.py` | `config` |
| `agent/news_analyzer.py` | `agent/llm_client` |
| `agent/market_analyst.py` | `agent/llm_client` |
| `agent/fundamental_analyst.py` | `agent/llm_client` |
| `agent/views_generator.py` | `agent/llm_client` |
| `agent/debate.py` | `agent/llm_client` |
| `agent/report_generator.py` | `db/database` |
| `data/fetcher.py` | `utils/helpers` |
| `data/news_fetcher.py` | `utils/helpers` |
| `data/economic_data.py` | `config`, `utils/constants`, `utils/helpers` |
| `data/market_data.py` | `data/fetcher` |
| `portfolio/manager.py` | `db/database`, `db/models` |
| `portfolio/optimizer.py` | `db/models` |
| `portfolio/allocator.py` | `data/fetcher`, `portfolio/optimizer` |
| `portfolio/tracker.py` | `db/database` |
| `analysis/technical.py` | (독립) |
| `analysis/backtest.py` | `portfolio/optimizer` |
| `broker/csv_parser.py` | (독립) |
| `broker/aggregator.py` | (독립) |
| `db/database.py` | `config` |
| `db/models.py` | (독립) |
| `utils/fx.py` | `utils/helpers` |
| `utils/helpers.py` | `config` |
| `utils/constants.py` | (독립) |

### 1.4 사용 기술 스택과 선택 이유

| 기술 | 용도 | 선택 이유 |
|------|------|----------|
| **Streamlit** | 웹 UI | Python만으로 인터랙티브 대시보드 구축, 빠른 프로토타이핑 |
| **Ollama + OpenAI SDK** | 로컬 LLM | 100% 로컬 실행으로 API 과금 없음, OpenAI 호환 API로 이식성 확보 |
| **yfinance** | 미국 주가/재무 데이터 | 무료, 풍부한 데이터, ETF 지원 |
| **pykrx** | 한국 주가 데이터 | KRX 공식 데이터, 한국 종목 특화 |
| **pypfopt (PyPortfolioOpt)** | 포트폴리오 최적화 | Mean-Variance, Black-Litterman, Efficient Frontier 내장 |
| **FRED API** | 거시경제 지표 | 미국 연방준비제도 공식 경제 데이터 |
| **feedparser** | 뉴스 RSS 파싱 | Google News RSS 표준 지원 |
| **Plotly** | 차트 시각화 | 인터랙티브 차트, Streamlit 네이티브 지원 |
| **SQLite** | 데이터 저장 | 서버 불필요, 단일 파일 DB, WAL 모드로 동시 접근 지원 |
| **pandas** | 데이터 처리 | 시계열 데이터 조작의 사실상 표준 |
| **numpy** | 수치 연산 | 행렬 연산, Black-Litterman 모델 구현 |

---

## 2. LLM 엔진 상세 (`agent/`)

### 2.1 LLM 클라이언트 (`llm_client.py`)

**파일 경로**: `/agent/llm_client.py`

#### Ollama OpenAI 호환 API 연동 방식

시스템은 Ollama의 OpenAI 호환 API 엔드포인트를 사용한다. Ollama는 로컬 머신에서 LLM을 실행하는 도구로, `/v1` 경로를 통해 OpenAI SDK와 100% 호환되는 API를 제공한다. 이를 통해 OpenAI의 공식 Python SDK(`openai` 패키지)를 그대로 사용하면서도 완전히 로컬에서 추론을 수행한다.

```python
self.client = OpenAI(
    base_url=LLM_BASE_URL,      # "http://localhost:11434/v1"
    api_key=LLM_API_KEY,        # "ollama" (더미 값)
)
```

`base_url`을 Ollama의 로컬 서버 주소로 지정하고, `api_key`는 Ollama에서는 검증하지 않으므로 `"ollama"` 문자열을 사용한다.

#### 듀얼 모델 라우팅 (light/heavy) 구현 상세

시스템은 작업의 복잡도에 따라 두 가지 모델을 사용한다:

| 구분 | 모델 | 파라미터 수 | 용도 |
|------|------|-----------|------|
| **light** | `llama3.1:8b` | 80억 | JSON 파싱, 감성 분석, 뷰 생성 등 구조화된 응답 |
| **heavy** | `qwen3.5:27b` | 270억 | 리포트 생성, 토론, 펀더멘탈 분석 등 복잡한 추론 |

#### model_tier 파라미터에 따른 모델 선택 로직

`generate()` 메서드에서 `model_tier` 파라미터에 따라 모델과 temperature를 동시에 결정한다:

```python
model = self.model_light if model_tier == "light" else self.model_heavy
temperature = 0.3 if model_tier == "light" else 0.5
```

#### temperature 설정 전략

- **light (0.3)**: JSON 응답 등 정형화된 출력이 필요한 작업에 낮은 temperature를 사용하여 일관성과 정확성을 높인다. 너무 창의적인 응답은 JSON 파싱 오류를 유발할 수 있다.
- **heavy (0.5)**: 리포트, 토론 등 자연어 생성 작업에 중간 수준의 temperature를 사용하여 다양하면서도 지나치게 무작위하지 않은 응답을 생성한다.

#### JSON 코드펜스 스트리핑 로직

로컬 LLM은 JSON 응답을 마크다운 코드블록으로 감싸는 경향이 있다. 이를 처리하기 위한 정규표현식 기반 스트리핑 로직:

```python
@staticmethod
def _strip_code_fences(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    return text
```

정규표현식 분석:
- `` ``` ``: 코드블록 시작 마커 (3개 백틱)
- `(?:json)?`: 선택적 "json" 언어 태그 (비캡처 그룹)
- `\s*`: 선택적 공백/개행
- `([\s\S]*?)`: 코드블록 내용 (비탐욕적 캡처, 줄바꿈 포함)
- `` ``` ``: 코드블록 종료 마커

코드펜스가 발견되면 내부 내용만 추출하고, 없으면 원본 텍스트를 그대로 반환한다.

#### generate() vs generate_json() 차이점

| 메서드 | 기본 모델 | 추가 처리 | 용도 |
|--------|----------|----------|------|
| `generate()` | heavy | 없음 | 자유 형식 텍스트 생성 (리포트, 토론) |
| `generate_json()` | light | 시스템 프롬프트에 JSON 지시 추가 + 코드펜스 스트리핑 | JSON 구조화 응답 (감성 분석, 뷰 생성) |

`generate_json()`은 시스템 프롬프트 끝에 다음 지시를 자동 추가한다:
```
반드시 유효한 JSON으로만 응답하세요. 마크다운 코드블록이나 다른 텍스트를 포함하지 마세요.
```

---

### 2.2 뉴스 분석 에이전트 (`news_analyzer.py`)

**파일 경로**: `/agent/news_analyzer.py`

#### 프롬프트 설계 상세

프롬프트는 4가지 분석 작업을 명시적으로 지시한다:

1. **감성 분석**: 각 뉴스의 시장 영향을 긍정/중립/부정으로 분류
2. **관련 종목 매핑**: 뉴스가 영향을 미칠 포트폴리오 종목 식별
3. **리스크 이벤트 감지**: 급락/급등 가능성이 있는 이벤트 식별
4. **종합 시장 전망**: 현재 시장 분위기 요약

시스템 프롬프트는 "전문 금융 뉴스 분석가" 페르소나를 설정하고, "객관적이고 데이터 기반의 분석"을 지시한다.

#### JSON 응답 스키마

```json
{
    "market_sentiment": "bullish|neutral|bearish",
    "sentiment_score": -1.0,  // -1.0 ~ 1.0 범위
    "key_events": [
        {
            "event": "이벤트 설명",
            "impact": "positive|negative|neutral",
            "affected_tickers": ["AAPL"],
            "severity": "high|medium|low"
        }
    ],
    "ticker_sentiments": {
        "TICKER": {"score": 0.0, "reason": "..."}
    },
    "summary": "종합 시장 전망 요약"
}
```

각 필드 설명:
- `market_sentiment`: 전체 시장 감성 방향 (3단계)
- `sentiment_score`: -1.0(극도 부정)부터 1.0(극도 긍정)까지 수치화된 감성 점수
- `key_events`: 주요 이벤트 목록 (영향도, 관련 종목, 심각도 포함)
- `ticker_sentiments`: 종목별 개별 감성 점수와 근거
- `summary`: 종합 요약 텍스트

#### 파싱 실패 시 fallback 처리

JSON 파싱에 실패하면 기본값으로 중립 감성을 반환하되, LLM의 원본 응답을 `summary` 필드에 저장하고 `parse_error: True` 플래그를 추가한다:

```python
except json.JSONDecodeError:
    return {
        "market_sentiment": "neutral",
        "sentiment_score": 0.0,
        "key_events": [],
        "ticker_sentiments": {},
        "summary": response,        # LLM 원본 응답 보존
        "parse_error": True,         # 파싱 실패 플래그
    }
```

#### light 모델 사용 이유

뉴스 감성 분석은 주어진 텍스트를 분류하고 점수를 매기는 비교적 정형화된 작업이다. 복잡한 추론보다는 정확한 JSON 출력이 중요하므로, 빠르고 가벼운 light 모델(`llama3.1:8b`)이 적합하다.

---

### 2.3 포트폴리오 매니저 에이전트 (`market_analyst.py`)

**파일 경로**: `/agent/market_analyst.py`

#### 프롬프트에 주입되는 6가지 데이터

`generate_recommendation()` 메서드는 다음 데이터를 프롬프트에 JSON 형태로 주입한다:

1. **현재 포트폴리오** (`current_portfolio`): 보유 종목, 수량, 평균매입가, 시장, 통화 정보
2. **최적화 결과** (`optimization_result`): Mean-Variance 또는 BL 기반 최적 비중, 기대 수익률, 변동성, 샤프 비율
3. **뉴스/시장 감성 분석** (`news_analysis`): `NewsAnalystAgent`의 분석 결과
4. **거시경제 지표** (`macro_data`): FRED 경제 지표 데이터
5. **추가 투자 예산** (`budget`): 원화 기준 투자 가능 금액
6. **시스템 프롬프트**: "경험 많은 포트폴리오 매니저" 페르소나 설정

#### 리포트 출력 형식 (6개 섹션)

LLM에게 다음 6개 섹션 형식을 지시한다:

1. **시장 환경 요약**: 현재 거시 환경과 시장 전망 (2~3문장)
2. **포트폴리오 진단**: 현재 포트폴리오의 강점/약점
3. **최적화 추천**: 수학적 최적화 결과에 뉴스/시장 상황을 반영한 조정 의견
4. **구체적 매수 가이드**: 예산으로 어떤 종목을 몇 주 매수할지
5. **리스크 요인**: 주의해야 할 리스크와 대응 방안
6. **신뢰도 평가**: 추천의 신뢰 수준 (high/medium/low)과 그 이유

프롬프트 말미에 투자 면책 고지를 포함한다.

#### heavy 모델 사용 이유

종합 투자 리포트는 여러 데이터 소스를 교차 분석하고, 논리적 추론을 수행하며, 구체적인 매수 수량까지 제시해야 하는 복잡한 작업이다. 높은 추론 능력이 필요하므로 heavy 모델(`qwen3.5:27b`)을 사용한다. `max_tokens`는 3000으로 설정하여 상세한 리포트 생성을 허용한다.

---

### 2.4 펀더멘탈 분석 에이전트 (`fundamental_analyst.py`)

**파일 경로**: `/agent/fundamental_analyst.py`

#### 분석 항목 5가지

1. **밸류에이션 평가**: P/E, P/B 등 기반 적정가치 판단
2. **수익성 분석**: ROE, 영업이익률, 순이익 추이
3. **재무 건전성**: 부채비율, 유동비율
4. **성장성**: 매출/이익 성장률 추이
5. **종합 의견**: 매수/보유/매도 의견과 근거

#### 재무제표 데이터 구조

`StockDataFetcher.get_financials()`에서 반환하는 3가지 재무제표:

```python
{
    "income": stock.financials,       # 손익계산서 (매출, 영업이익, 순이익 등)
    "balance": stock.balance_sheet,   # 재무상태표 (자산, 부채, 자본 등)
    "cashflow": stock.cashflow,       # 현금흐름표 (영업활동, 투자활동, 재무활동 CF)
}
```

각 항목은 `pd.DataFrame`으로, `app.py`에서 `to_dict()`로 변환하여 LLM에 전달한다.

#### yfinance에서 가져오는 stock_info 필드들

`MarketDataProcessor.get_stock_info()`에서 추출하는 필드:

| 필드 | 설명 | 예시 |
|------|------|------|
| `shortName` | 기업 약칭 | "Apple Inc." |
| `sector` | 산업 섹터 | "Technology" |
| `marketCap` | 시가총액 | 3000000000000 |
| `trailingPE` | 후행 P/E 비율 | 28.5 |
| `dividendYield` | 배당수익률 | 0.005 |
| `fiftyTwoWeekHigh` | 52주 최고가 | 199.62 |
| `fiftyTwoWeekLow` | 52주 최저가 | 143.90 |
| `currentPrice` | 현재가 | 178.85 |

US/ETF 종목만 지원하며, KR 종목은 기본 정보(`name`, `sector: "N/A"`)만 반환한다.

---

### 2.5 BL 뷰 생성기 (`views_generator.py`)

**파일 경로**: `/agent/views_generator.py`

#### Black-Litterman "뷰"의 의미

Black-Litterman 모델에서 "뷰(View)"란 투자자의 주관적 전망을 수치화한 것이다. 구체적으로 각 종목의 **향후 6개월 기대 초과수익률**을 연율화 수치로 표현한다. 이 뷰는 시장 균형 수익률(사전 분포)과 결합되어 사후 기대수익률을 생성한다.

#### JSON 응답 스키마

```json
{
    "views": {
        "AAPL": 0.05,       // 연 5% 초과수익 기대
        "005930": -0.02      // 연 -2% 초과수익 기대 (부진 전망)
    },
    "confidence": {
        "AAPL": 0.7,         // 70% 확신
        "005930": 0.3         // 30% 확신
    },
    "reasoning": "반도체 사이클 회복 기대, 중국 수출 규제 리스크..."
}
```

#### 뷰 값 범위 (-0.3 ~ 0.3)

프롬프트에서 뷰 값의 범위를 `-0.3 ~ 0.3`으로 제한한다. 이는 연율화 기대 초과수익률이 -30%~+30% 범위 내에서 제시되어야 함을 의미한다. 이 제한은 LLM이 극단적인 전망을 내놓는 것을 방지한다.

#### 파싱 실패 시 처리

JSON 파싱 실패 시 모든 종목에 대해 0.0 뷰(중립), 0.1 확신도(매우 낮음)를 부여하는 보수적 fallback을 제공한다:

```python
except json.JSONDecodeError:
    return {
        "views": {t: 0.0 for t in tickers},
        "confidence": {t: 0.1 for t in tickers},
        "reasoning": "분석 실패 - 기본값 사용",
        "parse_error": True,
    }
```

---

### 2.6 멀티에이전트 토론 (`debate.py`)

**파일 경로**: `/agent/debate.py`

#### 3라운드 토론 구조

```
Round 1: Bull Analyst (강세론자)
    ↓ bull_case 생성
Round 2: Bear Analyst (약세론자) ← bull_case 참조
    ↓ bear_case 생성
Round 3: Moderator (중재자) ← bull_case + bear_case 참조
    ↓ synthesis + final_verdict 생성
```

#### 각 에이전트의 시스템 프롬프트

| 에이전트 | 시스템 프롬프트 |
|---------|--------------|
| Bull | "당신은 경험 많은 강세론자(Bull) 애널리스트입니다. 시장의 기회와 긍정적 요소를 찾는 것이 전문입니다." |
| Bear | "당신은 경험 많은 약세론자(Bear) 애널리스트입니다. 시장의 리스크와 위험 요소를 찾는 것이 전문입니다." |
| Moderator | "당신은 중립적인 수석 애널리스트입니다. 양측 의견을 공정하게 평가하여 균형 잡힌 결론을 내립니다." |

#### Bear가 Bull의 논거를 참고하는 방식

Bear 에이전트의 프롬프트에 Bull의 의견 앞부분(500자)을 포함시켜 반박하도록 유도한다:

```python
bear_case = self.llm.generate(
    f"""...
강세론자의 의견도 참고하되 반박하세요:
{bull_case[:500]}
..."""
)
```

`bull_case[:500]`으로 길이를 제한하는 이유는 프롬프트가 과도하게 길어지는 것을 방지하고, Bear가 핵심 논거만 참조하도록 하기 위함이다.

#### 최종 verdict 추출 로직

Moderator의 응답에서 키워드 기반으로 최종 판정을 추출한다:

```python
verdict = "neutral"
synthesis_lower = synthesis.lower()
if "bullish" in synthesis_lower or "강세" in synthesis_lower:
    verdict = "bullish"
elif "bearish" in synthesis_lower or "약세" in synthesis_lower:
    verdict = "bearish"
```

영문("bullish"/"bearish")과 한국어("강세"/"약세") 키워드를 모두 검색한다. 두 키워드가 모두 등장하면 먼저 매칭되는 bullish가 우선한다. 어떤 키워드도 발견되지 않으면 기본값 `"neutral"`이 사용된다.

모든 라운드에서 `model_tier="heavy"`, `max_tokens=1500~2000`을 사용한다. 총 3회의 LLM 호출이 발생하며, UI에서는 "약 1분 소요"로 안내한다.

---

### 2.7 리포트 생성기 (`report_generator.py`)

**파일 경로**: `/agent/report_generator.py`

#### SQLite 저장/조회

`ReportGenerator`는 `analysis_reports` 테이블에 리포트를 CRUD 관리한다:

- **`save_report(report_type, content, metadata)`**: `report_type`(예: "recommendation"), 내용, 메타데이터(JSON)를 INSERT
- **`get_latest_report(report_type)`**: 특정 유형의 최신 리포트 1건 조회 (created_at DESC)
- **`get_report_history(report_type, limit)`**: 최근 N건의 리포트 히스토리 조회

#### 리포트 마크다운 포매팅

`format_portfolio_report()` 메서드는 다음 구조의 마크다운 리포트를 생성한다:

```markdown
# 포트폴리오 분석 리포트
**생성 시각**: YYYY-MM-DD HH:MM

---

## 1. 포트폴리오 현황
- 보유 종목 수: N개

| 종목 | 시장 | 수량 | 평균매입가 |
|------|------|------|-----------|
| ... | ... | ... | ... |

---

## 2. 최적화 결과
- 전략: max_sharpe
- 기대 수익률: XX.XX%
- 변동성: XX.XX%
- 샤프 비율: X.XX

---

## 3. AI 투자 추천
(PortfolioManagerAgent의 응답)

---

*본 정보는 투자 권유가 아니며, 투자 결정의 책임은 사용자에게 있습니다.*
```

---

## 3. 데이터 수집 상세 (`data/`)

### 3.1 주가 데이터 (`fetcher.py`)

**파일 경로**: `/data/fetcher.py`

#### yfinance (미국/ETF) vs pykrx (한국 주식) 분기 로직

```python
if market == "KR":
    df = self._fetch_krx(ticker, period)
    if df.empty:
        df = self._fetch_yfinance(f"{ticker}.KS", period)
else:
    df = self._fetch_yfinance(ticker, period)
```

- **US/ETF 종목**: 직접 yfinance로 조회 (예: `AAPL`, `QQQ`)
- **KR 종목**: 먼저 pykrx로 조회 시도, 실패 시 yfinance fallback

#### KR 종목 pykrx 실패 시 yfinance `.KS` fallback 메커니즘

pykrx가 빈 DataFrame을 반환하는 경우(서버 오류, 종목코드 오류 등), 종목코드에 `.KS` 접미사를 붙여 yfinance로 재시도한다. `.KS`는 Yahoo Finance에서 한국거래소(KRX) KOSPI 시장 종목을 식별하는 접미사이다.

#### pykrx 기간 변환

pykrx는 `period` 문자열 대신 시작/종료 날짜를 요구하므로, 기간 매핑 테이블을 사용한다:

```python
period_days = {"6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
```

#### 캐시 시스템

**캐시 키 구조**: `price_{market}_{ticker}_{period}`
- 예: `price_KR_005930_1y`, `price_US_AAPL_6mo`

캐시 저장 시 pandas DataFrame의 Timestamp 인덱스를 문자열로 변환한다:
```python
cache_df = df.copy()
cache_df.index = cache_df.index.astype(str)
write_cache(cache_key, cache_df.to_dict())
```

캐시 만료 시간은 6시간이다 (`CACHE_EXPIRY_HOURS`).

#### get_multiple_prices()의 종가 통합 로직

여러 종목의 종가를 하나의 DataFrame으로 결합하는 과정:

```python
all_close = {}
for item in tickers:
    df = self.get_price_data(ticker, market, period)
    if not df.empty:
        close_col = "Close" if "Close" in df.columns else "종가"
        all_close[ticker] = df[close_col]

combined = pd.DataFrame(all_close)
combined = combined.ffill().dropna()
```

핵심 처리:
1. **종가 컬럼 자동 감지**: yfinance는 `"Close"`, pykrx는 `"종가"`를 사용하므로 동적 감지
2. **`ffill()` (전진 채움)**: 시장 휴장일 등으로 인한 NaN을 직전 거래일 값으로 채움
3. **`dropna()`**: 채울 수 없는 나머지 NaN 행 제거 (모든 종목이 거래된 날짜만 유지)

#### 환율 조회

```python
def get_exchange_rate(self, pair: str = "KRW=X") -> float:
    ticker = yf.Ticker(pair)
    hist = ticker.history(period="1d")
    if not hist.empty:
        return float(hist["Close"].iloc[-1])
    return 1350.0  # fallback
```

`KRW=X`는 Yahoo Finance에서 USD/KRW 환율 티커이다. 조회 실패 시 1350.0을 fallback으로 사용한다.

---

### 3.2 뉴스 수집 (`news_fetcher.py`)

**파일 경로**: `/data/news_fetcher.py`

#### Google News RSS URL 구조

```
https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={ceid}
```

| 파라미터 | 설명 | 한국 | 미국 |
|---------|------|------|------|
| `q` | URL 인코딩된 검색어 | "삼성전자 주식" | "AAPL stock" |
| `hl` | 언어 | ko | en |
| `gl` | 국가 | KR | US |
| `ceid` | 에디션 | KR:ko | US:en |

#### 한국 종목 티커→종목명 매핑 (KR_TICKER_NAMES)

한국 종목 코드(6자리 숫자)는 검색에 부적합하므로, 주요 20개 종목에 대해 종목명 매핑 딕셔너리를 제공한다:

```python
KR_TICKER_NAMES = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "373220": "LG에너지솔루션",
    # ... 총 20개 종목
}
```

매핑에 없는 종목은 티커 코드 자체를 검색어로 사용한다.

#### RSS 파싱 로직 (feedparser)

```python
feed = feedparser.parse(url)
for entry in feed.entries[:limit]:
    # published 날짜 파싱
    published = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d")

    # source 추출
    if hasattr(entry, "source") and hasattr(entry.source, "title"):
        source = entry.source.title
    elif " - " in entry.get("title", ""):
        source = entry.title.rsplit(" - ", 1)[-1]
```

#### source 추출 방식

1차: RSS 항목의 `source.title` 속성 (Google News에서 제공하는 출처 정보)
2차: 제목에서 마지막 ` - ` 이후 부분 추출 (Google News RSS에서 제목 끝에 출처를 포함하는 패턴)

결과 딕셔너리 구조:
```python
{
    "title": "기사 제목",
    "summary": "기사 요약",
    "source": "출처 (예: 조선비즈, Reuters)",
    "date": "2024-01-15",
    "url": "https://..."
}
```

---

### 3.3 경제 지표 (`economic_data.py`)

**파일 경로**: `/data/economic_data.py`

#### FRED API 연동

FRED(Federal Reserve Economic Data)는 미국 연방준비제도가 제공하는 경제 데이터 서비스이다. `fredapi` 패키지를 통해 API에 접근하며, API 키가 필수이다.

```python
self.fred = Fred(api_key=FRED_API_KEY)
data = self.fred.get_series(series_id)
```

#### 6개 지표

| 표시 이름 | FRED 시리즈 ID | 설명 |
|----------|---------------|------|
| 미국 기준금리 | `FEDFUNDS` | 연방기금금리 (Fed Funds Rate) |
| 미국 CPI | `CPIAUCSL` | 소비자물가지수 (계절 조정) |
| 미국 실업률 | `UNRATE` | 실업률 |
| VIX (변동성지수) | `VIXCLS` | CBOE 변동성 지수 |
| 10년물 국채금리 | `DGS10` | 미국 10년 만기 국채 수익률 |
| 달러인덱스 | `DTWEXBGS` | 무역가중 달러인덱스 (광범위) |

#### get_macro_summary()의 1개월 변화량 계산

```python
summary[name] = {
    "latest": float(data.iloc[-1]),           # 최신 값
    "date": str(data.index[-1].date()),       # 최신 데이터 날짜
    "change_1m": float(data.iloc[-1] - data.iloc[-22])  # 약 1개월(22 영업일) 전 대비 변화량
    if len(data) > 22 else None,
}
```

1개월을 22 영업일로 근사한다. 데이터가 22건 미만이면 `None`을 반환한다.

---

### 3.4 시장 데이터 가공 (`market_data.py`)

**파일 경로**: `/data/market_data.py`

#### 수익률 계산

```python
def calculate_returns(self, prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change().dropna()
```

일별 수익률: `r_t = (P_t - P_{t-1}) / P_{t-1}`

#### 누적수익률 계산

```python
def calculate_cumulative_returns(self, prices: pd.DataFrame) -> pd.DataFrame:
    return (prices / prices.iloc[0] - 1) * 100
```

기준일(첫 날) 대비 수익률(%): `CR_t = (P_t / P_0 - 1) * 100`

#### 변동성 계산

```python
def calculate_volatility(self, prices: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    returns = self.calculate_returns(prices)
    return returns.rolling(window=window).std() * (252 ** 0.5)
```

연환산 변동성: `σ_annual = σ_daily * √252`

여기서 252는 1년 영업일 수이다. 20일 롤링 윈도우의 표준편차에 √252를 곱하여 연환산한다.

#### 상관관계 계산

```python
def calculate_correlation(self, prices: pd.DataFrame) -> pd.DataFrame:
    returns = self.calculate_returns(prices)
    return returns.corr()
```

일별 수익률 기반 피어슨 상관계수 행렬을 반환한다.

---

## 4. 포트폴리오 관리 상세 (`portfolio/`)

### 4.1 매니저 (`manager.py`)

**파일 경로**: `/portfolio/manager.py`

#### CRUD 연산

| 메서드 | 동작 | SQL |
|--------|------|-----|
| `add_holding(holding)` | 종목 추가 | `INSERT INTO portfolio_holdings ...` |
| `update_holding(id, qty, price)` | 수량/가격 수정 | `UPDATE portfolio_holdings SET ... WHERE id=?` |
| `remove_holding(id)` | 종목 삭제 | `DELETE FROM portfolio_holdings WHERE id=?` |
| `get_all_holdings()` | 전체 조회 | `SELECT * FROM portfolio_holdings` |

`update_holding()`은 `updated_at`을 `CURRENT_TIMESTAMP`로 자동 갱신한다.

#### get_portfolio_summary() 반환 구조

```python
{
    "total_holdings": 5,
    "holdings": [
        {
            "ticker": "005930",
            "market": "KR",
            "name": "삼성전자",
            "quantity": 100,
            "avg_price": 72000.0,
            "currency": "KRW",
            "sector": "반도체",
        },
        # ...
    ]
}
```

#### 거래 기록 (record_transaction)

```python
def record_transaction(self, tx: Transaction) -> int:
    # INSERT INTO transactions (ticker, market, action, quantity, price, currency, note)
```

거래 히스토리를 `transactions` 테이블에 기록한다. `get_transactions(limit)`으로 최근 N건을 조회할 수 있다.

---

### 4.2 최적화 엔진 (`optimizer.py`)

**파일 경로**: `/portfolio/optimizer.py`

#### Mean-Variance 최적화 알고리즘

##### 기대수익률 계산: mean_historical_return()

```python
self.mu = expected_returns.mean_historical_return(price_data)
```

pypfopt의 `mean_historical_return()`은 다음 공식으로 연환산 기대수익률을 계산한다:

$$\mu_i = \left(\frac{P_{i,T}}{P_{i,0}}\right)^{\frac{252}{T}} - 1$$

여기서 $P_{i,0}$은 기간 시작 가격, $P_{i,T}$는 기간 종료 가격, $T$는 거래일 수이다. 기본적으로 기하평균(CAGR) 방식을 사용한다.

##### 공분산 행렬 계산: sample_cov()

```python
self.cov = risk_models.sample_cov(price_data)
```

표본 공분산 행렬을 계산한다:

$$\Sigma_{ij} = \frac{252}{T-1} \sum_{t=1}^{T} (r_{i,t} - \bar{r}_i)(r_{j,t} - \bar{r}_j)$$

252를 곱하여 연환산한다.

##### EfficientFrontier 클래스의 max_sharpe() 내부 동작

```python
ef = EfficientFrontier(self.mu, self.cov)
ef.max_sharpe(risk_free_rate=risk_free_rate)
```

최적화 문제:

$$\max_{w} \frac{w^T \mu - r_f}{\sqrt{w^T \Sigma w}}$$

제약조건:
- $\sum w_i = 1$ (비중 합 = 1)
- $0 \le w_i \le 1$ (공매도 금지, 기본값)

내부적으로 CVXPY를 사용한 2차 프로그래밍(QP)으로 풀린다.

##### min_volatility() 내부 동작

$$\min_{w} \sqrt{w^T \Sigma w}$$

동일한 제약조건 하에서 변동성(리스크)을 최소화하는 비중을 찾는다.

##### clean_weights()의 역할

```python
cleaned = ef.clean_weights()
```

최적화 결과에서 매우 작은 비중(기본 cutoff=0.0001)을 0으로 설정하고, 나머지 비중을 합이 1이 되도록 재조정한다. 이는 실용적으로 무시할 수 있는 미소 비중을 제거하여 깔끔한 포트폴리오 구성을 만든다.

##### portfolio_performance()의 3개 지표

```python
perf = ef.portfolio_performance(verbose=False, risk_free_rate=risk_free_rate)
# perf = (expected_return, volatility, sharpe_ratio)
```

1. **기대 수익률**: $E[R_p] = w^T \mu$
2. **변동성**: $\sigma_p = \sqrt{w^T \Sigma w}$
3. **샤프 비율**: $SR = \frac{E[R_p] - r_f}{\sigma_p}$

#### Black-Litterman 모델 알고리즘

##### 사전 분포 (시장 균형 수익률)

```python
bl = BlackLittermanModel(
    self.cov,
    pi="market",  # 시장 균형 수익률을 사전 분포로 사용
    Q=Q,
    P=P,
    omega=omega,
)
```

`pi="market"`은 시장 시가총액 가중 균형 수익률(CAPM 기반)을 사전 분포로 사용한다:

$$\pi = \delta \Sigma w_{mkt}$$

여기서 $\delta$는 위험회피계수, $\Sigma$는 공분산 행렬, $w_{mkt}$는 시장 시가총액 비중이다.

##### Picking Matrix P 구성 방식

```python
tickers = list(self.prices.columns)
P = np.zeros((len(valid_views), len(tickers)))
Q = np.zeros(len(valid_views))

for i, (ticker, view) in enumerate(valid_views.items()):
    P[i, tickers.index(ticker)] = 1
    Q[i] = view
```

P는 K x N 행렬 (K=뷰 수, N=종목 수)로, 각 행이 하나의 뷰를 나타낸다. 절대 뷰(absolute view)를 사용하므로 해당 종목 위치에 1을 설정한다.

예: 3개 종목 [AAPL, MSFT, GOOG]에서 AAPL에 대한 뷰:
```
P = [[1, 0, 0]]
Q = [0.05]  // AAPL이 연 5% 초과수익 기대
```

##### View Vector Q 구성 방식

Q는 K차원 벡터로, 각 뷰의 기대 초과수익률 값이다. `ViewsGeneratorAgent`가 생성한 `views` 딕셔너리에서 직접 추출한다.

##### Omega (불확실성 행렬) 계산

```python
tau = 0.05
omega_diag = []
for ticker in valid_views:
    conf = confidence.get(ticker, 0.5)
    omega_diag.append(tau * (1 - conf + 0.01))
omega = np.diag(omega_diag)
```

Omega는 뷰의 불확실성을 나타내는 대각 행렬이다:

$$\Omega_{ii} = \tau \times (1 - c_i + 0.01)$$

여기서:
- $\tau = 0.05$ (스케일링 팩터, 사전 분포의 불확실성)
- $c_i$ = 종목 $i$에 대한 확신도 (0~1)
- $0.01$ = 수치 안정성을 위한 소량 추가

확신도가 높을수록(1에 가까울수록) $\Omega_{ii}$가 작아져 뷰의 불확실성이 낮아지고, 사후 수익률이 뷰에 더 가까워진다.

##### 사후 기대수익률 bl_returns() 계산

```python
bl_returns = bl.bl_returns()
```

Black-Litterman 사후 기대수익률:

$$E[R] = [(\tau \Sigma)^{-1} + P^T \Omega^{-1} P]^{-1} [(\tau \Sigma)^{-1} \pi + P^T \Omega^{-1} Q]$$

이 결합 공식은 시장 균형 수익률(사전)과 투자자 뷰(관측)를 베이지안 방식으로 결합한다.

##### BL 수익률로 EfficientFrontier 재최적화

```python
ef = EfficientFrontier(bl_returns, self.cov)
ef.max_sharpe(risk_free_rate=risk_free_rate)
```

BL 사후 수익률을 기대수익률로 사용하여 다시 Max Sharpe 최적화를 수행한다.

#### 이산 배분 (Discrete Allocation)

##### greedy_portfolio() 알고리즘

```python
latest_prices = get_latest_prices(self.prices)
da = DiscreteAllocation(weights, latest_prices, total_portfolio_value=budget)
allocation, leftover = da.greedy_portfolio()
```

1. 각 종목에 대해 `비중 * 총 예산 / 현재 주가 = 목표 주수`를 계산
2. 소수점 이하를 내림하여 정수 주수로 변환
3. 잔여 현금으로 가장 많이 배분이 부족한 종목부터 추가 1주씩 매수 (탐욕 알고리즘)
4. 더 이상 매수 불가능하면 종료

결과:
```python
{
    "allocation": {"AAPL": 5, "MSFT": 3},  # 종목별 매수 수량
    "leftover": 12500.5,                     # 잔여 현금
    "invested": budget - leftover,           # 실제 투자 금액
}
```

#### 효율적 프론티어 데이터 생성

```python
def get_efficient_frontier_data(self, n_points: int = 50) -> list[dict]:
    target_returns = np.linspace(self.mu.min(), self.mu.max(), n_points)
    for target in target_returns:
        ef = EfficientFrontier(self.mu, self.cov)
        ef.efficient_return(target_return=float(target))
        perf = ef.portfolio_performance(verbose=False)
        ef_data.append({"return": perf[0], "volatility": perf[1], "sharpe": perf[2]})
```

`np.linspace`로 최소~최대 기대수익률 범위를 50등분하고, 각 목표 수익률에서 변동성을 최소화하는 포트폴리오를 계산한다. 이 점들을 연결하면 효율적 프론티어 곡선이 된다.

---

### 4.3 예산 배분 (`allocator.py`)

**파일 경로**: `/portfolio/allocator.py`

#### fetcher → optimizer → discrete_allocation 파이프라인

`generate_buy_guide()`의 전체 흐름:

```
1. StockDataFetcher.get_multiple_prices()
   → 여러 종목의 종가 DataFrame 생성

2. PortfolioOptimizer(prices)
   → 기대수익률(mu), 공분산(cov) 계산

3. optimizer.optimize_{strategy}()
   → 최적 비중(weights) 산출

4. active_weights 필터링
   → 비중 0.001 이하 종목 제거

5. optimizer.calculate_discrete_allocation(weights, budget)
   → 정수 주수 배분
```

#### 전략별 분기

```python
if strategy == "max_sharpe":
    result = optimizer.optimize_max_sharpe()
elif strategy == "min_volatility":
    result = optimizer.optimize_min_volatility()
else:
    result = optimizer.optimize_max_sharpe()  # 기본값
```

최소 2개 종목의 시세 데이터가 필요하며, 부족 시 에러를 반환한다.

---

### 4.4 성과 추적 (`tracker.py`)

**파일 경로**: `/portfolio/tracker.py`

#### 일별 스냅샷 INSERT OR REPLACE

```python
def take_snapshot(self, total_value, total_cost, holdings):
    today = date.today().isoformat()
    self.conn.execute(
        """INSERT OR REPLACE INTO portfolio_snapshots (date, total_value, total_cost, holdings_json)
           VALUES (?, ?, ?, ?)""",
        (today, total_value, total_cost, holdings_json),
    )
```

`portfolio_snapshots` 테이블의 `date` 컬럼에 `UNIQUE` 제약이 있으므로, 같은 날짜에 이미 스냅샷이 있으면 새 값으로 교체한다. 이를 통해 하루에 여러 번 앱을 실행해도 중복 스냅샷이 생기지 않는다.

#### get_history()의 수익률 계산

```python
pnl = total_value - total_cost
return_pct = (pnl / total_cost * 100) if total_cost else 0.0
```

수익률(%) = (평가금액 - 매입금액) / 매입금액 * 100

`total_cost`가 0인 경우 ZeroDivisionError를 방지한다.

---

## 5. 분석 엔진 상세 (`analysis/`)

### 5.1 기술적 분석 (`technical.py`)

**파일 경로**: `/analysis/technical.py`

#### RSI (Relative Strength Index)

```python
@staticmethod
def rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))
```

수학적 공식:

$$\Delta_t = P_t - P_{t-1}$$

$$\text{Gain}_t = \frac{1}{n} \sum_{i=t-n+1}^{t} \max(\Delta_i, 0)$$

$$\text{Loss}_t = \frac{1}{n} \sum_{i=t-n+1}^{t} |\min(\Delta_i, 0)|$$

$$RS = \frac{\text{Gain}}{\text{Loss}}$$

$$RSI = 100 - \frac{100}{1 + RS}$$

- `delta.clip(lower=0)`: 음수 변화량을 0으로 클리핑 (상승분만 추출)
- `-delta.clip(upper=0)`: 양수 변화량을 0으로 클리핑 후 부호 반전 (하락분의 절대값)
- 14일 단순이동평균 사용

해석:
- RSI > 70: 과매수 (가격 하락 가능성)
- RSI < 30: 과매도 (가격 상승 가능성)

#### MACD (Moving Average Convergence Divergence)

```python
@staticmethod
def macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
```

수학적 공식:

$$\text{MACD Line} = \text{EMA}_{12}(P) - \text{EMA}_{26}(P)$$

$$\text{Signal Line} = \text{EMA}_9(\text{MACD Line})$$

$$\text{Histogram} = \text{MACD Line} - \text{Signal Line}$$

EMA(지수이동평균) 공식:

$$\text{EMA}_t = \alpha \cdot P_t + (1 - \alpha) \cdot \text{EMA}_{t-1}, \quad \alpha = \frac{2}{n+1}$$

`adjust=False`는 재귀적 EMA 계산을 사용한다 (초기값에 대한 편향 보정 없음).

해석:
- MACD Line > Signal Line: 매수 신호 (상승 모멘텀)
- MACD Line < Signal Line: 매도 신호 (하락 모멘텀)

#### 볼린저 밴드

```python
@staticmethod
def bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> dict:
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
```

수학적 공식:

$$\text{Middle} = \text{SMA}_{20}(P)$$

$$\text{Upper} = \text{SMA}_{20}(P) + 2 \times \sigma_{20}(P)$$

$$\text{Lower} = \text{SMA}_{20}(P) - 2 \times \sigma_{20}(P)$$

해석:
- 가격 > 상단 밴드: 과매수 (가격이 평균에서 크게 벗어남)
- 가격 < 하단 밴드: 과매도
- 밴드 폭: 변동성의 시각적 표현

#### 이동평균선

```python
{
    "MA5": prices.rolling(5).mean(),    # 5일 (주간)
    "MA20": prices.rolling(20).mean(),  # 20일 (월간)
    "MA60": prices.rolling(60).mean(),  # 60일 (분기)
    "MA120": prices.rolling(120).mean(), # 120일 (반기)
}
```

#### 종합 신호 판정 로직

`get_signal_summary()` 메서드는 4가지 지표를 종합하여 신호를 판정한다:

**각 지표별 신호 분류 규칙:**

| 지표 | 조건 | 신호 |
|------|------|------|
| RSI | > 70 | "과매수" |
| RSI | < 30 | "과매도" |
| RSI | 30~70 | "중립" |
| MACD | MACD > Signal | "MACD 매수" |
| MACD | MACD <= Signal | "MACD 매도" |
| BB | 현재가 > 상단 | "BB 상단 돌파" |
| BB | 현재가 < 하단 | "BB 하단 돌파" |
| MA20 | 현재가 > MA20 | "20일선 위" |
| MA20 | 현재가 <= MA20 | "20일선 아래" |

**bullish/bearish 카운팅 방식:**

```python
bullish = sum(1 for s in signals if "매수" in s or "과매도" in s or "위" in s)
bearish = sum(1 for s in signals if "매도" in s or "과매수" in s or "아래" in s or "돌파" in s)
```

- **bullish 키워드**: "매수", "과매도" (반전 기대), "위"
- **bearish 키워드**: "매도", "과매수" (반전 기대), "아래", "돌파" (BB 돌파)

최종 판정:
- bullish > bearish → "매수 우위"
- bearish > bullish → "매도 우위"
- 동점 → "중립"

**주의사항**: "BB 상단 돌파"는 "돌파" 키워드가 bearish에 포함되어 있어 매도 신호로 분류된다. 이는 볼린저 밴드의 해석(상단 돌파 = 과매수 = 하락 가능성)과 일치한다.

---

### 5.2 백테스팅 (`backtest.py`)

**파일 경로**: `/analysis/backtest.py`

#### Walk-forward 백테스팅 알고리즘

Walk-forward 백테스트는 미래 데이터를 사용하지 않는(look-ahead bias 방지) 현실적인 백테스팅 방식이다.

**알고리즘 흐름:**

```
시간 →
|---lookback_days---|---rebalance_days---|---rebalance_days---|
|    최적화 윈도우    |     포트폴리오 운용    |     포트폴리오 운용    |
                    ↑ 비중 재조정           ↑ 비중 재조정
```

```python
portfolio_values = [1.0]  # 초기 자산 = 1.0 (정규화)
current_weights = None
days_since_rebalance = rebalance_days  # 첫 날부터 리밸런싱 강제

for i in range(start_idx, len(returns)):
    # 리밸런싱 주기 도달 시 재최적화
    if days_since_rebalance >= rebalance_days:
        lookback_prices = prices.iloc[i - lookback_days:i]
        # 과거 데이터만 사용하여 최적화 실행
        opt = PortfolioOptimizer(lookback_prices)
        result = opt.optimize_max_sharpe()
        current_weights = result.weights
        days_since_rebalance = 0

    # 일별 포트폴리오 수익률 계산
    daily_return = sum(weight * daily_return_for_stock for each stock)
    new_value = portfolio_values[-1] * (1 + daily_return)
```

**핵심 설계:**
- `lookback_days=252` (1년): 최적화에 사용할 과거 데이터 기간
- `rebalance_days=63` (분기): 포트폴리오 비중 재조정 주기
- `days_since_rebalance = rebalance_days`로 초기화하여 첫 날에 즉시 최적화 실행
- 최적화 실패 시 동일 비중(equal weight)으로 fallback

#### 일별 포트폴리오 수익률 계산

$$R_{p,t} = \sum_{i=1}^{N} w_i \cdot r_{i,t}$$

여기서 $w_i$는 종목 $i$의 비중, $r_{i,t}$는 종목 $i$의 $t$일 수익률이다.

#### 자산 곡선(equity curve) 생성

$$V_t = V_{t-1} \times (1 + R_{p,t})$$

초기값 $V_0 = 1.0$에서 시작하여 복리 방식으로 포트폴리오 가치를 누적한다.

#### 성과 지표 계산 공식

| 지표 | 공식 | 코드 |
|------|------|------|
| **총 수익률** | $\frac{V_T}{V_0} - 1$ | `equity.iloc[-1] / equity.iloc[0] - 1` |
| **연환산 수익률** | $(1 + R_{total})^{365/D} - 1$ | `(1 + total_return) ** (365.0 / total_days) - 1` |
| **변동성** | $\sigma_{daily} \times \sqrt{252}$ | `daily_returns.std() * np.sqrt(252)` |
| **샤프 비율** | $\frac{R_{annual}}{\sigma_{annual}}$ | `annualized_return / vol` |
| **최대 낙폭(MDD)** | $\min_t \frac{V_t - V_{max,t}}{V_{max,t}}$ | `((equity - rolling_max) / rolling_max).min()` |

MDD 계산 상세:
```python
rolling_max = equity.expanding().max()    # 시점별 역대 최고가
drawdowns = (equity - rolling_max) / rolling_max  # 고점 대비 하락률
max_dd = float(drawdowns.min())           # 최대 하락률 (음수)
```

#### 3전략 비교

```python
def compare_strategies(self, strategies=None, ...):
    if strategies is None:
        strategies = ["max_sharpe", "min_volatility", "equal_weight"]
    for strat in strategies:
        result = self.run_backtest(strat, lookback_days, rebalance_days)
```

- **max_sharpe**: 샤프 비율 최대화 전략
- **min_volatility**: 변동성 최소화 전략
- **equal_weight**: 동일 비중 전략 (벤치마크)

equal_weight는 최적화 없이 단순히 모든 종목에 `1/N` 비중을 할당한다.

---

## 6. 증권사 연동 상세 (`broker/`)

### 6.1 CSV 파서 (`csv_parser.py`)

**파일 경로**: `/broker/csv_parser.py`

#### 증권사별 컬럼 매핑 테이블

시스템은 3개 브로커 프리셋을 지원한다:

| 항목 | 신한투자증권 | KB증권 | 범용 |
|------|------------|--------|------|
| 날짜 | 거래일자 | 거래일 | 거래일자 |
| 종목코드 | 종목코드 | 종목코드 | 종목코드 |
| 종목명 | 종목명 | 종목명 | 종목명 |
| 매매구분 | 매매구분 | 거래구분 | 매매구분 |
| 수량 | 수량 | 거래수량 | 수량 |
| 단가 | 단가 | 거래단가 | 단가 |
| 금액 | 거래금액 | 거래금액 | 거래금액 |
| 수수료 | 수수료 | 수수료 | 수수료 |
| 세금 | 세금 | 제세금 | 세금 |
| 날짜형식 | %Y%m%d | %Y.%m.%d | %Y-%m-%d |
| 인코딩 | cp949 | cp949 | utf-8 |

#### 인코딩 자동 감지

CSV 파일의 인코딩을 다음 순서로 시도한다:

```python
for try_enc in [enc, "utf-8", "cp949", "euc-kr"]:
    try:
        df = pd.read_csv(io.BytesIO(file_data), encoding=try_enc)
        break
    except (UnicodeDecodeError, pd.errors.ParserError):
        continue
else:
    raise ValueError("파일 인코딩을 인식할 수 없습니다.")
```

1. 증권사 프리셋의 기본 인코딩
2. UTF-8
3. CP949 (한국어 Windows 기본 인코딩)
4. EUC-KR

모든 인코딩에 실패하면 ValueError를 발생시킨다.

#### 컬럼 fuzzy matching 로직

프리셋의 컬럼명과 실제 CSV 컬럼이 정확히 일치하지 않을 때 키워드 기반 퍼지 매칭을 수행한다:

```python
def _detect_columns(self, df, fmt):
    for key, expected_col in col_keys.items():
        if expected_col in df.columns:
            mapping[key] = expected_col
        else:
            for col in df.columns:
                # 키워드 기반 매칭
                if key == "date" and any(kw in col for kw in ["일자", "일시", "날짜", "date", "거래일"]):
                    mapping[key] = col
                    break
                # ... 다른 키도 동일 패턴
```

매칭 키워드:
- date: "일자", "일시", "날짜", "date", "거래일"
- ticker: "종목코드", "코드", "ticker", "symbol"
- name: "종목명", "종목", "name"
- action: "매매", "구분", "거래구분", "type", "action"
- quantity: "수량", "qty", "quantity"
- price: "단가", "가격", "price"
- amount: "금액", "거래금액", "amount"
- fee: "수수료", "fee", "commission"
- tax: "세금", "제세금", "tax"

#### 날짜 형식 자동 감지

```python
def _parse_date(self, value, date_format):
    # datetime/Timestamp 객체인 경우 직접 변환
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.strftime("%Y-%m-%d")

    # 문자열인 경우 여러 포맷 시도
    for fmt in [date_format, "%Y%m%d", "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"]:
        try:
            return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s[:10]  # 모든 포맷 실패 시 앞 10자 그대로 반환
```

지원 형식: `20240115`, `2024-01-15`, `2024.01.15`, `2024/01/15`

#### 티커 전처리

```python
# A 접두사 제거 (일부 증권사에서 종목코드 앞에 A를 붙임)
if ticker.startswith("A") and ticker[1:].isdigit():
    ticker = ticker[1:]

# 6자리 zero-padding (한국 종목코드)
ticker = ticker.zfill(6) if ticker.isdigit() and len(ticker) < 6 else ticker
```

예: `"A005930"` → `"005930"`, `"5930"` → `"005930"`

#### 숫자 파싱

```python
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
```

쉼표 제거(`"72,000"` → `72000`), 공백 제거, NaN/빈값 → 0.0 처리.

#### CSV 템플릿 생성

```python
@staticmethod
def generate_template() -> pd.DataFrame:
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
```

---

### 6.2 거래 집계기 (`aggregator.py`)

**파일 경로**: `/broker/aggregator.py`

#### 가중평균 매입가 계산 알고리즘

```python
if txn["action"] == "BUY":
    existing_cost = h["total_cost"]
    new_cost = txn["price"] * txn["quantity"]
    h["quantity"] += txn["quantity"]
    h["total_cost"] = existing_cost + new_cost

elif txn["action"] == "SELL":
    if h["quantity"] > 0:
        avg_cost_per_share = h["total_cost"] / h["quantity"]
        sell_qty = min(txn["quantity"], h["quantity"])
        h["quantity"] -= sell_qty
        h["total_cost"] -= avg_cost_per_share * sell_qty
        h["total_cost"] = max(0, h["total_cost"])
```

**매수 시:**

$$\text{total\_cost}_{new} = \text{total\_cost}_{old} + (\text{price} \times \text{quantity})$$

$$\text{avg\_price} = \frac{\text{total\_cost}}{\text{total\_quantity}}$$

예: 기존 10주 @ 70,000원 (총 700,000원) + 5주 @ 75,000원 (375,000원)
→ 15주, 총 1,075,000원, 평균매입가 = 71,666.67원

**매도 시:**

$$\text{avg\_cost\_per\_share} = \frac{\text{total\_cost}}{\text{quantity}}$$

$$\text{total\_cost}_{new} = \text{total\_cost}_{old} - (\text{avg\_cost\_per\_share} \times \text{sell\_qty})$$

매도 수량이 보유 수량을 초과하면 `min()`으로 제한한다. `max(0, total_cost)`로 부동소수점 오차로 인한 음수를 방지한다.

최종 결과에서 `quantity <= 0`인 종목은 제외하고, `total_cost` 기준 내림차순으로 정렬한다.

#### DCA (적립식 매수) 분석

```python
def get_dca_summary(self, transactions, ticker):
    ticker_txns = [t for t in transactions if t["ticker"] == ticker and t["action"] == "BUY"]

    total_invested = sum(t["price"] * t["quantity"] for t in ticker_txns)
    total_qty = sum(t["quantity"] for t in ticker_txns)
    prices = [t["price"] for t in ticker_txns]

    # 월평균 투자금 계산
    months_span = max(1, (dates[-1] - dates[0]).days / 30)
    monthly_avg = total_invested / months_span
```

반환값:
- `total_invested`: 총 투자 금액
- `current_quantity`: 현재 보유 수량 (매수만 집계)
- `avg_price`: 평균 매수가
- `buy_history`: 매수 이력 타임라인
- `price_range`: 매수가 범위 (min/max)
- `monthly_avg_amount`: 월평균 투자금

---

## 7. 데이터베이스 상세 (`db/`)

### 7.1 스키마 (`database.py`)

**파일 경로**: `/db/database.py`

#### PRAGMA 설정

```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys=ON")
```

- **WAL (Write-Ahead Logging)**: 읽기와 쓰기를 동시에 수행할 수 있는 저널 모드. Streamlit의 다중 세션에서 동시 접근 시 성능 향상.
- **foreign_keys=ON**: 외래 키 제약 활성화.

`sqlite3.Row` 팩토리를 설정하여 쿼리 결과를 딕셔너리처럼 접근할 수 있게 한다.

#### 6개 테이블 DDL 상세

**1. portfolio_holdings** — 포트폴리오 보유 종목

```sql
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,                              -- 종목코드
    market TEXT NOT NULL CHECK(market IN ('KR', 'US', 'ETF')),  -- 시장 구분
    name TEXT NOT NULL,                                -- 종목명
    quantity INTEGER NOT NULL,                         -- 보유 수량
    avg_price REAL NOT NULL,                           -- 평균매입가
    currency TEXT NOT NULL DEFAULT 'KRW',              -- 통화 (KRW/USD)
    sector TEXT,                                       -- 섹터 (선택)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,    -- 생성일
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP     -- 수정일
);
```
사용처: `PortfolioManager` CRUD 연산

**2. transactions** — 거래 기록

```sql
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    market TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('BUY', 'SELL')),
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'KRW',
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
사용처: `PortfolioManager.record_transaction()`

**3. optimization_history** — 최적화 이력

```sql
CREATE TABLE IF NOT EXISTS optimization_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy TEXT NOT NULL,           -- 최적화 전략명
    weights_json TEXT NOT NULL,       -- 비중 JSON
    expected_return REAL,             -- 기대수익률
    volatility REAL,                  -- 변동성
    sharpe_ratio REAL,                -- 샤프비율
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
사용처: 최적화 결과 이력 관리 (현재 코드에서는 직접 사용되지 않음)

**4. analysis_reports** — 분석 리포트

```sql
CREATE TABLE IF NOT EXISTS analysis_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL,        -- 리포트 유형 (예: "recommendation")
    content TEXT NOT NULL,            -- 리포트 내용 (Markdown)
    metadata_json TEXT,               -- 메타데이터 JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
사용처: `ReportGenerator` 리포트 저장/조회

**5. portfolio_snapshots** — 포트폴리오 스냅샷

```sql
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,        -- 날짜 (YYYY-MM-DD), UNIQUE 제약
    total_value REAL NOT NULL,        -- 총 평가금액
    total_cost REAL NOT NULL,         -- 총 매입금액
    holdings_json TEXT,               -- 보유 종목 상세 JSON
    created_at TEXT DEFAULT (datetime('now'))
);
```
사용처: `PortfolioTracker` 일별 성과 추적

**6. sentiment_history** — 감성 분석 이력

```sql
CREATE TABLE IF NOT EXISTS sentiment_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,               -- 날짜
    market_sentiment TEXT,            -- 시장 감성 (bullish/neutral/bearish)
    sentiment_score REAL,             -- 감성 점수 (-1.0 ~ 1.0)
    ticker_sentiments_json TEXT,      -- 종목별 감성 JSON
    summary TEXT,                     -- 요약
    created_at TEXT DEFAULT (datetime('now'))
);
```
사용처: `app.py` Tab3에서 뉴스 분석 결과 저장, 감성 추이 차트

---

### 7.2 데이터 모델 (`models.py`)

**파일 경로**: `/db/models.py`

#### 5개 dataclass

**1. Holding**

```python
@dataclass
class Holding:
    ticker: str            # 종목코드 (예: "AAPL", "005930")
    market: str            # 시장 구분 ("KR", "US", "ETF")
    name: str              # 종목명 (예: "Apple Inc.", "삼성전자")
    quantity: int           # 보유 수량
    avg_price: float        # 평균매입가
    currency: str = "KRW"   # 통화 기본값 KRW
    sector: str | None = None  # 섹터 (선택)
    id: int | None = None      # DB 자동생성 ID
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

**2. Transaction**

```python
@dataclass
class Transaction:
    ticker: str
    market: str
    action: str            # "BUY" 또는 "SELL"
    quantity: int
    price: float           # 거래 단가
    currency: str = "KRW"
    note: str | None = None  # 메모 (선택)
    id: int | None = None
    created_at: datetime | None = None
```

**3. OptimizationResult**

```python
@dataclass
class OptimizationResult:
    strategy: str                               # 전략명 (예: "max_sharpe")
    weights: dict[str, float] = field(default_factory=dict)  # 종목별 비중
    expected_return: float = 0.0                # 기대수익률 (연율화)
    volatility: float = 0.0                     # 변동성 (연율화)
    sharpe_ratio: float = 0.0                   # 샤프 비율
```

**4. AnalysisReport**

```python
@dataclass
class AnalysisReport:
    report_type: str        # 리포트 유형 (예: "recommendation")
    content: str            # 리포트 내용
    metadata: dict | None = None
    id: int | None = None
    created_at: datetime | None = None
```

**5. PortfolioSnapshot**

```python
@dataclass
class PortfolioSnapshot:
    date: str               # 날짜 (YYYY-MM-DD)
    total_value: float      # 총 평가금액
    total_cost: float       # 총 매입금액
    holdings_json: str | None = None  # 보유 종목 상세 JSON
    id: int | None = None
```

---

## 8. 유틸리티 상세 (`utils/`)

### 8.1 환율 (`fx.py`)

**파일 경로**: `/utils/fx.py`

#### yfinance KRW=X 조회

```python
def get_usd_krw_rate() -> float:
    cached = read_cache(CACHE_KEY)
    if cached is not None:
        return cached["rate"]
    try:
        ticker = yf.Ticker("KRW=X")
        rate = ticker.fast_info["lastPrice"]
        write_cache(CACHE_KEY, {"rate": rate})
        return float(rate)
    except Exception:
        return FALLBACK_RATE  # 1350.0
```

`fast_info["lastPrice"]`는 `history()`보다 빠르게 최신 가격을 가져온다.

- 캐시 키: `fx_usd_krw`
- fallback: `1350.0`원 (환율 조회 실패 시)

#### 통화 변환 함수

```python
def convert_to_krw(amount: float, currency: str) -> float:
    if currency == "KRW": return amount
    return amount * get_usd_krw_rate()

def convert_to_usd(amount: float, currency: str) -> float:
    if currency == "USD": return amount
    return amount / get_usd_krw_rate()
```

---

### 8.2 캐시 (`helpers.py`)

**파일 경로**: `/utils/helpers.py`

#### MD5 해시 기반 캐시 파일명

```python
def get_cache_path(key: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    hashed = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{hashed}.json")
```

캐시 키(예: `"price_KR_005930_1y"`)를 MD5 해시로 변환하여 파일명으로 사용한다. 이를 통해 파일 시스템에서 안전한 파일명을 보장한다.

예: `"price_KR_005930_1y"` → `data/cache/a1b2c3d4...json`

#### 6시간 만료 체크 (mtime 기반)

```python
def read_cache(key: str) -> dict | None:
    path = get_cache_path(key)
    if not os.path.exists(path):
        return None
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    if datetime.now() - mtime > timedelta(hours=CACHE_EXPIRY_HOURS):
        os.remove(path)
        return None
```

파일의 수정 시각(`mtime`)을 확인하여 6시간(`CACHE_EXPIRY_HOURS`)이 경과했으면 캐시를 삭제하고 `None`을 반환한다.

#### 깨진 캐시 자동 삭제

```python
try:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
except (json.JSONDecodeError, ValueError):
    os.remove(path)
    return None
```

JSON 파싱에 실패하면(파일 손상, 불완전한 쓰기 등) 해당 캐시 파일을 삭제하고 `None`을 반환한다.

#### 추가 유틸리티

```python
def format_currency(value, currency="KRW"):
    if currency == "KRW": return f"{value:,.0f}원"     # "1,000,000원"
    return f"${value:,.2f}"                              # "$1,000.00"

def format_percent(value):
    return f"{value * 100:.2f}%"                         # "12.34%"
```

---

### 8.3 상수 (`constants.py`)

**파일 경로**: `/utils/constants.py`

#### RISK_LEVELS 매핑

```python
RISK_LEVELS = {
    "매우 보수적": 0.05,    # 연 5% 목표
    "보수적": 0.10,         # 연 10% 목표
    "중립": 0.15,           # 연 15% 목표
    "공격적": 0.20,         # 연 20% 목표
    "매우 공격적": 0.30,    # 연 30% 목표
}
```

UI의 위험 선호도 슬라이더에서 사용된다.

#### FRED_INDICATORS 시리즈 ID

```python
FRED_INDICATORS = {
    "미국 기준금리": "FEDFUNDS",
    "미국 CPI": "CPIAUCSL",
    "미국 실업률": "UNRATE",
    "VIX (변동성지수)": "VIXCLS",
    "10년물 국채금리": "DGS10",
    "달러인덱스": "DTWEXBGS",
}
```

#### 기타 상수

- `MARKET_KR = "KR"`, `MARKET_US = "US"`, `MARKET_ETF = "ETF"`: 시장 식별자
- `FX_TICKER_USDKRW = "KRW=X"`: Yahoo Finance USD/KRW 티커
- `DISCLAIMER`: 투자 면책 고지 문구

---

## 9. UI 상세 (`app.py`)

**파일 경로**: `/app.py`

### 9.1 초기 설정

```python
st.set_page_config(page_title="주식 포트폴리오 에이전트", layout="wide")
init_db()  # DB 테이블 생성 (이미 존재하면 무시)

pm = PortfolioManager()
fetcher = StockDataFetcher()
market_proc = MarketDataProcessor()
news_fetcher = NewsFetcher()
tracker = PortfolioTracker()
```

`sys.path.insert(0, os.path.dirname(__file__))`로 프로젝트 루트를 Python 경로에 추가한다.

### 9.2 사이드바

#### 투자 설정

- **예산**: `st.number_input` (기본값 1,000,000원, 100,000원 단위)
- **위험 선호도**: `st.select_slider` (5단계)
- **전략**: `st.radio` ("최대 샤프 비율" / "최소 변동성" / "Black-Litterman")

#### 종목 검색

`KR_STOCK_MAP` 딕셔너리에 한국 주요 종목 및 ETF 약 30개를 하드코딩하여 빠른 검색을 지원한다. 검색어가 KR_STOCK_MAP에서 발견되지 않고 6자 이하이면 yfinance로 미국 종목 검색을 시도한다.

```python
t = yf.Ticker(search_query.upper())
info = t.info
if info.get("shortName"):
    search_results.append({...})
```

ETF 여부는 yfinance의 `quoteType` 필드로 판단한다.

#### 종목 수동 추가 폼

`st.form`으로 구성된 입력 폼:
- 티커, 시장(US/KR/ETF), 종목명, 수량, 평균매입가, 섹터
- 시장이 US/ETF면 통화를 USD, KR이면 KRW로 자동 설정
- 제출 시 `PortfolioManager.add_holding()`으로 DB에 저장

#### 거래내역 CSV 업로드

1. 증권사 선택 (신한투자증권 / KB증권 / 범용)
2. CSV/Excel 파일 업로드
3. `BrokerCSVParser.parse()`로 파싱
4. 거래 내역 미리보기 (Expander)
5. `TransactionAggregator.aggregate()`로 집계
6. 집계 결과 테이블 표시
7. "포트폴리오에 반영" 버튼 → 각 종목을 `Holding`으로 변환하여 DB에 추가

ETF 판별 키워드: "TIGER", "KODEX", "ACE", "ARIRANG", "KBSTAR", "SOL", "HANARO"

#### CSV 템플릿 다운로드

`BrokerCSVParser.generate_template()`으로 생성한 DataFrame을 `utf-8-sig` 인코딩(BOM 포함)으로 CSV 변환하여 다운로드 버튼을 제공한다.

#### 환율 표시

`get_usd_krw_rate()`의 결과를 `st.metric`으로 표시한다. 실패 시 "환율 정보 로딩 실패" 캡션을 표시한다.

---

### 9.3 Tab 1: 포트폴리오 현황

**호출 모듈**: `PortfolioManager`, `StockDataFetcher`, `PortfolioTracker`

**데이터 흐름**:
1. `pm.get_all_holdings()` → 전체 보유 종목
2. 각 종목에 대해 `fetcher.get_price_data(ticker, market, period="5d")` → 최근 5일 현재가
3. 현재가 × 수량 = 평가금액, USD 종목은 환율 적용하여 KRW 환산
4. 손익 = 평가금액 - 매입금액, 수익률 = 손익/매입금액 × 100

**시각화**:
- 4개 지표: 총 평가금액, 총 손익, 총 수익률, 보유 종목 수 (`st.metric`)
- 종목 테이블: 종목명, 티커, 시장, 수량, 평균매입가, 현재가, 통화, 평가금액, 손익, 수익률, 섹터
- Plotly 파이 차트 2개: 시장별 비중, 섹터별 비중 (`px.pie`)
- 성과 추이 라인 차트: 평가금액 vs 매입금액 (90일, `go.Scatter`)

**session_state 키**: 없음 (매번 DB에서 재로드)

**스냅샷 저장**: Tab 1 표시 시 자동으로 `tracker.take_snapshot()` 호출

**종목 삭제**: `st.selectbox`로 삭제할 종목 선택 → `pm.remove_holding()` → `st.rerun()`

---

### 9.4 Tab 2: 최적화 결과

**호출 모듈**: `BudgetAllocator`, `PortfolioOptimizer`, `ViewsGeneratorAgent`

**데이터 흐름**:
1. 전략 선택에 따른 분기:
   - max_sharpe / min_volatility: `BudgetAllocator.generate_buy_guide()` 직접 호출
   - Black-Litterman:
     a. `ViewsGeneratorAgent.generate_views()` → 뉴스 기반 투자 뷰 생성
     b. `StockDataFetcher.get_multiple_prices()` → 가격 데이터
     c. `PortfolioOptimizer.optimize_black_litterman()` → BL 최적화
     d. `PortfolioOptimizer.calculate_discrete_allocation()` → 이산 배분
2. 결과를 `session_state["optimization_result"]`에 저장

**시각화**:
- 3개 지표: 기대 수익률, 변동성, 샤프 비율 (`st.metric`)
- 최적 비중 막대 차트 (`px.bar`)
- 효율적 프론티어 곡선 + 최적 포트폴리오 위치 (`go.Scatter` + `go.Scatter` 별 마커)

**session_state 키**:
- `optimization_result`: 최적화 결과 dict
- `bl_views`: BL 모델 투자 뷰 (BL 전략 시)

---

### 9.5 Tab 3: 뉴스 & 시장 분석

**호출 모듈**: `NewsFetcher`, `NewsAnalystAgent`, `EconomicDataFetcher`

**데이터 흐름**:
1. **뉴스 수집**: 최대 5개 종목의 뉴스(각 3건) + 시장별 뉴스(각 3건) → `news_fetcher.get_ticker_news()`, `get_market_news()`
2. **AI 감성 분석**: 수집된 뉴스를 `NewsAnalystAgent.analyze_news()`에 전달
3. **감성 히스토리 저장**: `sentiment_history` 테이블에 INSERT
4. **경제지표 조회**: `EconomicDataFetcher.get_macro_summary()`

**시각화**:
- 시장 감성 + 감성 점수 (`st.metric`)
- 주요 이벤트 목록 (심각도별 색상 표시)
- 종합 요약 텍스트
- 감성 점수 추이 라인 차트 (`go.Scatter`, y=0 기준선 포함)
- 거시경제 지표 3열 그리드 (`st.metric`, delta 표시)

**session_state 키**:
- `collected_news`: 수집된 뉴스 리스트
- `news_analysis`: AI 감성 분석 결과
- `macro_data`: 거시경제 지표 딕셔너리

---

### 9.6 Tab 4: 매수 가이드

**호출 모듈**: `PortfolioManagerAgent`, `ReportGenerator`

**데이터 흐름**:
1. `session_state["optimization_result"]`에서 매수 가이드 표시
2. "AI 종합 리포트 생성" 버튼 → `PortfolioManagerAgent.generate_recommendation()` 호출
3. 리포트를 `ReportGenerator.save_report()`로 DB에 저장

**시각화**:
- 매수 가이드 테이블 (종목별 매수 수량)
- 투자 금액 / 잔여 현금 (`st.metric`)
- AI 리포트 (Markdown 렌더링)
- 리포트 다운로드 버튼 (Markdown 파일)
- 과거 리포트 히스토리 (Expander)

**session_state 키**:
- `ai_report`: 최신 AI 리포트 텍스트

---

### 9.7 Tab 5: 기술적 분석

**호출 모듈**: `StockDataFetcher`, `TechnicalAnalyzer`, `FundamentalAnalystAgent`

**데이터 흐름**:
1. 종목 선택 → `fetcher.get_price_data()` → 종가 Series
2. `TechnicalAnalyzer.get_signal_summary()` → 종합 신호
3. 개별 지표 계산: RSI, MACD, BB, MA

**시각화**:
- 종합 신호 (색상별 표시), RSI, MACD, BB 위치, MA20 대비 (`st.metric`)
- 3행 서브플롯 차트 (`make_subplots`, 높이 800px):
  - Row 1: 가격 + 볼린저밴드 + MA20 + MA60
  - Row 2: RSI (70/30 기준선)
  - Row 3: MACD Line + Signal Line + Histogram (Bar)
- 상세 기술적 신호 목록 (Expander)

**펀더멘탈 분석** (US/ETF 종목만):
1. `fetcher.get_financials()` → 재무제표 DataFrame
2. `market_proc.get_stock_info()` → 기업 정보
3. DataFrame을 dict로 변환
4. `FundamentalAnalystAgent.analyze()` → AI 펀더멘탈 리포트

---

### 9.8 Tab 6: 백테스팅

**호출 모듈**: `StockDataFetcher`, `Backtester`

**데이터 흐름**:
1. 설정: 데이터 기간(1y/2y/5y), 룩백 기간(60~504일), 리밸런싱 주기(21~252일)
2. `fetcher.get_multiple_prices()` → 종가 DataFrame
3. `Backtester.compare_strategies()` → 3개 전략 결과

**시각화**:
- 전략별 성과 비교 테이블: 총 수익률, 연환산 수익률, 변동성, 샤프 비율, 최대 낙폭
- 자산 곡선 라인 차트: 3개 전략 동시 표시 (blue/orange/green)

**session_state 키**:
- `backtest_results`: 백테스팅 결과 리스트

---

### 9.9 Tab 7: AI 토론

**호출 모듈**: `DebateAgent`, `PortfolioManager`

**데이터 흐름**:
1. `pm.get_portfolio_summary()` → 포트폴리오 요약
2. `session_state`에서 `news_analysis`, `macro_data` 가져오기
3. `DebateAgent.run_debate()` → 3라운드 토론 결과

**시각화**:
- 최종 판정 (`st.metric` + 색상 이모지)
- 2열 레이아웃: 좌측=강세론(Bull), 우측=약세론(Bear) (Markdown 렌더링)
- 종합 판정(Moderator) (Markdown 렌더링)
- 투자 면책 고지

**session_state 키**:
- `debate_result`: 토론 결과 dict

---

## 10. 설정 및 환경 변수 (`config.py`)

**파일 경로**: `/config.py`

### 전체 환경변수 목록과 기본값

| 환경변수 | 기본값 | 필수 여부 | 설명 |
|---------|--------|----------|------|
| `FRED_API_KEY` | `""` | 경제지표 사용 시 필수 | FRED API 키 |
| `DART_API_KEY` | `""` | 선택 | 전자공시 API 키 (현재 미사용) |
| `NEWS_API_KEY` | `""` | 선택 | 뉴스 API 키 (현재 미사용, RSS 사용) |
| `BOK_API_KEY` | `""` | 선택 | 한국은행 API 키 (현재 미사용) |
| `LLM_BASE_URL` | `"http://localhost:11434/v1"` | 필수 | Ollama API 엔드포인트 |
| `LLM_API_KEY` | `"ollama"` | 필수(더미) | Ollama API 키 (검증 안 함) |
| `LLM_MODEL_LIGHT` | `"llama3.1:8b"` | 필수 | 경량 LLM 모델명 |
| `LLM_MODEL_HEAVY` | `"qwen3.5:27b"` | 필수 | 중량 LLM 모델명 |

### 고정 설정값

| 설정 | 값 | 설명 |
|------|------|------|
| `LLM_MAX_TOKENS` | 4096 | LLM 최대 출력 토큰 수 |
| `DB_PATH` | `data/stock_agent.db` | SQLite DB 파일 경로 |
| `CACHE_DIR` | `data/cache/` | 캐시 파일 디렉토리 |
| `CACHE_EXPIRY_HOURS` | 6 | 캐시 만료 시간 (시간) |
| `BASE_CURRENCY` | `"KRW"` | 기본 통화 |

`.env` 파일은 `python-dotenv`의 `load_dotenv()`로 자동 로드된다.

---

## 11. 데이터 흐름 종합

사용자가 종목을 추가하고, 최적화를 실행하고, 뉴스 분석을 하고, AI 리포트를 생성하기까지의 전체 데이터 흐름을 단계별로 설명한다.

### 단계 1: 종목 추가

```
사용자 → 사이드바 종목 추가 폼 (or CSV 업로드)
    │
    ├── [수동 추가]
    │   └── Holding 객체 생성 → PortfolioManager.add_holding() → INSERT INTO portfolio_holdings
    │
    └── [CSV 업로드]
        ├── BrokerCSVParser.parse(file_data, filename, broker)
        │   ├── 인코딩 자동 감지 (cp949/utf-8/euc-kr)
        │   ├── 컬럼 자동 매핑 (fuzzy matching)
        │   ├── 날짜/숫자/티커 전처리
        │   └── → list[dict] (거래 내역)
        │
        ├── TransactionAggregator.aggregate(transactions)
        │   ├── 시간순 정렬
        │   ├── 종목별 가중평균 매입가 계산
        │   ├── 매도 반영 (비례 차감)
        │   └── → list[dict] (현재 보유 현황)
        │
        └── 각 종목에 대해 Holding 생성 → PortfolioManager.add_holding()
```

### 단계 2: 포트폴리오 현황 확인 (Tab 1)

```
Tab 1 렌더링
    │
    ├── PortfolioManager.get_all_holdings() → list[Holding]
    │
    ├── 각 종목에 대해:
    │   ├── StockDataFetcher.get_price_data(ticker, market, "5d")
    │   │   ├── 캐시 확인 (helpers.read_cache)
    │   │   ├── KR: pykrx → yfinance .KS fallback
    │   │   └── US/ETF: yfinance
    │   └── 현재가 추출 (Close/종가 컬럼)
    │
    ├── 평가금액 = 현재가 × 수량
    ├── USD 종목: 평가금액 × 환율 (get_usd_krw_rate)
    ├── 손익 = 평가금액 - 매입금액
    ├── 수익률 = 손익 / 매입금액 × 100
    │
    ├── PortfolioTracker.take_snapshot(total_value, total_cost, holdings)
    │   └── INSERT OR REPLACE INTO portfolio_snapshots
    │
    └── Plotly 시각화: 파이 차트(시장별/섹터별), 성과 추이 라인 차트
```

### 단계 3: 포트폴리오 최적화 (Tab 2)

```
"최적화 실행" 버튼 클릭
    │
    ├── [max_sharpe / min_volatility 전략]
    │   └── BudgetAllocator.generate_buy_guide(tickers, budget, strategy)
    │       ├── StockDataFetcher.get_multiple_prices(tickers, "1y")
    │       │   ├── 각 종목 종가 수집
    │       │   └── ffill() + dropna() → 정렬된 DataFrame
    │       │
    │       ├── PortfolioOptimizer(prices)
    │       │   ├── mu = mean_historical_return(prices)  # 연환산 기대수익률
    │       │   └── cov = sample_cov(prices)             # 공분산 행렬
    │       │
    │       ├── optimizer.optimize_max_sharpe() 또는 optimize_min_volatility()
    │       │   ├── EfficientFrontier(mu, cov)
    │       │   ├── max_sharpe() / min_volatility()      # CVXPY 2차 프로그래밍
    │       │   ├── clean_weights()                       # 미소 비중 제거
    │       │   └── portfolio_performance()               # (수익률, 변동성, 샤프비율)
    │       │
    │       └── optimizer.calculate_discrete_allocation(weights, budget)
    │           ├── get_latest_prices(prices)             # 최신 종가
    │           ├── DiscreteAllocation(weights, prices, budget)
    │           └── greedy_portfolio()                    # 정수 주수 배분
    │
    └── [Black-Litterman 전략]
        ├── ViewsGeneratorAgent.generate_views(tickers, news_analysis, macro_data)
        │   ├── LLM(light) → JSON 응답
        │   └── → {views: {AAPL: 0.05}, confidence: {AAPL: 0.7}, reasoning: "..."}
        │
        ├── StockDataFetcher.get_multiple_prices(tickers, "1y")
        │
        ├── PortfolioOptimizer(prices)
        │
        └── optimizer.optimize_black_litterman(views, confidence)
            ├── Picking Matrix P 구성 (종목별 절대 뷰)
            ├── View Vector Q 구성
            ├── Omega 계산: τ × (1 - confidence + 0.01)
            ├── BlackLittermanModel(cov, pi="market", Q, P, omega)
            ├── bl_returns() → 사후 기대수익률
            ├── EfficientFrontier(bl_returns, cov)
            ├── max_sharpe()
            └── calculate_discrete_allocation()
```

### 단계 4: 뉴스 수집 & AI 감성 분석 (Tab 3)

```
"뉴스 수집 & AI 분석 실행" 버튼 클릭
    │
    ├── 뉴스 수집
    │   ├── 각 종목(최대 5개): NewsFetcher.get_ticker_news(ticker, market, limit=3)
    │   │   ├── KR: 종목명 검색 (KR_TICKER_NAMES 매핑)
    │   │   └── US: "{ticker} stock" 검색
    │   └── 시장별: NewsFetcher.get_market_news(market, limit=3)
    │
    ├── Google News RSS 파싱
    │   ├── URL 생성: https://news.google.com/rss/search?q=...
    │   ├── feedparser.parse(url)
    │   └── → [{title, summary, source, date, url}, ...]
    │
    ├── AI 감성 분석
    │   ├── NewsAnalystAgent.analyze_news(all_news, tickers)
    │   ├── LLM(light) → JSON 응답
    │   └── → {market_sentiment, sentiment_score, key_events, ticker_sentiments, summary}
    │
    └── 감성 히스토리 저장
        └── INSERT INTO sentiment_history
```

### 단계 5: AI 종합 리포트 생성 (Tab 4)

```
"AI 종합 리포트 생성" 버튼 클릭
    │
    ├── 데이터 수집
    │   ├── portfolio_summary ← PortfolioManager.get_portfolio_summary()
    │   ├── optimization_result ← session_state["optimization_result"]
    │   ├── news_analysis ← session_state["news_analysis"]
    │   └── macro_data ← session_state["macro_data"]
    │
    ├── PortfolioManagerAgent.generate_recommendation(
    │       portfolio, optimization, news, macro, budget
    │   )
    │   ├── 프롬프트 구성 (6가지 데이터 주입)
    │   ├── LLM(heavy, max_tokens=3000) → 자유형식 텍스트
    │   └── → 6개 섹션 리포트 (Markdown)
    │
    └── ReportGenerator.save_report("recommendation", report, metadata)
        └── INSERT INTO analysis_reports
```

---

## 12. 의존성 패키지 상세 (`pyproject.toml`)

**파일 경로**: `/pyproject.toml`

| 패키지 | 버전 요구 | 역할 | 사용처 |
|--------|----------|------|--------|
| `openai` | >=1.30.0 | OpenAI 호환 API SDK | `agent/llm_client.py` - Ollama 통신 |
| `fredapi` | >=0.5.2 | FRED API 래퍼 | `data/economic_data.py` - 거시경제 지표 수집 |
| `numpy` | >=2.4.3 | 수치 연산 | `portfolio/optimizer.py` - 행렬 연산, BL 모델 |
| `opendartreader` | >=0.2.3 | 전자공시(DART) API | (현재 직접 사용되지 않음, 향후 확장용) |
| `pandas` | >=2.3.3 | 데이터 조작 | 전역 - 시계열 데이터, DataFrame 처리 |
| `plotly` | >=6.6.0 | 인터랙티브 차트 | `app.py` - 파이 차트, 라인 차트, 서브플롯 |
| `pykrx` | >=1.0.51 | KRX 데이터 수집 | `data/fetcher.py` - 한국 주식 OHLCV |
| `pyportfolioopt` | >=1.6.0 | 포트폴리오 최적화 | `portfolio/optimizer.py` - MV, BL, Efficient Frontier |
| `python-dotenv` | >=1.2.2 | .env 파일 로드 | `config.py` - 환경변수 로드 |
| `requests` | >=2.32.5 | HTTP 클라이언트 | 간접 의존 (yfinance, fredapi 등에서 사용) |
| `streamlit` | >=1.55.0 | 웹 UI 프레임워크 | `app.py` - 전체 UI |
| `yfinance` | >=1.2.0 | Yahoo Finance 데이터 | `data/fetcher.py`, `utils/fx.py`, `data/market_data.py` |
| `feedparser` | >=6.0 | RSS 파싱 | `data/news_fetcher.py` - Google News RSS 파싱 |
| `setuptools` | <82 | 빌드 도구 | 패키지 빌드 호환성 (상한 제한) |

**Python 버전 요구**: `>=3.11` (union type hint `X | Y` 문법 사용)
