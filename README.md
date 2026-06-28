🔍 EchoBreaker — 확증편향 방지 뉴스 추천기
> \*\*필터 버블(Filter Bubble)을 깨고, 균형 잡힌 시각을 제공합니다.\*\*
알고리즘이 만든 에코체임버에서 벗어나세요.  
읽은 뉴스 기사의 URL을 입력하면, 반대 관점의 기사를 자동으로 찾아드립니다.
---
📌 프로젝트 개요
항목	내용
문제	알고리즘 기반 뉴스 추천이 사용자의 기존 신념을 강화하는 '필터 버블' 현상 심화
해결	읽은 기사의 관점을 분석하고, 반대/대안 관점의 기사를 자동 매칭
기술	Python + Claude AI API + 웹 스크래핑
실행	CLI(터미널) 실행 → 추후 웹앱으로 확장 예정
---
🏗️ 프로젝트 구조
```
echo-breaker/
├── README.md                  # 프로젝트 설명서 (현재 파일)
├── requirements.txt           # Python 패키지 의존성
├── .env.example               # 환경변수 예시 파일
├── .gitignore                 # Git 무시 파일 목록
│
├── src/
│   ├── main.py                # 🚀 메인 실행 파일 (CLI 진입점)
│   ├── article\_fetcher.py     # 기사 URL → 본문 텍스트 추출
│   ├── keyword\_extractor.py   # 본문 → 핵심 키워드 추출 (Claude AI)
│   ├── perspective\_analyzer.py# 기사의 정치적/논조 관점 분석 (Claude AI)
│   ├── news\_searcher.py       # 반대 관점 기사 검색 (Claude AI + 웹 검색)
│   └── reporter.py            # 결과를 사용자에게 보기 좋게 출력
│
├── tests/
│   └── test\_pipeline.py       # 핵심 기능 단위 테스트
│
└── public/                    # 웹앱 확장 시 사용할 정적 파일 (예약)
    └── index.html             # 웹 프론트엔드 (Phase 2)
```
---
⚙️ 설치 및 실행 방법
1. 저장소 클론
```bash
git clone https://github.com/your-username/echo-breaker.git
cd echo-breaker
```
2. Python 가상환경 생성 (권장)
```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\\Scripts\\activate         # Windows
```
3. 패키지 설치
```bash
pip install -r requirements.txt
```
4. 환경변수 설정
```bash
cp .env.example .env
# .env 파일을 열어 ANTHROPIC\_API\_KEY 값을 입력하세요
```
5. 실행
```bash
python src/main.py
```
---
🔑 API 키 발급
Anthropic API Key: https://console.anthropic.com/
Claude AI가 키워드 추출, 관점 분석, 반대 기사 검색에 사용됩니다.
---
💡 사용 예시
```
$ python src/main.py

╔══════════════════════════════════════╗
║     🔍 EchoBreaker - 에코체임버 탈출기    ║
╚══════════════════════════════════════╝

분석할 뉴스 기사 URL을 입력하세요:
> https://www.hani.co.kr/arti/economy/...

⏳ 기사를 분석 중입니다...

📰 원본 기사 분석 결과
───────────────────────
제목   : 최저임금 1만2천원 인상, 소득 불평등 완화 기대
키워드 : 최저임금, 인상, 소득불평등, 저소득층
관점   : 🔵 진보 성향 — 임금 인상 찬성 관점

🔄 균형 잡힌 시각을 위한 추천 기사
───────────────────────────────────
\[1] "최저임금 급격한 인상, 중소기업 고용 악화 우려"
    📰 출처: 조선일보
    🔗 https://...
    💬 관점: 🔴 보수 성향 — 임금 인상 반대 관점

\[2] "최저임금 인상 효과, 업종별로 극명히 엇갈려"
    📰 출처: 한국경제
    🔗 https://...
    💬 관점: ⚪ 중립 — 데이터 중심 분석

💡 에코체임버 탈출 팁: 같은 사안을 다른 관점에서 읽으면
   더 입체적인 판단이 가능합니다.
```
---
🗺️ 개발 로드맵
[x] Phase 1 — CLI 버전 (현재)
URL 입력 → 기사 분석 → 반대 관점 추천
[ ] Phase 2 — 웹앱 버전
Flask/FastAPI 백엔드 + HTML/JS 프론트엔드
분석 히스토리 저장
[ ] Phase 3 — 고도화
북마크 기능, 읽기 목록 편향 분석
크롬 익스텐션 버전
---
🛠️ 기술 스택
역할	기술
언어	Python 3.9+
AI 분석	Anthropic Claude API (`claude-sonnet-4-6`)
웹 스크래핑	`requests`, `BeautifulSoup4`, `newspaper3k`
환경변수	`python-dotenv`
텍스트 처리	`konlpy` (한국어 형태소 분석, 선택)
---
📄 라이선스
MIT License — 자유롭게 사용, 수정, 배포하세요.
---
🤝 기여하기
PR과 이슈는 언제든지 환영합니다!  
새로운 언론사 지원, UI 개선, 버그 수정 등 어떤 기여도 좋습니다.
