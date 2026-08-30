"""阶段 1 示例：最小 DAG 执行器。

运行::

    python -m examples.stage_1_dag.run
"""

from __future__ import annotations

from tiny_langgraph import END, START, Graph


def main() -> None:
    print("=" * 60)
    print("示例 1：数字管线")
    print("=" * 60)

    graph = Graph()
    graph.add_node("add_one", lambda x: x + 1)
    graph.add_node("times_two", lambda x: x * 2)
    graph.add_node("square", lambda x: x**2)
    graph.add_edge(START, "add_one")
    graph.add_edge("add_one", "times_two")
    graph.add_edge("times_two", "square")
    graph.add_edge("square", END)

    app = graph.compile()
    for n in (1, 2, 3, 5):
        result = app.invoke(n)
        print(f"  {n} -> +1 -> *2 -> ^2 = {result}")

    print()
    print("=" * 60)
    print("示例 2：文本管线")
    print("=" * 60)

    text_graph = Graph()
    text_graph.add_node("strip", str.strip)
    text_graph.add_node("lower", str.lower)
    text_graph.add_node("reverse", lambda s: s[::-1])
    text_graph.add_edge(START, "strip")
    text_graph.add_edge("strip", "lower")
    text_graph.add_edge("lower", "reverse")
    text_graph.add_edge("reverse", END)

    text_app = text_graph.compile()
    print("  '  Hello World  ' -> strip -> lower -> reverse =")
    print(f"  '{text_app.invoke('  Hello World  ')}'")

    print()
    print("=" * 60)
    print("示例 3：单节点图")
    print("=" * 60)

    single = Graph()
    single.add_node("negate", lambda x: -x)
    single.add_edge(START, "negate")
    single.add_edge("negate", END)
    print(f"  negate(42) = {single.compile().invoke(42)}")


if __name__ == "__main__":
    main()