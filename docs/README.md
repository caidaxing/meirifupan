# 发家致富 - A股短线复盘系统

## 项目简介

A股投资助手，专注于短线复盘。自动爬取涨停数据，生成可视化看板，帮助快速掌握每日市场热点。

## 核心功能

- **涨停数据爬取**：自动爬取近15个交易日涨停数据
- **表结构存储**：写入本地 SQLite 数据库，支持去重、查询和后续分析
- **每日复盘看板**：展示涨停板块、涨停梯队、热门板块、涨停股明细
- **盘前分析**：盘前资讯、美股隔夜、公告汇总
- **情绪周期**：5 指标加权情绪评分模型
- **AI 问答**：基于 LangGraph 的智能选股助手

## 文档目录

### 产品文档 (`product/`)

- [产品路线图](./product/product-plan.md)
- [复盘模块产品需求](./product/daily-review-spec.md)
- [自在量化网站模块梳理](./product/quantzz-site-module-map.md)
- [Quantzz 同类产品复刻方案](./product/quantzz-clone-product-tech-data-plan.md)

### 技术文档 (`technical/`)

- [复盘模块技术方案](./technical/daily-review-tech.md)
- [复盘模块实施方案](./technical/review-module-implementation-spec.md)
- [复盘模块开发规范](./technical/review-module-development-standards.md)
- [复盘模块数据可行性与缺口评估](./technical/review-module-data-feasibility.md)
- [扶摇数据接入与落地文档](./technical/fuyao-data-integration-plan.md)
- [API 接口文档](./technical/api-reference.md)
- [数据存储说明](./technical/data-storage.md)
- [配置说明](./technical/configuration.md)
- [搭建指南](./technical/setup-guide.md)
- [前端文档](./technical/frontend.md)
- [数据渠道全景](./technical/data-sources.md) — 44 个数据源的来源、方式、认证、兜底策略

### 项目方案 (`plans/`)

- [盘前 Agent 方案](./plans/2026-06-24-premarket-agent.md)
- [复盘模块 Phase1 实施方案](./plans/2026-06-24-review-module-phase1-implementation.md)
- [扶摇数据源接入方案](./plans/2026-07-02-fuyao-data-source.md)

### 历史资料 (`archive/`)

- [复盘模块进展记录 2026-06-25](./archive/review-module-progress-2026-06-25.md)
- [数据预览 2026-06-01](./archive/data-preview-2026-06-01.md)

## 项目结构

```
发家致富/
├── pyproject.toml           # 依赖管理
├── Dockerfile               # Docker 构建
├── docker-compose.yml       # Docker 编排
├── src/
│   ├── utils.py             # 共享工具函数
│   ├── db/
│   │   ├── __init__.py      # MarketDB 主类
│   │   └── schema.py        # DDL + 迁移
│   ├── fetch_*.py           # 数据采集模块
│   ├── derive_*.py          # 数据衍生
│   ├── generate_*.py        # 报告生成
│   ├── daily_update.py      # 每日主流水线
│   ├── premarket_update.py  # 盘前流水线
│   └── daily_scheduler.py   # 定时调度
├── server/
│   ├── main.py              # FastAPI 服务
│   ├── api/                 # REST 端点
│   └── services/            # 业务逻辑
├── web/                     # React + TS 前端
├── tests/                   # 测试
├── config/                  # 配置文件
├── data/                    # SQLite 数据库
└── docs/                    # 项目文档
```

## 快速开始

```bash
# 安装依赖
pip install -e .

# 运行数据采集
python src/daily_update.py

# 启动服务
cd server && bash start.sh

# 访问
open http://localhost:8765
```

## 技术栈

- **后端**: Python 3.12, FastAPI, SQLite
- **前端**: React 19, TypeScript, Vite, ECharts
- **数据源**: AkShare, 扶摇 API, 自在量化 API
- **AI**: LangGraph + Anthropic Claude
