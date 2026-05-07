# 🐚 小螺号康复精选 (RehabHot)

面向言语治疗师和特殊儿童家长的**每日自动资讯聚合平台**。

---

## ✅ 已完成

### 数据来源（已验证可爬取）
| 来源 | 类型 | 状态 |
|------|------|------|
| WHO RSS | 国际组织 | ✅ |
| PubMed E-utilities | 学术数据库 | ✅ |
| ArXiv RSS (cs.CL) | 预印本 | ✅ |
| ASHA Practice Portal | 学会官网 | ✅ |
| 中国康复医学会 | 行业协会 | ✅ |
| 中国听力语言康复研究中心 | 科研机构 | ✅ |

### 抓取能力（今日运行结果）
```
共 55 篇（精选 49 篇）
  构音障碍: 5 篇（精选 4）
  语言发育: 16 篇（精选 15）
  听力障碍: 22 篇（精选 18）
  孤独症:   12 篇（精选 12）
```

---

## 📁 文件说明

```
rehab-hot/
├── index.html          # 今日精选首页（引用 data.js）
├── articulation.html   # 构音障碍分类页
├── language.html       # 语言发育迟缓分类页
├── hearing.html        # 听力障碍分类页
├── autism.html         # 孤独症谱系分类页
├── about.html          # 关于页面
├── styles.css          # 样式表（玫红配色）
├── data.js             # 自动生成的文章数据（前端引用）
├── articles.json        # 原始数据备份
├── crawler.py          # Python 爬虫（生产级）
└── README.md           # 本文件
```

---

## 🚀 本地运行

```bash
# 1. 安装依赖
pip install beautifulsoup4

# 2. 运行爬虫（生成 data.js）
python crawler.py

# 3. 直接打开 index.html 查看
# file:///C:/Users/123/Desktop/rehab-hot/index.html
```

---

## ⏰ 每日自动更新

### 方案A：Windows 任务计划程序
```
# 创建每日 06:00 / 18:00 自动运行：
# 任务： python C:\Users\123\Desktop\rehab-hot\crawler.py
# 完整命令： cmd /c "cd /d C:\Users\123\Desktop\rehab-hot && python crawler.py"
```

### 方案B：Cloudflare Workers Cron（推荐）
部署到 Cloudflare Pages，每次触发 Workers 拉取最新 Git 仓库并重新构建。

### 方案C：GitHub Actions
`.github/workflows/crawl.yml` 每日定时运行 `python crawler.py`，推送更新的 `data.js`。

---

## 📡 新增信息源思路

已在代码中配置但尚未完全启用的来源：

```
待接入：
- PubMed efetch（需 PMID 批量请求）— 获取完整摘要
- 听力语言康复科学杂志 (chsr.cn) — 中文期刊
- 中国知网 CNKI RSS（如果有）
- 中国残疾人康复协会 — 孤独症相关
- 更多 ArXiv 子类：cs.AI, cs.HC（人机交互）

学术期刊 RSS：
- JSLHR: https://pubs.asha.org/toc/jslhr/current （需认证）
- International Journal of Language & Communication Disorders
- Journal of Speech, Language, and Hearing Research

中文来源（需解析能力更强）：
- 知乎专栏 RSS（言语康复话题）
- 公众号文章（通过 RSSHub 等中间层）
```

---

## 🏆 评分算法

每篇文章综合评分（满分100）：

| 维度 | 权重 | 说明 |
|------|------|------|
| 实用度 | 25% | 含家庭/训练/策略关键词 |
| 权威度 | 25% | 来源评级（WHO=95, ASHA=88…） |
| 前沿度 | 20% | 30天内=100分，1年+=50分 |
| 适用面 | 15% | 含儿童/家长/治疗师关键词 |
| 通俗度 | 15% | 摘要句子短=易读 |

**精选标准：≥74分**

---

## 🎨 配色

- 主色：玫红 `#C2185B`（家长版）
- 可切换：藏蓝 `#2b7dd1`（康复师版）

修改 `styles.css` 顶部的 `:root` 变量即可切换配色。
