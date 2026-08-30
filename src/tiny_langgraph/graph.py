"""图执行引擎核心 - 阶段 1：最小 DAG 执行器。

本阶段实现一个最小的"函数链"图引擎：

    - 节点（Node）= 一个可调用对象，接收上一步的输出，返回自己的输出
    - 边（Edge）= 静态跳转，决定执行完一个节点后去哪个节点
    - 执行 = 从入口节点开始，顺着边依次执行（线性链）

这是 LangGraph 最朴素的形态——没有状态、没有条件分支、没有循环。
后续阶段会逐步引入这些能力。

为什么从"线性链"开始
--------------------
真实 LangGraph 的 ``langgraph.graph.Graph`` 也是这种"无状态线性链"语义：
节点签名是 ``Callable[[Any], Any]``，接收上一步的输出值，返回自己的输出值。
状态能力是在 ``StateGraph`` 中引入的（阶段 2）。

从线性链开始，是为了先把"图怎么存、怎么校验、怎么编译成可执行物"这套
骨架立起来，不被状态的合并逻辑干扰。一旦骨架稳了，阶段 2 只需把节点的
签名从 ``Callable[[Any], Any]`` 换成 ``Callable[[State], StateUpdate]``。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["START", "END", "Graph", "CompiledGraph"]

START = "__start__"
END = "__end__"


class Graph:
    """有向无环图（线性链形态）。

    阶段 1 限制为**线性链**：每个节点最多一条出边。这对应"无状态函数链"，
    节点接收上一步的输出值，返回自己的输出值。

    用法::

        graph = Graph()
        graph.add_node("a", lambda x: x + 1)
        graph.add_node("b", lambda x: x * 2)
        graph.add_edge(START, "a")
        graph.add_edge("a", "b")
        graph.add_edge("b", END)

        app = graph.compile()
        app.invoke(3)  # 3 -> a:4 -> b:8 -> 返回 8
    """

    def __init__(self) -> None:
        self._nodes: dict[str, Callable[[Any], Any]] = {}
        self._edges: dict[str, str] = {}
        self._entry_point: str | None = None

    def add_node(self, name: str, func: Callable[[Any], Any]) -> None:
        """添加一个节点。

        Args:
            name: 节点名（唯一标识，不能用 ``START`` / ``END``）。
            func: 节点函数，签名 ``func(prev_output) -> this_output``。
        """
        if name in (START, END):
            raise ValueError(f"节点名 '{name}' 是保留字，不能用作节点名")
        if name in self._nodes:
            raise ValueError(f"节点 '{name}' 已存在")
        self._nodes[name] = func

    def add_edge(self, source: str, target: str) -> None:
        """添加一条静态边：执行完 ``source`` 后跳到 ``target``。

        特殊用法：
            - ``add_edge(START, "a")``：设置入口节点为 ``a``
            - ``add_edge("c", END)``：设置 ``c`` 为结束节点

        阶段 1 限制：每个节点最多一条出边（线性链）。
        """
        if source == START:
            if target not in self._nodes:
                raise ValueError(f"目标节点 '{target}' 不存在")
            self._entry_point = target
            return
        if source not in self._nodes:
            raise ValueError(f"源节点 '{source}' 不存在")
        if target != END and target not in self._nodes:
            raise ValueError(f"目标节点 '{target}' 不存在")
        if source in self._edges:
            raise ValueError(
                f"节点 '{source}' 已有出边（阶段 1 为线性链：每节点最多一条出边）"
            )
        self._edges[source] = target

    def set_entry_point(self, name: str) -> None:
        """设置入口节点（等价于 ``add_edge(START, name)``）。"""
        if name not in self._nodes:
            raise ValueError(f"节点 '{name}' 不存在")
        self._entry_point = name

    def set_finish_point(self, name: str) -> None:
        """设置结束节点（等价于 ``add_edge(name, END)``）。"""
        self.add_edge(name, END)

    def compile(self) -> CompiledGraph:
        """校验图结构并编译为可执行物。

        compile 做两件事：
            1. 校验：有入口、边指向的节点都存在、无环
            2. 构建执行顺序：从入口顺着边走，收集节点序列

        Returns:
            编译后的 :class:`CompiledGraph`，可调用其 ``invoke`` 方法执行。
        """
        if self._entry_point is None:
            raise ValueError(
                "未设置入口节点（用 add_edge(START, ...) 或 set_entry_point(...)）"
            )
        order = self._build_execution_order()
        return CompiledGraph(nodes=self._nodes, order=order)

    def _build_execution_order(self) -> list[str]:
        """从入口顺着边走，构建线性执行顺序；同时检测环。"""
        order: list[str] = []
        current: str | None = self._entry_point
        while current is not None and current != END:
            if current not in self._nodes:
                raise ValueError(f"边指向不存在的节点 '{current}'")
            if current in order:
                raise ValueError(f"检测到环：节点 '{current}' 被二次访问")
            order.append(current)
            current = self._edges.get(current)
        return order


class CompiledGraph:
    """编译后的可执行图。

    由 :meth:`Graph.compile` 产生，不可变。调用 :meth:`invoke` 执行图。
    """

    def __init__(
        self, nodes: dict[str, Callable[[Any], Any]], order: list[str]
    ) -> None:
        self._nodes = nodes
        self._order = order

    def invoke(self, input: Any) -> Any:
        """从 ``input`` 开始，按编译好的顺序依次执行节点，返回最终输出。

        Args:
            input: 传给入口节点的初始值。

        Returns:
            最后一个节点的输出（若图为空则返回 ``input`` 本身）。
        """
        result = input
        for name in self._order:
            result = self._nodes[name](result)
        return result
