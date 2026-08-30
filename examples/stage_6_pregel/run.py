"""阶段 6 示例：Pregel 超级步 —— fan-out 并行 + 收集。

图结构：split 同时分发到 process_a 和 process_b（并行），
两者在同一个超级步执行，结果合并后传给 merge。

运行::

    python -m examples.stage_6_pregel.run
"""

from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from tiny_langgraph import END, START, StateGraph


class State(TypedDict):
    number: int
    doubled: Annotated[list[int], add]
    shifted: Annotated[list[int], add]
    combined: int


def main() -> None:
    print("=" * 60)
    print("示例：Pregel 超级步 —— 分发-并行-收集")
    print("=" * 60)
    print("图: split -> {process_a, process_b} -> merge")
    print("     process_a 和 process_b 在同一超级步并行执行")
    print()

    def split(state: State) -> dict:
        print(f"  [split] 收到 number={state['number']}, 分发到两个处理器")
        return {}

    def process_a(state: State) -> dict:
        result = state["number"] * 2
        print(f"  [process_a] 并行执行: {state['number']} * 2 = {result}")
        return {"doubled": [result]}

    def process_b(state: State) -> dict:
        result = state["number"] + 100
        print(f"  [process_b] 并行执行: {state['number']} + 100 = {result}")
        return {"shifted": [result]}

    def merge(state: State) -> dict:
        d, s = state["doubled"][-1], state["shifted"][-1]
        combined = d + s
        print(f"  [merge] 收集并行结果: {d} + {s} = {combined}")
        return {"combined": combined}

    graph = StateGraph(State)
    graph.add_node("split", split)
    graph.add_node("process_a", process_a)
    graph.add_node("process_b", process_b)
    graph.add_node("merge", merge)
    graph.add_edge(START, "split")
    graph.add_edge("split", "process_a")
    graph.add_edge("split", "process_b")
    graph.add_edge("process_a", "merge")
    graph.add_edge("process_b", "merge")
    graph.add_edge("merge", END)

    app = graph.compile()
    initial = {"number": 7, "doubled": [], "shifted": [], "combined": 0}

    print("按超级步执行：")
    print("-" * 60)
    for event in app.stream(initial):
        nodes = event["nodes"]
        print(f"  超级步 {event['step']}: 执行 {nodes}")
    print()

    result = app.invoke(initial)
    print(f"最终结果: combined = {result['combined']}")
    print(f"  (doubled={result['doubled']}, shifted={result['shifted']})")

    print()
    print("=" * 60)
    print("关键观察：Pregel 超级步")
    print("=" * 60)
    print("  - 超级步 0: split（1 个节点）")
    print("  - 超级步 1: process_a + process_b（2 个节点并行，读同一快照）")
    print("  - 超级步 2: merge（收集并行结果）")
    print("  - fan-out: split 有两条出边 -> process_a 和 process_b")
    print("  - 同层节点读同一状态快照，互不影响，最后用 Reducer 合并")


if __name__ == "__main__":
    main()