#!/usr/bin/env python3
"""
ai_trends.py — Fetch the most viral/discussable AI trends from the last 24 hours,
optimized for short-form content (TikTok / Xiaohongshu / YouTube Shorts).
"""

import urllib.request
import urllib.error
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import re
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# ← Paste your Zapier webhook URL here
ZAPIER_WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/26951471/unrbet9/"

CUTOFF = datetime.now(timezone.utc) - timedelta(hours=24)


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

VIRAL_KEYWORDS = [
    # money / jobs / disruption
    "replace", "job", "fired", "layoff", "salary", "billion", "revenue",
    "profit", "startup", "invest", "funding", "ipo", "acquisition", "acquire",
    # controversy / drama
    "ban", "illegal", "lawsuit", "sue", "regulation", "censor", "scandal",
    "hack", "breach", "leak", "fraud", "fake", "deepfake", "scam",
    # consumer impact
    "everyone", "free", "cheaper", "faster", "beats", "outperform", "surpass",
    "human", "creative", "artist", "writer", "music", "video", "image",
    # hype / surprise
    "first", "new", "launch", "release", "breakthrough", "record", "biggest",
    "best", "worst", "insane", "wild", "shocking", "surprising", "secret",
    # hot topics
    "gpt", "gemini", "claude", "llm", "agent", "robot", "autonomous",
    "openai", "google", "meta", "apple", "microsoft", "nvidia", "tesla",
    "china", "chinese", "regulation", "europe", "safety", "alignment",
]

AI_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "ml", "llm",
    "gpt", "chatgpt", "gemini", "claude", "copilot", "openai", "deepmind",
    "midjourney", "stable diffusion", "dall-e", "neural", "model", "robot",
    "automation", "autonomous", "generative", "diffusion", "transformer",
    "anthropic", "mistral", "llama", "groq", "sora", "agent", "agi",
]

# Topics that are too developer/engineer-specific — penalize heavily
TECH_NERD_KEYWORDS = [
    "react", "typescript", "javascript", "python", "rust", "golang", "java",
    "kubernetes", "docker", "api", "sdk", "github", "gitlab", "pull request",
    " pr ", "open source", "open-source", "repository", "repo", "commit",
    "cloudflare", "router", "dns", "tcp", "http", "css", "html", "webpack",
    "postgresql", "sqlite", "database", "backend", "frontend", "devops",
    "cli", "bash", "shell", "terminal", "linux", "kernel", "compiler",
    "benchmark", "inference", "token", "parameter", "fine-tun", "finetun",
    "embedding", "vector", "rag ", "retrieval", "quantiz",
]

# Topics that resonate with general consumers — boost score
CONSUMER_KEYWORDS = [
    "everyone", "people", "user", "consumer", "daily", "life", "work",
    "job", "salary", "money", "income", "career", "business", "company",
    "school", "student", "education", "health", "medical", "doctor",
    "creative", "artist", "music", "photo", "video", "movie", "game",
    "shopping", "price", "cheap", "free", "app", "phone", "iphone",
    "ban", "law", "illegal", "government", "regulation", "privacy",
    "scam", "fraud", "fake", "deepfake", "dangerous", "safe", "rights",
    "billion", "million", "funding", "ipo", "stock", "invest",
    "robot", "humanoid", "autonomous", "self-driving", "electric",
    "chatgpt", "siri", "alexa", "gemini", "copilot", "midjourney",
]


def is_ai_related(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in AI_KEYWORDS)


def is_too_technical(text: str) -> bool:
    """True if the topic is aimed primarily at developers, not general public."""
    t = text.lower()
    hits = sum(1 for kw in TECH_NERD_KEYWORDS if kw in t)
    return hits >= 2  # 2+ dev keywords = skip it


def viral_score(text: str, extra_signal: int = 0) -> float:
    """Return a score reflecting viral / discussion potential for general audiences."""
    t = text.lower()
    base  = sum(1 for kw in VIRAL_KEYWORDS if kw in t)
    boost = sum(1 for kw in CONSUMER_KEYWORDS if kw in t)
    penalty = sum(2 for kw in TECH_NERD_KEYWORDS if kw in t)  # dev topics cost double
    return base + boost - penalty + extra_signal


def parse_date_rss(date_str: str):
    """Parse RSS pubDate; return aware datetime or None."""
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Source fetchers
# ---------------------------------------------------------------------------

def fetch_url(url: str, extra_headers: dict = None, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={**HEADERS, **(extra_headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_techcrunch() -> list[dict]:
    """TechCrunch AI RSS feed."""
    items = []
    try:
        data = fetch_url("https://techcrunch.com/category/artificial-intelligence/feed/")
        root = ET.fromstring(data)
        ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            pub   = item.findtext("pubDate") or ""
            desc  = (item.findtext("description") or "").strip()
            pub_dt = parse_date_rss(pub)
            if pub_dt and pub_dt < CUTOFF:
                continue
            if not is_ai_related(title + " " + desc):
                continue
            if is_too_technical(title):
                continue
            items.append({
                "title":  title,
                "link":   link,
                "source": "TechCrunch",
                "score":  viral_score(title + " " + desc),
                "text":   desc[:300],
            })
    except Exception as e:
        print(f"[WARN] TechCrunch fetch failed: {e}", file=sys.stderr)
    return items


def fetch_hackernews() -> list[dict]:
    """Hacker News frontpage RSS — keep AI items."""
    items = []
    try:
        data = fetch_url("https://hnrss.org/frontpage")
        root = ET.fromstring(data)
        for item in root.iter("item"):
            title    = (item.findtext("title") or "").strip()
            link     = (item.findtext("link")  or "").strip()
            pub      = item.findtext("pubDate") or ""
            comments = item.findtext("{http://www.w3.org/2005/Atom}link") or ""
            desc     = (item.findtext("description") or "")
            pub_dt   = parse_date_rss(pub)
            if pub_dt and pub_dt < CUTOFF:
                continue
            # Extract comment count from description
            comment_match = re.search(r"Comments:\s*(\d+)", desc)
            n_comments = int(comment_match.group(1)) if comment_match else 0
            if not is_ai_related(title + " " + desc):
                continue
            if is_too_technical(title):
                continue
            # Normalize comment count to a score bonus (cap at 10)
            bonus = min(n_comments // 50, 10)
            items.append({
                "title":  title,
                "link":   link,
                "source": "Hacker News",
                "score":  viral_score(title + " " + desc, bonus),
                "text":   f"{n_comments} comments on HN",
            })
    except Exception as e:
        print(f"[WARN] Hacker News fetch failed: {e}", file=sys.stderr)
    return items




def fetch_theverge() -> list[dict]:
    """The Verge AI — Atom feed."""
    items = []
    try:
        data = fetch_url("https://www.theverge.com/rss/ai-artificial-intelligence/index.xml")
        root = ET.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", default="", namespaces=ns)).strip()
            link_el = entry.find("atom:link[@rel='alternate']", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            pub = entry.findtext("atom:published", default="", namespaces=ns)
            summary = (entry.findtext("atom:content", default="", namespaces=ns) or
                       entry.findtext("atom:summary", default="", namespaces=ns))
            # Strip HTML tags from summary
            summary = re.sub(r"<[^>]+>", "", summary).strip()
            pub_dt = None
            if pub:
                try:
                    pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                except Exception:
                    pass
            if pub_dt and pub_dt < CUTOFF:
                continue
            if is_too_technical(title):
                continue
            items.append({
                "title":  title,
                "link":   link,
                "source": "The Verge",
                "score":  viral_score(title + " " + summary, 2),  # boost: major outlet
                "text":   summary[:300],
            })
    except Exception as e:
        print(f"[WARN] The Verge fetch failed: {e}", file=sys.stderr)
    return items


def fetch_ai_company_x() -> list[dict]:
    """Fetch latest posts from major AI companies on X (via Nitter RSS).
    Monitors: OpenAI, ChatGPT, Anthropic, Google AI, Google DeepMind.
    Only keeps posts that announce something new (product, model, feature, update).
    """
    ACCOUNTS = [
        ("OpenAI",        "https://nitter.net/OpenAI/rss"),
        ("ChatGPT",       "https://nitter.net/ChatGPTapp/rss"),
        ("Anthropic",     "https://nitter.net/AnthropicAI/rss"),
        ("Google AI",     "https://nitter.net/GoogleAI/rss"),
        ("Google DeepMind", "https://nitter.net/GoogleDeepMind/rss"),
    ]
    # Keywords that signal a real announcement (not just a retweet or thought piece)
    ANNOUNCE_KEYWORDS = [
        "introducing", "announcing", "launch", "released", "now available",
        "rolling out", "new feature", "new model", "update", "upgrade",
        "available today", "just shipped", "open source", "api", "access",
        "gpt-", "claude", "gemini", "o1", "o3", "o4", "codex", "sora",
        "dall-e", "chatgpt", "copilot", "agents", "tool use",
    ]
    items = []
    for account_name, feed_url in ACCOUNTS:
        try:
            data = fetch_url(feed_url)
            root = ET.fromstring(data)
            for item_el in root.iter("item"):
                title = (item_el.findtext("title") or "").strip()
                link  = (item_el.findtext("link") or "").strip()
                pub   = item_el.findtext("pubDate") or ""
                desc  = (item_el.findtext("description") or "").strip()
                # Strip HTML
                desc_clean = re.sub(r"<[^>]+>", "", desc).strip()
                pub_dt = parse_date_rss(pub)
                if pub_dt and pub_dt < CUTOFF:
                    continue
                # Skip retweets that are just "RT by @..." unless they contain announcement keywords
                combined_text = (title + " " + desc_clean).lower()
                is_rt = title.lower().startswith("rt by @")
                # Must contain at least one announcement keyword
                has_announce = any(kw in combined_text for kw in ANNOUNCE_KEYWORDS)
                if not has_announce:
                    continue
                # Build a clean title: use first ~120 chars of desc for tweets
                clean_title = desc_clean[:120].split("\n")[0]
                if len(clean_title) > 100:
                    clean_title = clean_title[:100] + "…"
                # High score boost: official AI company announcements are top priority
                bonus = 8 if not is_rt else 4
                items.append({
                    "title":  clean_title,
                    "link":   link.replace("nitter.net", "x.com"),
                    "source": f"X @{account_name}",
                    "score":  viral_score(combined_text, bonus),
                    "text":   desc_clean[:300],
                })
        except Exception as e:
            print(f"[WARN] X @{account_name} fetch failed: {e}", file=sys.stderr)
    return items


def fetch_x_trending_ai() -> list[dict]:
    """Fetch trending AI content from high-engagement AI influencer accounts on X.
    These accounts curate and amplify the most viral AI news daily.
    """
    INFLUENCERS = [
        ("TheRundownAI",   "https://nitter.net/TheRundownAI/rss"),
        ("bindureddy",     "https://nitter.net/bindureddy/rss"),
        ("slow_developer", "https://nitter.net/slow_developer/rss"),
        ("TheAIGRID",      "https://nitter.net/TheAIGRID/rss"),
        ("rowancheung",    "https://nitter.net/rowancheung/rss"),
    ]
    items = []
    for account_name, feed_url in INFLUENCERS:
        try:
            data = fetch_url(feed_url)
            root = ET.fromstring(data)
            for item_el in root.iter("item"):
                title = (item_el.findtext("title") or "").strip()
                link  = (item_el.findtext("link") or "").strip()
                pub   = item_el.findtext("pubDate") or ""
                desc  = (item_el.findtext("description") or "").strip()
                desc_clean = re.sub(r"<[^>]+>", "", desc).strip()
                pub_dt = parse_date_rss(pub)
                if pub_dt and pub_dt < CUTOFF:
                    continue
                combined = (title + " " + desc_clean).lower()
                # Must be AI/tech related
                if not is_ai_related(combined):
                    continue
                if is_too_technical(title + " " + desc_clean):
                    continue
                # Skip very short posts (likely replies or one-liners)
                if len(desc_clean) < 40:
                    continue
                clean_title = desc_clean[:120].split("\n")[0]
                if len(clean_title) > 100:
                    clean_title = clean_title[:100] + "…"
                # These are curated viral posts — give a solid score boost
                items.append({
                    "title":  clean_title,
                    "link":   link.replace("nitter.net", "x.com"),
                    "source": f"X @{account_name}",
                    "score":  viral_score(combined, 5),
                    "text":   desc_clean[:300],
                })
        except Exception as e:
            print(f"[WARN] X @{account_name} fetch failed: {e}", file=sys.stderr)
    return items


def fetch_ai_company_blogs() -> list[dict]:
    """Fetch official blog posts from OpenAI and Google DeepMind RSS."""
    BLOGS = [
        ("OpenAI Blog",    "https://openai.com/blog/rss.xml"),
        ("Google AI Blog", "https://blog.google/technology/ai/rss/"),
    ]
    items = []
    for blog_name, feed_url in BLOGS:
        try:
            data = fetch_url(feed_url)
            root = ET.fromstring(data)
            for item_el in root.iter("item"):
                title = (item_el.findtext("title") or "").strip()
                link  = (item_el.findtext("link") or "").strip()
                pub   = item_el.findtext("pubDate") or ""
                desc  = (item_el.findtext("description") or "").strip()
                desc = re.sub(r"<[^>]+>", "", desc).strip()
                pub_dt = parse_date_rss(pub)
                if pub_dt and pub_dt < CUTOFF:
                    continue
                if is_too_technical(title):
                    continue
                # Official blog posts get a high score boost
                items.append({
                    "title":  title,
                    "link":   link,
                    "source": blog_name,
                    "score":  viral_score(title + " " + desc, 6),
                    "text":   desc[:300],
                })
        except Exception as e:
            print(f"[WARN] {blog_name} fetch failed: {e}", file=sys.stderr)
    return items


def fetch_venturebeat() -> list[dict]:
    """VentureBeat AI RSS feed."""
    items = []
    try:
        data = fetch_url("https://venturebeat.com/category/ai/feed")
        root = ET.fromstring(data)
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            pub   = item.findtext("pubDate") or ""
            desc  = (item.findtext("description") or "").strip()
            # Strip HTML tags
            desc = re.sub(r"<[^>]+>", "", desc).strip()
            pub_dt = parse_date_rss(pub)
            if pub_dt and pub_dt < CUTOFF:
                continue
            if is_too_technical(title):
                continue
            items.append({
                "title":  title,
                "link":   link,
                "source": "VentureBeat",
                "score":  viral_score(title + " " + desc, 1),  # slight boost
                "text":   desc[:300],
            })
    except Exception as e:
        print(f"[WARN] VentureBeat fetch failed: {e}", file=sys.stderr)
    return items


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate(items: list[dict]) -> list[dict]:
    """Remove near-duplicate titles using word-overlap heuristic."""
    seen: list[str] = []
    unique = []

    def normalize(s: str) -> set[str]:
        return set(re.sub(r"[^a-z0-9 ]", "", s.lower()).split())

    for item in items:
        words = normalize(item["title"])
        duplicate = False
        for s in seen:
            overlap = len(words & normalize(s)) / max(len(words | normalize(s)), 1)
            if overlap > 0.55:
                duplicate = True
                break
        if not duplicate:
            seen.append(item["title"])
            unique.append(item)
    return unique


# ---------------------------------------------------------------------------
# Insight generator
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Insight generator — extract core content + compelling hook for Chinese audience
# ---------------------------------------------------------------------------

# Category detection: (category_name, keywords, hook_prefix, hook_suffix)
INSIGHT_CATEGORIES = [
    # 大厂动态 — 优先匹配公司名（最常见、最吸引眼球）
    ("bigtech", ["openai", "google", "microsoft", "meta ", "apple", "nvidia", "tesla", "anthropic", "amazon", "sam altman", "zuckerberg", "elon"],
     "科技巨头刚刚放了个大招！",
     "巨头的每一步棋，都在提前布局你的未来。"),
    # 中美竞争
    ("china", ["china", "chinese", "baidu", "alibaba", "tencent", "bytedance", "deepseek", "qwen", "huawei"],
     "中美AI大战白热化！",
     "这场科技博弈的结果，影响每一个普通人。"),
    # 职业/就业冲击
    ("job", ["replace", "job", "fired", "layoff", "hire", "worker", "employee", "workforce", "unemployment"],
     "AI正在颠覆职场！",
     "你的工作还安全吗？这不是危言耸听。"),
    # 隐私/安全/造假
    ("safety", ["hack", "breach", "leak", "privacy", "deepfake", "fake", "scam", "fraud", "spy", "surveillance"],
     "细思极恐！",
     "你的隐私可能早就不存在了。"),
    # 监管/法律
    ("regulation", ["ban", "lawsuit", "sue", "regulation", "illegal", "law", "court", "government", "policy"],
     "政府终于出手了！",
     "这次的监管会直接影响你能用哪些AI。"),
    # 钱/投资/融资
    ("money", ["funding", "billion", "million", "ipo", "invest", "revenue", "profit", "valuation", "acquisition", "acquire"],
     "硅谷的钱正在疯狂涌入AI！",
     "跟着聪明钱走，普通人也能看懂下一个风口。"),
    # 能力突破
    ("breakthrough", ["beats", "surpass", "breakthrough", "record", "outperform", "fastest", "revolutionary", "smarter"],
     "AI又突破人类极限了！",
     "这一次，可能真的不一样。"),
    # 创意/内容
    ("creative", ["artist", "music", "video", "image", "movie", "creative", "writer", "art", "design", "generate"],
     "创作者危机！",
     "AI正在重新定义什么叫'原创'。"),
    # 机器人/硬件
    ("robot", ["robot", "humanoid", "autonomous", "self-driving", "hardware", "chip"],
     "AI走出屏幕了！",
     "机器人时代比你想象的来得更快。"),
    # 免费/工具/发布 — 放最后（launch/release 太泛，容易误匹配）
    ("tool", ["free", "launch", "release", "app", "tool", "update", "feature", "available"],
     "新工具来了！",
     "先用上的人，效率直接碾压同行。"),
]


def _extract_core(text: str, max_len: int = 120) -> str:
    """Extract the most informative sentence from description text."""
    if not text:
        return ""
    # Clean up whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Split into sentences
    sentences = re.split(r"(?<=[.!?。！？])\s+", text)
    # Filter out very short or boilerplate sentences
    useful = [s for s in sentences if len(s) > 20 and not s.lower().startswith(("subscribe", "read more", "click", "follow"))]
    if not useful:
        useful = sentences
    # Pick the first substantive sentence, trim to max_len
    best = useful[0] if useful else text
    if len(best) > max_len:
        best = best[:max_len].rsplit(" ", 1)[0] + "…"
    return best


def generate_insight(item: dict) -> str:
    """Generate a compelling Chinese insight that includes the core news content."""
    title = item["title"]
    desc = item.get("text", "")
    combined = (title + " " + desc).lower()

    # Detect category
    hook_prefix = "刚刚，一条AI新闻在硅谷炸了！"
    hook_suffix = "这件事值得每个人花30秒了解。"
    for _cat, keywords, prefix, suffix in INSIGHT_CATEGORIES:
        hits = sum(1 for kw in keywords if kw in combined)
        if hits >= 1:
            hook_prefix = prefix
            hook_suffix = suffix
            break

    # Extract core content from description for the middle section
    core = _extract_core(desc)
    short_title = title[:80] + ("…" if len(title) > 80 else "")

    if core and core.lower() != title.lower()[:len(core)].lower():
        # We have meaningful description content — use it
        return f"{hook_prefix}{short_title}。{core}。{hook_suffix}"
    else:
        # No description or same as title — use title only
        return f"{hook_prefix}{short_title}。{hook_suffix}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Fetching AI trends from the last 24 hours…")

    all_items: list[dict] = []

    # Priority 0 — Official AI company X accounts (highest priority)
    x_official = fetch_ai_company_x()
    print(f"  X (AI companies): {len(x_official)} posts")
    all_items.extend(x_official)

    # Priority 0.5 — Trending AI posts from high-engagement X influencers
    x_trending = fetch_x_trending_ai()
    print(f"  X (AI trending):  {len(x_trending)} posts")
    all_items.extend(x_trending)

    # Priority 0.5 — Official AI company blogs
    blogs = fetch_ai_company_blogs()
    print(f"  AI company blogs: {len(blogs)} posts")
    all_items.extend(blogs)

    # Priority 1 — TechCrunch
    tc = fetch_techcrunch()
    print(f"  TechCrunch:   {len(tc)} AI items")
    all_items.extend(tc)

    # Priority 2 — Hacker News
    hn = fetch_hackernews()
    print(f"  Hacker News:  {len(hn)} AI items")
    all_items.extend(hn)

    # Priority 3 — The Verge AI
    verge = fetch_theverge()
    print(f"  The Verge:    {len(verge)} AI items")
    all_items.extend(verge)

    # Priority 4 — VentureBeat AI
    vb = fetch_venturebeat()
    print(f"  VentureBeat:  {len(vb)} AI items")
    all_items.extend(vb)

    if not all_items:
        print("No items fetched. Check your network connection.", file=sys.stderr)
        sys.exit(1)

    # Sort by score descending, then deduplicate
    all_items.sort(key=lambda x: x["score"], reverse=True)
    unique_items = deduplicate(all_items)

    # Top 2 for Zapier, top 5 saved to trends.txt (3-5 reserved for mindset_pipeline)
    top = unique_items[:5]

    if len(top) < 2:
        print("No qualifying AI trends found in the last 24 hours.", file=sys.stderr)
        sys.exit(1)

    top2 = top[:2]

    # Build output — one trend per line; lines 1-2 = sent to Zapier, lines 3+ = for mindset
    lines = []
    for item in top:
        insight = generate_insight(item)
        lines.append(f"Title: {item['title']} || Insight: {insight} || Link: {item['link']}")

    output = "\n".join(lines)

    with open(os.path.join(SCRIPT_DIR, "trends.txt"), "w", encoding="utf-8") as f:
        f.write(output + "\n")

    print(f"\nSaved {len(top)} trends to trends.txt (top 2 → Zapier, rest → mindset)\n")
    print("=" * 60)
    print(output)
    print("=" * 60)

    # Send each trend to Zapier webhook
    if not ZAPIER_WEBHOOK_URL:
        print("\n[SKIP] ZAPIER_WEBHOOK_URL is not set.", file=sys.stderr)
        return

    print("\nSending to Zapier…")
    for item in top2:
        insight = generate_insight(item)
        payload = json.dumps({
            "title":   item["title"],
            "insight": insight,
            "link":    item["link"],
        }).encode("utf-8")
        req = urllib.request.Request(
            ZAPIER_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.getcode()
            print(f"  [{status}] {item['title'][:60]}")
        except Exception as e:
            print(f"  [ERROR] {item['title'][:60]} — {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
