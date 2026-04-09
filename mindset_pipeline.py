#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mindset_pipeline.py — Scrape trending mindset posts from Reddit,
combine with today's top AI news from trends.txt,
generate 2 script options, and push to Zapier → HeyGen.
"""

import urllib.request
import json
import sys
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ← Same webhook as video_pipeline; update if you have a dedicated one
ZAPIER_WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/26951471/unakh8k/"
HEYGEN_AVATAR_ID   = "1450565002f64e9c86defed726b03f06"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# ---------------------------------------------------------------------------
# X (Twitter) mindset / entrepreneur influencers via Nitter RSS
# ---------------------------------------------------------------------------

X_MINDSET_ACCOUNTS = [
    ("SahilBloom",      "https://nitter.net/SahilBloom/rss"),
    ("JamesClear",      "https://nitter.net/JamesClear/rss"),
    ("AlexHormozi",     "https://nitter.net/AlexHormozi/rss"),
    ("codie_sanchez",   "https://nitter.net/codie_sanchez/rss"),
    ("thejustinwelsh",  "https://nitter.net/thejustinwelsh/rss"),
    ("naval",           "https://nitter.net/naval/rss"),
    ("Dan_Koe",         "https://nitter.net/Dan_Koe/rss"),
]

# Keywords that signal a mindset/growth post (not a promo or reply)
MINDSET_KEYWORDS = [
    "success", "fail", "habit", "discipline", "fear", "growth", "mindset",
    "learn", "improve", "focus", "money", "wealth", "career", "job",
    "hustle", "purpose", "goal", "mistake", "advice", "lesson", "truth",
    "hard", "sacrifice", "grind", "consistency", "patience", "courage",
    "regret", "risk", "confidence", "action", "lazy", "procrastinat",
    "overthink", "comparison", "jealous", "anxiety", "identity", "value",
    "invest", "build", "create", "change", "entrepreneur", "business",
    "great", "best", "worst", "never", "always", "most people", "nobody",
]


def fetch_x_mindset() -> list[dict]:
    """Fetch mindset/growth posts from influencer X accounts via Nitter RSS."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    items = []
    for account_name, feed_url in X_MINDSET_ACCOUNTS:
        try:
            req = urllib.request.Request(feed_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            if len(data) < 100:
                continue
            root = ET.fromstring(data)
            for item_el in root.iter("item"):
                title = (item_el.findtext("title") or "").strip()
                link  = (item_el.findtext("link") or "").strip()
                pub   = item_el.findtext("pubDate") or ""
                desc  = (item_el.findtext("description") or "").strip()
                desc_clean = re.sub(r"<[^>]+>", "", desc).strip()
                try:
                    pub_dt = parsedate_to_datetime(pub)
                except Exception:
                    continue
                if pub_dt < cutoff:
                    continue
                # Skip retweets
                if title.lower().startswith("rt by @"):
                    continue
                # Skip very short posts (replies, one-liners)
                if len(desc_clean) < 50:
                    continue
                # Must contain mindset-related keywords
                combined = desc_clean.lower()
                hits = sum(1 for kw in MINDSET_KEYWORDS if kw in combined)
                if hits < 1:
                    continue
                items.append({
                    "title":    desc_clean[:150].split("\n")[0],
                    "text":     desc_clean[:400],
                    "score":    hits * 50,  # normalize to be comparable with Reddit scores
                    "comments": 0,
                    "source":   f"X @{account_name}",
                })
        except Exception as e:
            print(f"[WARN] X @{account_name} failed: {e}", file=sys.stderr)

    items.sort(key=lambda x: x["score"], reverse=True)
    return items


# ---------------------------------------------------------------------------
# Load today's top AI trend
# ---------------------------------------------------------------------------

def load_top_ai_trend() -> dict:
    """Load an AI trend from trends.txt that was NOT already sent by ai_trends.py.
    Lines 1-2 are already sent to Zapier by ai_trends; pick from line 3+ to avoid overlap.
    Falls back to line 1 if fewer than 3 lines exist.
    """
    path = os.path.join(SCRIPT_DIR, "trends.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            all_lines = [l.strip() for l in f.readlines() if l.strip()]
        # Skip first 2 lines (already sent by ai_trends), use line 3+
        target_line = all_lines[2] if len(all_lines) > 2 else all_lines[0]
        title_match   = re.search(r"Title: (.+?) \|\| Insight:", target_line)
        insight_match = re.search(r"Insight: (.+?) \|\| Link:", target_line)
        return {
            "title":   title_match.group(1)   if title_match   else "AI 正在改变一切",
            "insight": insight_match.group(1) if insight_match else "",
        }
    except Exception as e:
        print(f"[WARN] Could not load trends.txt: {e}", file=sys.stderr)
        return {
            "title":   "AI 正在改变一切",
            "insight": "就在刚刚，一条 AI 新闻在硅谷引起了轰动——这件事正在影响每一个普通人的生活。",
        }


# ---------------------------------------------------------------------------
# Theme detection
# ---------------------------------------------------------------------------

THEME_KEYWORDS = {
    "failure":      ["fail", "mistake", "wrong", "loss", "setback", "rejection", "fired", "quit", "regret"],
    "consistency":  ["habit", "daily", "routine", "consistent", "discipline", "streak", "every day", "small steps"],
    "fear":         ["fear", "anxiety", "scared", "nervous", "worry", "afraid", "overthink", "doubt"],
    "comparison":   ["compare", "jealous", "others", "social media", "envy", "behind", "imposter"],
    "focus":        ["focus", "distraction", "attention", "deep work", "procrastinat", "lazy", "motivation"],
    "identity":     ["identity", "who you are", "purpose", "meaning", "values", "authentic", "real you"],
    "growth":       ["growth", "learn", "improve", "better", "progress", "develop", "skill", "mindset"],
    "money":        ["money", "wealth", "rich", "poor", "financial", "income", "salary", "broke"],
    "career":       ["career", "job", "work", "boss", "office", "corporate", "startup", "hustle"],
    "relationships":["relationship", "friend", "family", "people", "social", "alone", "lonely", "network"],
}

THEME_ORDER = list(THEME_KEYWORDS.keys())  # fallback rotation


def detect_theme(title: str, text: str) -> str:
    combined = (title + " " + text).lower()
    scores = {
        theme: sum(1 for kw in kws if kw in combined)
        for theme, kws in THEME_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "growth"


# ---------------------------------------------------------------------------
# Script bodies — one per theme
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# News summary templates — 用中文概括新闻全貌（按关键词匹配）
# 每个 key: (keywords, summary_template)
# {title} 会被替换为新闻标题的中文化简述
# ---------------------------------------------------------------------------

NEWS_HOOKS = [
    # 大厂/公司动态
    (["openai", "sam altman"],
     "刚刚，OpenAI 又搞了个大动作。"
     "整个硅谷都在讨论这件事，因为 OpenAI 每次出手，基本上就是在告诉全世界：AI 的下一步往哪走。"),
    (["anthropic", "claude"],
     "刚刚，做 Claude 的那家公司 Anthropic 放了个大消息。"
     "这家公司一直走安全路线，但这次的动作说明：安全和强大，它全都要。"),
    (["google", "deepmind", "gemini"],
     "谷歌刚刚出手了，又是一个重磅动作。"
     "别忘了谷歌手里有搜索、有安卓、有云计算，一旦它把 AI 真正嵌进这些产品，影响的是几十亿人的日常。"),
    (["meta", "zuckerberg", "muse"],
     "扎克伯格刚刚亮牌了，Meta 在 AI 赛道上又放了一个大招。"
     "Meta 在 AI 上砸的钱已经是天文数字了，这次的动作说明它要的不是跟随，是定义规则。"),
    (["microsoft", "copilot"],
     "微软刚刚又往 AI 里砸了一记重锤。"
     "微软可怕的地方在于：它不需要你主动选择 AI，它直接把 AI 放进你每天在用的工具里。"),
    (["nvidia", "chip"],
     "英伟达又出大消息了。"
     "AI 时代所有人都在挖矿，但英伟达是卖铲子的那个。它的每一步，决定了整个行业能跑多快。"),
    (["apple", "siri"],
     "苹果终于动了，这次是认真的。"
     "苹果一旦认真做 AI，十几亿 iPhone 用户一夜之间全部升级。这就是它可怕的地方。"),
    # 融资/商业
    (["billion", "million", "funding", "valuation", "ipo"],
     "硅谷又一笔疯狂的钱砸进了 AI 赛道。"
     "钱的方向，就是未来的方向。聪明钱现在押注的赛道，三年后就是普通人的日常。"),
    # 就业冲击
    (["job", "replace", "layoff", "fired", "worker"],
     "又一条 AI 取代人类的消息炸了，这次是真的。"
     "这不是电影情节，是正在发生的事。问题不是 AI 会不会取代你，是什么时候轮到你。"),
    # 安全/隐私
    (["hack", "breach", "privacy", "deepfake", "fake"],
     "一条细思极恐的 AI 消息刚刚爆出来。"
     "技术越强大，风险越真实。你以为你在用工具，但工具可能也在用你。"),
    # 监管/法律
    (["ban", "regulation", "law", "illegal", "government"],
     "政府终于对 AI 出手了，这次动真格的。"
     "监管来了，说明这个行业大到不能忽视了。规则改变的时候，有人被淘汰，有人抢到新位置。"),
    # 突破/能力
    (["breakthrough", "beats", "surpass", "record", "smarter"],
     "AI 又刷新了一个让人不敢相信的纪录。"
     "每次有人说「AI 还差得远」，下一周就被打脸。这个速度，已经超出大多数人的想象了。"),
    # 创意/内容
    (["artist", "music", "video", "image", "creative", "generate"],
     "AI 在创作领域又往前迈了一大步。"
     "当机器开始「创作」，人类的价值到底在哪？这个问题已经不是哲学了，是生存问题。"),
    # 机器人
    (["robot", "humanoid", "autonomous"],
     "AI 走出屏幕了，这次是实实在在的物理世界。"
     "当 AI 有了身体，世界的变化速度会再翻一个量级。"),
]

# 默认 hook（兜底）
DEFAULT_NEWS_HOOK = (
    "刚刚，一条 AI 新闻在科技圈炸开了。"
    "这件事看起来是行业新闻，但拆开来看，跟每个普通人都有关系。"
)


def _extract_proper_nouns(title: str) -> list[str]:
    """从标题中提取英文专有名词（公司名、产品名），只保留这些。"""
    KNOWN_NOUNS = [
        "OpenAI", "ChatGPT", "GPT-5", "GPT-4", "GPT", "Claude", "Gemini",
        "Copilot", "Sora", "Codex", "DALL-E", "Midjourney",
        "Meta", "Google", "Apple", "Microsoft", "Nvidia", "Tesla", "Amazon",
        "Anthropic", "DeepMind", "DeepSeek", "Mistral", "xAI", "Grok",
        "iPhone", "Android", "AGI", "Muse Spark", "Llama",
        "Sam Altman", "Elon Musk", "Mark Zuckerberg",
    ]
    found = []
    for noun in KNOWN_NOUNS:
        if noun.lower() in title.lower():
            found.append(noun)
    return found


def _make_news_section(ai_trend: dict) -> str:
    """生成新闻 hook + 概括段落，全中文，最多保留 1-2 个英文专有名词。"""
    title = ai_trend["title"]
    nouns = _extract_proper_nouns(title)
    noun_str = "、".join(nouns[:2]) if nouns else "AI"
    t = title.lower()

    # 匹配最佳 hook 模板
    best_template = DEFAULT_NEWS_HOOK
    best_hits = 0
    for keywords, template in NEWS_HOOKS:
        hits = sum(1 for kw in keywords if kw in t)
        if hits > best_hits:
            best_hits = hits
            best_template = template

    return best_template


# ---------------------------------------------------------------------------
# Script bodies — 结构：转折 → 个人经历/IP → 观点 → 行动号召
# 全中文为主，每段最多 1-2 个英文词
# ---------------------------------------------------------------------------

MINDSET_BODIES = {
    "failure": (
        "但这条新闻让我想起一件更重要的事。"
        "我创业失败过。不是那种「差一点就成了」的故事，是真实地烧光了钱、散掉了团队、一个人坐在空办公室里发呆的那种。"
        "那段时间最大的收获，不是什么商业经验，是我发现自己根本没有想象中那么脆弱。"
        "初中一个人来美国，语言不通、文化不懂，每天都在硬撑。那段日子教会我：人能承受的，远比自己以为的多。"
        "AI 时代最大的风险不是失败，是你把失败当终点。真正的问题不是「我搞砸了」，而是「搞砸之后，我做了什么」。"
        "今天给你一个动作：找出你最近搞砸的一件事，写下它教了你的三样东西。不是为了安慰自己，是为了把代价变成资产。"
    ),
    "consistency": (
        "但真正让我思考的，不是这条新闻本身，而是它背后的一个规律。"
        "我做长期投资好几年了。投资最反人性的地方不是选什么标的，是等待。"
        "市场跌的时候所有人都喊「这次不一样」，但真正赚到钱的，不是判断最准的人，是最不容易被噪音带跑的人。"
        "每次 AI 有大新闻，就有一批人焦虑：是不是该立刻转型、立刻学新东西？我不是说不学，是说——爆发式的焦虑，永远打不过细水长流的坚持。"
        "选一个你要在 AI 时代押注的方向，今天做十五分钟，明天继续。不要等准备好了再开始，开始了你才会慢慢准备好。"
    ),
    "fear": (
        "但比新闻更值得聊的，是它激起的那种情绪——恐惧。"
        "初中的时候，我一个人飞到美国。不会英语、不认识任何人，第一个学期几乎每天都想回家。"
        "那段日子教会我最重要的一件事：恐惧本身不会伤害你，但你为了逃避恐惧做的决定，会。"
        "现在很多人看到 AI 的进展，第一反应就是怕——怕被取代、怕跟不上、怕选错方向。"
        "但我见过太多人，不是输在能力上，是输在「怕输」上。因为怕做错所以什么都不做，五年后发现最大的错误就是什么都没做。"
        "问你一个问题：你现在最怕的那件事，如果你不怕了，明天会怎么行动？把答案写下来。那就是你该走的下一步。"
    ),
    "comparison": (
        "但说实话，这种新闻最容易引发的不是思考，是焦虑。"
        "我代表过中国顶尖的公司去硅谷谈判。坐对面的，有管几十亿美金基金的人，有最老牌的投资人。"
        "见过这些人之后我发现一个规律——真正有实力的人，几乎没有一个在比较。他们只关心一个问题：我现在要解决什么。"
        "AI 时代信息太透明了，别人用什么工具、拿了什么融资、升了什么职，全都看得见。但你看到的，永远是别人的精选集。"
        "今天做一件事：把你手机里最让你焦虑的那个 APP 静音一周。先把注意力还给自己，再谈进步。"
    ),
    "focus": (
        "但这条新闻让我想到一个更底层的问题——在这么多信息轰炸里，你还能专注吗？"
        "有一年我辞掉工作，去泰国打了半年泰拳。"
        "不是因为迷茫，是因为我太清楚——我需要一段时间只做一件事，搞清楚自己真正的极限在哪里。"
        "每天五点起来跑步，上午练技术，下午对打，晚上复盘。没有手机、没有会议、没有「这个也很重要」。"
        "那半年教会我的不是泰拳，是专注本身的力量。当你把所有精力压在一件事上，进步的速度会让你自己都吓一跳。"
        "AI 时代最稀缺的能力，不是会用什么工具，是在信息爆炸中保持深度专注。今天试一下：找一件最重要的事，做九十分钟，期间不看任何消息。"
    ),
    "identity": (
        "但这条新闻让我想到一个更深的问题——在 AI 什么都能做的时代，你是谁？"
        "我的经历有点杂。初中来美国，后来创业、辞职去打拳、做投资、帮中国公司跟硅谷谈判。"
        "很多人问我：你到底是做什么的？我以前觉得很难回答，后来想通了——我不是在做某件事，我是在成为某种人。"
        "AI 时代很多人怀疑自己的价值：我能做什么是 AI 做不了的？但这个问题方向就问错了。"
        "真正该问的是：只有我能带来什么？你的判断力、你的经历、你对人的理解——这些不是技能，是你这个人本身。"
        "今天想一个问题：你这辈子经历过最独特的三件事是什么？那里面藏着你真正的差异化，AI 复制不了。"
    ),
    "growth": (
        "但新闻只是表面，我更想聊聊它背后那个不舒服的真相——成长从来都不舒服。"
        "我第一次代表公司去硅谷谈判，完全不知道规则。"
        "对面是管几十亿美金的基金，我这边是一个刚出来没多久的中国团队。谈判结束后，我在酒店复盘了三个小时，把每一句说错的话全部写下来。"
        "那是我成长最快的三个月。不是因为我聪明，是因为我把每一次不舒服都当成了数据。"
        "AI 时代变化太快，很多人想等「准备好了」再行动。但真相是：你不会在行动前准备好，只会在行动中变得准备好。"
        "找一件你一直在「等准备好」的事，今天就做第一步。哪怕只有二十分钟，成长从来不等人。"
    ),
    "money": (
        "但这条新闻真正值得思考的，不是技术，是钱的逻辑。"
        "做投资这些年，我见过最多的亏损方式，不是判断错了市场，是在错误的时间做了情绪化的决定。"
        "牛市的时候贪，熊市的时候怕。AI 概念火了所有人追，泡沫一破所有人跑。"
        "但真正的财富积累，靠的不是每次都判断对，是在别人恐慌的时候保持清醒，在别人疯狂的时候保持克制。"
        "你现在最值得投资的资产，不是某只股票，是你自己的不可替代性。"
        "想一个问题：你现在的技能组合，五年后会因为 AI 更值钱还是更不值钱？想清楚这个，比买任何东西都重要。"
    ),
    "career": (
        "但这条新闻真正戳到的，是一个很多人不敢面对的问题——你现在做的事，还有多久的保质期？"
        "我辞过职。不是被逼的，是主动离开一份别人看来很好的工作，去打泰拳、去创业、去做我觉得值得做的事。"
        "很多人说：你不怕吗？怕，当然怕。但我更怕十年后回头看，发现自己一直在做一件让自己麻木的事。"
        "AI 把很多「稳定」的工作变得不再稳定了。但这可能是好事——它逼着每个人重新想一个问题：你在为谁工作？为什么工作？"
        "真正的职业安全感，从来不来自某一家公司，而是你有没有一种能力，离开任何平台之后市场还愿意为它买单。"
        "今天想一个问题：如果你明天失去现在的工作，你最有底气重新出发的能力是什么？那就是你该投资的方向。"
    ),
    "relationships": (
        "但这条新闻让我想到一件更根本的事——在 AI 越来越强的世界里，人和人之间的连接反而更值钱了。"
        "跟硅谷投资人谈判教了我一个书上学不到的道理——真正的信任，不是靠资料建立的，是靠你让对方感觉到你真的懂他在乎什么。"
        "我见过拿着完美方案但毫无存在感的人，也见过准备一般但每次开口都能让整个房间安静下来的人。"
        "区别不是口才，是他们真的花时间去理解对方的顾虑、动机、和没有说出口的担心。"
        "AI 可以帮你写邮件、做分析、整理资料，但它替代不了真实的人际理解。这种能力在 AI 时代只会越来越值钱。"
        "今天试一下：找一个你需要说服的人，开口之前先花五分钟想清楚——他最在乎的一件事是什么。从那里开始，而不是从你想说的开始。"
    ),
}


# ---------------------------------------------------------------------------
# Script generator — hook(新闻) + 概括 + 转折 + 个人经历/思维 + 行动
# ---------------------------------------------------------------------------

def generate_script(ai_trend: dict, theme: str) -> str:
    news = _make_news_section(ai_trend)
    body = MINDSET_BODIES.get(theme, MINDSET_BODIES["growth"])
    return f"{news}{body}"


# ---------------------------------------------------------------------------
# Send to Zapier
# ---------------------------------------------------------------------------

def send_to_zapier(script: str):
    payload = json.dumps({
        "content": script,
    }).encode("utf-8")

    req = urllib.request.Request(
        ZAPIER_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.getcode()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Fetching trending mindset posts from X...")
    posts = fetch_x_mindset()
    print(f"  Found {len(posts)} posts from influencer accounts")

    print("Loading today's top AI trend...")
    ai_trend = load_top_ai_trend()
    print(f"  Trend: {ai_trend['title'][:70]}...")

    # Detect themes from top posts, ensure option 1 and 2 use different themes
    used_themes = set()
    selected = []
    for post in posts:
        theme = detect_theme(post["title"], post["text"])
        if theme not in used_themes:
            selected.append((post, theme))
            used_themes.add(theme)
        if len(selected) == 2:
            break

    # Fallback: rotate through default themes if Reddit posts aren't enough
    if len(selected) < 2:
        day = datetime.now(timezone.utc).timetuple().tm_yday
        fallback_themes = [t for t in THEME_ORDER if t not in used_themes]
        while len(selected) < 2 and fallback_themes:
            theme = fallback_themes.pop(day % len(fallback_themes) if fallback_themes else 0)
            selected.append(({"title": theme, "text": ""}, theme))

    (post_1, theme_1), (post_2, theme_2) = selected[0], selected[1]

    print(f"\n  Option 1: theme={theme_1}  source={post_1.get('source','fallback')}")
    print(f"  Option 2: theme={theme_2}  source={post_2.get('source','fallback')}")

    script_1 = generate_script(ai_trend, theme_1)
    script_2 = generate_script(ai_trend, theme_2)

    print(f"\nScript 1 preview: {script_1[:100]}...")
    print(f"Script 2 preview: {script_2[:100]}...")

    if not ZAPIER_WEBHOOK_URL:
        print("\n[SKIP] ZAPIER_WEBHOOK_URL not set.", file=sys.stderr)
        return

    print("\nSending to Zapier → HeyGen...")
    for i, script in enumerate([script_1, script_2], 1):
        status = send_to_zapier(script)
        print(f"  [{status}] Script {i} sent")


if __name__ == "__main__":
    main()
