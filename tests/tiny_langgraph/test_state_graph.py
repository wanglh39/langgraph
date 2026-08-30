"""StateGraph 模块的测试 - 阶段 2：共享状态。

镜像 src/tiny_langgraph/graph.py 中 StateGraph 部分。
"""

from __future__ import annotations

from typing import TypedDict

import pytest

from tiny_langgraph import END, START, StateGraph


class State(TypedDict):
    count: int
    messages: list[str]
    total: int


class TestStateGraphBasic:
    """StateGraph 基本结构。"""

    def test_add_node_succeeds(self) -> None:
        graph = StateGraph(State)
        graph.add_node("a", lambda s: {})
        assert "a" in graph._nodes

    def test_duplicate_node_raises(self) -> None:
        graph = StateGraph(State)
        graph.add_node("a", lambda s: {})
        with pytest.raises(ValueError, match="已存在"):
            graph.add_node("a", lambda s: {})

    def test_compile_without_entry_raises(self) -> None:
        graph = StateGraph(State)
        graph.add_node("a", lambda s: {})
        with pytest.raises(ValueError, match="入口"):
            graph.compile()


class TestStateInvoke:
    """invoke 的状态传递与合并。"""

    def test_single_node_update(self) -> None:
        graph = StateGraph(State)
        graph.add_node("inc", lambda s: {"count": s["count"] + 1})
        graph.add_edge(START, "inc")
        graph.add_edge("inc", END)
        result = graph.compile().invoke({"count": 0, "messages": [], "total": 0})
        assert result["count"] == 1

    def test_state_flows_between_nodes(self) -> None:
        graph = StateGraph(State)
        graph.add_node("inc", lambda s: {"count": s["count"] + 1})
        graph.add_node("double", lambda s: {"count": s["count"] * 2})
        graph.add_edge(START, "inc")
        graph.add_edge("inc", "double")
        graph.add_edge("double", END)
        result = graph.compile().invoke({"count": 3, "messages": [], "total": 0})
        assert result["count"] == 8  # 3 -> 4 -> 8

    def test_partial_update_preserves_other_fields(self) -> None:
        graph = StateGraph(State)
        graph.add_node("a", lambda s: {"count": 99})
        graph.add_edge(START, "a")
        graph.add_edge("a", END)
        result = graph.compile().invoke({"count": 0, "messages": ["x"], "total": 5})
        assert result["count"] == 99
        assert result["messages"] == ["x"]
        assert result["total"] == 5

    def test_nodes_can_read_full_state(self) -> None:
        graph = StateGraph(State)
        graph.add_node("set_total", lambda s: {"total": s["count"] * 10})
        graph.add_edge(START, "set_total")
        graph.add_edge("set_total", END)
        result = graph.compile().invoke({"count": 7, "messages": [], "total": 0})
        assert result["total"] == 70
        assert result["count"] == 7

    def test_overwrite_semantics(self) -> None:
        graph = StateGraph(State)
        graph.add_node("a", lambda s: {"messages": ["a"]})
        graph.add_node("b", lambda s: {"messages": ["b"]})
        graph.add_edge(START, "a")
        graph.add_edge("a", "b")
        graph.add_edge("b", END)
        result = graph.compile().invoke({"count": 0, "messages": [], "total": 0})
        assert result["messages"] == ["b"]  # 覆盖，不是追加

    def test_invoke_does_not_mutate_input(self) -> None:
        graph = StateGraph(State)
        graph.add_node("inc", lambda s: {"count": s["count"] + 1})
        graph.add_edge(START, "inc")
        graph.add_edge("inc", END)
        initial = {"count": 0, "messages": [], "total": 0}
        graph.compile().invoke(initial)
        assert initial["count"] == 0  # 原 dict 未被修改

    def test_empty_update(self) -> None:
        graph = StateGraph(State)
        graph.add_node("noop", lambda s: {})
        graph.add_edge(START, "noop")
        graph.add_edge("noop", END)
        result = graph.compile().invoke({"count": 5, "messages": [], "total": 0})
        assert result["count"] == 5