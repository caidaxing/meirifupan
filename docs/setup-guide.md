# 使用指南

## 环境要求

- Python 3.x
- 网络连接

## 第一步：获取 Token

详细配置清单见 [`docs/configuration.md`](configuration.md)。真实账号、密码、token 不要提交到 Git。

1. 浏览器打开数据平台
2. 登录账号
3. 打开开发者工具（F12）→ Application → Local Storage
4. 复制 token 值

将 token 保存到 `config/token.json`：
```json
{
  "token": "你的token值"
}
```

## 第二步：爬取数据

```bash
cd /Users/admin/Desktop/obsidian/热爱生活/发家致富
python src/fetch_uplimit.py
```

脚本会：
1. 读取 token
2. 获取最近15个交易日
3. 逐日爬取涨停数据
4. 写入 `data/market_review.db`

输出示例：
```
==================================================
爬取 2026-06-01 的涨停数据...
==================================================
  [1/3] 涨停原因...
    ✅ 25 个板块, 68 只涨停股
  [2/3] 涨停梯队...
    ✅ 15 个热门板块
  [3/3] 板块排名...
    ✅ 30 个板块
  💾 已写入数据库: data/market_review.db
```

## 第三步：迁移历史 JSON

如果本地已有 `data/uplimit/uplimit_*.json`，可以先迁移到 SQLite：

```bash
python src/migrate_json_to_db.py
```

重复运行不会重复插入涨停事件。

## 第四步：启动旧看板

```bash
python -m http.server 8080
```

浏览器访问：http://localhost:8080

注意：当前 `index.html` 还是旧静态看板，读取的是 `data/uplimit/` 下的 JSON 文件。数据库迁移完成后，下一步需要增加本地服务接口，让看板改为读取 SQLite。

## 第五步：启动数据库数据页

如果要直接从 SQLite 读取并展示数据，启动本地数据服务：

```bash
python src/data_server.py
```

浏览器访问：

```text
http://127.0.0.1:8765
```

默认展示数据库里的最新交易日。也可以指定日期：

```text
http://127.0.0.1:8765/?date=2026-05-28
```

## 第六步：更新数据

每天收盘后（15:00后）重新运行爬取脚本即可获取当日数据。

## 自动化脚本

项目提供一个统一入口：

```bash
scripts/auto_review.sh status
```

常用命令：

```bash
# 立即补最近 30 个交易日数据
scripts/auto_review.sh once

# 启动数据库数据页
scripts/auto_review.sh server

# 启动每日自动调度：盘前 08:30，复盘 17:30
scripts/auto_review.sh schedule

# 查看数据库、数据页、调度器状态
scripts/auto_review.sh status

# 停止数据页和调度器
scripts/auto_review.sh stop
```

可以用环境变量调整时间：

```bash
DAILY_UPDATE_AT=18:00 PREMARKET_UPDATE_AT=08:45 scripts/auto_review.sh schedule
```

日志位置：

```text
logs/auto_update.log
logs/data_server.log
logs/daily_scheduler.log
```

## Docker/服务器配置

复制模板后再填真实配置：

```bash
cp .env.example .env
cp config/token.example.json config/token.json
cp config/quantzz_token.example.json config/quantzz_token.json
```

`docker-compose.yml` 会读取 `.env`。常用配置包括：

```text
PORT=8765
DAILY_UPDATE_AT=17:30
PREMARKET_UPDATE_AT=08:30
QUANTZZ_TOKEN_FILE=/app/config/quantzz_token.json
```

## 代码同步

当前默认仓库是：

```text
https://github.com/caidaxing/meirifupan.git
```

第一次使用前，确认 GitHub CLI 登录的是 `caidaxing`：

```bash
gh auth status
```

如果不是 `caidaxing`，重新登录：

```bash
gh auth logout -h github.com
gh auth login -h github.com -p https -w
gh auth setup-git
```

日常同步用这个脚本：

```bash
# 查看同步状态
scripts/git_sync.sh status

# 从 GitHub 拉取最新代码
scripts/git_sync.sh pull

# 推送已经提交的代码
scripts/git_sync.sh push

# 提交当前改动，然后拉取并推送
scripts/git_sync.sh save "本次修改说明"
```

建议每次换电脑或开始改代码前先运行：

```bash
scripts/git_sync.sh pull
```

## 常见问题

### Token 过期

重新从浏览器获取 token，更新 `config/token.json`。

### 数据为空

检查：
1. 当天是否为交易日
2. Token 是否有效
3. 网络连接是否正常

### 看板页面空白

1. 确认 HTTP 服务器已启动
2. 确认 `data/uplimit/` 目录下仍有旧 JSON 文件
3. 打开浏览器控制台（F12）查看错误信息
