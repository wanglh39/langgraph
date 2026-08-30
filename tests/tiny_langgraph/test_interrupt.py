"""Interrupt 人机协作的测试 - 阶段 8。"""

from __future__ import annotations

from typing import Any, TypedDict

from tiny_langgraph import END, START, MemorySaver, StateGraph


class State(TypedDict):
    step_name: str
    approved: bool
    result: str


def _make_approval_graph() -> StateGraph:
    """审批流程：propose -> review -> execute。"""
    graph = StateGraph(State)
    graph.add_node("propose", lambda s: {"step_name": "proposed", "result": "方案A"})
    graph.add_node("review", lambda s: {"step_name": "reviewed"})
    graph.add_node("execute", lambda s: {"result": f"执行: {s['result']}"})
    graph.add_edge(START, "propose")
    graph.add_edge("propose", "review")
    graph.add_edge("review", "execute")
    graph.add_edge("execute", END)
    return graph


class TestInterruptBefore:
    """interrupt_before 在指定节点前暂停。"""

    def test_pauses_before_node(self) -> None:
        app = _make_approval_graph().compile(
            checkpointer=MemorySaver(), interrupt_before=["review"]
        )
        config = {"configurable": {"thread_id": "t1"}}
        events = list(app.stream({"step_name": "", "approved": False, "result": ""}, config=config))
        assert len(events) == 2
        assert events[0]["nodes"] == {"propose"}
        assert events[1]["nodes"] == {"review"}
        assert events[1].get("interrupt") == "before"

    def test_resume_after_interrupt(self) -> None:
        app = _make_approval_graph().compile(
            checkpointer=MemorySaver(), interrupt_before=["review"]
        )
        config = {"configurable": {"thread_id": "t1"}}
        list(app.stream({"step_name": "", "approved": False, "result": ""}, config=config))

        result = app.invoke(None, config=config)
        assert result["step_name"] == "reviewed"
        assert "执行" in result["result"]


class TestInterruptAfter:
    """interrupt_after 在指定节点后暂停。"""

    def test_pauses_after_node(self) -> None:
        app = _make_approval_graph().compile(
            checkpointer=MemorySaver(), interrupt_after=["propose"]
        )
        config = {"configurable": {"thread_id": "t1"}}
        events = list(app.stream({"step_name": "", "approved": False, "result": ""}, config=config))
        assert len(events) == 1
        assert events[0].get("interrupt") == "after"

    def test_resume_after_interrupt_after(self) -> None:
        app = _make_approval_graph().compile(
            checkpointer=MemorySaver(), interrupt_after=["propose"]
        )
        config = {"configurable": {"thread_id": "t1"}}
        list(app.stream({"step_name": "", "approved": False, "result": ""}, config=config))
        result = app.invoke(None, config=config)
        assert "执行" in result["result"]


class TestHumanInTheLoop:
    """人机协作：暂停 → 人类修改状态 → 续跑。"""

    def test_update_state_then_resume(self) -> None:
        graph = StateGraph(State)
        graph.add_node("propose", lambda s: {"result": "原始方案"})
        graph.add_node("execute", lambda s: {"result": f"执行: {s['result']}"})
        graph.add_edge(START, "propose")
        graph.add_edge("propose", "execute")
        graph.add_edge("execute", END)

        app = graph.compile(
            checkpointer=MemorySaver(), interrupt_after=["propose"]
        )
        config = {"configurable": {"thread_id": "t1"}}

        list(app.stream({"step_name": "", "approved": False, "result": ""}, config=config))

        app.update_state(config, {"result": "人类修改的方案"})

        result = app.invoke(None, config=config)
        assert result["result"] == "执行: 人类修改的方案"

    def test_update_state_with_approval(self) -> None:
        graph = StateGraph(State)

        def review(s: State) -> dict[str, Any]:
            return {"step_name": "approved" if s["approved"] else "rejected"}

        graph.add_node("propose", lambda s: {"result": "方案"})
        graph.add_node("review", review)
        graph.add_edge(START, "propose")
        graph.add_edge("propose", "review")
        graph.add_edge("review", END)

        app = graph.compile(
            checkpointer=MemorySaver(), interrupt_before=["review"]
        )
        config = {"configurable": {"thread_id": "t1"}}

        list(app.stream({"step_name": "", "approved": False, "result": ""}, config=config))
        app.update_state(config, {"approved": True})
        result = app.invoke(None, config=config)
        assert result["step_name"] == "approved"