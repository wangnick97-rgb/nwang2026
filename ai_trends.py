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


def fetch_reddit_sub(subreddit: str) -> list[dict]:
    """Reddit top posts (day) for a subreddit."""
    items = []
    url = f"https://www.reddit.com/r/{subreddit}/top/.json?t=day&limit=10"
    try:
        data = fetch_url(url, extra_headers={"Accept": "application/json"})
        payload = json.loads(data)
        posts = payload.get("data", {}).get("children", [])
        for post in posts:
            d = post.get("data", {})
            title     = (d.get("title") or "").strip()
            permalink = d.get("permalink") or ""
            link      = f"https://www.reddit.com{permalink}"
            score     = d.get("score", 0)
            comments  = d.get("num_comments", 0)
            created   = d.get("created_utc", 0)
            url_dest  = d.get("url") or link
            pub_dt    = datetime.fromtimestamp(created, tz=timezone.utc) if created else None
            if pub_dt and pub_dt < CUTOFF:
                continue
            if not is_ai_related(title):
                continue
            if is_too_technical(title):
                continue
            bonus = min((score // 500) + (comments // 100), 10)
            items.append({
                "title":  title,
                "link":   url_dest if url_dest.startswith("http") else link,
                "source": f"Reddit r/{subreddit}",
                "score":  viral_score(title, bonus),
                "text":   f"{score} upvotes · {comments} comments",
            })
    except Exception as e:
        print(f"[WARN] Reddit r/{subreddit} fetch failed: {e}", file=sys.stderr)
    return items


def fetch_producthunt() -> list[dict]:
    """Product Hunt RSS feed — AI launches."""
    items = []
    try:
        data = fetch_url("https://www.producthunt.com/feed")
        root = ET.fromstring(data)
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
                "source": "Product Hunt",
                "score":  viral_score(title + " " + desc),
                "text":   desc[:200],
            })
    except Exception as e:
        print(f"[WARN] Product Hunt fetch failed: {e}", file=sys.stderr)
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

INSIGHT_TEMPLATES = {
    # 职业/就业冲击
    "job":        "打工人注意了！AI 正在悄悄接管这个岗位——{title}，你的工作还安全吗？",
    "replace":    "又一个职业被盯上了。{title}——如果连这个都能被替代，我们还能靠什么赚钱？",
    "layoff":     "裁员潮来了？{title}——AI 时代，第一批失业的往往是这类人。",
    "fired":      "这不是段子，是真实发生的事：{title}。你所在的行业还有多久？",
    # 钱/投资/商业机会
    "funding":    "资本在押注什么？{title}——读懂这笔钱的方向，普通人也能找到下一个风口。",
    "billion":    "又是百亿美元级别的动作。{title}——AI 的钱都流向哪了？跟着钱走准没错。",
    "ipo":        "AI 独角兽要上市了！{title}——这波红利，普通人怎么蹭到？",
    "invest":     "聪明钱已经下场了。{title}——不懂 AI 投资逻辑，可能真的会错过这个时代。",
    "revenue":    "AI 开始真正赚钱了。{title}——这才是这波浪潮最值得关注的信号。",
    # 隐私/安全/信任危机
    "ad":         "震惊！{title}——你以为在用工具，工具其实在用你做广告。",
    "inject":     "这已经不是 bug，是赤裸裸的商业操控：{title}。用 AI 工具的人都该看看。",
    "hack":       "你的数据安全吗？{title}——AI 时代的安全漏洞，受害的是每一个普通用户。",
    "breach":     "又泄露了。{title}——用 AI 产品之前，你知道它在收集什么吗？",
    "privacy":    "隐私正在消失。{title}——在你不知情的情况下，AI 已经看了多少？",
    "deepfake":   "你看到的可能是假的。{title}——AI 换脸、伪造声音，普通人该怎么辨别？",
    # 监管/法律/政府
    "ban":        "政府出手了！{title}——这次的监管，会直接影响你能用哪些 AI 产品。",
    "lawsuit":    "开始打官司了。{title}——这场法律战的结果，将决定 AI 能走多远。",
    "regulation": "AI 监管时代正式开启？{title}——规则变了，机会和风险都在重新分配。",
    "illegal":    "有人踩红线了。{title}——AI 的边界在哪，这件事给了一个清晰的答案。",
    # 免费/工具/生产力
    "free":       "免费！{title}——以前要花大价钱的能力，现在人人都能用，行业洗牌开始了。",
    "launch":     "新工具来了！{title}——先用上的人，效率可能直接碾压同行。",
    "release":    "刚刚发布！{title}——这个工具值不值得上手，我们帮你先看了。",
    # 能力突破/超越人类
    "beats":      "AI 又赢了。{title}——这次被超越的，是很多人引以为傲的技能。",
    "surpass":    "人类又输了一局。{title}——但这不是坏事，关键是你怎么利用这个工具。",
    "breakthrough": "真正的突破来了！{title}——这一次，可能不是炒作。",
    "first":      "历史首次！{title}——第一个吃螃蟹的往往定义整个赛道。",
    # 创意/内容/媒体
    "artist":     "创作者们，AI 又来抢饭碗了。{title}——你的作品还值钱吗？",
    "music":      "AI 作曲、AI 唱歌……{title}——音乐人的未来在哪里？",
    "video":      "AI 已经能生成这样的视频了。{title}——做内容的人，压力越来越大了。",
    "image":      "一键生图时代，谁还在付钱请设计师？{title}。",
    # 中美竞争
    "china":      "中美 AI 战争升级！{title}——这场科技博弈的输赢，会影响每个普通人的生活。",
    "chinese":    "中国 AI 又有大动作。{title}——这次的进展，连硅谷都开始紧张了。",
    # OpenAI/大厂动态
    "openai":     "OpenAI 又整活了。{title}——这家公司每次动作，都在重新定义 AI 的边界。",
    "google":     "谷歌出手了。{title}——科技巨头的每一步棋，都在提前布局你的未来。",
    "microsoft":  "微软又赢了？{title}——这家公司把 AI 嵌进每个产品，没人能绕开它。",
    "meta":       "Meta 在 AI 上的野心比你想象的大。{title}——扎克伯格到底在下什么棋？",
    "nvidia":     "英伟达又涨了？{title}——AI 时代，卖铲子的比挖矿的更赚钱。",
    "apple":      "苹果终于动了！{title}——一旦苹果认真做 AI，游戏规则就变了。",
}

DEFAULT_INSIGHT = "AI 正在以你看不见的速度改变这个世界——这条新闻，值得每个普通人花 30 秒了解。"


def generate_insight(item: dict) -> str:
    t = item["title"].lower()
    for kw, template in INSIGHT_TEMPLATES.items():
        if kw in t:
            # Trim title for readability
            short_title = item["title"][:80] + ("…" if len(item["title"]) > 80 else "")
            return template.format(title=short_title)
    return DEFAULT_INSIGHT


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Fetching AI trends from the last 24 hours…")

    all_items: list[dict] = []

    # Priority 1 — TechCrunch
    tc = fetch_techcrunch()
    print(f"  TechCrunch:   {len(tc)} AI items")
    all_items.extend(tc)

    # Priority 2 — Hacker News
    hn = fetch_hackernews()
    print(f"  Hacker News:  {len(hn)} AI items")
    all_items.extend(hn)

    # Priority 3 — Reddit
    r_ai = fetch_reddit_sub("artificial")
    r_ml = fetch_reddit_sub("MachineLearning")
    print(f"  Reddit r/artificial:      {len(r_ai)} items")
    print(f"  Reddit r/MachineLearning: {len(r_ml)} items")
    all_items.extend(r_ai)
    all_items.extend(r_ml)

    # Priority 4 — Product Hunt
    ph = fetch_producthunt()
    print(f"  Product Hunt: {len(ph)} AI items")
    all_items.extend(ph)

    if not all_items:
        print("No items fetched. Check your network connection.", file=sys.stderr)
        sys.exit(1)

    # Sort by score descending, then deduplicate
    all_items.sort(key=lambda x: x["score"], reverse=True)
    unique_items = deduplicate(all_items)

    # Take top 5
    top5 = unique_items[:5]

    if not top5:
        print("No qualifying AI trends found in the last 24 hours.", file=sys.stderr)
        sys.exit(1)

    # Build output — one trend per line
    lines = []
    for item in top5:
        insight = generate_insight(item)
        lines.append(f"Title: {item['title']} || Insight: {insight} || Link: {item['link']}")

    output = "\n".join(lines)

    with open(os.path.join(SCRIPT_DIR, "trends.txt"), "w", encoding="utf-8") as f:
        f.write(output + "\n")

    print(f"\nSaved {len(top5)} trends to trends.txt\n")
    print("=" * 60)
    print(output)
    print("=" * 60)

    # Send each trend to Zapier webhook
    if not ZAPIER_WEBHOOK_URL:
        print("\n[SKIP] ZAPIER_WEBHOOK_URL is not set.", file=sys.stderr)
        return

    print("\nSending to Zapier…")
    for item in top5:
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
