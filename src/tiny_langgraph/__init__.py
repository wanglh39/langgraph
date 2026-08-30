"""tiny_langgraph - 从零渐进式实现 LangGraph。

当前阶段：1（最小 DAG 执行器）

可用 API::

    from tiny_langgraph import Graph, START, END

    graph = Graph()
    graph.add_node("a", lambda x: x + 1)
    graph.add_node("b", lambda x: x * 2)
    graph.add_edge(START, "a")
    graph.add_edge("a", "b")
    graph.add_edge("b", END)

    app = graph.compile()
    app.invoke(3)  # 8

后续阶段将逐步引入：
    - 阶段 2：共享状态 StateGraph
    - 阶段 3：条件边与路由
    - 阶段 4：循环图
    - 阶段 5：Reducer 机制
    - 阶段 6：Pregel 超级步引擎
    - 阶段 7：Checkpoint 持久化
    - 阶段 8：Interrupt + 流式
    - 阶段 9：完整 Tool-calling Agent
"""

from tiny_langgraph.graph import END, START, CompiledGraph, Graph

__version__ = "0.1.0"
__all__ = ["START", "END", "Graph", "CompiledGraph", "__version__"]
