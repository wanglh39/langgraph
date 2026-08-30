"""图执行引擎核心 - 阶段 1-4：DAG + 状态 + 条件边 + 循环。

阶段 1：无状态函数链
    - 节点 = ``Callable[[Any], Any]``，接收上一步输出，返回自己的输出
    - :class:`Graph` / :class:`CompiledGraph`

阶段 2：共享状态
    - 节点 = ``Callable[[State], StateUpdate]``，接收整个状态，返回更新片段
    - 引擎负责把更新片段合并回完整状态（覆盖合并）
    - :class:`StateGraph` / :class:`CompiledStateGraph`

阶段 3：条件边
    - :meth:`StateGraph.add_conditional_edges`：执行完节点后，根据状态决定跳哪
    - 执行模型从"预编译顺序"改为"运行时动态遍历"（while 循环）
    - 这就是 ``if/else`` 在图里的表达

阶段 4：循环图 + stream
    - 回边 + 条件边构成循环（Agent 的 ReAct 循环）
    - :meth:`CompiledStateGraph.stream`：流式 yield 每步事件
    - ``invoke`` 委托给 ``stream``，为阶段 7 检查点和阶段 8 流式铺路
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = [
    "START",
    "END",
    "Graph",
    "CompiledGraph",
    "StateGraph",
    "CompiledStateGraph",
]

START = "__start__"
END = "__end__"

DEFAULT_RECURSION_LIMIT = 25


class Graph:
    """有向无环图（线性链形态） - 阶段 1。

    无状态函数链：节点签名 ``Callable[[Any], Any]``，接收上一步输出，返回自己的输出。

    用法::

        graph = Graph()
        graph.add_node("a", lambda x: x + 1)
        graph.add_node("b", lambda x: x * 2)
        graph.add_edge(START, "a")
        graph.add_edge("a", "b")
        graph.add_edge("b", END)

        app = graph.compile()
        app.invoke(3)  # 3 -> a:4 -> b:8
    """

    def __init__(self) -> None:
        self._nodes: dict[str, Callable[[Any], Any]] = {}
        self._edges: dict[str, str] = {}
        self._entry_point: str | None = None

    def add_node(self, name: str, func: Callable[[Any], Any]) -> None:
        if name in (START, END):
            raise ValueError(f"节点名 '{name}' 是保留字，不能用作节点名")
        if name in self._nodes:
            raise ValueError(f"节点 '{name}' 已存在")
        self._nodes[name] = func

    def add_edge(self, source: str, target: str) -> None:
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
        if name not in self._nodes:
            raise ValueError(f"节点 '{name}' 不存在")
        self._entry_point = name

    def set_finish_point(self, name: str) -> None:
        self.add_edge(name, END)

    def compile(self) -> CompiledGraph:
        if self._entry_point is None:
            raise ValueError(
                "未设置入口节点（用 add_edge(START, ...) 或 set_entry_point(...)）"
            )
        order = self._build_execution_order()
        return CompiledGraph(nodes=self._nodes, order=order)

    def _build_execution_order(self) -> list[str]:
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
    """编译后的可执行图（无状态）。"""

    def __init__(
        self, nodes: dict[str, Callable[[Any], Any]], order: list[str]
    ) -> None:
        self._nodes = nodes
        self._order = order

    def invoke(self, input: Any) -> Any:
        result = input
        for name in self._order:
            result = self._nodes[name](result)
        return result


class StateGraph:
    """有状态的有向图 - 阶段 2-3。

    节点签名 ``Callable[[State], StateUpdate]``：接收整个状态，返回更新片段。
    引擎用覆盖合并：``state.update(update)``。

    阶段 3 新增 :meth:`add_conditional_edges`：执行完节点后，根据状态路由到
    不同节点。这让图能做 ``if/else`` 分支。

    用法::

        from typing import TypedDict

        class State(TypedDict):
            count: int

        graph = StateGraph(State)
        graph.add_node("inc", lambda s: {"count": s["count"] + 1})
        graph.add_node("done", lambda s: {})

        def router(s) -> str:
            return "inc" if s["count"] < 3 else "done"

        graph.add_edge(START, "inc")
        graph.add_conditional_edges("inc", router, {"inc": "inc", "done": "done"})
        graph.add_edge("done", END)

        app = graph.compile()
        app.invoke({"count": 0})  # count: 0->1->2->3
    """

    def __init__(self, state_type: type) -> None:
        self._state_type = state_type
        self._nodes: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
        self._edges: dict[str, str] = {}
        self._conditional_edges: dict[
            str,
            tuple[
                Callable[[dict[str, Any]], str],
                dict[str, str],
            ],
        ] = {}
        self._entry_point: str | None = None

    def add_node(
        self, name: str, func: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> None:
        """添加一个节点。

        Args:
            name: 节点名。
            func: ``func(state) -> update``，返回**更新片段**。
        """
        if name in (START, END):
            raise ValueError(f"节点名 '{name}' 是保留字，不能用作节点名")
        if name in self._nodes:
            raise ValueError(f"节点 '{name}' 已存在")
        self._nodes[name] = func

    def add_edge(self, source: str, target: str) -> None:
        """添加一条静态边：执行完 ``source`` 后无条件跳 ``target``。"""
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
            raise ValueError(f"节点 '{source}' 已有静态出边")
        if source in self._conditional_edges:
            raise ValueError(f"节点 '{source}' 已有条件出边，不能再加静态边")
        self._edges[source] = target

    def add_conditional_edges(
        self,
        source: str,
        router: Callable[[dict[str, Any]], str],
        mapping: dict[str, str],
    ) -> None:
        """添加条件边：执行完 ``source`` 后，调用 ``router(state)`` 决定跳哪。

        Args:
            source: 源节点名。
            router: ``router(state) -> label``，返回路由标签。
            mapping: ``{label: target_node}``，标签到目标节点的映射。
                     目标可以是节点名或 :data:`END`。
        """
        if source not in self._nodes:
            raise ValueError(f"源节点 '{source}' 不存在")
        if source in self._edges:
            raise ValueError(f"节点 '{source}' 已有静态出边，不能再加条件边")
        if source in self._conditional_edges:
            raise ValueError(f"节点 '{source}' 已有条件出边")
        for label, target in mapping.items():
            if target != END and target not in self._nodes:
                raise ValueError(
                    f"条件边标签 '{label}' 指向不存在的节点 '{target}'"
                )
        self._conditional_edges[source] = (router, mapping)

    def set_entry_point(self, name: str) -> None:
        if name not in self._nodes:
            raise ValueError(f"节点 '{name}' 不存在")
        self._entry_point = name

    def set_finish_point(self, name: str) -> None:
        self.add_edge(name, END)

    def compile(self) -> CompiledStateGraph:
        """校验图结构并编译为可执行物。

        阶段 3 起，因条件边让执行顺序依赖运行时状态，compile 不再预构建
        执行顺序，而是把图结构原样传给 :class:`CompiledStateGraph`，
        由 invoke 在运行时动态遍历。
        """
        if self._entry_point is None:
            raise ValueError(
                "未设置入口节点（用 add_edge(START, ...) 或 set_entry_point(...)）"
            )
        return CompiledStateGraph(
            nodes=self._nodes,
            edges=self._edges,
            conditional_edges=self._conditional_edges,
            entry_point=self._entry_point,
        )


class CompiledStateGraph:
    """编译后的有状态可执行图。

    执行模型（阶段 3 起）：从入口节点开始，while 循环动态遍历——
    每步执行当前节点、合并状态、决定下一个节点（静态边 or 条件边）。
    """

    def __init__(
        self,
        nodes: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
        edges: dict[str, str],
        conditional_edges: dict[
            str,
            tuple[Callable[[dict[str, Any]], str], dict[str, str]],
        ],
        entry_point: str,
    ) -> None:
        self._nodes = nodes
        self._edges = edges
        self._conditional_edges = conditional_edges
        self._entry_point = entry_point

    def stream(
        self,
        input: dict[str, Any],
        *,
        recursion_limit: int = DEFAULT_RECURSION_LIMIT,
    ):
        """流式执行图，逐步 yield 执行事件。

        每个事件是一个 dict：``{"node": str, "state": dict, "step": int}``。

        这是阶段 4 的核心：把执行循环从 ``invoke`` 提取出来，让调用方能
        逐步观察执行过程（调试、前端流式展示、阶段 7 检查点）。

        Args:
            input: 初始状态（会被复制）。
            recursion_limit: 最大执行步数。

        Yields:
            每步的执行事件 dict。
        """
        state = dict(input)
        current = self._entry_point
        step = 0
        while current != END:
            if step >= recursion_limit:
                raise RecursionError(
                    f"执行超过 recursion_limit ({recursion_limit}) 步，疑似死循环"
                )
            update = self._nodes[current](state)
            state.update(update)
            yield {"node": current, "state": dict(state), "step": step}
            current = self._next_node(current, state)
            step += 1

    def invoke(
        self,
        input: dict[str, Any],
        *,
        recursion_limit: int = DEFAULT_RECURSION_LIMIT,
    ) -> dict[str, Any]:
        """从初始状态 ``input`` 开始执行图，返回最终状态。

        内部委托给 :meth:`stream`，取最后一个事件的状态。

        Args:
            input: 初始状态（会被复制，不修改原 dict）。
            recursion_limit: 最大执行步数，防止死循环。默认 25。

        Returns:
            执行完后的最终状态。
        """
        final_state = dict(input)
        for event in self.stream(input, recursion_limit=recursion_limit):
            final_state = event["state"]
        return final_state

    def _next_node(self, current: str, state: dict[str, Any]) -> str:
        """决定下一个节点：条件边优先，否则静态边，否则 END。"""
        if current in self._conditional_edges:
            router, mapping = self._conditional_edges[current]
            label = router(state)
            if label not in mapping:
                raise ValueError(
                    f"节点 '{current}' 的路由返回了未知标签 '{label}'"
                )
            return mapping[label]
        return self._edges.get(current, END)
