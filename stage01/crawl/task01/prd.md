# 爬虫项目技术选型 PRD

> 评估日期：2026-06-09
> 项目：NLP-SCX 数据采集模块
> 目标：初始化 `stage01/crawl/task01` 爬虫项目

---

## 1. 2026 年 GitHub 热门 Python 爬虫框架评估

| 框架 | 2026 预计 Stars | 定位 | 趋势 | 适用场景 |
|------|----------------|------|------|---------|
| **Scrapy** | ~60k+ | 企业级全栈框架 | 稳定增长 | 大规模分布式采集 |
| **Crawlee Python** | ~40k+ | 现代化异步框架 | 🔥高速增长 | JS 重站点、反爬场景 |
| **DrissionPage** | ~20k+ | 反检测浏览器自动化 | 🔥国产黑马 | 严格反爬/中国站点 |
| **pyspider** | ~18k | 分布式脚本化框架 | ⬇维护放缓 | 小团队快速原型 |
| **Firecrawl** | ~12k+ | AI 智能提取 | 🔥新势力 | LLM 驱动的结构化提取 |

---

## 2. 各框架深度评估

### 2.1 Scrapy（~60k+ Stars）
- **架构**：Twisted 异步引擎，回调式设计
- **优势**：生态最完善，中间件/管道/信号系统成熟，文档丰富，社区庞大
- **劣势**：Twisted 非标准 async/await，学习曲线陡，项目结构重
- **爬虫适配度**：⭐⭐⭐⭐（过重，回调模型不够 Pythonic）

### 2.2 Crawlee Python（~40k+ Stars）🏆 首选
- **架构**：原生 async/await + httpx，async generator 模型
- **优势**：
  - 现代化 Python 异步，代码简洁
  - 内置 Playwright 集成（JS 渲染开箱即用）
  - 自动指纹生成 + 代理轮换（反爬核心能力）
  - Apify 公司维护，2026 增长最快的爬虫框架
  - 自动 `robots.txt` 遵守 + sitemap 解析
- **劣势**：生态较 Scrapy 小，部分文档仍以 JS 版为主
- **爬虫适配度**：⭐⭐⭐⭐⭐（最佳平衡点）

### 2.3 DrissionPage（~20k+ Stars）
- **架构**：CDP 协议直连浏览器 + HTTP 请求双模式
- **优势**：
  - 不泄露 `navigator.webdriver` 属性，绕过常规检测
  - 中国开发者维护，中文文档极佳
  - 浏览器+请求混合模式，反爬能力顶尖
- **劣势**：重度依赖浏览器，纯 HTTP 采集性能不如 Scrapy/Crawlee
- **爬虫适配度**：⭐⭐⭐⭐（反爬利器，作为补充方案）

### 2.4 pyspider / Firecrawl
- **pyspider**：维护放缓，不推荐新项目使用
- **Firecrawl**：AI 提取概念好，但成熟度不足，适合探索性使用

---

## 3. 最终技术选型

### 3.1 推荐方案：Crawlee Python + DrissionPage 双引擎

```
┌─────────────────────────────────────────────────┐
│                  调度层 (Crawlee)                 │
│  ┌─────────────┐  ┌──────────────┐              │
│  │ HTTP 引擎    │  │ 浏览器引擎    │              │
│  │ (httpx)     │  │ (Playwright/ │              │
│  │             │  │  DrissionPage)│              │
│  └──────┬──────┘  └──────┬───────┘              │
│         ↓                ↓                      │
│  ┌──────────────────────────────────┐           │
│  │       解析层 (parsel/selectolax)  │           │
│  └──────────────┬───────────────────┘           │
│                 ↓                               │
│  ┌──────────────────────────────────┐           │
│  │      存储层 (Peewee + DBUtils)    │           │
│  └──────────────────────────────────┘           │
└─────────────────────────────────────────────────┘
```

### 3.2 技术栈清单

| 层级 | 选型 | 版本要求 | 用途 |
|------|------|---------|------|
| **核心框架** | `crawlee` | ≥1.0 | 爬虫调度、请求管理、去重 |
| **HTTP 客户端** | `httpx` | ≥0.28 | 异步 HTTP 请求（Crawlee 内置） |
| **浏览器引擎** | `playwright` | ≥1.50 | JS 渲染（Crawlee 集成） |
| **反爬增强** | `drissionpage` | ≥4.0 | 中国站点/CDP 级反检测（备选） |
| **HTML 解析** | `parsel` | ≥1.9 | CSS/XPath 选择器（Scrapy 同款） |
| **快速解析** | `selectolax` | ≥0.3 | Modest 引擎极速解析（大文本场景） |
| **连接池** | `DBUtils` | ≥3.1 | MySQL 连接复用，防断开 |
| **ORM** | `peewee` | ≥3.17 | 轻量 ORM，模型定义与 CRUD |
| **数据库驱动** | `pymysql` | ≥1.1 | MySQL 原生驱动 |
| **配置管理** | `pydantic-settings` | ≥2.0 | 类型安全的环境变量/配置文件 |
| **日志** | `loguru` | ≥0.7 | 结构化日志，替代 stdlib logging |
| **任务调度** | `apscheduler` | ≥3.10 | 定时/周期采集任务 |
| **重试** | `tenacity` | ≥8.0 | 请求重试与退避策略 |

### 3.3 为什么不选 Scrapy？

1. **Twisted 架构过时** — 非标准 async/await，与项目其他异步代码难以协同
2. **项目结构太重** — Scrapy 项目有固定的文件结构和 CLI 约定，灵活性低
3. **学习成本** — 回调式设计 + Settings + Signals + Middleware 体系复杂
4. **DBUtils 集成不便** — Scrapy 有自己的连接管理，注入 DBUtils 需要绕过框架

### 3.4 为什么主选 Crawlee？

1. **2026 年增长最快** — Apify 持续投入，社区活跃度超越 Scrapy
2. **原生 async/await** — 标准 Python 异步，学习成本低
3. **反爬能力内置** — 指纹生成、代理轮换、自动限速，无需额外配置
4. **灵活管道** — 易于对接 Peewee + DBUtils 自定义存储
5. **渐进式复杂度** — 可从简单脚本开始，按需启用高级功能

---

## 4. 数据库设计原则

- **业务前缀**：`scx_`（表名如 `scx_articles`、`scx_crawl_tasks`）
- **连接池参数**：mincached=3, maxconnections=10, maxusage=1000（复用 1000 次后回收）
- **批量写入**：每 500 条执行一次 `bulk_create` / `insert_many`
- **编码**：utf8mb4（支持 emoji 和特殊字符）

---

## 5. 目录结构规划

```
stage01/crawl/task01/
├── prd.md                  # 本文档
├── pyproject.toml          # 项目依赖和配置
├── .env.example            # 环境变量模板
├── src/
│   ├── __init__.py
│   ├── config.py           # 配置（pydantic-settings）
│   ├── models/
│   │   ├── __init__.py
│   │   └── article.py      # Peewee 数据模型
│   ├── crawlers/
│   │   ├── __init__.py
│   │   ├── base.py         # 基础爬虫（Crawlee 封装）
│   │   └── example.py      # 示例爬虫
│   ├── pipelines/
│   │   ├── __init__.py
│   │   └── storage.py      # Peewee + DBUtils 存储管道
│   ├── parsers/
│   │   ├── __init__.py
│   │   └── extractor.py    # 数据提取器
│   └── utils/
│       ├── __init__.py
│       ├── db.py           # 数据库连接池管理
│       └── logger.py       # 日志配置
└── tests/
    ├── __init__.py
    └── test_example.py
```

---

## 6. 下一步

- [ ] 创建 `pyproject.toml` 并安装依赖
- [ ] 实现 `db.py`（DBUtils 连接池 + Peewee 桥接）
- [ ] 实现 `storage.py`（存储管道）
- [ ] 实现 `base.py`（Crawlee 基础封装）
- [ ] 编写示例爬虫验证链路
- [ ] 编写测试用例

---

> **结论**：Crawlee Python 是 2026 年爬虫框架的最佳选择，兼顾现代化开发体验与反爬实战能力。配合 DrissionPage 作为反爬增强，Peewee + DBUtils 作为轻量存储层，形成「**现代调度 + 双引擎抓取 + 轻量存储**」的三层架构。
