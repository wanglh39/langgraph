"""条件边的测试 - 阶段 3。"""

from __future__ import annotations

from typing import TypedDict

import pytest

from tiny_langgraph import END, START, StateGraph


class State(TypedDict):
    count: int
    branch: str


class TestConditionalEdges:
    """add_conditional_edges 的行为。"""

    def test_router_selects_branch(self) -> None:
        graph = StateGraph(State)
        graph.add_node("start", lambda s: {"branch": "left" if s["count"] < 5 else "right"})
        graph.add_node("left", lambda s: {"count": -1})
        graph.add_node("right", lambda s: {"count": 99})
        graph.add_edge(START, "start")
        graph.add_conditional_edges(
            "start",
            lambda s: s["branch"],
            {"left": "left", "right": "right"},
        )
        graph.add_edge("left", END)
        graph.add_edge("right", END)

        app = graph.compile()
        assert app.invoke({"count": 0, "branch": ""})["count"] == -1
        assert app.invoke({"count": 10, "branch": ""})["count"] == 99

    def test_router_to_end(self) -> None:
        graph = StateGraph(State)
        graph.add_node("check", lambda s: {})
        graph.add_edge(START, "check")
        graph.add_conditional_edges(
            "check",
            lambda s: "stop" if s["count"] >= 3 else "go",
            {"stop": END, "go": "check"},
        )
        result = graph.compile().invoke({"count": 3, "branch": ""})
        assert result["count"] == 3

    def test_unknown_label_raises(self) -> None:
        graph = StateGraph(State)
        graph.add_node("a", lambda s: {})
        graph.add_edge(START, "a")
        graph.add_conditional_edges("a", lambda s: "unknown", {"known": END})
        with pytest.raises(ValueError, match="未知标签"):
            graph.compile().invoke({"count": 0, "branch": ""})

    def test_cannot_mix_static_and_conditional(self) -> None:
        graph = StateGraph(State)
        graph.add_node("a", lambda s: {})
        graph.add_node("b", lambda s: {})
        graph.add_edge("a", "b")
        with pytest.raises(ValueError, match="静态出边"):
            graph.add_conditional_edges("a", lambda s: "x", {"x": END})

    def test_conditional_then_static_blocks_edge(self) -> None:
        graph = StateGraph(State)
        graph.add_node("a", lambda s: {})
        graph.add_node("b", lambda s: {})
        graph.add_conditional_edges("a", lambda s: "x", {"x": "b"})
        with pytest.raises(ValueError, match="条件出边"):
            graph.add_edge("a", END)

    def test_conditional_target_must_exist(self) -> None:
        graph = StateGraph(State)
        graph.add_node("a", lambda s: {})
        with pytest.raises(ValueError, match="不存在"):
            graph.add_conditional_edges("a", lambda s: "x", {"x": "ghost"})


class TestRecursionLimit:
    """recursion_limit 防死循环。"""

    def test_recursion_limit_raises(self) -> None:
        graph = StateGraph(State)
        graph.add_node("loop", lambda s: {"count": s["count"] + 1})
        graph.add_edge(START, "loop")
        graph.add_conditional_edges(
            "loop",
            lambda s: "again",
            {"again": "loop"},
        )
        with pytest.raises(RecursionError, match="recursion_limit"):
            graph.compile().invoke({"count": 0, "branch": ""}, recursion_limit=10)

    def test_custom_recursion_limit(self) -> None:
        graph = StateGraph(State)
        graph.add_node("loop", lambda s: {"count": s["count"] + 1})
        graph.add_edge(START, "loop")
        graph.add_conditional_edges(
            "loop",
            lambda s: "again" if s["count"] < 5 else "stop",
            {"again": "loop", "stop": END},
        )
        result = graph.compile().invoke({"count": 0, "branch": ""}, recursion_limit=100)
        assert result["count"] == 5