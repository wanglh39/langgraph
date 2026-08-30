"""阶段 3 示例：条件边与路由（Collatz 猜想）。

运行::

    python -m examples.stage_3_conditional.run
"""

from __future__ import annotations

from typing import TypedDict

from tiny_langgraph import END, START, StateGraph


class State(TypedDict):
    number: int
    parity: str
    steps: list[str]


def main() -> None:
    print("=" * 60)
    print("示例：Collatz 猜想 —— 根据奇偶性路由")
    print("=" * 60)

    def classify(state: State) -> dict:
        parity = "even" if state["number"] % 2 == 0 else "odd"
        return {"parity": parity, "steps": state["steps"] + [f"classify->{parity}"]}

    def halve(state: State) -> dict:
        n = state["number"] // 2
        return {"number": n, "steps": state["steps"] + [f"halve->{n}"]}

    def triple_plus_one(state: State) -> dict:
        n = state["number"] * 3 + 1
        return {"number": n, "steps": state["steps"] + [f"3n+1->{n}"]}

    graph = StateGraph(State)
    graph.add_node("classify", classify)
    graph.add_node("halve", halve)
    graph.add_node("triple_plus_one", triple_plus_one)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        lambda s: "done" if s["number"] == 1 else s["parity"],
        {"even": "halve", "odd": "triple_plus_one", "done": END},
    )
    graph.add_edge("halve", "classify")
    graph.add_edge("triple_plus_one", "classify")

    app = graph.compile()
    for start in (6, 11, 27):
        result = app.invoke(
            {"number": start, "parity": "", "steps": []}, recursion_limit=500
        )
        print(f"  Collatz({start}) -> 1, 共 {len(result['steps'])} 步")

    print()
    print("=" * 60)
    print("关键观察：条件边让图能根据状态做 if/else 分支")
    print("=" * 60)
    print("  - classify 用条件边路由到 halve / triple_plus_one / END")
    print("  - 回边 halve->classify 构成循环（阶段 4 重点）")
    print("  - recursion_limit 防止死循环")


if __name__ == "__main__":
    main()
