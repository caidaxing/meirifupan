"""
A股复盘 Agent - 基于 LangGraph + akshare

功能：
1. 自动获取今日市场数据（涨停、板块、人气）
2. 分析市场情绪和主线
3. 生成结构化复盘报告

用法：
    python agent_review.py                # 生成今日复盘
    python agent_review.py --date 2026-07-01  # 生成指定日期复盘
"""

import os
import sys
from datetime import datetime, timedelta
from typing import TypedDict, Annotated, Any

import akshare as ak
import pandas as pd
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent

# ============ 1. LLM ============
llm = ChatAnthropic(
    model="mimo-v2.5-pro",
    base_url=os.environ.get("ANTHROPIC_BASE_URL") or None,
    api_key=os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
    default_headers={"anthropic-version": "2023-06-01"},
)

# ============ 2. 工具定义 ============

@tool
def get_limit_up_data(date: str) -> str:
    """获取指定日期的涨停板数据。

    Args:
        date: 日期，格式 YYYY-MM-DD

    Returns:
        涨停板数据摘要，包括股票代码、名称、连板数、所属行业
    """
    try:
        date_str = date.replace("-", "")
        df = ak.stock_zt_pool_em(date=date_str)
        if df.empty:
            return f"{date} 没有涨停数据"

        # 统计
        total = len(df)
        industries = df["所属行业"].value_counts().head(10)
        max_board = df["连板数"].max()
        top_stocks = df.nlargest(10, "连板数")[["代码", "名称", "连板数", "所属行业", "封板资金"]]

        result = f"## {date} 涨停数据\n\n"
        result += f"- 涨停总数: {total} 只\n"
        result += f"- 最高连板: {max_board} 板\n\n"

        result += "### 连板 Top 10\n"
        for _, row in top_stocks.iterrows():
            result += f"- {row['名称']}({row['代码']}): {row['连板数']}板, {row['所属行业']}\n"

        result += "\n### 涨停行业分布 Top 10\n"
        for industry, count in industries.items():
            result += f"- {industry}: {count} 只\n"

        return result
    except Exception as e:
        return f"获取涨停数据失败: {e}"


@tool
def get_market_overview(date: str) -> str:
    """获取指定日期的大盘指数数据。

    Args:
        date: 日期，格式 YYYY-MM-DD

    Returns:
        主要指数（上证、深证、创业板）的涨跌幅和成交额
    """
    try:
        # 获取主要指数
        indices = {
            "上证指数": "sh000001",
            "深证成指": "sz399001",
            "创业板指": "sz399006",
        }

        result = f"## {date} 大盘指数\n\n"
        for name, code in indices.items():
            try:
                df = ak.stock_zh_index_daily(symbol=code)
                df["date"] = pd.to_datetime(df["date"])
                day_data = df[df["date"] == date]
                if not day_data.empty:
                    row = day_data.iloc[0]
                    change_pct = (row["close"] - row["open"]) / row["open"] * 100
                    result += f"- {name}: {row['close']:.2f} ({'+' if change_pct > 0 else ''}{change_pct:.2f}%)\n"
            except Exception:
                result += f"- {name}: 数据获取失败\n"

        return result
    except Exception as e:
        return f"获取大盘数据失败: {e}"


@tool
def get_hot_stocks(date: str) -> str:
    """获取指定日期的热门股票（人气榜）。

    Args:
        date: 日期，格式 YYYY-MM-DD

    Returns:
        人气排名前 20 的股票，包括代码、名称、涨跌幅
    """
    try:
        date_str = date.replace("-", "")
        df = ak.stock_hot_rank_em()
        if df.empty:
            return "没有热门股票数据"

        result = f"## 今日热门股票 Top 20\n\n"
        top20 = df.head(20)
        for i, (_, row) in enumerate(top20.iterrows(), 1):
            name = row.get("股票简称", "")
            code = row.get("股票代码", "")
            change = row.get("涨跌幅", 0)
            result += f"{i}. {name}({code}): {'+' if change > 0 else ''}{change:.2f}%\n"

        return result
    except Exception as e:
        return f"获取热门股票失败: {e}"


@tool
def get_plate_rotation(date: str) -> str:
    """获取指定日期的板块轮动数据。

    Args:
        date: 日期，格式 YYYY-MM-DD

    Returns:
        涨幅前 10 和跌幅前 10 的板块
    """
    try:
        date_str = date.replace("-", "")
        df = ak.stock_board_industry_name_em()
        if df.empty:
            return "没有板块数据"

        result = f"## {date} 板块轮动\n\n"

        # 涨幅前10
        if "涨跌幅" in df.columns:
            top_up = df.nlargest(10, "涨跌幅")
            result += "### 涨幅前 10\n"
            for _, row in top_up.iterrows():
                name = row.get("板块名称", "")
                change = row.get("涨跌幅", 0)
                result += f"- {name}: +{change:.2f}%\n"

            # 跌幅前10
            top_down = df.nsmallest(10, "涨跌幅")
            result += "\n### 跌幅前 10\n"
            for _, row in top_down.iterrows():
                name = row.get("板块名称", "")
                change = row.get("涨跌幅", 0)
                result += f"- {name}: {change:.2f}%\n"

        return result
    except Exception as e:
        return f"获取板块数据失败: {e}"


@tool
def get_limit_down_data(date: str) -> str:
    """获取指定日期的跌停板数据。

    Args:
        date: 日期，格式 YYYY-MM-DD

    Returns:
        跌停股票数量和列表
    """
    try:
        date_str = date.replace("-", "")
        df = ak.stock_zt_pool_dtgc_em(date=date_str)
        if df.empty:
            return f"{date} 没有跌停数据"

        total = len(df)
        result = f"## {date} 跌停数据\n\n"
        result += f"- 跌停总数: {total} 只\n\n"

        top_stocks = df.head(10)[["代码", "名称", "涨跌幅", "所属行业"]]
        for _, row in top_stocks.iterrows():
            result += f"- {row['名称']}({row['代码']}): {row['涨跌幅']:.2f}%, {row['所属行业']}\n"

        return result
    except Exception as e:
        return f"获取跌停数据失败: {e}"


@tool
def save_report(content: str, date: str) -> str:
    """将复盘报告保存到 Obsidian vault。

    Args:
        content: 报告内容（Markdown 格式）
        date: 日期，格式 YYYY-MM-DD

    Returns:
        保存结果
    """
    try:
        output_dir = "/Users/admin/Desktop/obsidian/valut1/A股复盘"
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f"{date}-复盘.md")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return f"报告已保存到: {filepath}"
    except Exception as e:
        return f"保存失败: {e}"


# ============ 3. Agent 定义 ============

tools = [
    get_limit_up_data,
    get_market_overview,
    get_hot_stocks,
    get_plate_rotation,
    get_limit_down_data,
    save_report,
]

agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt="""你是一个专业的 A 股复盘分析师。

你的任务是：
1. 使用工具获取今日市场数据
2. 分析市场情绪、主线板块、风险点
3. 生成结构化的复盘报告
4. 使用 save_report 工具保存报告

分析维度：
- 涨停/跌停数量 → 市场情绪
- 连板高度 → 赚钱效应
- 板块分布 → 主线方向
- 人气股 → 资金偏好

报告格式：
```markdown
---
date: YYYY-MM-DD
tags: [复盘, A股]
---

# A股复盘 YYYY-MM-DD

## 一句话结论
（总结今日市场特征）

## 盘面数据
| 指标 | 数值 |
|------|------|
| 涨停 | X 只 |
| 跌停 | X 只 |
| 最高板 | X 板 |

## 主线板块
（分析哪些板块是主线，哪些是支线）

## 人气核心
（分析人气股特征）

## 风险点
（提示需要注意的风险）

## 明日计划
（给出明日操作建议）
```

重要规则：
1. 每个工具最多调用 1 次
2. 数据获取完成后立即分析并生成报告
3. 报告要简洁实用，不要废话
""",
)


# ============ 4. 运行 ============

def run_review(date: str | None = None):
    """运行复盘分析"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    print(f"开始分析 {date} 的 A 股市场...")

    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"请分析 {date} 的 A 股市场，生成复盘报告并保存。"}]},
        config={"recursion_limit": 15},
    )

    # 提取最终回复
    for msg in reversed(result["messages"]):
        if hasattr(msg, "content") and msg.content:
            print("\n" + "=" * 50)
            print(msg.content)
            break

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="A股复盘 Agent")
    parser.add_argument("--date", help="指定日期，格式 YYYY-MM-DD")
    args = parser.parse_args()

    run_review(args.date)


if __name__ == "__main__":
    main()
