"""
main.py — EchoBreaker CLI 메인 실행 파일
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

from article_fetcher import fetch_article
from keyword_extractor import extract_keywords
from perspective_analyzer import (
    analyze_perspective,
    get_perspective_label
)
from news_searcher import search_counter_perspectives
import reporter


def validate_environment() -> bool:
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        reporter.print_error(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다.\n"
            "   1. cp .env.example .env\n"
            "   2. .env 파일에 API 키를 입력하세요\n"
            "   3. API 키 발급: https://console.anthropic.com/"
        )
        return False

    if api_key == "your_anthropic_api_key_here":
        reporter.print_error(
            ".env 파일에 실제 API 키를 입력해주세요.\n"
            "   현재 예시 키(your_anthropic_api_key_here)가 입력되어 있습니다."
        )
        return False

    return True


def get_url_from_user() -> str:
    print("\n분석할 뉴스 기사의 URL을 입력하세요:")
    print("(예: https://www.hani.co.kr/arti/economy/...)")
    print()

    while True:
        try:
            url = input("  > ").strip()

            if not url:
                reporter.print_warning("URL을 입력해주세요.")
                continue

            if not (url.startswith("http://") or url.startswith("https://")):
                reporter.print_warning("http:// 또는 https://로 시작하는 URL을 입력해주세요.")
                continue

            return url

        except KeyboardInterrupt:
            print("\n\n프로그램을 종료합니다. 다음에 또 사용해주세요! 👋")
            sys.exit(0)


def run_pipeline(url: str):
    # 기 (起): 기사 본문 가져오기
    reporter.print_step(1, "기사를 불러오는 중...")
    reporter.print_loading("URL에 접속하여 본문을 추출합니다")

    article = fetch_article(url)

    if not article.success:
        reporter.print_error(f"기사를 불러올 수 없습니다: {article.error_message}")
        reporter.print_warning("일부 언론사는 스크래핑을 차단합니다.")
        return

    reporter.print_success(f"기사 추출 완료: {article.title[:40]}...")

    # 승 (承): 핵심 키워드 추출
    reporter.print_step(2, "핵심 키워드를 추출하는 중...")
    reporter.print_loading("Claude AI가 기사의 핵심 개념을 파악합니다")

    keywords_result = extract_keywords(
        article_title=article.title,
        article_text=article.text
    )

    if not keywords_result.success:
        reporter.print_error(f"키워드 추출 실패: {keywords_result.error_message}")
        return

    reporter.print_success(f"키워드 추출 완료: {', '.join(keywords_result.keywords)}")

    # 전 (轉): 관점 분석 + 반대 기사 검색
    reporter.print_step(3, "기사의 관점을 분석하는 중...")
    reporter.print_loading("논조, 정치적 성향, 프레이밍을 분석합니다")

    perspective = analyze_perspective(
        article_title=article.title,
        article_text=article.text,
        main_topic=keywords_result.main_topic,
        keywords=keywords_result.keywords
    )

    if not perspective.success:
        reporter.print_warning(f"관점 분석 일부 실패: {perspective.error_message}")
    else:
        reporter.print_success("관점 분석 완료")

    perspective_label = get_perspective_label(perspective)

    reporter.print_step(4, "반대 관점 기사를 검색하는 중...")
    reporter.print_loading("다른 시각의 뉴스 기사를 실시간으로 검색합니다 (10~30초 소요)")

    search_result = search_counter_perspectives(
        main_topic=keywords_result.main_topic,
        keywords=keywords_result.keywords,
        search_queries=keywords_result.search_queries,
        original_perspective_summary=perspective.perspective_summary,
        opposite_perspective=perspective.opposite_perspective
    )

    if not search_result.success and not search_result.articles:
        reporter.print_warning(f"기사 검색 실패: {search_result.error_message}")

    # 결 (結): 분석 결과 출력
    print("\n\n")

    reporter.print_original_article(
        title=article.title,
        domain=article.source_domain,
        main_topic=keywords_result.main_topic,
        keywords=keywords_result.keywords,
        perspective_label=perspective_label,
        perspective_summary=perspective.perspective_summary,
        key_framing=perspective.key_framing
    )

    reporter.print_recommendations(search_result.articles)
    reporter.print_echo_chamber_tip()


def ask_to_continue() -> bool:
    print("\n다른 기사를 분석하시겠습니까? (y/n): ", end="")
    try:
        answer = input().strip().lower()
        return answer in ("y", "yes", "예", "ㅇ")
    except KeyboardInterrupt:
        return False


def main():
    reporter.print_banner()

    if not validate_environment():
        sys.exit(1)

    while True:
        url = get_url_from_user()
        run_pipeline(url)

        if not ask_to_continue():
            print("\n프로그램을 종료합니다. 균형 잡힌 뉴스 읽기를 응원합니다! 👋\n")
            break
"""
article_fetcher.py — 뉴스 기사 URL에서 본문을 가져오는 모듈
"""

import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional
import os
import re

try:
    from newspaper import Article
    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False


@dataclass
class FetchedArticle:
    url: str
    title: str
    text: str
    source_domain: str
    success: bool
    error_message: Optional[str] = None


def fetch_article(url: str, timeout: int = None) -> FetchedArticle:
    if timeout is None:
        timeout = int(os.getenv("REQUEST_TIMEOUT", 15))

    source_domain = _extract_domain(url)

    if NEWSPAPER_AVAILABLE:
        result = _fetch_with_newspaper(url, source_domain, timeout)
        if result.success and len(result.text) > 200:
            return result

    return _fetch_with_beautifulsoup(url, source_domain, timeout)


def _fetch_with_newspaper(url: str, domain: str, timeout: int) -> FetchedArticle:
    try:
        article = Article(url, language='ko')
        article.download()
        article.parse()

        if not article.title or not article.text:
            return FetchedArticle(
                url=url, title="", text="", source_domain=domain,
                success=False, error_message="newspaper3k: 제목 또는 본문 추출 실패"
            )

        return FetchedArticle(
            url=url,
            title=article.title.strip(),
            text=_clean_text(article.text),
            source_domain=domain,
            success=True
        )

    except Exception as e:
        return FetchedArticle(
            url=url, title="", text="", source_domain=domain,
            success=False, error_message=f"newspaper3k 오류: {str(e)}"
        )


def _fetch_with_beautifulsoup(url: str, domain: str, timeout: int) -> FetchedArticle:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        response.encoding = response.apparent_encoding

        soup = BeautifulSoup(response.text, "lxml")
        title = _extract_title(soup)
        text = _extract_body_text(soup)

        if not text or len(text) < 100:
            return FetchedArticle(
                url=url, title=title, text="", source_domain=domain,
                success=False, error_message="본문 추출 실패: 텍스트가 너무 짧습니다"
            )

        return FetchedArticle(
            url=url,
            title=title,
            text=_clean_text(text),
            source_domain=domain,
            success=True
        )

    except requests.exceptions.Timeout:
        return FetchedArticle(
            url=url, title="", text="", source_domain=domain,
            success=False, error_message=f"요청 시간 초과 ({timeout}초)"
        )
    except requests.exceptions.ConnectionError:
        return FetchedArticle(
            url=url, title="", text="", source_domain=domain,
            success=False, error_message="연결 오류: URL을 확인해주세요"
        )
    except Exception as e:
        return FetchedArticle(
            url=url, title="", text="", source_domain=domain,
            success=False, error_message=f"알 수 없는 오류: {str(e)}"
        )


def _extract_title(soup: BeautifulSoup) -> str:
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()

    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)

    title_tag = soup.find("title")
    if title_tag:
        return title_tag.get_text(strip=True)

    return "제목 없음"


def _extract_body_text(soup: BeautifulSoup) -> str:
    body_selectors = [
        "div.article-text", "div.article-body-ct",
        "div#article-body", "div.article_body",
        "div#article_body", "div.article_body_content",
        "div.article_txt",
        "div.article", "article.story-news",
        "div.art_body",
        "div.detail-body",
        "div.news_txt",
        "div.text_area",
        "article", "div.content", "div.article-content",
        "div#content", "main",
    ]

    for selector in body_selectors:
        element = soup.select_one(selector)
        if element:
            for tag in element.find_all(["script", "style", "aside", "figure"]):
                tag.decompose()
            text = element.get_text(separator="\n", strip=True)
            if len(text) > 100:
                return text

    return ""


def _extract_domain(url: str) -> str:
    try:
        domain = url.split("//")[-1].split("/")[0]
        domain = domain.replace("www.", "")
        return domain
    except Exception:
        return "알 수 없음"


def _clean_text(text: str) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)

    ad_patterns = [
        r'구독\s*신청.*?\n',
        r'▶.*?\n',
        r'☞.*?\n',
        r'Copyright.*?\n',
        r'무단\s*전재.*?금지\s*\n',
        r'기자\s+\S+@\S+\.\S+',
    ]
    for pattern in ad_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    return text.strip()
  """
keyword_extractor.py — 기사 본문에서 핵심 키워드를 추출하는 모듈
"""

import anthropic
import json
import os
from dataclasses import dataclass
from typing import List


@dataclass
class ExtractedKeywords:
    main_topic: str
    keywords: List[str]
    search_queries: List[str]
    success: bool
    error_message: str = ""


def extract_keywords(article_title: str, article_text: str) -> ExtractedKeywords:
    client = anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )

    text_snippet = article_text[:2000] if len(article_text) > 2000 else article_text

    prompt = f"""다음 뉴스 기사를 분석하여 핵심 정보를 추출해주세요.

[기사 제목]
{article_title}

[기사 본문 일부]
{text_snippet}

아래 JSON 형식으로만 응답해주세요. 설명이나 마크다운 없이 순수 JSON만 출력하세요:

{{
  "main_topic": "기사의 핵심 주제를 한 문장으로",
  "keywords": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"],
  "search_queries": [
    "반대 관점 검색에 사용할 쿼리 1",
    "반대 관점 검색에 사용할 쿼리 2",
    "중립적 시각 검색 쿼리"
  ]
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text.strip()
        response_text = _strip_json_fences(response_text)
        data = json.loads(response_text)

        return ExtractedKeywords(
            main_topic=data.get("main_topic", "주제 불명"),
            keywords=data.get("keywords", [])[:5],
            search_queries=data.get("search_queries", [])[:3],
            success=True
        )

    except json.JSONDecodeError as e:
        return ExtractedKeywords(
            main_topic="", keywords=[], search_queries=[],
            success=False, error_message=f"JSON 파싱 실패: {str(e)}"
        )
    except anthropic.AuthenticationError:
        return ExtractedKeywords(
            main_topic="", keywords=[], search_queries=[],
            success=False,
            error_message="API 키 인증 실패: .env 파일의 ANTHROPIC_API_KEY를 확인하세요"
        )
    except Exception as e:
        return ExtractedKeywords(
            main_topic="", keywords=[], search_queries=[],
            success=False, error_message=f"키워드 추출 오류: {str(e)}"
        )


def _strip_json_fences(text: str) -> str:
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()

if __name__ == "__main__":
    main()
  """
perspective_analyzer.py — 기사의 관점/논조를 분석하는 모듈
"""

import anthropic
import json
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class PerspectiveAnalysis:
    political_lean: str
    stance_on_topic: str
    tone: str
    perspective_summary: str
    opposite_perspective: str
    key_framing: str
    success: bool
    error_message: str = ""


LEAN_EMOJI = {
    "진보": "🔵",
    "중도": "⚪",
    "보수": "🔴",
    "불명확": "❓"
}

STANCE_EMOJI = {
    "찬성": "✅",
    "반대": "❌",
    "중립": "⚖️",
    "혼합": "↔️"
}


def analyze_perspective(
    article_title: str,
    article_text: str,
    main_topic: str,
    keywords: list
) -> PerspectiveAnalysis:
    client = anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )

    text_snippet = article_text[:3000] if len(article_text) > 3000 else article_text
    keywords_str = ", ".join(keywords)

    prompt = f"""다음 뉴스 기사의 관점, 논조, 프레이밍을 정밀하게 분석해주세요.

[기사 제목]
{article_title}

[핵심 주제]
{main_topic}

[주요 키워드]
{keywords_str}

[기사 본문]
{text_snippet}

아래 JSON 형식으로만 응답하세요. 마크다운 없이 순수 JSON만:

{{
  "political_lean": "진보 | 중도 | 보수 | 불명확 중 하나만",
  "stance_on_topic": "찬성 | 반대 | 중립 | 혼합 중 하나만",
  "tone": "긍정적 | 부정적 | 중립적 | 분석적 중 하나만",
  "perspective_summary": "이 기사의 관점을 한 문장으로",
  "opposite_perspective": "반대 관점을 한 문장으로",
  "key_framing": "기사가 이 사안을 어떤 틀로 보는지"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text.strip()
        response_text = _strip_json_fences(response_text)
        data = json.loads(response_text)

        return PerspectiveAnalysis(
            political_lean=data.get("political_lean", "불명확"),
            stance_on_topic=data.get("stance_on_topic", "중립"),
            tone=data.get("tone", "중립적"),
            perspective_summary=data.get("perspective_summary", ""),
            opposite_perspective=data.get("opposite_perspective", ""),
            key_framing=data.get("key_framing", ""),
            success=True
        )

    except json.JSONDecodeError as e:
        return PerspectiveAnalysis(
            political_lean="불명확", stance_on_topic="중립", tone="중립적",
            perspective_summary="", opposite_perspective="", key_framing="",
            success=False, error_message=f"JSON 파싱 실패: {str(e)}"
        )
    except Exception as e:
        return PerspectiveAnalysis(
            political_lean="불명확", stance_on_topic="중립", tone="중립적",
            perspective_summary="", opposite_perspective="", key_framing="",
            success=False, error_message=f"관점 분석 오류: {str(e)}"
        )


def get_perspective_label(analysis: PerspectiveAnalysis) -> str:
    lean_emoji = LEAN_EMOJI.get(analysis.political_lean, "❓")
    stance_emoji = STANCE_EMOJI.get(analysis.stance_on_topic, "⚖️")

    return (
        f"{lean_emoji} {analysis.political_lean} 성향 "
        f"| {stance_emoji} {analysis.stance_on_topic} 입장 "
        f"| 논조: {analysis.tone}"
    )


def _strip_json_fences(text: str) -> str:
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()
  """
news_searcher.py — 반대/대안 관점의 뉴스 기사를 검색하는 모듈
"""

import anthropic
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RecommendedArticle:
    title: str
    url: str
    source_name: str
    perspective_label: str
    summary: str
    why_recommended: str


@dataclass
class SearchResult:
    articles: List[RecommendedArticle]
    success: bool
    error_message: str = ""


def search_counter_perspectives(
    main_topic: str,
    keywords: List[str],
    search_queries: List[str],
    original_perspective_summary: str,
    opposite_perspective: str,
    max_results: int = None
) -> SearchResult:
    if max_results is None:
        max_results = int(os.getenv("MAX_RECOMMENDATIONS", 3))

    client = anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )

    keywords_str = ", ".join(keywords)
    queries_str = "\n".join(f"- {q}" for q in search_queries)

    prompt = f"""당신은 미디어 리터러시 전문가입니다. 다음 뉴스 기사와 반대되는 관점의 실제 뉴스 기사를 웹에서 검색해주세요.

[원본 기사 정보]
- 주제: {main_topic}
- 키워드: {keywords_str}
- 원본 관점: {original_perspective_summary}
- 찾아야 할 반대 관점: {opposite_perspective}

[검색 시 사용할 쿼리들]
{queries_str}

지시사항:
1. 위 검색 쿼리들을 사용해 반대/대안 관점의 실제 뉴스 기사를 {max_results}개 검색하세요
2. 반드시 실제로 존재하는 기사 URL만 포함하세요
3. 주요 한국 언론사의 기사를 우선 검색하세요

검색 후 아래 JSON 형식으로만 응답하세요:

{{
  "articles": [
    {{
      "title": "기사 제목",
      "url": "https://실제기사URL",
      "source_name": "언론사명",
      "perspective_label": "관점 레이블",
      "summary": "기사 내용 2-3문장 요약",
      "why_recommended": "이 기사를 읽어야 하는 이유 1문장"
    }}
  ]
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            tools=[
                {
                    "type": "web_search_20250305",
                    "name": "web_search"
                }
            ],
            messages=[{"role": "user", "content": prompt}]
        )

        full_text = ""
        for block in response.content:
            if block.type == "text":
                full_text += block.text

        if not full_text.strip():
            return SearchResult(
                articles=[], success=False,
                error_message="AI 응답에서 텍스트를 찾을 수 없습니다"
            )

        clean_text = _strip_json_fences(full_text.strip())
        data = json.loads(clean_text)

        articles = []
        for item in data.get("articles", []):
            articles.append(RecommendedArticle(
                title=item.get("title", "제목 없음"),
                url=item.get("url", ""),
                source_name=item.get("source_name", "출처 불명"),
                perspective_label=item.get("perspective_label", "관점 불명"),
                summary=item.get("summary", ""),
                why_recommended=item.get("why_recommended", "")
            ))

        articles = [a for a in articles if a.url.startswith("http")]

        return SearchResult(articles=articles[:max_results], success=True)

    except json.JSONDecodeError as e:
        fallback = _fallback_extract(full_text if 'full_text' in locals() else "")
        if fallback.articles:
            return fallback
        return SearchResult(
            articles=[], success=False,
            error_message=f"JSON 파싱 실패: {str(e)}"
        )
    except Exception as e:
        return SearchResult(
            articles=[], success=False,
            error_message=f"검색 오류: {str(e)}"
        )


def _fallback_extract(text: str) -> SearchResult:
    import re
    urls = re.findall(r'https?://[^\s\)\]\'"]+', text)
    urls = list(set(urls))

    articles = []
    for url in urls[:3]:
        articles.append(RecommendedArticle(
            title="검색된 기사",
            url=url,
            source_name=url.split("//")[-1].split("/")[0].replace("www.", ""),
            perspective_label="관점 분석 필요",
            summary="직접 기사를 확인해주세요",
            why_recommended="다른 관점의 기사를 직접 확인해보세요"
        ))

    return SearchResult(articles=articles, success=bool(articles))


def _strip_json_fences(text: str) -> str:
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()
  """
reporter.py — 분석 결과를 터미널에 보기 좋게 출력하는 모듈
"""

import colorama
from colorama import Fore, Back, Style
import textwrap
import sys

colorama.init(autoreset=True)

C_TITLE     = Fore.CYAN + Style.BRIGHT
C_LABEL     = Fore.YELLOW
C_VALUE     = Fore.WHITE
C_SUCCESS   = Fore.GREEN
C_WARNING   = Fore.YELLOW + Style.BRIGHT
C_ERROR     = Fore.RED + Style.BRIGHT
C_DIVIDER   = Fore.WHITE + Style.DIM
C_HIGHLIGHT = Fore.MAGENTA
C_RESET     = Style.RESET_ALL


def print_banner():
    banner = f"""
{C_TITLE}╔══════════════════════════════════════════════╗
║                                              ║
║    🔍  EchoBreaker - 에코체임버 탈출기         ║
║    확증편향을 깨고 균형 잡힌 시각을 찾아드립니다  ║
║                                              ║
╚══════════════════════════════════════════════╝{C_RESET}
"""
    print(banner)


def print_step(step_num: int, message: str):
    steps = {1: "🌐", 2: "🔑", 3: "🧭", 4: "🔍"}
    emoji = steps.get(step_num, "⚙️")
    print(f"\n{C_LABEL}[{step_num}/4] {emoji} {message}{C_RESET}")


def print_original_article(title, domain, main_topic, keywords,
                            perspective_label, perspective_summary, key_framing):
    print(f"\n{C_TITLE}{'─' * 50}")
    print(f"  📰  원본 기사 분석 결과")
    print(f"{'─' * 50}{C_RESET}")

    wrapped_title = textwrap.fill(title, width=60, subsequent_indent="          ")
    print(f"  {C_LABEL}제목{C_RESET}   : {C_VALUE}{wrapped_title}{C_RESET}")
    print(f"  {C_LABEL}언론사{C_RESET} : {C_VALUE}{domain}{C_RESET}")

    wrapped_topic = textwrap.fill(main_topic, width=55, subsequent_indent="          ")
    print(f"  {C_LABEL}주제{C_RESET}   : {C_VALUE}{wrapped_topic}{C_RESET}")

    keywords_display = "  ".join(f"[{kw}]" for kw in keywords)
    print(f"  {C_LABEL}키워드{C_RESET} : {C_HIGHLIGHT}{keywords_display}{C_RESET}")
    print(f"  {C_LABEL}관점{C_RESET}   : {perspective_label}")

    if perspective_summary:
        wrapped_summary = textwrap.fill(
            perspective_summary, width=55, subsequent_indent="          "
        )
        print(f"  {C_LABEL}요약{C_RESET}   : {C_VALUE}{wrapped_summary}{C_RESET}")

    if key_framing:
        print(f"  {C_LABEL}프레임{C_RESET} : {C_VALUE}{key_framing}{C_RESET}")


def print_recommendations(articles: list):
    print(f"\n{C_SUCCESS}{'═' * 50}")
    print(f"  🔄  균형 잡힌 시각을 위한 추천 기사")
    print(f"{'═' * 50}{C_RESET}")

    if not articles:
        print(f"\n  {C_WARNING}⚠️  반대 관점의 기사를 찾지 못했습니다.")
        print(f"  직접 포털 사이트에서 검색해보세요.{C_RESET}")
        return

    for i, article in enumerate(articles, start=1):
        print(f"\n  {C_TITLE}[{i}] {article.title}{C_RESET}")
        print(f"      {C_LABEL}📰 출처{C_RESET} : {article.source_name}")
        print(f"      {C_LABEL}🔍 관점{C_RESET} : {article.perspective_label}")
        print(f"      {C_LABEL}🔗 링크{C_RESET} : {C_VALUE}{article.url}{C_RESET}")

        if article.summary:
            wrapped = textwrap.fill(
                article.summary, width=55,
                initial_indent="      ",
                subsequent_indent="      "
            )
            print(f"      {C_LABEL}📝 요약{C_RESET} :")
            print(f"{C_VALUE}{wrapped}{C_RESET}")

        if article.why_recommended:
            print(f"      {C_LABEL}💡 추천이유{C_RESET}: {C_HIGHLIGHT}{article.why_recommended}{C_RESET}")

        if i < len(articles):
            print(f"      {C_DIVIDER}{'·' * 40}{C_RESET}")


def print_echo_chamber_tip():
    print(f"\n{C_DIVIDER}{'─' * 50}{C_RESET}")
    print(f"""
{C_HIGHLIGHT}💡 에코체임버 탈출 가이드{C_RESET}

  • 같은 사안을 다른 관점에서 읽으면 더 입체적으로 이해됩니다
  • 동의하지 않는 관점을 읽는 것이 민주주의의 핵심입니다
  • 알고리즘 추천보다 직접 다양한 언론사를 방문해보세요

{C_SUCCESS}EchoBreaker와 함께 균형 잡힌 시각을 키워나가세요! 🌏{C_RESET}
""")


def print_error(message: str):
    print(f"\n{C_ERROR}❌ 오류: {message}{C_RESET}")


def print_warning(message: str):
    print(f"\n{C_WARNING}⚠️  {message}{C_RESET}")


def print_success(message: str):
    print(f"{C_SUCCESS}✅ {message}{C_RESET}")


def print_loading(message: str):
    print(f"   {C_DIVIDER}⏳ {message}...{C_RESET}")
  ANTHROPIC_API_KEY=your_anthropic_api_key_here
REQUEST_TIMEOUT=15
MAX_RECOMMENDATIONS=3
DEBUG=False
anthropic>=0.25.0
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
newspaper3k>=0.2.8
python-dotenv>=1.0.0
colorama>=0.4.6
requests-cache>=1.1.0
