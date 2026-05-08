"""Parse EUR-Lex HTML into article and Annex III chunks."""
from dataclasses import dataclass
from pathlib import Path
import re
from bs4 import BeautifulSoup


@dataclass
class Chunk:
    id: str        # e.g. "article-9", "annex-iii-5a"
    type: str      # "article" | "annex_point"
    number: str    # "9", "5(a)", etc.
    title: str     # human-readable title
    text: str      # full text body


def fetch_html(url: str, dest: Path) -> None:
    """Check that the HTML file exists; raise a clear error if not."""
    if dest.exists() and dest.stat().st_size > 10_000:
        return
    raise FileNotFoundError(
        f"AI Act HTML not found at: {dest}\n"
        f"Download it manually from: {url}\n"
        "Save as data/ai_act.html (right-click → Save Page As → Webpage, HTML Only). "
        "File should be ~3-4 MB."
    )


def _get_text(tag) -> str:
    """Extract clean text from a BS4 tag."""
    return tag.get_text(" ", strip=True)


def _find_body(soup: BeautifulSoup) -> BeautifulSoup:
    """Return the content div or fall back to body."""
    # EUR-Lex wraps content in a div with class containing "doc-content" or similar
    for selector in ["div.doc-content", "div#TexteOnly", "body"]:
        node = soup.select_one(selector)
        if node:
            return node
    return soup


def parse_articles(html: str) -> list[Chunk]:
    """Extract all articles from EUR-Lex OJ HTML."""
    soup = BeautifulSoup(html, "lxml")
    body = _find_body(soup)
    chunks: list[Chunk] = []

    # EUR-Lex OJ HTML marks articles with <p class="oj-ti-art"> containing "Article N"
    # followed by optional <p class="oj-sti-art"> for the title, then body paragraphs.
    # We walk all block elements and accumulate text between article markers.
    art_pattern = re.compile(r"Article\s+(\d+)", re.IGNORECASE)

    # Collect all relevant block-level tags in document order
    blocks = body.find_all(["p", "div", "h1", "h2", "h3", "h4", "table"])

    current_num: str | None = None
    current_title: str = ""
    current_lines: list[str] = []

    # Classes that carry article body text in EUR-Lex OJ format
    body_classes = {
        "oj-normal", "oj-list-para", "oj-list-para-1", "norm",
        "oj-ti-grseq-1", "oj-sti-grseq-1", "oj-txt-grseq-1", "oj-sti-art",
    }
    # Classes that mark a new article (article number header)
    art_header_classes = {"oj-ti-art", "ti-art"}

    def _flush(num, title, lines):
        text = "\n".join(lines).strip()
        if text and num:
            chunks.append(Chunk(
                id=f"article-{num}",
                type="article",
                number=num,
                title=title or f"Article {num}",
                text=text,
            ))

    for tag in blocks:
        classes = set(tag.get("class") or [])
        text = _get_text(tag)
        if not text:
            continue

        # Detect article header
        if classes & art_header_classes or (
            "oj-ti-art" in " ".join(classes)  # substring match for variants
        ):
            m = art_pattern.search(text)
            if m:
                _flush(current_num, current_title, current_lines)
                current_num = m.group(1)
                current_title = ""
                current_lines = []
                continue

        if current_num is None:
            continue  # skip preamble content before first article

        # Article title (subtitle line immediately after article header)
        if classes & {"oj-sti-art", "sti-art"} and not current_lines:
            current_title = text
            continue

        # Body text — accept any oj-* paragraph class OR plain <p> inside article
        if classes & body_classes or (tag.name == "p" and not classes):
            current_lines.append(text)
        elif "oj-" in " ".join(classes):
            current_lines.append(text)

    _flush(current_num, current_title, current_lines)
    return chunks


def parse_annex_iii(html: str) -> list[Chunk]:
    """Extract Annex III (high-risk AI systems) points."""
    soup = BeautifulSoup(html, "lxml")
    body = _find_body(soup)
    chunks: list[Chunk] = []

    blocks = body.find_all(["p", "div", "h1", "h2", "h3", "h4"])
    in_annex_iii = False

    # Pattern for numbered points like "1.", "2.", or "(a)", "(b)"
    point_pattern = re.compile(r"^(\d+)\.\s*(.*)")
    subpoint_pattern = re.compile(r"^\(([a-z])\)\s*(.*)")

    current_num: str | None = None
    current_title: str = ""
    current_lines: list[str] = []

    def _flush_annex(num, title, lines):
        text = "\n".join(lines).strip()
        if text and num:
            safe_num = num.replace("(", "").replace(")", "")
            chunks.append(Chunk(
                id=f"annex-iii-{safe_num}",
                type="annex_point",
                number=num,
                title=title or f"Annex III, point {num}",
                text=text,
            ))

    for tag in blocks:
        classes = set(tag.get("class") or [])
        text = _get_text(tag)
        if not text:
            continue

        # Detect entry into Annex III
        if not in_annex_iii:
            if re.search(r"ANNEX\s+III", text, re.IGNORECASE):
                in_annex_iii = True
            continue

        # Detect exit from Annex III (next annex)
        if re.search(r"ANNEX\s+IV", text, re.IGNORECASE):
            break

        # Parse numbered top-level points (e.g. "1. Biometric identification...")
        m = point_pattern.match(text)
        if m:
            _flush_annex(current_num, current_title, current_lines)
            current_num = m.group(1)
            current_title = m.group(2).strip()
            current_lines = [text]
            continue

        # Parse sub-points (e.g. "(a) AI systems...")
        m = subpoint_pattern.match(text)
        if m and current_num:
            _flush_annex(current_num, current_title, current_lines)
            letter = m.group(1)
            current_num = f"{current_num}({letter})" if current_num and not current_num.endswith(")") else f"({letter})"
            current_title = m.group(2).strip()
            current_lines = [text]
            continue

        if current_num:
            current_lines.append(text)

    _flush_annex(current_num, current_title, current_lines)
    return chunks


def parse_all(html_path: Path) -> list[Chunk]:
    """Return articles + Annex III points combined."""
    html = html_path.read_text(encoding="utf-8", errors="replace")
    articles = parse_articles(html)
    annex = parse_annex_iii(html)
    return articles + annex
