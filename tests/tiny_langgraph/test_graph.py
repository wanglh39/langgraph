"""graph 模块的测试 - 阶段 1：DAG 执行器。

镜像 src/tiny_langgraph/graph.py 的结构，逐功能覆盖。
"""

from __future__ import annotations

import pytest

from tiny_langgraph import END, START, Graph


class TestAddNode:
    """add_node 的行为。"""

    def test_add_node_succeeds(self) -> None:
        graph = Graph()
        graph.add_node("a", lambda x: x)
        assert "a" in graph._nodes

    def test_duplicate_node_raises(self) -> None:
        graph = Graph()
        graph.add_node("a", lambda x: x)
        with pytest.raises(ValueError, match="已存在"):
            graph.add_node("a", lambda x: x)

    @pytest.mark.parametrize("reserved", [START, END])
    def test_reserved_name_raises(self, reserved: str) -> None:
        graph = Graph()
        with pytest.raises(ValueError, match="保留字"):
            graph.add_node(reserved, lambda x: x)


class TestAddEdge:
    """add_edge 的行为。"""

    def test_start_edge_sets_entry_point(self) -> None:
        graph = Graph()
        graph.add_node("a", lambda x: x)
        graph.add_edge(START, "a")
        assert graph._entry_point == "a"

    def test_edge_to_end_succeeds(self) -> None:
        graph = Graph()
        graph.add_node("a", lambda x: x)
        graph.add_edge("a", END)

    def test_edge_to_unknown_target_raises(self) -> None:
        graph = Graph()
        graph.add_node("a", lambda x: x)
        with pytest.raises(ValueError, match="不存在"):
            graph.add_edge("a", "b")

    def test_edge_from_unknown_source_raises(self) -> None:
        graph = Graph()
        graph.add_node("a", lambda x: x)
        with pytest.raises(ValueError, match="不存在"):
            graph.add_edge("b", "a")

    def test_duplicate_outgoing_edge_raises(self) -> None:
        graph = Graph()
        graph.add_node("a", lambda x: x)
        graph.add_node("b", lambda x: x)
        graph.add_node("c", lambda x: x)
        graph.add_edge("a", "b")
        with pytest.raises(ValueError, match="已有出边"):
            graph.add_edge("a", "c")

    def test_start_edge_to_unknown_raises(self) -> None:
        graph = Graph()
        with pytest.raises(ValueError, match="不存在"):
            graph.add_edge(START, "a")


class TestCompile:
    """compile 的校验逻辑。"""

    def test_compile_without_entry_raises(self) -> None:
        graph = Graph()
        graph.add_node("a", lambda x: x)
        with pytest.raises(ValueError, match="入口"):
            graph.compile()

    def test_compile_detects_cycle(self) -> None:
        graph = Graph()
        graph.add_node("a", lambda x: x)
        graph.add_node("b", lambda x: x)
        graph.set_entry_point("a")
        graph._edges["a"] = "b"
        graph._edges["b"] = "a"
        with pytest.raises(ValueError, match="环"):
            graph.compile()

    def test_compile_detects_dangling_edge(self) -> None:
        graph = Graph()
        graph.add_node("a", lambda x: x)
        graph.set_entry_point("a")
        graph._edges["a"] = "ghost"
        with pytest.raises(ValueError, match="不存在"):
            graph.compile()


class TestInvoke:
    """invoke 的执行逻辑。"""

    def test_single_node(self) -> None:
        graph = Graph()
        graph.add_node("double", lambda x: x * 2)
        graph.add_edge(START, "double")
        graph.add_edge("double", END)
        assert graph.compile().invoke(5) == 10

    def test_linear_chain(self) -> None:
        graph = Graph()
        graph.add_node("add_one", lambda x: x + 1)
        graph.add_node("times_two", lambda x: x * 2)
        graph.add_node("minus_three", lambda x: x - 3)
        graph.add_edge(START, "add_one")
        graph.add_edge("add_one", "times_two")
        graph.add_edge("times_two", "minus_three")
        graph.add_edge("minus_three", END)
        # 3 -> 4 -> 8 -> 5
        assert graph.compile().invoke(3) == 5

    def test_chain_preserves_order(self) -> None:
        calls: list[str] = []
        graph = Graph()
        graph.add_node("a", lambda x: (calls.append("a"), x + 1)[1])
        graph.add_node("b", lambda x: (calls.append("b"), x + 1)[1])
        graph.add_node("c", lambda x: (calls.append("c"), x + 1)[1])
        graph.add_edge(START, "a")
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_edge("c", END)
        graph.compile().invoke(0)
        assert calls == ["a", "b", "c"]

    def test_entry_directly_to_end(self) -> None:
        graph = Graph()
        graph.add_node("a", lambda x: x * 10)
        graph.add_edge(START, "a")
        graph.add_edge("a", END)
        assert graph.compile().invoke(7) == 70

    def test_set_entry_and_finish_point(self) -> None:
        graph = Graph()
        graph.add_node("a", lambda x: x + 100)
        graph.add_node("b", lambda x: x + 1)
        graph.set_entry_point("a")
        graph.add_edge("a", "b")
        graph.set_finish_point("b")
        assert graph.compile().invoke(0) == 101

    def test_string_pipeline(self) -> None:
        graph = Graph()
        graph.add_node("upper", str.upper)
        graph.add_node("reverse", lambda s: s[::-1])
        graph.add_edge(START, "upper")
        graph.add_edge("upper", "reverse")
        graph.add_edge("reverse", END)
        assert graph.compile().invoke("abc") == "CBA"
