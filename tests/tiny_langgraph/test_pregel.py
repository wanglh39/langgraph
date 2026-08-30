"""Pregel 超级步与 fan-out 并行的测试 - 阶段 6。"""

from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from tiny_langgraph import END, START, StateGraph


class State(TypedDict):
    input: int
    result_a: Annotated[list[int], add]
    result_b: Annotated[list[int], add]
    final: int


class TestFanOut:
    """一个节点多条出边 → fan-out 并行。"""

    def test_fan_out_parallel(self) -> None:
        graph = StateGraph(State)
        graph.add_node("split", lambda s: {})
        graph.add_node("process_a", lambda s: {"result_a": [s["input"] * 2]})
        graph.add_node("process_b", lambda s: {"result_b": [s["input"] + 100]})
        graph.add_node("merge", lambda s: {"final": s["result_a"][-1] + s["result_b"][-1]})
        graph.add_edge(START, "split")
        graph.add_edge("split", "process_a")
        graph.add_edge("split", "process_b")
        graph.add_edge("process_a", "merge")
        graph.add_edge("process_b", "merge")
        graph.add_edge("merge", END)

        result = graph.compile().invoke(
            {"input": 5, "result_a": [], "result_b": [], "final": 0}
        )
        assert result["result_a"] == [10]
        assert result["result_b"] == [105]
        assert result["final"] == 115

    def test_parallel_nodes_read_same_snapshot(self) -> None:
        """同层节点读同一快照，互不影响。"""
        graph = StateGraph(State)
        graph.add_node("src", lambda s: {"input": 10})
        graph.add_node("a", lambda s: {"result_a": [s["input"]]})  # 读 input=10
        graph.add_node("b", lambda s: {"result_b": [s["input"]]})  # 也读 input=10
        graph.add_edge(START, "src")
        graph.add_edge("src", "a")
        graph.add_edge("src", "b")
        graph.add_edge("a", END)
        graph.add_edge("b", END)

        result = graph.compile().invoke(
            {"input": 0, "result_a": [], "result_b": [], "final": 0}
        )
        assert result["result_a"] == [10]
        assert result["result_b"] == [10]

    def test_superstep_events_show_parallel(self) -> None:
        graph = StateGraph(State)
        graph.add_node("split", lambda s: {})
        graph.add_node("a", lambda s: {"result_a": [1]})
        graph.add_node("b", lambda s: {"result_b": [2]})
        graph.add_edge(START, "split")
        graph.add_edge("split", "a")
        graph.add_edge("split", "b")
        graph.add_edge("a", END)
        graph.add_edge("b", END)

        events = list(graph.compile().stream(
            {"input": 0, "result_a": [], "result_b": [], "final": 0}
        ))
        assert events[0]["nodes"] == {"split"}
        assert events[1]["nodes"] == {"a", "b"}  # 并行层

    def test_multiple_edges_allowed(self) -> None:
        """阶段 6 允许一个节点多条出边。"""
        graph = StateGraph(State)
        graph.add_node("a", lambda s: {})
        graph.add_node("b", lambda s: {})
        graph.add_node("c", lambda s: {})
        graph.add_edge("a", "b")
        graph.add_edge("a", "c")  # 不报错
        assert graph._edges["a"] == ["b", "c"]


class TestSuperstepSemantics:
    """超级步语义。"""

    def test_reducer_merges_parallel_updates(self) -> None:
        """同层两个节点都写同一 Reducer 字段，合并。"""
        class S(TypedDict):
            values: Annotated[list[int], add]

        graph = StateGraph(S)
        graph.add_node("src", lambda s: {})
        graph.add_node("a", lambda s: {"values": [1]})
        graph.add_node("b", lambda s: {"values": [2]})
        graph.add_edge(START, "src")
        graph.add_edge("src", "a")
        graph.add_edge("src", "b")
        graph.add_edge("a", END)
        graph.add_edge("b", END)

        result = graph.compile().invoke({"values": []})
        assert result["values"] == [1, 2]