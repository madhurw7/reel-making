"""Hacker News capture: current top stories -> downloaded article + ranked comments, saved under
sources/hackernews/<date>-<id>/ so a local model (and later an editor) can work from files, offline.

Nothing here calls a model. Article pages and comments are untrusted text: they are stored and summarised,
never executed or obeyed.
"""
from __future__ import annotations

import html
import io
import json
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

from .config import ROOT, now, write_json

API = "https://hacker-news.firebaseio.com/v0"
SOURCES = ROOT / "sources" / "hackernews"
# A plain browser identity: many sites refuse unknown clients. Carries nothing about the user.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
MAX_BYTES = 8_000_000
THIN = 600                      # fewer characters than this is not an article


def _get(url: str, timeout: float = 30) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/pdf,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(MAX_BYTES), r.headers.get("Content-Type", ""), r.geturl()


def _json(url: str):
    return json.loads(_get(url, timeout=20)[0])


def html_to_text(s: str) -> str:
    """HN comment / self-post HTML -> plain text."""
    s = re.sub(r"<p>|<br\s*/?>", "\n\n", s or "")
    s = re.sub(r"<a\s+href=\"([^\"]+)\"[^>]*>.*?</a>", r"\1", s, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(s)).strip()


def top_stories(count: int) -> list[dict]:
    """The first `count` real stories on the front page, in rank order (job ads and dead items are skipped)."""
    out = []
    for rank, sid in enumerate(_json(f"{API}/topstories.json")[: count * 4], 1):
        item = _json(f"{API}/item/{sid}.json") or {}
        if item.get("type") != "story" or item.get("dead") or item.get("deleted"):
            continue
        item["rank"] = rank
        out.append(item)
        if len(out) == count:
            break
    return out


def _extract_html(page: str, url: str) -> tuple[str, dict]:
    import trafilatura
    # Precise extraction first (drops reader comments, sidebars); the greedy mode only if that finds too little.
    text = trafilatura.extract(page, url=url, include_tables=True, include_comments=False) or ""
    if len(text) < 3000:                                    # short result: the precise mode may have dropped rows
        loose = trafilatura.extract(page, url=url, favor_recall=True, include_tables=True, include_comments=False) or ""
        if len(loose) > len(text) * 1.1:
            text = loose
    meta = {}
    try:
        m = trafilatura.extract_metadata(page, default_url=url)
        if m:
            meta = {k: v for k, v in {"title": m.title, "author": m.author, "date": m.date,
                                      "site": m.sitename}.items() if v}
    except Exception:
        pass
    return text.strip(), meta


def trim_reader_comments(text: str) -> tuple[str, bool]:
    """Blog pages often carry their own reader comments after the article ("321 Comments" ...). Cut them off:
    they are not the article, and they would crowd out the real content in the digest."""
    m = re.search(r"(?im)^\s*\d+\s+(comments|responses|replies)\s*$|^\s*leave a (reply|comment)\s*$", text)
    if m and m.start() >= 800:
        return text[: m.start()].rstrip(), True
    return text, False


def _chrome_dom(url: str) -> str:
    """Rendered DOM via local headless Chrome, for pages that build their text with JavaScript."""
    if not CHROME.exists():
        return ""
    tmp = tempfile.mkdtemp(prefix="reelkit-chrome-")          # throwaway profile: never touches the user's Chrome
    try:
        p = subprocess.run([str(CHROME), "--headless=new", "--disable-gpu", "--no-first-run",
                            f"--user-data-dir={tmp}", f"--user-agent={UA}", "--virtual-time-budget=9000",
                            "--dump-dom", url], capture_output=True, text=True, timeout=60)
        return p.stdout
    except (subprocess.TimeoutExpired, OSError):
        return ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def fetch_article(url: str, dest: Path) -> dict:
    """Download `url` into dest/ (raw file + article.txt). Returns a status record; never raises."""
    info = {"url": url, "status": "failed", "chars": 0, "method": ""}
    try:
        raw, ctype, final = _get(url)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        raw, ctype, final = b"", "", url
        info["error"] = str(e)[:200]
    info.update(final_url=final, content_type=ctype.split(";")[0])
    text, meta = "", {}
    if raw[:5] == b"%PDF-" or "pdf" in ctype:
        (dest / "article.pdf").write_bytes(raw)
        try:
            from pypdf import PdfReader
            pages = PdfReader(io.BytesIO(raw)).pages[:25]
            text = "\n\n".join((pg.extract_text() or "") for pg in pages).strip()
            info["method"] = "pdf"
        except Exception as e:
            info["error"] = f"pdf: {e}"[:200]
    elif raw:
        page = raw.decode("utf-8", errors="replace")
        (dest / "article.html").write_text(page, encoding="utf-8")
        text, meta = _extract_html(page, final)
        info["method"] = "http"
    if len(text) < THIN and "pdf" not in info["method"]:
        dom = _chrome_dom(final or url)
        if dom:
            t2, m2 = _extract_html(dom, final or url)
            if len(t2) > len(text):
                (dest / "article.html").write_text(dom, encoding="utf-8")
                text, meta, info["method"] = t2, m2 or meta, "chrome"
    text, trimmed = trim_reader_comments(text)
    if trimmed:
        info["reader_comments_trimmed"] = True
    (dest / "article.txt").write_text(text, encoding="utf-8")
    info.update(meta)
    info["chars"] = len(text)
    info["status"] = "ok" if len(text) >= THIN else ("thin" if text else "failed")
    return info


def fetch_comments(story: dict, top: int, replies: int) -> list[dict]:
    """The `top` highest-ranked top-level comments, each with its first `replies` replies, in page order."""
    def item(cid):
        try:
            return _json(f"{API}/item/{cid}.json") or {}
        except Exception:
            return {}

    with ThreadPoolExecutor(8) as pool:
        tops = [c for c in pool.map(item, (story.get("kids") or [])[: top + 6])
                if c.get("text") and not c.get("dead") and not c.get("deleted")][:top]
        kid_ids = [k for c in tops for k in (c.get("kids") or [])[:replies]]
        kids = {c["id"]: c for c in pool.map(item, kid_ids)
                if c.get("text") and not c.get("dead") and not c.get("deleted")}
    out = []
    for rank, c in enumerate(tops, 1):
        out.append({"id": c["id"], "by": c.get("by", ""), "rank": rank, "depth": 0, "parent": story["id"],
                    "text": html_to_text(c["text"])})
        for k in (c.get("kids") or [])[:replies]:
            if k in kids:
                out.append({"id": k, "by": kids[k].get("by", ""), "rank": rank, "depth": 1, "parent": c["id"],
                            "text": html_to_text(kids[k]["text"])})
    return out


def capture_story(story: dict, top_comments: int, replies: int, force: bool = False) -> tuple[Path, bool]:
    """-> (source folder, newly_captured). An already captured story is left alone unless force."""
    existing = sorted(SOURCES.glob(f"*-{story['id']}"))
    if existing and not force:
        return existing[-1], False
    dest = existing[-1] if existing else SOURCES / f"{date.today().isoformat()}-{story['id']}"
    dest.mkdir(parents=True, exist_ok=True)
    hn_url = f"https://news.ycombinator.com/item?id={story['id']}"
    if story.get("url"):
        article = fetch_article(story["url"], dest)
    else:                                                       # Ask HN / text post: the post is the article
        text = html_to_text(story.get("text", ""))
        (dest / "article.txt").write_text(text, encoding="utf-8")
        article = {"url": hn_url, "status": "ok" if len(text) >= THIN else "thin", "chars": len(text),
                   "method": "hn-text"}
    comments = fetch_comments(story, top_comments, replies)
    write_json(dest / "comments.json", comments)
    write_json(dest / "story.json", {
        "id": story["id"], "title": story.get("title", ""), "url": story.get("url", hn_url), "hn_url": hn_url,
        "points": story.get("score", 0), "comment_count": story.get("descendants", 0), "by": story.get("by", ""),
        "rank": story.get("rank"), "posted_at": datetime.fromtimestamp(story.get("time", 0), timezone.utc).isoformat(),
        "captured_at": now(), "article": article, "comments_saved": len(comments)})
    return dest, True
