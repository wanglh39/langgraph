"""Reducer 机制的测试 - 阶段 5。"""

from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from tiny_langgraph import END, START, StateGraph, add_messages
from tiny_langgraph.reducers import extract_reducers


class State(TypedDict):
    messages: Annotated[list[str], add]
    count: int
    history: Annotated[list[str], add]


class TestExtractReducers:
    """extract_reducers 从 Annotated 提取。"""

    def test_extracts_annotated_reducers(self) -> None:
        reducers = extract_reducers(State)
        assert "messages" in reducers
        assert "history" in reducers
        assert "count" not in reducers

    def test_no_reducers_for_plain_types(self) -> None:
        class Plain(TypedDict):
            a: int
            b: str

        assert extract_reducers(Plain) == {}


class TestReducerMerge:
    """带 Reducer 的状态合并。"""

    def test_list_appends_with_add(self) -> None:
        graph = StateGraph(State)
        graph.add_node("a", lambda s: {"messages": ["hello"]})
        graph.add_node("b", lambda s: {"messages": ["world"]})
        graph.add_edge(START, "a")
        graph.add_edge("a", "b")
        graph.add_edge("b", END)
        result = graph.compile().invoke({"messages": [], "count": 0, "history": []})
        assert result["messages"] == ["hello", "world"]

    def test_non_reducer_field_overwrites(self) -> None:
        graph = StateGraph(State)
        graph.add_node("a", lambda s: {"count": 1})
        graph.add_node("b", lambda s: {"count": 2})
        graph.add_edge(START, "a")
        graph.add_edge("a", "b")
        graph.add_edge("b", END)
        result = graph.compile().invoke({"messages": [], "count": 0, "history": []})
        assert result["count"] == 2

    def test_mixed_reducer_and_overwrite(self) -> None:
        graph = StateGraph(State)
        graph.add_node("a", lambda s: {"messages": ["m1"], "count": 10})
        graph.add_node("b", lambda s: {"messages": ["m2"], "count": 20})
        graph.add_edge(START, "a")
        graph.add_edge("a", "b")
        graph.add_edge("b", END)
        result = graph.compile().invoke({"messages": [], "count": 0, "history": []})
        assert result["messages"] == ["m1", "m2"]
        assert result["count"] == 20

    def test_reducer_in_cycle(self) -> None:
        graph = StateGraph(State)
        graph.add_node(
            "loop",
            lambda s: {"messages": [f"step-{s['count']}"], "count": s["count"] + 1},
        )
        graph.add_edge(START, "loop")
        graph.add_conditional_edges(
            "loop",
            lambda s: "again" if s["count"] < 3 else "done",
            {"again": "loop", "done": END},
        )
        result = graph.compile().invoke({"messages": [], "count": 0, "history": []})
        assert result["messages"] == ["step-0", "step-1", "step-2"]
        assert result["count"] == 3


class TestAddMessages:
    """add_messages 智能合并。"""

    def test_append_new_messages(self) -> None:
        result = add_messages(["a"], ["b", "c"])
        assert result == ["a", "b", "c"]

    def test_overwrite_by_id(self) -> None:
        old = [{"id": 1, "content": "old"}, {"id": 2, "content": "keep"}]
        new = [{"id": 1, "content": "new"}]
        result = add_messages(old, new)
        assert result == [{"id": 1, "content": "new"}, {"id": 2, "content": "keep"}]

    def test_mixed_overwrite_and_append(self) -> None:
        old = [{"id": 1, "content": "old"}, "plain"]
        new = [{"id": 1, "content": "updated"}, {"id": 3, "content": "new"}]
        result = add_messages(old, new)
        assert result[0] == {"id": 1, "content": "updated"}
        assert result[1] == "plain"
        assert result[2] == {"id": 3, "content": "new"}

    def test_empty_old(self) -> None:
        assert add_messages(None, ["a"]) == ["a"]
        assert add_messages([], ["a"]) == ["a"]

    def test_empty_new(self) -> None:
        assert add_messages(["a"], None) == ["a"]
        assert add_messages(["a"], []) == ["a"]

    def test_does_not_mutate_inputs(self) -> None:
        old = ["a"]
        new = ["b"]
        add_messages(old, new)
        assert old == ["a"]
        assert new == ["b"]


class TestAddMessagesInGraph:
    """add_messages 作为 Reducer 在图中使用。"""

    def test_messages_accumulate(self) -> None:
        class MsgState(TypedDict):
            messages: Annotated[list[dict], add_messages]

        graph = StateGraph(MsgState)
        graph.add_node("a", lambda s: {"messages": [{"id": 1, "role": "user", "content": "hi"}]})
        graph.add_node("b", lambda s: {"messages": [{"id": 2, "role": "ai", "content": "hello"}]})
        graph.add_edge(START, "a")
        graph.add_edge("a", "b")
        graph.add_edge("b", END)
        result = graph.compile().invoke({"messages": []})
        assert len(result["messages"]) == 2
        assert result["messages"][0]["id"] == 1
        assert result["messages"][1]["id"] == 2

    def test_messages_overwrite_by_id_in_graph(self) -> None:
        class MsgState(TypedDict):
            messages: Annotated[list[dict], add_messages]

        graph = StateGraph(MsgState)
        graph.add_node("init", lambda s: {"messages": [{"id": 1, "content": "draft"}]})
        graph.add_node("update", lambda s: {"messages": [{"id": 1, "content": "final"}]})
        graph.add_edge(START, "init")
        graph.add_edge("init", "update")
        graph.add_edge("update", END)
        result = graph.compile().invoke({"messages": []})
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == "final"