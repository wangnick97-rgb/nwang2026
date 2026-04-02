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
from datetime import datetime, timezone

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
# Reddit scraper
# ---------------------------------------------------------------------------

MINDSET_SUBREDDITS = ["selfimprovement", "Entrepreneur", "productivity"]


def fetch_reddit_mindset() -> list[dict]:
    items = []
    for sub in MINDSET_SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/top/.json?t=day&limit=10"
        try:
            req = urllib.request.Request(
                url, headers={**HEADERS, "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read())
            posts = payload.get("data", {}).get("children", [])
            for post in posts:
                d = post.get("data", {})
                title    = (d.get("title") or "").strip()
                score    = d.get("score", 0)
                comments = d.get("num_comments", 0)
                selftext = (d.get("selftext") or "")[:400]
                if score < 30:
                    continue
                items.append({
                    "title":    title,
                    "text":     selftext,
                    "score":    score,
                    "comments": comments,
                    "source":   f"r/{sub}",
                })
        except Exception as e:
            print(f"[WARN] Reddit r/{sub} failed: {e}", file=sys.stderr)

    # Sort by engagement: upvotes + comments weighted
    items.sort(key=lambda x: x["score"] + x["comments"] * 2, reverse=True)
    return items


# ---------------------------------------------------------------------------
# Load today's top AI trend
# ---------------------------------------------------------------------------

def load_top_ai_trend() -> dict:
    path = os.path.join(SCRIPT_DIR, "trends.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
        title_match   = re.search(r"Title: (.+?) \|\| Insight:", first_line)
        insight_match = re.search(r"Insight: (.+?) \|\| Link:", first_line)
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
        "很多人看到 AI 抢走工作、替代人类的新闻，第一反应是恐慌——我够不够好？我会不会被淘汰？"
        "但我在美国这几年发现，真正厉害的人遇到挫败，反应完全不一样。"
        "他们不问「我哪里不够好」，他们问「这件事告诉了我什么」。"
        "失败从来不是终点，它只是一次数据更新。真正会学习的人，把每次失败当成系统升级的机会，而不是定义自己的标签。"
        "给你一个今天可以做的事：找出你最近一次搞砸的事，写下它教了你什么。不是为了原谅自己，是为了真正提取价值。"
        "后面我还会聊，为什么那些在硅谷最能扛住压力的人，反而是最不怕失败的人。"
    ),
    "consistency": (
        "看到这条 AI 新闻，很多人又开始焦虑——是不是要马上学新技能、马上转型、马上行动？"
        "但我在美国观察到，真正赢在 AI 时代的人，不是反应最快的，是最能坚持的。"
        "有一句话我在斯坦福第一次听到：Consistency beats intensity every single time. 短时间的爆发，赢不过长时间的稳定积累。"
        "你不需要今天就掌握所有新工具。你需要的，是每天哪怕只做一件小事，然后不停下来。"
        "复利的起点，不是你今天学了多少，是你明天还愿意继续。"
        "给你一个最小行动：今天选一件跟 AI 相关的事，做 15 分钟，明天再做 15 分钟。先把习惯建起来，能力自然跟上。"
    ),
    "fear": (
        "这条新闻出来，很多人的第一反应是害怕。害怕被取代，害怕跟不上，害怕做错选择。"
        "我在美国念书的时候，有个导师跟我说过一句话：Fear is just excitement without breath. 恐惧和兴奋，其实是同一种能量，只是你怎么解读它。"
        "我见过太多人，因为怕输所以不敢开始，因为怕错所以一直等待，因为怕后悔所以什么都不改变。"
        "但真正值得害怕的，不是你做了一个错误决定，而是五年后回头看，发现自己原地踏步。"
        "给你一个问题：你现在最怕的那件事，如果你不怕，你会怎么做？先把这个答案想清楚，再决定下一步。"
    ),
    "comparison": (
        "每次看到 AI 的新突破，很多人不是好奇，是焦虑——别人已经在用了，我是不是落后了？"
        "我在美国这几年，见过最多的一种痛苦，不是失败，是比较。"
        "LinkedIn 上所有人看起来都在赢，朋友圈里所有人好像都比你进展快。但你看到的，永远是别人的精选集，不是完整的人生。"
        "有一句话我反复想到：你不是在跟别人赛跑，你是在跟上个月的自己比。"
        "真正的进步感，不来自超过某个人，来自你知道自己在往哪走，而且在走。"
        "给你一个今天的练习：列出三件比三个月前的你进步了的事，不管多小。先找到自己的轨迹，再谈方向。"
    ),
    "focus": (
        "AI 时代信息爆炸，每天都有新工具、新模型、新机会。很多人越学越乱，越看越焦虑，根本静不下来。"
        "我在美国读书的时候，有一个发现改变了我——最高效的人，不是处理信息最快的，是最敢忽略信息的。"
        "Cal Newport 有本书叫 Deep Work，核心就一句话：你能专注多久，决定你能走多远。"
        "AI 把浅层工作自动化了，但它替代不了深度思考的能力。恰恰相反，越是 AI 时代，专注的人越稀缺，也越值钱。"
        "给你一个今天可以做的事：关掉所有通知，找一件最重要的事，做 90 分钟不中断。就这一件事，先把它做完。"
    ),
    "identity": (
        "看到 AI 又一次突破，很多人开始怀疑——我能做什么？AI 做不了什么？我的价值在哪？"
        "这个问题，我在美国见过很多聪明人都在问。但我发现，真正想清楚这个问题的人，不是靠找答案找到的，是靠先确定「我是谁」找到的。"
        "你不需要先弄清楚 AI 能做什么，才能决定自己做什么。你需要先知道自己真正看重什么、擅长什么，然后用 AI 放大它。"
        "工具会变，但你对世界的判断、你的审美、你对人的理解——这些是 AI 学不走的。"
        "给你一个问题带回去想：如果明天 AI 能做你所有的工作，你最想做什么？那个答案，可能才是你真正的方向。"
    ),
    "growth": (
        "每次看到 AI 的新进展，很多人的感受是焦虑，但我见过另一类人——他们的感受是兴奋。"
        "不是因为他们不担心，是因为他们早就接受了一件事：成长本来就是不舒服的。"
        "在常青藤读书的时候，我观察到一个规律：真正进步快的人，不是最聪明的，是最愿意「先难受再成长」的。"
        "Growth mindset 这个词被说烂了，但它的核心只有一句话：你相不相信，你今天不会的东西，明天可以会。"
        "AI 时代最大的机会，不是给那些已经很厉害的人，是给那些愿意持续学习的人。"
        "给你一个今天的行动：找一件你一直觉得「太难了先放着」的事，今天花 20 分钟开始。不是要做完，是要开始。"
    ),
    "money": (
        "AI 抢工作的新闻，让很多人开始担心收入、担心未来、担心钱的问题。"
        "我在美国这些年，观察过很多不同收入层级的人，发现一件反直觉的事——真正有钱的人，不是最会赚钱的，是最不把安全感寄托在钱上的。"
        "Morgan Housel 在《金钱心理学》里说：财富的本质不是数字，是选择权。你有多少自由决定怎么用自己的时间，才是真正的富有。"
        "AI 时代会让一部分工作的收入降低，但也会让另一部分人的杠杆变大。关键不是你现在赚多少，是你在建立哪种不可替代的价值。"
        "给你一个问题：你现在做的事，五年后会因为 AI 变得更值钱，还是更不值钱？先把这个想清楚，再谈怎么赚钱。"
    ),
    "career": (
        "这条 AI 新闻一出，职场人最怕的问题又来了——我的工作还有多久？"
        "我在美国接触过很多在大厂工作的人，发现真正不焦虑的，不是职位最稳的，而是那些「离开这家公司也能活得很好」的人。"
        "真正的职业安全感，不来自你在哪家公司，来自你有什么能力是市场一直需要的。"
        "AI 会替代的，是流程性的工作。它替代不了的，是你对问题的判断、对人的理解、和你把事情做成的能力。"
        "给你一个今天可以想的问题：你现在工作里最核心的技能，是流程性的，还是判断性的？如果是前者，现在就该开始转型了。"
    ),
    "relationships": (
        "AI 越来越强，有一件事反而变得更值钱了——真正的人与人之间的连接。"
        "我在美国观察到，那些在 AI 时代走得最快的人，几乎无一例外都有很强的人脉网络。不是那种加了很多好友的，是真正能打一个电话、对方愿意帮忙的那种。"
        "有一句话说：Your network is your net worth. 但很多人理解错了，以为是要认识厉害的人。真正的意思是，你愿意为别人创造价值，才会有人在你需要的时候出现。"
        "AI 可以替代你发邮件、做 PPT、写报告，但它替代不了你跟人建立真实信任的能力。"
        "给你一个今天可以做的事：给一个你许久没联系的人发一条消息，不是为了要什么，就是真诚问一句最近怎么样。先付出，再谈回报。"
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

def send_to_zapier(option_1: str, option_2: str):
    payload = json.dumps({
        "option_1":  option_1,
        "option_2":  option_2,
        "avatar_id": HEYGEN_AVATAR_ID,
        "date":      datetime.now(timezone.utc).strftime("%Y-%m-%d"),
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
    print("Fetching trending mindset posts from Reddit...")
    posts = fetch_reddit_mindset()
    print(f"  Found {len(posts)} posts across {MINDSET_SUBREDDITS}")

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
    status = send_to_zapier(script_1, script_2)
    print(f"Done. Status: {status}")


if __name__ == "__main__":
    main()
