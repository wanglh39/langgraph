"""阶段 8 示例：人机协作 —— Agent 提方案，人类审批，续跑执行。

运行::

    python -m examples.stage_8_interrupt.run
"""

from __future__ import annotations

from typing import TypedDict

from tiny_langgraph import END, START, MemorySaver, StateGraph


class State(TypedDict):
    proposal: str
    approved: bool
    outcome: str


def main() -> None:
    print("=" * 60)
    print("示例：人机协作审批流程")
    print("=" * 60)
    print("图: propose -> [interrupt] -> review -> execute")
    print()

    def propose(state: State) -> dict:
        print("  [propose] Agent 提出方案")
        return {"proposal": "把数据库迁移到 PostgreSQL"}

    def review(state: State) -> dict:
        if state["approved"]:
            print("  [review] 人类已批准")
            return {"outcome": "approved"}
        print("  [review] 人类未批准")
        return {"outcome": "rejected"}

    def execute(state: State) -> dict:
        if state["outcome"] == "approved":
            print(f"  [execute] 执行方案: {state['proposal']}")
            return {"outcome": "done"}
        print("  [execute] 方案被拒绝，不执行")
        return {"outcome": "cancelled"}

    graph = StateGraph(State)
    graph.add_node("propose", propose)
    graph.add_node("review", review)
    graph.add_node("execute", execute)
    graph.add_edge(START, "propose")
    graph.add_edge("propose", "review")
    graph.add_edge("review", "execute")
    graph.add_edge("execute", END)

    app = graph.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["review"],
    )
    config = {"configurable": {"thread_id": "approval-1"}}
    initial = {"proposal": "", "approved": False, "outcome": ""}

    print("第一次执行（跑到 review 前暂停）：")
    print("-" * 60)
    for event in app.stream(initial, config=config):
        print(f"  超级步 {event['step']}: 执行 {event['nodes']}", end="")
        if event.get("interrupt"):
            print(f"  [interrupt: {event['interrupt']}]")
        else:
            print()

    print()
    print("人类审批：调用 update_state 写入决策")
    app.update_state(config, {"approved": True})
    print("  → approved = True")

    print()
    print("续跑（invoke(None, config)）：")
    print("-" * 60)
    result = app.invoke(None, config=config)
    print(f"\n最终结果: outcome={result['outcome']}")

    print()
    print("=" * 60)
    print("关键观察：interrupt = 检查点 + 暂停 + 续跑")
    print("=" * 60)
    print("  - interrupt_before=['review']: 执行到 review 前暂停")
    print("  - update_state: 人类写入决策到检查点")
    print("  - invoke(None, config): 从检查点续跑")
    print("  - 整个过程状态不丢失，靠的是阶段 7 的检查点")


if __name__ == "__main__":
    main()