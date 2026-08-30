"""循环图与 stream 的测试 - 阶段 4。"""

from __future__ import annotations

from typing import TypedDict

import pytest

from tiny_langgraph import END, START, StateGraph


class State(TypedDict):
    count: int
    log: list[str]


def _make_counter_graph() -> StateGraph:
    """循环图：loop 节点累加 count，到 5 停止。"""
    graph = StateGraph(State)
    graph.add_node("loop", lambda s: {"count": s["count"] + 1, "log": s["log"] + [s["count"] + 1]})
    graph.add_edge(START, "loop")
    graph.add_conditional_edges(
        "loop",
        lambda s: "again" if s["count"] < 5 else "done",
        {"again": "loop", "done": END},
    )
    return graph


class TestStream:
    """stream 方法。"""

    def test_stream_yields_events(self) -> None:
        app = _make_counter_graph().compile()
        events = list(app.stream({"count": 0, "log": []}))
        assert len(events) == 5
        assert events[0] == {"node": "loop", "state": {"count": 1, "log": [1]}, "step": 0}
        assert events[-1]["step"] == 4
        assert events[-1]["state"]["count"] == 5

    def test_stream_event_keys(self) -> None:
        app = _make_counter_graph().compile()
        event = next(app.stream({"count": 0, "log": []}))
        assert set(event.keys()) == {"node", "state", "step"}

    def test_invoke_matches_stream(self) -> None:
        app = _make_counter_graph().compile()
        initial = {"count": 0, "log": []}
        invoke_result = app.invoke(initial)
        stream_events = list(app.stream(initial))
        assert invoke_result == stream_events[-1]["state"]

    def test_stream_state_is_copy(self) -> None:
        app = _make_counter_graph().compile()
        events = list(app.stream({"count": 0, "log": []}))
        # 修改 yield 出来的 state 不应影响其他事件
        events[0]["state"]["count"] = 999
        assert events[1]["state"]["count"] == 2


class TestCycleExecution:
    """循环图执行。"""

    def test_cycle_terminates(self) -> None:
        app = _make_counter_graph().compile()
        result = app.invoke({"count": 0, "log": []})
        assert result["count"] == 5
        assert result["log"] == [1, 2, 3, 4, 5]

    def test_cycle_recursion_limit_raises(self) -> None:
        graph = StateGraph(State)
        graph.add_node("forever", lambda s: {"count": s["count"] + 1, "log": s["log"]})
        graph.add_edge(START, "forever")
        graph.add_conditional_edges("forever", lambda s: "go", {"go": "forever"})
        with pytest.raises(RecursionError):
            graph.compile().invoke({"count": 0, "log": []}, recursion_limit=5)