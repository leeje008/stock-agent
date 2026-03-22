# Stock Portfolio Agent

한국/미국/글로벌 ETF를 통합 관리하는 AI 기반 주식 포트폴리오 에이전트입니다.
로컬 LLM(Ollama)을 활용하여 **과금 없이** 뉴스 감성 분석, 투자 추천 리포트, 펀더멘탈 분석, Bull/Bear 토론까지 수행합니다.

---

## 주요 기능

### 1. 포트폴리오 현황 (Tab 1)
- 한국(KRX) / 미국(NYSE, NASDAQ) / 글로벌 ETF 종목 통합 관리
- 실시간 시세 조회 (yfinance, pykrx)
- **USD/KRW 환율 자동 적용** — 다중 통화 포트폴리오도 KRW 기준으로 통일된 평가금액 표시
- 시장별 / 섹터별 비중 파이차트
- **포트폴리오 성과 추이 차트** — 일별 스냅샷 저장, 90일간 평가금액 vs 매입금액 추이 시각화

### 2. 포트폴리오 최적화 (Tab 2)
- **Mean-Variance 최적화** — 최대 샤프 비율 / 최소 변동성 전략
- **Black-Litterman 모델** — AI가 종목별 기대수익률 "뷰"를 생성하고, 이를 수학적 모델에 반영하여 최적 비중 산출
- 이산 배분(Discrete Allocation) — 예산 내 실제 매수 주수 계산
- **효율적 프론티어 시각화** — 위험-수익 곡선 + 최적 포트폴리오 위치 표시

### 3. 뉴스 & 시장 분석 (Tab 3)
- **실제 뉴스 수집** — Google News RSS를 통한 종목별/시장별 뉴스 자동 수집 (API 키 불필요)
- **AI 감성 분석** — 경량 모델(`llama3.1:8b`)로 빠르게 시장 감성(bullish/neutral/bearish), 주요 이벤트 감지, 종목별 영향도 분석
- **감성 점수 추이 차트** — 분석 이력을 DB에 저장, 30일간 감성 추이 시각화
- **거시경제 지표 대시보드** — FRED API 연동 (미국 기준금리, CPI, 실업률, VIX, 10년물 국채금리, 달러인덱스)

### 4. 매수 가이드 & AI 리포트 (Tab 4)
- 최적화 결과 기반 종목별 매수 수량 / 투자 금액 / 잔여 현금 안내
- **AI 종합 투자 리포트** — 고성능 모델(`qwen3.5:27b`)이 포트폴리오, 최적화 결과, 뉴스 분석, 거시경제 데이터를 종합하여 투자 추천 리포트 생성
- **리포트 Markdown 다운로드** — 생성된 리포트를 파일로 저장
- **리포트 히스토리** — 과거 생성된 리포트 열람 (SQLite 저장)

### 5. 기술적 분석 (Tab 5)
- **RSI (14)** — 과매수/과매도 구간 판단
- **MACD** — 추세 전환 신호
- **볼린저 밴드** — 가격 변동성 범위
- **이동평균선** (5, 20, 60, 120일) — 추세 방향
- **종합 기술적 신호** — 모든 지표를 종합한 매수/매도/중립 판정
- 인터랙티브 Plotly 차트 (3단 서브플롯: 가격+BB, RSI, MACD)
- **AI 펀더멘탈 분석** — US/ETF 종목의 재무제표(손익, 재무상태표, 현금흐름)를 AI가 분석하여 밸류에이션/수익성/건전성/성장성 평가

### 6. 백테스팅 (Tab 6)
- **3가지 전략 비교 백테스트** — 최대 샤프, 최소 변동성, 동일 비중
- Walk-forward 방식 — 과거 데이터로 최적화, 미래 성과 측정
- 성과 지표: 총 수익률, 연환산 수익률, 변동성, 샤프 비율, 최대 낙폭(MDD)
- **자산 곡선 차트** — 전략별 성과 비교 시각화
- 룩백 기간, 리밸런싱 주기 커스터마이징 가능

### 7. AI 토론 (Tab 7)
- **Bull vs Bear 멀티 에이전트 토론** — 강세론자와 약세론자 AI가 3라운드에 걸쳐 토론
  - Round 1: Bull 분석가가 낙관적 시나리오 제시
  - Round 2: Bear 분석가가 비관적 시나리오 제시 + Bull 반박
  - Round 3: 중립 Moderator가 양측 의견 종합, 최종 판정
- 최종 판정: bullish / neutral / bearish + 확신도

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit 대시보드 (7탭)                       │
│  포트폴리오 │ 최적화 │ 뉴스분석 │ 매수가이드 │ 기술분석 │ 백테스팅 │ AI토론 │
└──────────────────────────┬──────────────────────────────────────┘
                            │
┌──────────────────────────▼──────────────────────────────────────┐
│                      Core Engine (Python)                        │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Data Layer   │  │ Optimizer    │  │ AI Agent Module       │  │
│  │              │  │              │  │                       │  │
│  │ • fetcher    │  │ • Max Sharpe │  │ • News Analyzer       │  │
│  │ • news RSS   │  │ • Min Vol    │  │ • Market Analyst      │  │
│  │ • FRED API   │  │ • Black-     │  │ • Fundamental Analyst │  │
│  │ • market_data│  │   Litterman  │  │ • Views Generator     │  │
│  │ • FX rate    │  │ • Backtest   │  │ • Debate (Bull/Bear)  │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬────────────┘  │
│         │                  │                      │              │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌───────────▼───────────┐  │
│  │ yfinance     │  │ PyPortfolio  │  │ Ollama (로컬 LLM)     │  │
│  │ pykrx        │  │ Opt          │  │ • llama3.1:8b (Light) │  │
│  │ FRED API     │  │              │  │ • qwen3.5:27b (Heavy) │  │
│  │ Google RSS   │  │              │  │                       │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                            │
┌──────────────────────────▼──────────────────────────────────────┐
│                      Data Storage                                │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │ SQLite (stock_agent.db)                                   │   │
│  │ • portfolio_holdings — 보유 종목                            │   │
│  │ • transactions — 거래 내역                                  │   │
│  │ • optimization_history — 최적화 결과                        │   │
│  │ • analysis_reports — AI 리포트                              │   │
│  │ • portfolio_snapshots — 일별 성과 스냅샷                     │   │
│  │ • sentiment_history — 감성 분석 이력                         │   │
│  └───────────────────────────────────────────────────────────┘   │
│  ┌───────────────┐                                               │
│  │ JSON Cache    │ — 시세/뉴스/환율 캐시 (6시간 만료)              │
│  └───────────────┘                                               │
└──────────────────────────────────────────────────────────────────┘
```

---

## 스마트 모델 라우팅

모든 LLM 호출은 100% 로컬(Ollama)로 처리되며, **태스크 복잡도에 따라 자동으로 모델이 선택**됩니다.

| 태스크 | 모델 | 크기 | 응답 속도 | 선택 이유 |
|--------|------|------|-----------|-----------|
| 뉴스 감성 분석 (JSON) | `llama3.1:8b` | 4.9GB | ~2초 | 정형 JSON 출력, 단순 분류 |
| BL 뷰 생성 (JSON) | `llama3.1:8b` | 4.9GB | ~2초 | 숫자 기대수익률 추정 |
| 종합 투자 리포트 | `qwen3.5:27b` | 17GB | ~15초 | 다중 데이터 종합, 한국어 서술 |
| 펀더멘탈 분석 | `qwen3.5:27b` | 17GB | ~15초 | 재무제표 해석, 밸류에이션 판단 |
| Bull/Bear 토론 (3라운드) | `qwen3.5:27b` | 17GB | ~45초 | 복합 추론, 논증 |

**설계 원칙**: JSON 분류/추출 → 경량 모델 (빠름) / 서술형 분석·종합 추론 → 고성능 모델 (정확함)

---

## 프로젝트 구조

```
stock-agent/
├── app.py                          # Streamlit 메인 앱 (7탭 대시보드)
├── config.py                       # 환경변수, LLM 설정, DB 경로
├── main.py                         # 엔트리포인트 (stub)
├── pyproject.toml                  # 의존성 관리 (uv)
├── .env.example                    # 환경변수 템플릿
│
├── agent/                          # AI 에이전트 모듈
│   ├── llm_client.py              # Ollama LLM 클라이언트 (듀얼 모델 라우팅)
│   ├── news_analyzer.py           # 뉴스 감성 분석 (light 모델)
│   ├── market_analyst.py          # 종합 투자 리포트 생성 (heavy 모델)
│   ├── fundamental_analyst.py     # 재무제표 펀더멘탈 분석 (heavy 모델)
│   ├── views_generator.py         # Black-Litterman 뷰 생성 (light 모델)
│   ├── debate.py                  # Bull vs Bear 멀티에이전트 토론 (heavy 모델)
│   └── report_generator.py        # 리포트 저장/조회 (SQLite)
│
├── analysis/                       # 분석 엔진
│   ├── technical.py               # 기술적 분석 (RSI, MACD, BB, MA)
│   └── backtest.py                # 전략 백테스팅 (Walk-forward)
│
├── portfolio/                      # 포트폴리오 관리
│   ├── manager.py                 # CRUD (종목 추가/삭제/조회)
│   ├── optimizer.py               # 최적화 엔진 (Max Sharpe, Min Vol, BL)
│   ├── allocator.py               # 예산 배분 & 매수 가이드
│   └── tracker.py                 # 성과 추적 (일별 스냅샷)
│
├── data/                           # 데이터 수집
│   ├── fetcher.py                 # 주가 데이터 (yfinance, pykrx)
│   ├── news_fetcher.py            # 뉴스 수집 (Google News RSS)
│   ├── economic_data.py           # 거시경제 지표 (FRED API)
│   └── market_data.py             # 시세 가공 (수익률, 변동성, 상관관계)
│
├── db/                             # 데이터베이스
│   ├── database.py                # SQLite 초기화 & 연결 (6개 테이블)
│   └── models.py                  # 데이터 모델 (dataclass)
│
├── utils/                          # 유틸리티
│   ├── fx.py                      # USD/KRW 환율 변환
│   ├── helpers.py                 # 캐시 관리, 포매팅
│   └── constants.py               # 상수 (리스크 레벨, FRED 지표 ID)
│
└── data/                           # 데이터 저장 (자동 생성)
    ├── stock_agent.db             # SQLite 데이터베이스
    └── cache/                     # JSON 캐시 파일
```

---

## 기술 스택

| 구분 | 기술 | 용도 |
|------|------|------|
| **UI** | Streamlit | 대시보드, 사용자 입력, 차트 시각화 |
| **언어** | Python 3.11+ | 전체 백엔드 |
| **LLM** | Ollama (로컬) | 뉴스 분석, 리포트 생성, 토론 — **과금 없음** |
| **LLM SDK** | OpenAI Python SDK | Ollama OpenAI 호환 API 연동 |
| **최적화** | PyPortfolioOpt | Mean-Variance, Black-Litterman, 이산 배분 |
| **차트** | Plotly | 인터랙티브 차트 (서브플롯, 파이차트, 라인차트) |
| **주가 (미국)** | yfinance | NYSE/NASDAQ/ETF 시세, 재무제표 |
| **주가 (한국)** | pykrx | 코스피/코스닥 시세 |
| **뉴스** | feedparser | Google News RSS 파싱 |
| **경제지표** | fredapi | FRED 거시경제 데이터 |
| **DB** | SQLite | 포트폴리오, 리포트, 스냅샷, 감성 이력 |
| **패키지 관리** | uv | 의존성 관리 & 가상환경 |

---

## 설치 및 실행

### 사전 요구사항

- **Python 3.11+**
- **Ollama** — https://ollama.com 에서 설치
- **uv** — `pip install uv` 또는 `curl -LsSf https://astral.sh/uv/install.sh | sh`

### 1. Ollama 모델 준비

```bash
ollama pull llama3.1:8b      # Light 모델 (뉴스 분석, JSON 추출)
ollama pull qwen3.5:27b      # Heavy 모델 (종합 리포트, 토론)
```

### 2. 프로젝트 설치

```bash
git clone https://github.com/leeje008/stock-agent.git
cd stock-agent
uv sync
```

### 3. 환경 변수 설정 (선택)

```bash
cp .env.example .env
# 필요시 .env 파일을 열어 API 키 입력
```

> **참고**: `.env` 파일 없이도 앱의 모든 핵심 기능이 동작합니다.
> FRED API 키가 있으면 거시경제 지표 기능이 추가로 활성화됩니다.

### 4. 실행

```bash
ollama serve          # Ollama 서버 시작 (이미 실행 중이면 생략)
uv run streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속

---

## 환경 변수

| 변수 | 기본값 | 설명 | 필수 |
|------|--------|------|------|
| `LLM_BASE_URL` | `http://localhost:11434/v1` | Ollama API 주소 | 아니오 (기본값 사용) |
| `LLM_API_KEY` | `ollama` | Ollama는 인증 불필요 | 아니오 |
| `LLM_MODEL_LIGHT` | `llama3.1:8b` | 경량 태스크용 모델 | 아니오 |
| `LLM_MODEL_HEAVY` | `qwen3.5:27b` | 고성능 태스크용 모델 | 아니오 |
| `FRED_API_KEY` | — | FRED 거시경제 지표 | 아니오 (없으면 경제지표 기능 비활성) |
| `DART_API_KEY` | — | DART 기업 공시 | 아니오 (향후 사용 예정) |
| `BOK_API_KEY` | — | 한국은행 경제지표 | 아니오 (향후 사용 예정) |

---

## 데이터베이스 스키마

앱 최초 실행 시 `data/stock_agent.db`에 SQLite 데이터베이스가 자동 생성됩니다.

| 테이블 | 용도 | 주요 컬럼 |
|--------|------|-----------|
| `portfolio_holdings` | 보유 종목 | ticker, market, name, quantity, avg_price, currency, sector |
| `transactions` | 거래 내역 | ticker, action(BUY/SELL), quantity, price |
| `optimization_history` | 최적화 이력 | strategy, weights_json, expected_return, volatility, sharpe_ratio |
| `analysis_reports` | AI 리포트 | report_type, content, metadata_json |
| `portfolio_snapshots` | 성과 스냅샷 | date(UNIQUE), total_value, total_cost, holdings_json |
| `sentiment_history` | 감성 분석 이력 | date, market_sentiment, sentiment_score, summary |

---

## 사용 예시

### 기본 워크플로우

1. **사이드바에서 종목 추가** — 티커, 시장(US/KR/ETF), 수량, 매입가 입력
2. **Tab 1: 포트폴리오 확인** — 환율 적용된 평가금액, 손익 확인
3. **Tab 2: 최적화 실행** — 전략 선택 후 최적 비중 및 효율적 프론티어 확인
4. **Tab 3: 뉴스 분석** — 실제 뉴스 수집 + AI 감성 분석 실행
5. **Tab 4: AI 리포트** — 모든 분석 결과를 종합한 투자 추천 리포트 생성
6. **Tab 5: 기술적 분석** — 개별 종목의 RSI, MACD, BB 차트 확인
7. **Tab 6: 백테스팅** — 최적화 전략의 과거 성과 검증
8. **Tab 7: AI 토론** — Bull/Bear 관점의 균형 잡힌 투자 의견 확인

### 예시 포트폴리오

| 티커 | 시장 | 종목명 | 섹터 |
|------|------|--------|------|
| AAPL | US | Apple Inc. | Technology |
| MSFT | US | Microsoft | Technology |
| 005930 | KR | 삼성전자 | Semiconductor |
| QQQ | ETF | Invesco QQQ | ETF |

---

## 비용 정책

**모든 기능 100% 무료로 운영됩니다.**

| 항목 | 비용 | 방식 |
|------|------|------|
| LLM (AI 분석) | **무료** | Ollama 로컬 실행 |
| 주가 데이터 | **무료** | yfinance, pykrx |
| 뉴스 수집 | **무료** | Google News RSS |
| 경제 지표 | **무료** | FRED API (무료 키 발급) |
| 데이터 저장 | **무료** | SQLite 로컬 파일 |

---

## 면책 조항

본 앱은 **개인 참고용 도구**로만 사용해야 합니다.

- AI가 생성한 투자 추천은 금융 자문(financial advice)이 아닙니다
- 최종 투자 결정의 책임은 사용자에게 있습니다
- 투자에는 원금 손실 위험이 있습니다
- 이 앱을 타인에게 유료로 제공하면 자본시장법상 투자자문업 등록 의무가 발생할 수 있습니다

---

## 향후 개발 계획

- [ ] RAG 기반 심층 분석 — ChromaDB + 임베딩 모델(`nomic-embed-text`)로 과거 뉴스 검색 기반 분석
- [ ] 섹터 로테이션 전략 — 경기순환 분석 + 섹터별 투자 강도 히트맵
- [ ] PDF 리포트 내보내기 — Markdown → PDF 변환
- [ ] 증권사 API 연동 — 한국투자증권 OpenAPI를 통한 실계좌 조회/주문
- [ ] Telegram/이메일 알림 — 리밸런싱 시점 자동 알림
- [ ] 한국 기업 공시 연동 — DART API를 통한 한국 기업 재무제표/공시 분석

---

## 라이선스

이 프로젝트는 개인 학습 및 투자 참고 목적으로 개발되었습니다.
