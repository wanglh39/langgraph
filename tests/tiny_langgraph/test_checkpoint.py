"""检查点持久化的测试 - 阶段 7。"""

from __future__ import annotations

from typing import TypedDict

import pytest

from tiny_langgraph import END, START, MemorySaver, SqliteSaver, StateGraph


class State(TypedDict):
    count: int


def _make_counter_graph() -> StateGraph:
    """循环图：loop 累加 count，到 5 停止。"""
    graph = StateGraph(State)
    graph.add_node("loop", lambda s: {"count": s["count"] + 1})
    graph.add_edge(START, "loop")
    graph.add_conditional_edges(
        "loop",
        lambda s: "again" if s["count"] < 5 else "done",
        {"again": "loop", "done": END},
    )
    return graph


class TestMemorySaver:
    """MemorySaver 基本操作。"""

    def test_put_and_get(self) -> None:
        saver = MemorySaver()
        saver.put("t1", 0, {"count": 1}, {"loop"})
        cp = saver.get("t1")
        assert cp is not None
        assert cp["step"] == 0
        assert cp["state"] == {"count": 1}
        assert cp["pending"] == {"loop"}

    def test_get_nonexistent(self) -> None:
        saver = MemorySaver()
        assert saver.get("nope") is None

    def test_list_ordered(self) -> None:
        saver = MemorySaver()
        for step in range(3):
            saver.put("t1", step, {"count": step}, {"loop"})
        cps = list(saver.list("t1"))
        assert [cp["step"] for cp in cps] == [0, 1, 2]

    def test_get_at(self) -> None:
        saver = MemorySaver()
        saver.put("t1", 0, {"count": 0}, {"a"})
        saver.put("t1", 1, {"count": 1}, {"b"})
        cp = saver.get_at("t1", 1)
        assert cp is not None
        assert cp["state"]["count"] == 1


class TestSqliteSaver:
    """SqliteSaver 基本操作。"""

    def test_put_and_get(self, tmp_path) -> None:
        saver = SqliteSaver(str(tmp_path / "cp.db"))
        saver.put("t1", 0, {"count": 1}, {"loop"})
        cp = saver.get("t1")
        assert cp is not None
        assert cp["state"] == {"count": 1}
        assert cp["pending"] == {"loop"}

    def test_persistence_across_connections(self, tmp_path) -> None:
        path = str(tmp_path / "cp.db")
        saver1 = SqliteSaver(path)
        saver1.put("t1", 0, {"count": 42}, {"loop"})
        saver1.close()

        saver2 = SqliteSaver(path)
        cp = saver2.get("t1")
        assert cp is not None
        assert cp["state"]["count"] == 42

    def test_list(self, tmp_path) -> None:
        saver = SqliteSaver(str(tmp_path / "cp.db"))
        for step in range(3):
            saver.put("t1", step, {"count": step}, {"loop"})
        cps = list(saver.list("t1"))
        assert len(cps) == 3


class TestCheckpointInGraph:
    """检查点在图执行中的存储与续跑。"""

    def test_invoke_stores_checkpoints(self) -> None:
        app = _make_counter_graph().compile(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "t1"}}
        app.invoke({"count": 0}, config=config)
        history = app.get_state_history(config)
        assert len(history) == 5  # count 1..5

    def test_resume_from_checkpoint(self) -> None:
        app = _make_counter_graph().compile(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "t1"}}

        with pytest.raises(RecursionError):
            app.invoke({"count": 0}, recursion_limit=3, config=config)

        history = app.get_state_history(config)
        assert len(history) == 3
        assert history[-1]["state"]["count"] == 3

        result = app.invoke(None, config=config, recursion_limit=25)
        assert result["count"] == 5

    def test_no_checkpointer_no_history(self) -> None:
        app = _make_counter_graph().compile()
        config = {"configurable": {"thread_id": "t1"}}
        app.invoke({"count": 0}, config=config)
        assert app.get_state_history(config) == []

    def test_resume_without_checkpoint_raises(self) -> None:
        app = _make_counter_graph().compile(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "ghost"}}
        with pytest.raises(ValueError, match="没有检查点"):
            app.invoke(None, config=config)

    def test_time_travel(self) -> None:
        app = _make_counter_graph().compile(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "t1"}}
        app.invoke({"count": 0}, config=config)

        history = app.get_state_history(config)
        step2 = history[1]  # count=2
        assert step2["state"]["count"] == 2