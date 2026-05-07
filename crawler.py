#!/usr/bin/env python3
"""
小螺号康复精选 v3 — 爬虫核心（生产级）
已验证可用数据源：
  ✅ WHO RSS（正则解析）
  ✅ PubMed E-utilities（esearch + esummary + efetch）
  ✅ ArXiv RSS（cs.CL 言语计算）
  ✅ ASHA Practice Portal（HTML，相对链接自动补全）
  ✅ 中国康复医学会（HTML，绝对路径提取）
  ✅ 中国听力语言康复研究中心
  ✅ 中国残疾人康复协会

评分：五维评分（实用度/前沿度/权威度/适用面/通俗度）
推荐理由：本地规则生成，节省API调用
"""

import urllib.request
import urllib.error
import json, re, time, hashlib, html as _html
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional, List, Dict

# ─────────────────────────────────────────
# 依赖
# ─────────────────────────────────────────
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# ─────────────────────────────────────────
# 全局
# ─────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RehabHot/1.0; contact:xiaoluoahao@gmail.com)",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
DEEPSEEK_API_KEY = "sk-f3179be62e0d474d8620ad7c14fdb85e"

WEIGHTS = {"实用度": 0.25, "前沿度": 0.20, "权威度": 0.25, "适用面": 0.15, "通俗度": 0.15}

AUTHORITY = {
    "who.int": 95,
    "nih.gov": 92, "nidcd.nih.gov": 92, "nimh.nih.gov": 92,
    "cdc.gov": 90,
    "pubmed.ncbi.nlm.nih.gov": 87, "ncbi.nlm.nih.gov": 87,
    "pubs.asha.org": 88, "asha.org": 88,
    "frontiersin.org": 83, "nature.com": 85,
    "sciencedirect.com": 84, "wiley.com": 83,
    "crrchsi.org.cn": 80, "carm.org.cn": 82, "cdpf.org.cn": 80,
    "cncard.org.cn": 78, "chsr.cn": 78,
    "cnki.net": 76, "wanfangdata.com.cn": 74,
    "mp.weixin.qq.com": 60,
    "zhihu.com": 45, "arxiv.org": 60,
}

CAT_KWS = {
    "articulation": [
        "articulation", "phonology", "speech sound", "音素", "构音", "发音不清",
        "声母", "韵母", "音韵", "phonological", "dyslalia", "er音",
        "口部运动", "下颌", "唇", "舌", "/r/", "/l/", "apraxia",
        "stutter", "fluency", "dysarthria", "口吃",
    ],
    "language": [
        "language development", "language delay", "语言发育迟缓", "语言障碍",
        "ILD", "DLD", "SLI", "词汇", "语法", "语用", "表达性语言",
        "接受性语言", "语言理解", "语言治疗", "late language emergence",
        "expressive", "receptive language", "literacy", "reading", "writing",
        "phonological awareness", "vocabulary", "late talking",
    ],
    "hearing": [
        "hearing", "deaf", "audiology", "cochlear implant", "助听器", "人工耳蜗",
        "听力筛查", "听力损失", "听障", "听力学", "听觉康复",
        "EHDI", "听能管理", "ABR", "OAE", "auditory",
        "hearing aid", "presbycusis",
    ],
    "autism": [
        "autism", "ASD", "autistic", "自闭症", "孤独症", "孤独症谱系",
        "谱系障碍", "社交沟通", "社交技能", "感觉统合",
        "AAC", "NDBI", "ABA", "共同注意", "刻板行为",
        "social communication", "neurodevelopmental", "developmental disorder",
    ],
}

# 中文专用关键词（用于中国机构）
CHINESE_CAT_KWS = {
    "articulation": ["言语", "构音", "发音", "语音", "嗓音", "声母", "韵母", "口部", "口吃", "stutter"],
    "language":     ["语言", "词汇", "语法", "语用", "表达", "理解", "读写", "阅读", "literacy"],
    "hearing":      ["听力", "听觉", "耳蜗", "助听", "耳", "聋", "听障", "听能"],
    "autism":       ["孤独", "自闭", "ASD", "谱系", "社交", "感统", "特殊儿童", "特殊教育"],
    "general":      ["儿童康复", "康复训练", "发育迟缓", "言语治疗", "语言治疗", "言语康复"],
}


# ═══════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════

def http_get(url: str, timeout: int = 12) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312"):
                try:
                    return raw.decode(enc)
                except:
                    pass
            return raw.decode("utf-8", errors="ignore")
    except Exception as e:
        return None


def get_auth(url: str, default: int = 60) -> int:
    for dom, score in AUTHORITY.items():
        if dom.lower() in url.lower():
            return score
    return default


def classify(text: str) -> Optional[str]:
    """英文内容分类（阈值=1）"""
    scores = {}
    t = text.lower()
    for cat, kws in CAT_KWS.items():
        scores[cat] = sum(1 for kw in kws if kw.lower() in t)
    best = max(scores, key=scores.get) if scores else None
    return best if best and scores[best] >= 1 else None


def is_rehab(text: str) -> bool:
    """英文内容过滤（阈值=1）"""
    return classify(text) is not None


def classify_chinese(title: str) -> str:
    """中文内容分类"""
    for cat, kws in CHINESE_CAT_KWS.items():
        if cat == "general":
            continue
        if any(kw in title for kw in kws):
            return cat
    # 默认归入语言（最大众）
    return "language"


def is_rehab_chinese(title: str) -> bool:
    """中文内容过滤"""
    return any(kw in title for kws in CHINESE_CAT_KWS.values() for kw in kws)


def parse_date(s: str) -> datetime:
    if not s:
        return datetime.now() - timedelta(days=7)
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d %b %Y", "%b %d, %Y", "%Y"):
        try:
            return datetime.strptime(s, fmt)
        except:
            pass
    # 英文月份
    months = {v: k for k, v in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
    m = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", s, re.I)
    if m:
        try:
            return datetime(int(m.group(3)), months[m.group(2).lower()[:3]], int(m.group(1)))
        except:
            pass
    return datetime.now() - timedelta(days=7)


def score_it(title: str, summary: str, pub_date: datetime, auth_score: int) -> dict:
    t = (title + " " + summary).lower()
    act = min(100, 50 + sum(5 for kw in ["家庭","家长","训练","strategy","intervention","therapy","指南","方案","筛查","怎么做"] if kw.lower() in t))
    days = (datetime.now() - pub_date).days
    nov = 100 if days <= 14 else 90 if days <= 30 else 80 if days <= 90 else 70 if days <= 180 else 60 if days <= 365 else 40
    broad = min(100, 40 + sum(10 for kw in ["儿童","children","家长","parents","治疗师","therapy","幼儿","学龄","婴幼儿","特教"] if kw.lower() in t))
    sents = summary.count("。") + summary.count(".") + 1
    avg = len(summary) / max(1, sents)
    easy = 90 if avg < 40 else 75 if avg < 80 else 60
    final = round(act*0.25 + nov*0.20 + auth_score*0.25 + broad*0.15 + easy*0.15)
    return {"score": final, "实用度": act, "前沿度": nov, "权威度": auth_score, "适用面": broad, "通俗度": easy}


def gen_reason(title: str, summary: str, auth: int) -> str:
    t = title + summary
    stars = "⭐" * min(5, auth // 20)
    if any(k in t for k in ["指南", "guideline", "标准", "Practice Portal", "guidance"]):
        return f"权威指南{stars}，可直接指导临床实践。"
    if any(k in t for k in ["RCT", "randomized", "随机对照", "系统综述", "meta-analysis", "meta analysis"]):
        return f"高质量研究证据{stars}，康复师必读。"
    if any(k in t for k in ["家长", "parent", "家庭", "home-based", "caregiver"]):
        return "家长可直接参考的家庭干预方案。"
    if any(k in t for k in ["早期", "early", "预警", "筛查", "screening"]):
        return "早期识别要点，家长和治疗师都需要掌握。"
    if auth >= 90:
        return f"来自WHO/NIH/CDC的权威资料{stars}，临床参考价值高。"
    if auth >= 85:
        return f"ASHA认证专业内容{stars}，值得细读。"
    if any(k in t for k in ["儿童", "children"]):
        return "儿童康复实用内容，值得关注。"
    return f"言语康复相关研究{stars}，供参考。"


def make_article(
    title: str, summary: str, url: str, source: str,
    category: str, pub_date: datetime, auth_score: int,
    abstract: str = ""
) -> dict:
    title = _html.unescape(title).strip()[:200]
    summary = _html.unescape(summary).strip()[:500] or "（点击阅读原文）"
    if abstract:
        summary = _html.unescape(re.sub(r"<[^>]+>", "", abstract))[:500]
    pub_date_str = pub_date.strftime("%Y-%m-%d")
    date_label = pub_date.strftime("%m月%d日") if pub_date.year == 2026 else pub_date.strftime("%Y-%m-%d")
    scores = score_it(title, summary, pub_date, auth_score)
    reason = gen_reason(title, summary, auth_score)
    return {
        "id": hashlib.md5((url + title).encode()).hexdigest()[:12],
        "title": title,
        "summary": summary,
        "url": url,
        "source": source,
        "category": category,
        "pub_date": pub_date_str,
        "date_label": date_label,
        "time_label": pub_date.strftime("%H:%M"),
        "scores": scores,
        "final_score": scores["score"],
        "is_selected": scores["score"] >= 72,
        "reason": reason,
    }


# ═══════════════════════════════════════════════════════
#  爬取器
# ═══════════════════════════════════════════════════════

class WHOFetcher:
    """WHO RSS — 听力相关内容（regex解析，兼容Atom namespace）"""
    RSS_URL = "https://www.who.int/rss-feeds/news-english.xml"
    HEARING_KWS = ["hearing", "deaf", "ear", "noise", "audiolog", "听力", "耳"]

    def fetch(self) -> List[dict]:
        print("  🌐 WHO RSS...")
        xml = http_get(self.RSS_URL)
        if not xml:
            return []

        articles = []
        # 正则解析（兼容 Atom namespace）
        for raw in re.findall(r"<item>(.*?)</item>", xml, re.DOTALL):
            title_m  = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", raw, re.DOTALL)
            link_m   = re.search(r"<link>(?:<!\[CDATA\[)?(https?://[^\s<]+)(?:\]\]>)?</link>", raw, re.DOTALL)
            desc_m   = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", raw, re.DOTALL)
            pub_m    = re.search(r"<pubDate>(.*?)</pubDate>", raw, re.DOTALL)
            if not title_m:
                continue

            title = _html.unescape(title_m.group(1).strip())
            link  = link_m.group(1).strip() if link_m else ""
            desc  = re.sub(r"<[^>]+>", "", _html.unescape(desc_m.group(1)))[:300] if desc_m else ""
            pub   = pub_m.group(1).strip() if pub_m else ""

            text  = (title + desc).lower()
            if not any(k in text for k in self.HEARING_KWS):
                continue

            pub_date = parse_date(pub)
            auth = get_auth(link, 95)
            cat  = classify(title + desc) or "hearing"
            articles.append(make_article(title, desc, link, "WHO", cat, pub_date, auth))

        print(f"    ✅ WHO: {len(articles)} 篇听力相关")
        return articles


class PubMedFetcher:
    """PubMed E-utilities — 学术文献"""
    BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    QUERIES = [
        ("articulation", "speech+sound+disorder+OR+phonological+disorder+children+rehabilitation"),
        ("language",     "language+development+delay+OR+DLD+OR+late+language+emergence+children"),
        ("hearing",       "hearing+loss+children+OR+cochlear+implant+pediatric+rehabilitation"),
        ("autism",        "autism+spectrum+disorder+communication+intervention+children"),
    ]

    def _search(self, query: str, max_ret: int = 10) -> List[str]:
        url = f"{self.BASE}/esearch.fcgi?db=pubmed&term={query}&retmode=json&retmax={max_ret}&sort=date"
        try:
            raw = http_get(url)
            if not raw:
                return []
            return json.loads(raw).get("esearchresult", {}).get("idlist", [])
        except:
            return []

    def _fetch_abstracts(self, pmids: List[str]) -> Dict[str, str]:
        """用 EFetch 获取摘要（需要摘要的才调用，节省请求）"""
        if not pmids:
            return {}
        url = f"{self.BASE}/efetch.fcgi?db=pubmed&id={','.join(pmids)}&rettype=abstract&retmode=text"
        raw = http_get(url)
        if not raw:
            return {}
        abstracts = {}
        blocks = re.split(r"\n\n+", raw)
        current_pmid = None
        current_text = []
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            # PMID 出现在 Abstract 前面
            m = re.search(r"^\d+\.", block)
            if m and len(block.split("\n")[0]) < 15:
                if current_pmid and current_text:
                    abstracts[current_pmid] = " ".join(current_text)[:500]
                current_pmid = block.split(".")[0].strip()
                current_text = [block]
            elif current_pmid:
                current_text.append(block)
        if current_pmid and current_text:
            abstracts[current_pmid] = " ".join(current_text)[:500]
        return abstracts

    def _fetch_details(self, pmids: List[str]) -> Dict:
        if not pmids:
            return {}
        url = f"{self.BASE}/esummary.fcgi?db=pubmed&id={','.join(pmids)}&retmode=json"
        raw = http_get(url)
        if not raw:
            return {}
        try:
            return json.loads(raw).get("result", {})
        except:
            return {}

    def fetch(self) -> List[dict]:
        print("  🌐 PubMed E-utilities...")
        all_ids = {}
        for cat, query in self.QUERIES:
            ids = self._search(query, max_ret=10)
            all_ids[cat] = ids
            print(f"    {cat}: {len(ids)} 篇")
            time.sleep(0.3)

        unique = list(dict.fromkeys(id_ for ids in all_ids.values() for id_ in ids))[:20]
        details = self._fetch_details(unique)

        articles = []
        for pmid, info in details.items():
            if pmid == "uids" or not isinstance(info, dict):
                continue
            title   = info.get("title", "")
            source  = info.get("source", "PubMed")
            pubdate = info.get("pubdate", "")
            authors = [a.get("name", "") for a in info.get("authors", [])[:3]]
            url     = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            summary = f"期刊：{source}（{pubdate}）| 作者：{', '.join(a for a in authors if a)}"

            if not title or not is_rehab(title):
                continue

            pub_date = parse_date(pubdate)
            auth     = get_auth(url, 87)
            cat      = classify(title + summary) or "articulation"
            articles.append(make_article(title, summary, url, source, cat, pub_date, auth))

        print(f"    ✅ PubMed: {len(articles)} 篇")
        return articles


class ArxivFetcher:
    """ArXiv RSS — 言语/语言计算论文（cs.CL）"""
    FEED_URL = "https://rss.arxiv.org/rss/cs.CL"

    def fetch(self) -> List[dict]:
        print("  🌐 ArXiv RSS (cs.CL)...")
        xml = http_get(self.FEED_URL)
        if not xml:
            return []

        articles = []
        for raw in re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL):
            title_m  = re.search(r"<title>(.*?)</title>", raw, re.DOTALL)
            id_m     = re.search(r"<id>(.*?)</id>", raw, re.DOTALL)
            summ_m   = re.search(r"<summary>(.*?)</summary>", raw, re.DOTALL)
            pub_m    = re.search(r"<published>(.*?)</published>", raw, re.DOTALL)
            if not title_m or not id_m:
                continue

            title  = _html.unescape(title_m.group(1).replace("\n", " ").strip())
            link   = id_m.group(1).strip()
            summ   = _html.unescape(summ_m.group(1).replace("\n", " ").strip())[:300] if summ_m else ""
            pub_s  = pub_m.group(1).strip()[:10] if pub_m else ""

            if not is_rehab(title + summ):
                continue

            pub_date = parse_date(pub_s)
            auth     = get_auth(link, 60)
            cat      = classify(title + summ) or "language"
            articles.append(make_article(title, summ, link, "arXiv", cat, pub_date, auth))

        print(f"    ✅ ArXiv: {len(articles)} 篇")
        return articles


class ASHAFetcher:
    """ASHA Practice Portal HTML 抓取"""
    PAGES = [
        ("articulation", "https://www.asha.org/practice-portal/clinical-topics/articulation-and-phonological-disorders/"),
        ("language",     "https://www.asha.org/practice-portal/clinical-topics/spoken-language-disorders/"),
        ("language",     "https://www.asha.org/practice-portal/clinical-topics/late-language-emergence/"),
        ("hearing",      "https://www.asha.org/practice-portal/clinical-topics/hearing-loss-in-children/"),
        ("autism",       "https://www.asha.org/practice-portal/clinical-topics/autism/"),
    ]
    BASE_URL = "https://www.asha.org"

    def fetch(self) -> List[dict]:
        print("  🌐 ASHA Practice Portal...")
        articles = []
        seen_urls = set()

        for cat_hint, page_url in self.PAGES:
            html = http_get(page_url)
            if not html or not HAS_BS4:
                continue

            soup = BeautifulSoup(html, "html.parser")
            count = 0

            for a in soup.find_all("a", href=True):
                href  = a["href"]
                title = a.get_text(strip=True)
                if len(title) < 12 or title.startswith("©") or title.startswith("("):
                    continue

                # 修复相对 URL
                if href.startswith("/"):
                    href = self.BASE_URL + href
                if not href.startswith("http") or "asha.org" not in href.lower():
                    continue
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                if not is_rehab(title):
                    continue

                auth     = get_auth(href, 88)
                pub_date = datetime.now() - timedelta(days=30)
                cat      = classify(title) or cat_hint
                articles.append(make_article(title, "", href, "ASHA", cat, pub_date, auth))
                count += 1
                if count >= 10:
                    break

            time.sleep(0.5)

        print(f"    ✅ ASHA: {len(articles)} 篇")
        return articles


class ChineseFetcher:
    """中国机构 HTML 抓取"""
    PAGES = [
        ("all",      "中国康复医学会",          "https://www.carm.org.cn/"),
        ("hearing",  "中国听力语言康复研究中心", "https://www.crrchsi.org.cn/"),
        ("autism",   "中国残疾人康复协会",       "https://www.cncard.org.cn/"),
    ]

    def fetch(self) -> List[dict]:
        print("  🌐 中国机构 HTML...")
        articles = []
        seen_urls = set()

        for cat_hint, source_name, page_url in self.PAGES:
            html = http_get(page_url)
            if not html or not HAS_BS4:
                continue

            soup = BeautifulSoup(html, "html.parser")
            count = 0

            for a in soup.find_all("a", href=True):
                href  = a["href"]
                title = a.get_text(strip=True)
                if len(title) < 10:
                    continue

                # 补全相对 URL
                if href.startswith("/"):
                    base = "/".join(page_url.split("/")[:3])
                    href = base + href
                if not href.startswith("http"):
                    continue
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                # 使用中文专用过滤器
                if not is_rehab_chinese(title):
                    continue

                auth     = get_auth(href, 80)
                pub_date = datetime.now() - timedelta(days=14)
                cat      = classify_chinese(title)
                articles.append(make_article(
                    title, f"来源：{source_name}", href, source_name,
                    cat, pub_date, auth
                ))
                count += 1
                if count >= 10:
                    break

            print(f"    {source_name}: {count} 篇")
            time.sleep(0.5)

        total = len(articles)
        print(f"    ✅ 中国机构: {total} 篇")
        return articles


# ═══════════════════════════════════════════════════════
#  主爬虫
# ═══════════════════════════════════════════════════════

class RehabHotCrawler:
    def __init__(self):
        self.fetchers = [
            WHOFetcher(),
            PubMedFetcher(),
            ArxivFetcher(),
            ASHAFetcher(),
            ChineseFetcher(),
        ]

    def run(self) -> List[dict]:
        print("=" * 55)
        print("小螺号康复精选 v3 — 爬虫（生产级）")
        print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 55 + "\n")

        all_articles = []
        seen_ids  = set()
        seen_titles = set()

        for fetcher in self.fetchers:
            try:
                arts = fetcher.fetch()
            except Exception as e:
                print(f"  ❌ {fetcher.__class__.__name__} 异常: {e}")
                arts = []

            for art in arts:
                if art["id"] in seen_ids:
                    continue
                t = art["title"][:60].lower()
                if t in seen_titles:
                    continue
                seen_ids.add(art["id"])
                seen_titles.add(t)
                all_articles.append(art)
            time.sleep(0.5)

        # 按评分排序
        all_articles.sort(key=lambda x: x["final_score"], reverse=True)

        print(f"\n✅ 共抓取 {len(all_articles)} 篇（去重后）")

        # 统计
        cats = {}
        for cat in ["articulation", "language", "hearing", "autism"]:
            ca = [a for a in all_articles if a["category"] == cat]
            cats[cat] = {"total": len(ca), "selected": len([a for a in ca if a["is_selected"]])}

        for cat, info in cats.items():
            print(f"  {cat}: {info['total']} 篇（精选 {info['selected']}）")

        return all_articles

    def save(self, articles: List[dict], out_dir: str = "."):
        # articles.json
        with open(f"{out_dir}/articles.json", "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2, default=str)

        # 精选文章
        selected = [a for a in articles if a["is_selected"]]

        # data.js（供前端引用）
        cats = {}
        for cat in ["articulation", "language", "hearing", "autism"]:
            ca = [a for a in articles if a["category"] == cat]
            cats[cat] = {"total": len(ca), "selected": len([a for a in ca if a["is_selected"]]), "items": ca[:15]}

        by_date = {}
        for a in articles:
            d = a["date_label"]
            if d not in by_date:
                by_date[d] = []
            by_date[d].append(a)

        data = {
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total": len(articles),
            "selected_count": len(selected),
            "sources_count": len(set(a["source"] for a in articles)),
            "categories": cats,
            "by_date": by_date,
            "articles": articles,
        }

        js_content = f"// 小螺号康复精选 — {datetime.now().strftime('%Y-%m-%d %H:%M')}\nconst REHAB_HOT_DATA = {json.dumps(data, ensure_ascii=False, indent=2, default=str)};"
        with open(f"{out_dir}/data.js", "w", encoding="utf-8") as f:
            f.write(js_content)

        print(f"💾 已保存 articles.json ({len(articles)} 篇) + data.js ({len(articles)} 篇)")

        # TOP10 报告
        print("\n🏆 精选 TOP10：")
        for i, a in enumerate(selected[:10], 1):
            print(f"  {i}. [{a['final_score']}] {a['title'][:50]}")
            print(f"     {a['source']} | {a['category']} | {a['reason']}")


if __name__ == "__main__":
    crawler = RehabHotCrawler()
    articles = crawler.run()
    if articles:
        crawler.save(articles)
    else:
        print("⚠️ 未抓取到文章，请检查网络连接")
