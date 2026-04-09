#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fitness_pipeline.py — Scrape trending health/fitness/longevity content from X,
generate 2 Chinese short-form video scripts with personal IP,
and push to Zapier → HeyGen.

Runs every other day (odd days — opposite of mindset_pipeline).
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

ZAPIER_WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/26951471/u7ivsg7/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# ---------------------------------------------------------------------------
# X (Twitter) health/fitness/longevity accounts via Nitter RSS
# ---------------------------------------------------------------------------

X_FITNESS_ACCOUNTS = [
    ("hubermanlab",    "https://nitter.net/hubermanlab/rss"),
    ("bryan_johnson",  "https://nitter.net/bryan_johnson/rss"),
    ("foundmyfitness", "https://nitter.net/foundmyfitness/rss"),
    ("PeterAttiaMD",   "https://nitter.net/PeterAttiaMD/rss"),
    ("DrAndyGalpin",   "https://nitter.net/DrAndyGalpin/rss"),
    ("maxlugavere",    "https://nitter.net/maxlugavere/rss"),
    ("SolBrah",        "https://nitter.net/SolBrah/rss"),
    ("biolayne",       "https://nitter.net/biolayne/rss"),
    ("BradStanfieldMD","https://nitter.net/BradStanfieldMD/rss"),
    ("drchatterjeeuk", "https://nitter.net/drchatterjeeuk/rss"),
]

# Keywords: health, fitness, longevity, nutrition, sleep, recovery
FITNESS_KEYWORDS = [
    "health", "healthy", "fitness", "workout", "exercise", "train",
    "muscle", "strength", "cardio", "run", "lift", "squat", "deadlift",
    "sleep", "recovery", "rest", "stress", "cortisol", "hormone",
    "longevity", "aging", "lifespan", "healthspan", "biohack",
    "nutrition", "diet", "protein", "fasting", "intermittent",
    "supplement", "vitamin", "creatine", "omega", "magnesium",
    "testosterone", "dopamine", "serotonin", "insulin", "glucose",
    "body fat", "lean", "weight", "obesity", "metabol",
    "heart", "brain", "gut", "immune", "inflammation",
    "cold plunge", "sauna", "sunlight", "circadian", "breathe",
    "mental health", "anxiety", "depression", "mindful", "meditat",
    "posture", "mobility", "flexibility", "stretch", "yoga",
    "cancer", "diabetes", "disease", "blood pressure", "cholesterol",
    "water", "hydrat", "alcohol", "sugar", "processed",
    "walk", "steps", "zone 2", "vo2", "hiit",
]


def fetch_x_fitness() -> list[dict]:
    """Fetch health/fitness/longevity posts from X influencers via Nitter RSS."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
    items = []
    for account_name, feed_url in X_FITNESS_ACCOUNTS:
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
                if title.lower().startswith("rt by @"):
                    continue
                if len(desc_clean) < 50:
                    continue
                combined = desc_clean.lower()
                hits = sum(1 for kw in FITNESS_KEYWORDS if kw in combined)
                if hits < 1:
                    continue
                items.append({
                    "title":    desc_clean[:150].split("\n")[0],
                    "text":     desc_clean[:400],
                    "score":    hits,
                    "source":   f"X @{account_name}",
                })
        except Exception as e:
            print(f"[WARN] X @{account_name} failed: {e}", file=sys.stderr)

    items.sort(key=lambda x: x["score"], reverse=True)
    return items


# ---------------------------------------------------------------------------
# Theme detection
# ---------------------------------------------------------------------------

THEME_KEYWORDS = {
    "sleep":       ["sleep", "insomnia", "circadian", "melatonin", "rest", "nap", "tired", "fatigue"],
    "nutrition":   ["diet", "protein", "fasting", "carb", "calorie", "nutrition", "eat", "food", "meal", "sugar", "processed"],
    "training":    ["workout", "train", "exercise", "muscle", "strength", "squat", "lift", "cardio", "hiit", "zone 2"],
    "longevity":   ["longevity", "aging", "lifespan", "healthspan", "telomere", "autophagy", "biohack", "bryan johnson"],
    "stress":      ["stress", "cortisol", "burnout", "anxiety", "overwhelm", "mental health", "relax", "calm"],
    "recovery":    ["recovery", "stretch", "mobility", "sauna", "cold plunge", "ice bath", "massage", "foam roll"],
    "supplement":  ["supplement", "vitamin", "creatine", "omega", "magnesium", "zinc", "vitamin d", "fish oil"],
    "hormone":     ["testosterone", "hormone", "dopamine", "serotonin", "insulin", "glucose", "thyroid", "estrogen"],
    "weight":      ["weight", "fat loss", "body fat", "lean", "obesity", "metabolism", "cut", "bulk"],
    "habit":       ["habit", "routine", "consistency", "discipline", "morning", "daily", "ritual", "mindful"],
}

THEME_ORDER = list(THEME_KEYWORDS.keys())


def detect_theme(title: str, text: str) -> str:
    combined = (title + " " + text).lower()
    scores = {
        theme: sum(1 for kw in kws if kw in combined)
        for theme, kws in THEME_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "training"


# ---------------------------------------------------------------------------
# News hook — 全中文，最多保留 1-2 个英文专有名词
# ---------------------------------------------------------------------------

NEWS_HOOKS = [
    # 睡眠
    (["sleep", "insomnia", "circadian", "melatonin"],
     "一条关于睡眠的研究刚刚火了。"
     "睡眠是身体修复的底层代码，睡不好的人，练得再狠、吃得再干净都白搭。"),
    # 营养/饮食
    (["diet", "protein", "fasting", "nutrition", "food", "sugar", "processed"],
     "一条关于饮食的消息刚刚在健康圈炸了。"
     "吃什么、怎么吃、什么时候吃——这三件事搞对了，比吃任何补剂都管用。"),
    # 训练
    (["workout", "exercise", "muscle", "strength", "squat", "lift", "cardio", "hiit"],
     "一条关于训练的新发现刚刚引爆了健身圈。"
     "很多人练了几年，效果不如别人练几个月。差距往往不在努力程度，在方法。"),
    # 长寿/抗衰
    (["longevity", "aging", "lifespan", "healthspan", "biohack", "bryan johnson"],
     "长寿圈又出了一个让人震惊的研究。"
     "活得久不是目的，活得久还活得好，才是真正的赢。"),
    # 压力/心理
    (["stress", "cortisol", "burnout", "anxiety", "mental health"],
     "一条关于压力的真相刚刚被揭开了。"
     "压力不是敌人，不会管理压力才是。你的身体一直在给你信号，只是你没听懂。"),
    # 恢复
    (["recovery", "sauna", "cold plunge", "ice bath", "stretch", "mobility"],
     "一条关于身体恢复的新发现刚刚火了。"
     "会练的是徒弟，会恢复的才是师傅。你身体的进步，百分之八十发生在你不练的时候。"),
    # 补剂
    (["supplement", "vitamin", "creatine", "omega", "magnesium"],
     "一条关于补剂的消息让健康圈吵翻了。"
     "补剂这个东西，用对了是加速器，用错了就是交智商税。"),
    # 激素
    (["testosterone", "hormone", "dopamine", "insulin", "glucose"],
     "一条关于激素的研究刚刚爆了。"
     "激素是你身体的操作系统。睡眠、饮食、训练——归根到底都在调节这套系统。"),
    # 体重/体脂
    (["weight", "fat", "lean", "obesity", "metabol"],
     "一条关于体脂的真相刚刚被扒出来了。"
     "减脂这件事，百分之九十的人方法都是错的。不是吃得少就能瘦，是吃得对才能瘦。"),
    # 习惯
    (["habit", "routine", "consistency", "discipline", "morning", "ritual"],
     "一条关于健康习惯的分享刚刚火了。"
     "健康不是某一天的决定，是每天重复的那些小事。方向对了，时间会替你做剩下的事。"),
]

DEFAULT_NEWS_HOOK = (
    "一条健康领域的消息刚刚在全网引发讨论。"
    "这件事看起来是专业话题，但拆开来看，跟你每天的精力、体能、状态都有关系。"
)


def _make_news_section(post: dict) -> str:
    """生成健康新闻 hook 段落。"""
    text = (post["title"] + " " + post.get("text", "")).lower()

    best_template = DEFAULT_NEWS_HOOK
    best_hits = 0
    for keywords, template in NEWS_HOOKS:
        hits = sum(1 for kw in keywords if kw in text)
        if hits > best_hits:
            best_hits = hits
            best_template = template

    return best_template


# ---------------------------------------------------------------------------
# Script bodies — 转折 → 个人IP → 观点 → 行动
# 个人IP：快30岁，身材好，中美背景，到处飞，高强度工作
# ---------------------------------------------------------------------------

FITNESS_BODIES = {
    "sleep": (
        "这条消息让我特别有感触，因为睡眠是我踩过最大的坑。"
        "以前我觉得少睡点没什么，反正年轻、体力好、到处飞也能扛。但真实情况是：睡眠不够的时候，训练效果直接减半，注意力碎成渣，开会的时候脑子像在水里游泳。"
        "后来我开始严格控制睡眠：不管在哪个时区，睡前一小时不看手机，卧室温度调低，固定时间上床。"
        "就这几个小调整，体脂降了，力量涨了，白天的精力完全不是一个级别。"
        "快三十岁了我才真正明白：睡眠不是浪费时间，是你身体最强的修复工具。你不给它时间修，它就带着伤替你扛，迟早会崩。"
        "今天试一件事：今晚比平时早睡三十分钟。就这一个改变，坚持一周，你会感觉自己像换了一个人。"
    ),
    "nutrition": (
        "说到吃这件事，我走过的弯路可能比大多数人都多。"
        "在美国长大，从小被快餐文化包围。后来开始健身，又经历了一段什么都计算卡路里、疯狂吃鸡胸肉的阶段。"
        "真正让我想明白的是：饮食不是数学题，是一套跟你身体长期合作的系统。"
        "现在我的原则很简单——吃真正的食物，优质蛋白质每餐都有，加工食品能不碰就不碰。到处飞的时候，宁可少吃一顿也不随便对付。"
        "快三十了，代谢已经不是二十出头的时候了。你吃进去的每一口，要么在帮你，要么在拖你。"
        "今天做一件事：把你这周吃的最多的三样加工食品找出来，想想能不能换成真正的食物。这个小改变，三个月后你会感谢自己。"
    ),
    "training": (
        "关于训练这件事，我有一个可能跟大多数人不一样的经历。"
        "我练过泰拳、练过力量、也做过长距离有氧。到处飞的生活让我不得不学会一件事——在任何条件下都能练。"
        "酒店房间、公园、甚至机场候机楼，我都练过。器材不是借口，时间也不是借口。"
        "快三十岁了，我发现训练最重要的不是练什么，是持续。一周练两次坚持全年，比一周练六次坚持两个月强一百倍。"
        "而且高强度工作的时候，训练不是消耗精力，是充电。每次练完，脑子反而更清醒，决策也更果断。"
        "今天给你一个最简单的起步：做二十个深蹲，不需要任何器材。就现在，站起来做。动起来的人，和想着要动的人，差距就是从这二十个深蹲开始的。"
    ),
    "longevity": (
        "长寿这个话题，我以前觉得离自己很远。快三十岁之后，想法完全变了。"
        "不是怕死，是我意识到：如果未来几十年我还想保持现在的精力、体力和清醒度，现在就得开始投资。"
        "我每年做一次全面体检，会看自己的血糖、炎症指标、激素水平。不是焦虑，是把身体当成一家公司来管理——你得看数据，才知道哪里需要优化。"
        "在中国和美国两边跑，我见过太多四五十岁的成功人士，事业巅峰但身体已经垮了。钱赚到了，但没有体力去享受。"
        "真正的长寿不是活得久，是每一年都活得有质量。"
        "今天做一件事：如果你超过半年没体检了，现在就预约一次。你的身体可能正在给你发信号，只是你还没听到。"
    ),
    "stress": (
        "压力这个东西，我太熟了。"
        "中美两边跑、高强度的工作节奏、时差、谈判、deadline——如果不会管理压力，我早就废了。"
        "以前我的方式是硬扛。后来身体给了我一个很明确的信号：睡不着、脾气变差、训练没劲。那不是因为我不够努力，是因为皮质醇爆表了。"
        "现在我有几个铁打的规矩：每天至少二十分钟完全不看手机；每周有一天彻底不工作；压力大的时候先动起来，不要躺着想。"
        "快三十岁了，我越来越相信一件事：管理压力不是软弱，是最硬核的自我管理。你的身体是你最重要的资产，别把它当消耗品。"
        "今天试一件事：找二十分钟，关掉所有通知，去外面走一走。不带目的，不听播客，就走。你的大脑需要这段空白。"
    ),
    "recovery": (
        "说到恢复，这是我踩过最久的坑。"
        "以前觉得练得越多越好，休息就是偷懒。结果呢？越练越累，关节开始疼，力量不涨反降。"
        "后来我学到了一个观念彻底改变了我：训练是破坏，恢复才是建设。你的肌肉不是在健身房里长的，是在你休息的时候长的。"
        "现在我每周至少一天完全不练，睡够八小时，到处飞的时候会做拉伸和呼吸练习。"
        "快三十了，恢复能力确实不如二十出头。但这不是坏事——它逼着你变聪明，逼着你学会听身体的信号。"
        "今天做一件事：如果你已经连续练了三天以上，明天休息一天。不是偷懒，是让身体把你的努力变成真正的进步。"
    ),
    "supplement": (
        "补剂这个话题，我聊起来可能会得罪一些人。"
        "因为真相是：百分之九十的补剂，对大多数人来说都没必要。"
        "我自己只吃几样东西：肌酸、鱼油、维生素D、镁。都是有大量研究支持的，不贵，也不玄乎。"
        "在美国，补剂市场是一个几百亿美元的产业，营销做得特别好。但你要知道，补剂的意思是「补充」——它补的是你饮食里缺的那一块，不是替代真正的食物。"
        "快三十了，我的原则是：先把睡眠、饮食、训练搞好，这三样是地基。地基不稳，吃再贵的补剂也是往沙子上盖房子。"
        "今天做一件事：看看你现在在吃的补剂，查一下有没有靠谱的研究支持。没有的，可以考虑停掉，把钱省下来买真正的好食物。"
    ),
    "hormone": (
        "激素这个话题，很多人觉得离自己很远。但其实你的精力、情绪、体脂、甚至决策能力，全都跟激素有关。"
        "我自己每年会查一次激素水平。不是因为焦虑，是因为这些数据能告诉你很多——你最近睡够了吗？压力是不是太大了？训练方式对不对？"
        "快三十岁，睾酮水平开始自然下降，这是事实。但下降的速度你可以控制——力量训练、充足睡眠、控制体脂、减少酒精，这四件事做到了，你的激素水平会比大多数同龄人好很多。"
        "在中美两边高强度工作，我最大的感受是：当你的激素系统健康的时候，你处理压力、做判断、保持专注的能力完全不一样。"
        "今天做一件事：如果你从来没查过自己的激素水平，预约一次检查。了解自己身体的底层数据，是最值得的健康投资。"
    ),
    "weight": (
        "关于体重和体脂，我想说一个很多人不愿意听的真相。"
        "减脂不是靠少吃，是靠吃对。我见过太多人疯狂节食，体重确实掉了，但掉的是肌肉，体脂率反而没变。"
        "我自己常年保持比较低的体脂，不是因为天赋好，是因为我搞清楚了几个底层逻辑：蛋白质摄入够不够、训练有没有力量训练、睡眠质量怎么样。"
        "到处飞、高强度工作，很容易让人乱吃。但我有一个铁的规矩：不管多忙，每顿饭必须有优质蛋白质。这一条守住了，其他都好说。"
        "快三十了，新陈代谢确实在变。但变的不是你控制不了的部分，是你愿不愿意更聪明地对待自己的身体。"
        "今天做一件事：算一下你昨天吃了多少克蛋白质。如果不到体重公斤数乘以一点六，那你可能一直在亏待自己的肌肉。"
    ),
    "habit": (
        "健康习惯这件事，我的经验是——不要追求完美，追求可持续。"
        "我试过各种极端的方案：严格生酮、断碳水、每天五点起床、冷水澡。有些有用，但大多数坚持不了两周。"
        "后来我想明白了一件事：最好的习惯不是最科学的那个，是你能坚持一辈子的那个。"
        "现在我的日常很简单：每天动一下（哪怕只有二十分钟）、每顿有蛋白质、睡前不看手机、每周有一天彻底休息。"
        "在中美两边跑、时差不断切换的生活里，这套系统帮我保持了稳定的体能和精力。不是因为它完美，是因为它够简单，简单到在任何情况下都能执行。"
        "今天做一件事：选一个你想养成的健康习惯，把它简化到不可能失败的程度。比如「每天做五个俯卧撑」。先做到，再做好。"
    ),
}


# ---------------------------------------------------------------------------
# CTA — 每个 theme 有独特的社群引导，不重复、有吸引力
# ---------------------------------------------------------------------------

FITNESS_CTAS = {
    "sleep": (
        "我在老王的社群里，每天会晒我的睡眠数据——深睡时长、心率变异性、入睡效率，全部可视化。"
        "你能看到我在不同时区、不同工作强度下，怎么把睡眠质量稳定在高水平。"
        "不是鸡汤，是真实数据。想跟我一起用数据优化自己的身体，评论区见。"
    ),
    "nutrition": (
        "我在老王的社群里，每天会发我当天吃了什么——每一餐的搭配、蛋白质克数、热量分布，全部拍照加数据。"
        "不管我在纽约、上海还是东京，你都能看到我怎么在不同环境下保持饮食标准。"
        "不是食谱，是一个活人在真实生活中的饮食系统。想看的，评论区加入。"
    ),
    "training": (
        "我在老王的社群里，每天更新我的训练计划——动作、组数、重量、心率，全部记录。"
        "出差在酒店怎么练、时间紧怎么练、状态差怎么调整——这些真实场景你在任何教程里都找不到。"
        "想拿到我的训练模板，跟着一起练，评论区见。"
    ),
    "longevity": (
        "我在老王的社群里，会定期分享我的体检数据和健康指标——血糖、炎症、激素、心肺功能，全部透明公开。"
        "你能看到一个快三十岁、全球到处飞的人，怎么用数据管理自己的身体。"
        "把身体当产品来迭代，这是我正在做的事。想一起做的，评论区加入。"
    ),
    "stress": (
        "我在老王的社群里，会分享我每天的压力管理方法——心率变异性数据、恢复评分、还有我自己摸索出来的减压流程。"
        "高强度工作不是问题，不会管理高强度才是问题。"
        "想看一个真实的高压生活怎么保持不崩，评论区见。"
    ),
    "recovery": (
        "我在老王的社群里，每周会更新我的恢复数据——训练负荷、恢复评分、睡眠质量，三个维度交叉对比。"
        "你能直接看到什么时候该推、什么时候该停，不靠感觉，靠数据。"
        "想把你的恢复也变成可视化的系统，评论区加入。"
    ),
    "supplement": (
        "我在老王的社群里，会公开我每天吃的所有补剂——品牌、剂量、时间、为什么吃，全部透明。"
        "不带货、不推销，就是一个真实用户的真实记录。哪个有用哪个没用，数据说话。"
        "想看我的补剂清单和效果追踪，评论区见。"
    ),
    "hormone": (
        "我在老王的社群里，会分享我的激素检测报告和优化方案——睾酮、皮质醇、胰岛素，每个指标怎么调。"
        "这些数据大多数人一辈子都没看过，但它们决定了你百分之八十的状态。"
        "想了解自己身体的底层操作系统，评论区加入。"
    ),
    "weight": (
        "我在老王的社群里，每周会更新我的体成分数据——体脂率、肌肉量、内脏脂肪，全部可视化追踪。"
        "你能看到我在不同饮食和训练方案下，身体是怎么一点一点变化的。不是修图，是真实数据。"
        "想跟我一起用数据减脂增肌，评论区见。"
    ),
    "habit": (
        "我在老王的社群里，每天会打卡我的健康习惯——训练、饮食、睡眠、压力管理，四个维度全部量化。"
        "你能看到一个在全球到处飞的人，怎么在最不稳定的生活里维持最稳定的习惯系统。"
        "想建立你自己的健康系统，跟一群认真的人一起做，评论区加入。"
    ),
}

DEFAULT_CTA = (
    "我在老王的社群里，每天分享我的训练、饮食、睡眠数据——全部透明、全部可视化。"
    "不是教你该怎么做，是让你看到一个真实的人每天在怎么做。"
    "想加入的，评论区见。"
)


# ---------------------------------------------------------------------------
# Script generator
# ---------------------------------------------------------------------------

def generate_script(post: dict, theme: str) -> str:
    news = _make_news_section(post)
    body = FITNESS_BODIES.get(theme, FITNESS_BODIES["training"])
    cta = FITNESS_CTAS.get(theme, DEFAULT_CTA)
    return f"{news}{body}{cta}"


# ---------------------------------------------------------------------------
# Send to Zapier
# ---------------------------------------------------------------------------

def send_to_zapier(script: str):
    payload = json.dumps({"content": script}).encode("utf-8")
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
    print("Fetching trending health/fitness posts from X...")
    posts = fetch_x_fitness()
    print(f"  Found {len(posts)} posts from fitness/health accounts")

    if not posts:
        print("[WARN] No fitness posts found. Using fallback.", file=sys.stderr)
        posts = [{"title": "健康是最好的投资", "text": "health longevity fitness", "score": 1, "source": "fallback"}]

    # Detect themes, ensure 2 different themes
    used_themes = set()
    selected = []
    for post in posts:
        theme = detect_theme(post["title"], post["text"])
        if theme not in used_themes:
            selected.append((post, theme))
            used_themes.add(theme)
        if len(selected) == 2:
            break

    # Fallback
    if len(selected) < 2:
        day = datetime.now(timezone.utc).timetuple().tm_yday
        fallback_themes = [t for t in THEME_ORDER if t not in used_themes]
        while len(selected) < 2 and fallback_themes:
            theme = fallback_themes.pop(day % len(fallback_themes) if fallback_themes else 0)
            selected.append(({"title": theme, "text": "", "score": 0, "source": "fallback"}, theme))

    (post_1, theme_1), (post_2, theme_2) = selected[0], selected[1]

    print(f"\n  Option 1: theme={theme_1}  source={post_1.get('source','fallback')}")
    print(f"  Option 2: theme={theme_2}  source={post_2.get('source','fallback')}")

    script_1 = generate_script(post_1, theme_1)
    script_2 = generate_script(post_2, theme_2)

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
