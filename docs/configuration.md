# 配置清单

这份清单只记录配置项，不保存真实账号、密码、token。真实值放在每台机器自己的 `.env`、`config/*.json`、SSH 或 GitHub 凭证里。

## 需要单独保存的敏感配置

| 配置 | 用途 | 建议保存位置 | 是否进 Git |
| --- | --- | --- | --- |
| Quantzz token | 拉取涨停、情绪、热点等登录接口数据 | `config/token.json` | 否 |
| Quantzz access token | 题材轮动接口优先读取的 token | `config/quantzz_token.json` 或 `.env` 的 `QUANTZZ_TOKEN` | 否 |
| Quantzz 账号密码 | token 失效时用于重新登录题材轮动接口 | `.env` 的 `QUANTZZ_EMAIL`、`QUANTZZ_PASSWORD` | 否 |
| GitHub 登录凭证 | 本地 push/pull 代码 | GitHub CLI keychain 或系统 Git 凭证 | 否 |
| 服务器 SSH 凭证 | 登录 `47.96.138.82` 部署和查日志 | 本机 `~/.ssh` 或云厂商控制台 | 否 |

当前本地已有真实文件：

- `config/token.json`
- `config/token.json.bak.20260608-161309`
- `config/settings.yaml`

这些文件已在 `.gitignore` 中忽略，不要提交。

## 非敏感运行配置

| 配置 | 默认值 | 用途 |
| --- | --- | --- |
| `TZ` | `Asia/Shanghai` | 容器时区 |
| `PORT` | `8765` | 本地或服务器 Web 端口 |
| `DB_PATH` | `/app/data/market_review.db` | Docker 容器内 SQLite 路径 |
| `DAILY_UPDATE_AT` | `17:30` | 每天收盘后自动复盘时间 |
| `PREMARKET_UPDATE_AT` | `08:30` | 每天盘前指引生成时间 |
| `DAILY_KLINE_LIMIT` | `30` | 日线补数数量 |
| `DAILY_UPDATE_FORCE` | `0` | 是否强制重跑更新 |
| `QUANTZZ_API_BASE` | `https://api.zizizaizai.com` | 数据接口地址 |
| `QUANTZZ_TOKEN_FILE` | `/app/config/quantzz_token.json` | Docker 内 access token 文件路径 |

## 文件模板

仓库里只保留模板：

- `.env.example`
- `config/token.example.json`
- `config/quantzz_token.example.json`
- `config/settings.example.yaml`

新机器初始化时：

```bash
cp .env.example .env
cp config/token.example.json config/token.json
cp config/quantzz_token.example.json config/quantzz_token.json
```

然后把真实值填进本机文件。

## 本地运行

本地脚本默认读：

- 数据库：`data/market_review.db`
- 老 token：`config/token.json`
- 运行日志：`logs/`
- pid 文件：`.run/`

常用命令：

```bash
scripts/auto_review.sh status
scripts/auto_review.sh once
scripts/auto_review.sh server
scripts/auto_review.sh schedule
```

如果要临时改时间：

```bash
DAILY_UPDATE_AT=18:00 PREMARKET_UPDATE_AT=08:45 scripts/auto_review.sh schedule
```

## Docker/服务器运行

Docker Compose 会自动读取 `.env`：

```bash
cp .env.example .env
docker compose up -d --build
```

服务器上真实文件应该放在：

- `/root/fajiazhifu/.env`
- `/root/fajiazhifu/config/token.json`
- `/root/fajiazhifu/config/quantzz_token.json`
- `/root/fajiazhifu/data/market_review.db`

## Token 关系

目前代码里有两套读取方式：

1. `src/fetch_uplimit.py` 读取 `config/token.json` 的 `token` 字段。
2. `src/fetch_plate_rotation.py` 优先读取 `QUANTZZ_TOKEN`，其次读取 `QUANTZZ_TOKEN_FILE`，默认是 `config/quantzz_token.json`，字段名支持 `access_token` 或 `token`。

为了减少混乱，可以让 `config/token.json` 和 `config/quantzz_token.json` 保存同一个有效 token。后续如果要再收敛，可以把老的 `config/token.json` 读取逻辑也改成统一的 `QUANTZZ_TOKEN_FILE`。

## GitHub 同步

项目代码仓库：

```text
https://github.com/caidaxing/meirifupan.git
```

本地建议使用：

```bash
scripts/git_sync.sh doctor
scripts/git_sync.sh pull
scripts/git_sync.sh save "修改说明"
scripts/git_sync.sh push
```

GitHub token 不放项目目录。它由 `gh auth login` 写入系统凭证。

## 需要补齐但当前代码还没有的配置

邮件提醒还没有正式进仓库。后面如果要把 token 过期提醒自动化，需要新增：

| 配置 | 用途 |
| --- | --- |
| `SMTP_HOST` | SMTP 服务器 |
| `SMTP_PORT` | SMTP 端口 |
| `SMTP_USER` | 发件邮箱账号 |
| `SMTP_PASSWORD` | 发件邮箱授权码，不是网页登录密码 |
| `ALERT_EMAIL_TO` | 接收提醒的邮箱 |

这些也应该放 `.env`，不要写进代码或文档。
