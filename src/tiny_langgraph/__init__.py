"""tiny_langgraph - 从零渐进式实现 LangGraph。

当前阶段：2（共享状态 StateGraph）

可用 API::

    from typing import TypedDict
    from tiny_langgraph import StateGraph, START, END

    class State(TypedDict):
        count: int

    graph = StateGraph(State)
    graph.add_node("a", lambda s: {"count": s["count"] + 1})
    graph.add_edge(START, "a")
    graph.add_edge("a", END)
    graph.compile().invoke({"count": 0})  # {"count": 1}
"""

from tiny_langgraph.graph import (
    END,
    START,
    CompiledGraph,
    CompiledStateGraph,
    Graph,
    StateGraph,
)

__version__ = "0.2.0"
__all__ = [
    "START",
    "END",
    "Graph",
    "CompiledGraph",
    "StateGraph",
    "CompiledStateGraph",
    "__version__",
]
