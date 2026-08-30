"""阶段 4 示例：ReAct 雏形（mock LLM 的思考-行动-观察循环）。

用 mock LLM 演示 Agent 的 ReAct 循环怎么映射到循环图。
阶段 9 才接真 OpenAI。

运行::

    python -m examples.stage_4_cycle.run
"""

from __future__ import annotations

from typing import TypedDict

from tiny_langgraph import END, START, StateGraph


class AgentState(TypedDict):
    messages: list[str]
    tool_calls: int


def agent_node(state: AgentState) -> dict:
    """模拟 LLM 决策：前两轮要调工具，第三轮给最终答案。"""
    if state["tool_calls"] < 2:
        msg = f"AI: 我需要查一下资料（工具调用 #{state['tool_calls'] + 1}）"
    else:
        msg = "AI: 综合以上信息，最终答案是 42"
    return {"messages": state["messages"] + [msg]}


def tool_node(state: AgentState) -> dict:
    """模拟工具执行。"""
    return {
        "messages": state["messages"] + [f"Tool: 返回了查询结果 #{state['tool_calls'] + 1}"],
        "tool_calls": state["tool_calls"] + 1,
    }


def should_continue(state: AgentState) -> str:
    """路由：看最后一条消息决定继续调工具还是结束。"""
    last = state["messages"][-1]
    return "tools" if "需要查" in last else "end"


def main() -> None:
    print("=" * 60)
    print("示例：ReAct 雏形（mock LLM）")
    print("=" * 60)
    print("图结构: agent -> (需要工具?) -> tool -> agent -> ... -> END")
    print()

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent", should_continue, {"tools": "tools", "end": END}
    )
    graph.add_edge("tools", "agent")

    app = graph.compile()
    initial = {"messages": [], "tool_calls": 0}

    print("用 stream 逐步观察执行过程：")
    print("-" * 60)
    for event in app.stream(initial):
        print(f"  [step {event['step']}] 节点: {event['node']}")
        for msg in event["state"]["messages"]:
            print(f"      {msg}")
        print()

    print("=" * 60)
    print("关键观察：ReAct 循环 = 回边 + 条件边")
    print("=" * 60)
    print("  - agent 节点：调 LLM 决定下一步（思考）")
    print("  - 条件边 should_continue：根据 LLM 输出决定调工具还是结束")
    print("  - tools 节点：执行工具（行动）")
    print("  - 回边 tools->agent：构成循环（观察后继续思考）")
    print("  - stream：逐步 yield，能看到每轮思考-行动-观察")


if __name__ == "__main__":
    main()