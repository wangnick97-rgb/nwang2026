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

MINDSET_BODIES = {
    "failure": (
        "我创业失败过。不是那种「哦差点成功」的失败，是真实烧掉了钱、散掉了团队、在镜子前不知道说什么的那种失败。"
        "那段时间我最大的收获，不是什么商业lesson，是我发现自己根本没有想象中那么脆。"
        "初中就一个人来美国，语言不通、文化不懂，每天硬撑。那段经历教会我一件事：人可以承受的，比自己以为的多得多。"
        "AI 时代最大的风险不是失败，是你把失败当成终点，而不是拐点。真正的问题从来不是「我搞砸了」，是「我搞砸了，然后呢」。"
        "给你一个今天的动作：找出你最近搞砸的一件事，写下三个它教了你的东西。不是为了原谅自己，是为了把代价变成资产。"
    ),
    "consistency": (
        "我做长期投资很多年了。长期投资最反人性的地方不是选股，是等待。"
        "市场跌的时候，所有人都在说「这次不一样」。但真正赢钱的人，不是判断最准的，是最不被噪音带跑的。"
        "这条 AI 新闻，又会让一批人开始焦虑要不要立刻转型、立刻学新东西。我不是说不学，是说：爆发式的行动，打不过细水长流的坚持。"
        "巴菲特说过：The stock market is a device for transferring money from the impatient to the patient. AI 时代也一样——从焦虑者转移到坚持者手里。"
        "给你一个今天可以开始的事：选一个你打算在 AI 时代押注的方向，今天做 15 分钟，明天继续。不要等准备好了再开始，开始了才算准备。"
    ),
    "fear": (
        "初中，一个人飞到美国。不会英文，不认识任何人，第一个学期几乎每天都想回家。"
        "那段时间我学到的最重要的一件事，不是英文，不是成绩，是：恐惧本身不会伤害你，但你为了逃避恐惧做的决定，会。"
        "现在很多人看到 AI 的新进展，第一反应是害怕——害怕被取代，害怕跟不上，害怕选错了方向。"
        "但我见过太多人，不是输在能力上，是输在「怕输」上。因为怕做错，所以什么都不做。五年过去，发现最大的错误就是什么都没做。"
        "给你一个问题：你现在最怕的那件事，如果你不怕，你明天会怎么行动？把这个答案写下来。那就是你下一步该走的路。"
    ),
    "comparison": (
        "我代表过中国顶尖的公司，在美国跟各类投资人谈判。坐在对面的，有管几十亿美元的基金经理，有硅谷最老牌的 VC partner。"
        "见过这些人之后，我发现一件事——真正有实力的人，几乎没有一个在比较。他们只问：我现在要解决什么问题？"
        "AI 时代，最容易让人焦虑的，就是信息太透明了。别人在用什么工具、拿了什么融资、升了什么职，全都看得见。"
        "但你看到的永远是别人的精选集。那些坐在谈判桌对面的人，背后也有你看不到的代价和取舍。"
        "今天只做一件事：把你手机里最让你感到焦虑的一个 app，静音一周。先把注意力还给自己，再谈进步。"
    ),
    "focus": (
        "有一年，我辞掉工作，去泰国打了半年泰拳。"
        "不是因为迷茫，是因为我太清楚了——我需要一段时间，只做一件事，彻底搞清楚自己真正的极限在哪。"
        "每天早上五点起来跑步，上午练技术，下午对打，晚上复盘。没有手机、没有会议、没有「这个也很重要」。"
        "那半年教会我的，不是泰拳，是专注本身的力量。当你把所有资源压在一件事上，进步的速度会让你自己都吃惊。"
        "AI 时代最稀缺的能力，不是会用哪个工具，是在信息爆炸里保持深度专注的能力。给你一个挑战：今天找一件最重要的事，做 90 分钟，期间不看任何消息。就这一件事。"
    ),
    "identity": (
        "我的经历有点杂——初中留美，后来创业，辞职去打拳，做投资，帮中国公司跟硅谷谈判。"
        "很多人问我：你到底是做什么的？我以前觉得这个问题很难回答。后来我想明白了：我不是在做某件事，我是在成为某种人。"
        "AI 时代，很多人开始怀疑自己的价值——我能做什么是 AI 做不了的？但这个问题问错了方向。"
        "真正的问题不是「AI 做不了什么」，是「只有我能带来什么」。你的判断力、你的经历、你对人性的理解——这些不是技能，是你这个人本身。"
        "给你一个今天的思考题：你这辈子经历过的最独特的三件事是什么？那里面藏着你真正的差异化，和任何 AI 都无法复制的东西。"
    ),
    "growth": (
        "我第一次代表公司去硅谷谈判，完全不知道规则是什么。"
        "对面是管几十亿美元的基金，我这边是一个刚出来没多久的中国团队。那次谈判结束之后，我在酒店房间里复盘了三个小时，把所有说错的话、判断错的地方全部写下来。"
        "那是我成长最快的三个月。不是因为我聪明，是因为我把每一次不舒服都当成了数据。"
        "AI 时代变化太快，很多人想等「准备好了」再行动。但真相是：你永远不会在行动前准备好，只会在行动中变得准备好。"
        "给你一个今天可以做的事：找一件你一直在「等准备好」的事，今天做第一步。哪怕只有 20 分钟。成长从来不等人准备好。"
    ),
    "money": (
        "做长期投资这些年，我见过最多的一种亏损，不是市场判断错了，是人在错误的时间做了情绪化的决定。"
        "牛市的时候贪，熊市的时候怕。AI 概念火起来，所有人都追；AI 泡沫破一点，所有人都跑。"
        "但真正的财富积累，从来不是靠判断每一次涨跌，是靠在别人恐慌的时候保持清醒，在别人疯狂的时候保持克制。"
        "这条 AI 新闻会让一批人焦虑收入、担心未来。但我想说的是：你现在最值得投资的资产，不是某只股票，是你自己的不可替代性。"
        "给你一个问题：你现在的技能组合，五年后因为 AI 会更值钱还是更不值钱？先把这个想清楚，比买任何资产都重要。"
    ),
    "career": (
        "我辞过职。不是被逼的，是主动选择离开一份别人看来很好的工作，去打泰拳、去创业、去做我觉得值得做的事。"
        "很多人跟我说：你不怕吗？我说：怕。但我更怕的，是十年后回头看，发现自己一直在做一件让自己麻木的事。"
        "AI 把很多「稳定」的工作变得不再稳定了。但我觉得这是好事。它逼着大家重新思考一个问题：你在为谁工作，为什么工作？"
        "真正的职业安全感，从来不来自一家公司，而来自你有没有一种能力，是离开任何平台之后市场还愿意为之付钱的。"
        "给你一个今天的问题：如果你明天失去现在的工作，你最有把握用来重新出发的能力是什么？那个答案，才是你真正该投资的方向。"
    ),
    "relationships": (
        "跟硅谷投资人谈判这件事，教了我一个在书上学不到的道理——真正的信任，不是靠 deck 建立的，是靠你让对方感觉到你真的懂他在乎什么。"
        "我见过很多人拿着完美的 pitch，但谈判桌上毫无存在感。也见过资料一般，但每次开口都能让房间安静下来的人。"
        "区别不是口才，是他们真的花时间去理解对方——对方的顾虑是什么，对方的激励是什么，对方没有说出口的担心是什么。"
        "AI 可以帮你写 email、做分析、整理资料，但它替代不了这种真实的人与人之间的理解能力。而这种能力，在 AI 时代只会越来越值钱。"
        "给你一个今天可以做的练习：找一个你最近需要说服的人，在开口之前，先花五分钟想清楚他最在乎的一件事是什么。从那里开始，而不是从你想说的开始。"
    ),
}


# ---------------------------------------------------------------------------
# Script generator
# ---------------------------------------------------------------------------

def generate_script(ai_trend: dict, theme: str) -> str:
    body = MINDSET_BODIES.get(theme, MINDSET_BODIES["growth"])
    hook = ai_trend["insight"] or f"就在刚刚，AI 的新动作在硅谷引起了轰动——{ai_trend['title'][:60]}。"
    return f"{hook} {body}"


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
