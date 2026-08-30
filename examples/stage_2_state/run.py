"""阶段 2 示例：共享状态 StateGraph。

运行::

    python -m examples.stage_2_state.run
"""

from __future__ import annotations

from typing import TypedDict

from tiny_langgraph import END, START, StateGraph


class PipelineState(TypedDict):
    number: int
    history: list[str]
    squared: int


def main() -> None:
    print("=" * 60)
    print("示例：带共享状态的数字管线")
    print("=" * 60)

    def increment(state: PipelineState) -> dict:
        n = state["number"] + 1
        return {"number": n, "history": state["history"] + [f"inc->{n}"]}

    def square(state: PipelineState) -> dict:
        n = state["number"] ** 2
        return {"squared": n, "history": state["history"] + [f"sq->{n}"]}

    def label(state: PipelineState) -> dict:
        return {"history": state["history"] + [f"final={state['squared']}"]}

    graph = StateGraph(PipelineState)
    graph.add_node("increment", increment)
    graph.add_node("square", square)
    graph.add_node("label", label)
    graph.add_edge(START, "increment")
    graph.add_edge("increment", "square")
    graph.add_edge("square", "label")
    graph.add_edge("label", END)

    app = graph.compile()
    for start in (2, 5, 10):
        result = app.invoke({"number": start, "history": [], "squared": 0})
        print(f"  起始 {start}: number={result['number']} squared={result['squared']}")
        print(f"    history={result['history']}")

    print()
    print("=" * 60)
    print("关键观察：节点能读整个 state，但只返回要改的字段")
    print("=" * 60)
    print("  - increment 改了 number 和 history，没碰 squared")
    print("  - square 改了 squared 和 history，number 保持不变")
    print("  - 合并是覆盖：history 每次被整体替换（阶段 5 会用 Reducer 改成追加）")


if __name__ == "__main__":
    main()