"""阶段 5 示例：Reducer 让消息自动追加。

对比阶段 4（手动 messages + [new]），本阶段用 Annotated[list, add] 声明 Reducer，
节点只返回新消息，引擎自动追加。

运行::

    python -m examples.stage_5_reducer.run
"""

from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from tiny_langgraph import END, START, StateGraph, add_messages


class AgentState(TypedDict):
    messages: Annotated[list[str], add]       # 自动追加
    tool_messages: Annotated[list[dict], add_messages]  # 按 id 智能合并
    tool_calls: int                           # 默认覆盖


def main() -> None:
    print("=" * 60)
    print("示例 1：messages 自动追加（不用手动拼）")
    print("=" * 60)

    def agent(state: AgentState) -> dict:
        if state["tool_calls"] < 2:
            return {"messages": [f"AI: 需要查资料 #{state['tool_calls'] + 1}"]}
        return {"messages": ["AI: 最终答案是 42"]}

    def tool(state: AgentState) -> dict:
        return {
            "messages": [f"Tool: 结果 #{state['tool_calls'] + 1}"],
            "tool_calls": state["tool_calls"] + 1,
        }

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent)
    graph.add_node("tools", tool)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        lambda s: "tools" if "需要查" in s["messages"][-1] else "end",
        {"tools": "tools", "end": END},
    )
    graph.add_edge("tools", "agent")

    result = graph.compile().invoke({"messages": [], "tool_messages": [], "tool_calls": 0})
    for msg in result["messages"]:
        print(f"  {msg}")

    print()
    print("=" * 60)
    print("示例 2：add_messages 按 id 覆盖（流式更新同一条消息）")
    print("=" * 60)

    def draft(state: AgentState) -> dict:
        return {"tool_messages": [{"id": 1, "content": "草稿..."}]}

    def stream_update(state: AgentState) -> dict:
        return {"tool_messages": [{"id": 1, "content": "完整内容"}]}

    def add_new(state: AgentState) -> dict:
        return {"tool_messages": [{"id": 2, "content": "另一条消息"}]}

    graph2 = StateGraph(AgentState)
    graph2.add_node("draft", draft)
    graph2.add_node("stream_update", stream_update)
    graph2.add_node("add_new", add_new)
    graph2.add_edge(START, "draft")
    graph2.add_edge("draft", "stream_update")
    graph2.add_edge("stream_update", "add_new")
    graph2.add_edge("add_new", END)

    result2 = graph2.compile().invoke({"messages": [], "tool_messages": [], "tool_calls": 0})
    for msg in result2["tool_messages"]:
        print(f"  id={msg['id']}: {msg['content']}")

    print()
    print("  → id=1 被 stream_update 覆盖（草稿→完整内容），没有变成两条")
    print("  → id=2 是新消息，追加")

    print()
    print("=" * 60)
    print("关键对比：阶段 4 vs 阶段 5")
    print("=" * 60)
    print("  阶段 4: return {'messages': state['messages'] + [new]}  # 手动拼")
    print("  阶段 5: return {'messages': [new]}                      # 引擎自动追加")


if __name__ == "__main__":
    main()