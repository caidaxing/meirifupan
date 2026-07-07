"""
A股智能问答助手 - FastAPI 后端

功能：
- 接收用户问题
- 调用 LangGraph Agent 获取数据并回答
- 返回结构化响应

启动：
    python stock_agent_server.py
    或
    uvicorn stock_agent_server:app --host 0.0.0.0 --port 8002
"""

import os
import sys
from datetime import datetime
from typing import TypedDict, Annotated

import akshare as ak
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# ============ 初始化 ============
app = FastAPI(title="A股智能问答助手")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ LLM ============
llm = ChatAnthropic(
    model="mimo-v2.5-pro",
    base_url=os.environ.get("ANTHROPIC_BASE_URL") or None,
    api_key=os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
    default_headers={"anthropic-version": "2023-06-01"},
)

# ============ 工具定义 ============

@tool
def get_limit_up(date: str) -> str:
    """获取涨停板数据。

    Args:
        date: 日期，格式 YYYY-MM-DD
    """
    try:
        df = ak.stock_zt_pool_em(date=date.replace("-", ""))
        if df.empty:
            return f"{date} 没有涨停数据"

        total = len(df)
        industries = df["所属行业"].value_counts().head(5)
        max_board = df["连板数"].max()
        top = df.nlargest(5, "连板数")[["名称", "代码", "连板数", "所属行业"]]

        result = f"涨停{total}只，最高{max_board}板。"
        result += f"连板前5: " + ", ".join([f"{r['名称']}({r['连板数']}板)" for _, r in top.iterrows()])
        result += f"。行业分布: " + ", ".join([f"{k}({v}只)" for k, v in industries.items()])
        return result
    except Exception as e:
        return f"获取涨停数据失败: {e}"


@tool
def get_limit_down(date: str) -> str:
    """获取跌停板数据。

    Args:
        date: 日期，格式 YYYY-MM-DD
    """
    try:
        df = ak.stock_zt_pool_dtgc_em(date=date.replace("-", ""))
        if df.empty:
            return f"{date} 没有跌停数据"

        total = len(df)
        stocks = df.head(5)[["名称", "代码", "涨跌幅"]].values.tolist()
        result = f"跌停{total}只。"
        if stocks:
            result += "主要跌停: " + ", ".join([f"{s[0]}({s[2]:.1f}%)" for s in stocks])
        return result
    except Exception as e:
        return f"获取跌停数据失败: {e}"


@tool
def get_market_index() -> str:
    """获取主要大盘指数（上证、深证、创业板）的最新行情。"""
    try:
        indices = {"上证": "sh000001", "深证": "sz399001", "创业板": "sz399006"}
        result = ""
        for name, code in indices.items():
            try:
                df = ak.stock_zh_index_daily(symbol=code)
                if not df.empty:
                    last = df.iloc[-1]
                    change = (last["close"] - last["open"]) / last["open"] * 100
                    sign = "+" if change > 0 else ""
                    result += f"{name}{last['close']:.2f}({sign}{change:.2f}%) "
            except Exception:
                pass
        return result.strip() if result else "指数数据获取失败"
    except Exception as e:
        return f"获取指数失败: {e}"


@tool
def get_hot_stocks() -> str:
    """获取当前热门股票排行（人气榜）。"""
    try:
        df = ak.stock_hot_rank_em()
        if df.empty:
            return "没有热门股票数据"

        top10 = df.head(10)
        result = "人气前10: "
        for i, (_, row) in enumerate(top10.iterrows(), 1):
            name = row.get("股票简称", "")
            code = row.get("股票代码", "")
            result += f"{i}.{name}({code}) "
        return result.strip()
    except Exception as e:
        return f"获取热门股票失败: {e}"


@tool
def get_plate_industry() -> str:
    """获取行业板块涨跌情况。"""
    try:
        df = ak.stock_board_industry_name_em()
        if df.empty:
            return "没有板块数据"

        if "涨跌幅" in df.columns:
            top_up = df.nlargest(5, "涨跌幅")[["板块名称", "涨跌幅"]]
            top_down = df.nsmallest(5, "涨跌幅")[["板块名称", "涨跌幅"]]

            result = "涨幅前5: "
            result += ", ".join([f"{r['板块名称']}(+{r['涨跌幅']:.2f}%)" for _, r in top_up.iterrows()])
            result += "。跌幅前5: "
            result += ", ".join([f"{r['板块名称']}({r['涨跌幅']:.2f}%)" for _, r in top_down.iterrows()])
            return result
        return "板块数据格式异常"
    except Exception as e:
        return f"获取板块数据失败: {e}"


@tool
def get_stock_info(stock_code: str) -> str:
    """获取单只股票的最新行情。

    Args:
        stock_code: 股票代码，如 300308、000001
    """
    try:
        code = stock_code.strip().zfill(6)
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
        if df.empty:
            return f"找不到股票: {stock_code}"

        last = df.iloc[-1]
        result = f"{code}: "
        result += f"日期{last['日期']}, "
        result += f"收盘{last['收盘']:.2f}, "
        result += f"涨跌幅{last['涨跌幅']:.2f}%, "
        result += f"成交额{last['成交额']/100000000:.2f}亿"
        return result
    except Exception as e:
        return f"获取股票信息失败: {e}"


@tool
def get_market_sentiment(date: str) -> str:
    """综合评估市场情绪。

    Args:
        date: 日期，格式 YYYY-MM-DD
    """
    try:
        zt_df = ak.stock_zt_pool_em(date=date.replace("-", ""))
        zt_count = len(zt_df) if not zt_df.empty else 0

        dt_df = ak.stock_zt_pool_dtgc_em(date=date.replace("-", ""))
        dt_count = len(dt_df) if not dt_df.empty else 0

        max_board = zt_df["连板数"].max() if not zt_df.empty else 0

        if zt_count > 100 and dt_count < 10:
            mood = "强势"
        elif zt_count > 50 and dt_count < 20:
            mood = "偏暖"
        elif zt_count < 30 and dt_count > 30:
            mood = "弱势"
        else:
            mood = "震荡"

        result = f"{date}市场情绪{mood}。"
        result += f"涨停{zt_count}只，跌停{dt_count}只，最高{max_board}板。"

        if max_board >= 5:
            result += "连板高度打开，赚钱效应好。"
        elif max_board <= 2:
            result += "连板高度受限，赚钱效应一般。"

        return result
    except Exception as e:
        return f"评估市场情绪失败: {e}"


@tool
def get_trade_calendar() -> str:
    """获取最近的交易日信息。"""
    try:
        df = ak.tool_trade_date_hist_sina()
        today = datetime.now().strftime("%Y-%m-%d")
        trade_days = [str(d) for d in df["trade_date"] if str(d) <= today]
        last_trade = trade_days[-1] if trade_days else "未知"
        return f"最近交易日: {last_trade}"
    except Exception as e:
        return f"获取交易日历失败: {e}"


# ============ Agent ============

tools = [
    get_limit_up,
    get_limit_down,
    get_market_index,
    get_hot_stocks,
    get_plate_industry,
    get_stock_info,
    get_market_sentiment,
    get_trade_calendar,
]

agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt="""你是一个专业的 A 股投资助手。

你的能力：
- 查询涨停/跌停数据
- 查询大盘指数
- 查询热门股票
- 查询板块涨跌
- 查询个股信息
- 综合评估市场情绪

回答规则：
1. 根据用户问题，选择合适的工具获取数据
2. 用简洁的中文回答，不要废话
3. 如果用户问的问题需要多个数据，可以调用多个工具
4. 回答要直接，先说结论，再说数据支撑
5. 每个工具最多调用1次

示例：
- "今天行情怎么样" → 调用 get_market_index + get_limit_up
- "市场情绪如何" → 调用 get_market_sentiment
- "半导体板块怎么样" → 调用 get_plate_industry
- "中际旭创什么情况" → 调用 get_stock_info("300308")
""",
)


# ============ API ============

class ChatRequest(BaseModel):
    message: str
    date: str = None  # 可选，默认今天

class ChatResponse(BaseModel):
    reply: str
    timestamp: str

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        # 如果用户没传日期，在消息里补充今天的日期
        message = req.message
        if req.date:
            message = f"[日期: {req.date}] {message}"
        else:
            today = datetime.now().strftime("%Y-%m-%d")
            message = f"[今天是 {today}] {message}"

        result = agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config={"recursion_limit": 10},
        )

        for msg in reversed(result["messages"]):
            if hasattr(msg, "content") and msg.content:
                content = msg.content
                if isinstance(content, list):
                    texts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
                    content = "\n".join(texts)
                if content:
                    return ChatResponse(
                        reply=content,
                        timestamp=datetime.now().isoformat(),
                    )

        return ChatResponse(
            reply="无法回答",
            timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Chat endpoint error")
        return ChatResponse(
            reply="抱歉，处理请求时出现错误，请稍后重试。",
            timestamp=datetime.now().isoformat(),
        )

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "A股智能问答助手"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
