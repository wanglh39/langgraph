"""图执行引擎核心 - 阶段 1-6：DAG + 状态 + 条件边 + 循环 + Reducer + Pregel。

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
    - ``invoke`` 委托给 ``stream``

阶段 5：Reducer
    - ``Annotated[T, reducer]`` 声明字段合并策略
    - :func:`add_messages` 智能合并消息（按 id 覆盖）
    - 合并从 ``state.update`` 改为 :meth:`_merge`（有 Reducer 用 Reducer，否则覆盖）

阶段 6：Pregel 超级步
    - 执行模型从"单节点遍历"升级为"超级步并行层"
    - 同一超级步的多个节点读同一状态快照、各自计算、最后合并
    - 静态边支持 fan-out（一个节点多条出边 → 多个后继并行）
    - 通道 = 字段 + Reducer（概念统一）
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Any

from tiny_langgraph.checkpoint import BaseCheckpointSaver
from tiny_langgraph.reducers import extract_reducers

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
        self._reducers = extract_reducers(state_type)
        self._nodes: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
        self._edges: dict[str, list[str]] = {}
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
        if source in self._conditional_edges:
            raise ValueError(f"节点 '{source}' 已有条件出边，不能再加静态边")
        self._edges.setdefault(source, []).append(target)

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

    def compile(
        self,
        checkpointer: BaseCheckpointSaver | None = None,
        *,
        interrupt_before: list[str] | None = None,
        interrupt_after: list[str] | None = None,
    ) -> CompiledStateGraph:
        """校验图结构并编译为可执行物。

        Args:
            checkpointer: 检查点存储（阶段 7）。
            interrupt_before: 在这些节点**之前**暂停（阶段 8）。需配合 checkpointer。
            interrupt_after: 在这些节点**之后**暂停（阶段 8）。需配合 checkpointer。
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
            reducers=self._reducers,
            checkpointer=checkpointer,
            interrupt_before=set(interrupt_before or []),
            interrupt_after=set(interrupt_after or []),
        )


class CompiledStateGraph:
    """编译后的有状态可执行图。

    执行模型（阶段 3 起）：从入口节点开始，while 循环动态遍历——
    每步执行当前节点、合并状态、决定下一个节点（静态边 or 条件边）。
    """

    def __init__(
        self,
        nodes: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
        edges: dict[str, list[str]],
        conditional_edges: dict[
            str,
            tuple[Callable[[dict[str, Any]], str], dict[str, str]],
        ],
        entry_point: str,
        reducers: dict[str, Callable[[Any, Any], Any]] | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        interrupt_before: set[str] | None = None,
        interrupt_after: set[str] | None = None,
    ) -> None:
        self._nodes = nodes
        self._edges = edges
        self._conditional_edges = conditional_edges
        self._entry_point = entry_point
        self._reducers = reducers or {}
        self._checkpointer = checkpointer
        self._interrupt_before = interrupt_before or set()
        self._interrupt_after = interrupt_after or set()

    def _merge(self, state: dict[str, Any], update: dict[str, Any]) -> None:
        """把更新片段合并进状态：有 Reducer 用 Reducer，否则覆盖。"""
        for key, value in update.items():
            if key in self._reducers:
                state[key] = self._reducers[key](state.get(key), value)
            else:
                state[key] = value

    def stream(
        self,
        input: dict[str, Any] | None,
        *,
        recursion_limit: int = DEFAULT_RECURSION_LIMIT,
        config: dict[str, Any] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """流式执行图，按 Pregel 超级步逐步 yield 事件。

        每个事件：``{"nodes": set[str], "state": dict, "step": int}``。

        检查点（阶段 7）：
            - 传了 ``config`` 含 ``thread_id`` 且编译时有 checkpointer，
              每个超级步后存快照
            - ``input=None`` 表示**续跑**：从该 thread 的最新检查点恢复

        Args:
            input: 初始状态；``None`` 表示从检查点续跑。
            recursion_limit: 最大超级步数。
            config: ``{"configurable": {"thread_id": "..."}}``。

        Yields:
            每个超级步的执行事件 dict。
        """
        thread_id = self._get_thread_id(config)

        if input is None and self._checkpointer and thread_id:
            cp = self._checkpointer.get(thread_id)
            if cp is None:
                raise ValueError(f"thread '{thread_id}' 没有检查点，无法续跑")
            state = dict(cp["state"])
            pending = set(cp["pending"])
            step = cp["step"] + 1
            resuming = True
        else:
            state = dict(input) if input else {}
            pending = {self._entry_point}
            step = 0
            resuming = False

        while pending:
            if step >= recursion_limit:
                raise RecursionError(
                    f"执行超过 recursion_limit ({recursion_limit}) 步，疑似死循环"
                )

            if not resuming and self._interrupt_before and (
                pending & self._interrupt_before
            ):
                if self._checkpointer and thread_id:
                    self._checkpointer.put(thread_id, step, dict(state), pending)
                yield {
                    "nodes": pending,
                    "state": dict(state),
                    "step": step,
                    "interrupt": "before",
                }
                return
            resuming = False

            step_state = dict(state)
            updates: list[dict[str, Any]] = []
            for node_name in sorted(pending):
                update = self._nodes[node_name](step_state)
                updates.append(update)
            for update in updates:
                self._merge(state, update)

            if self._interrupt_after and (pending & self._interrupt_after):
                next_pending = self._next_nodes(pending, state)
                if self._checkpointer and thread_id:
                    self._checkpointer.put(thread_id, step, dict(state), next_pending)
                yield {
                    "nodes": pending,
                    "state": dict(state),
                    "step": step,
                    "interrupt": "after",
                }
                return

            if self._checkpointer and thread_id:
                self._checkpointer.put(thread_id, step, dict(state), pending)
            yield {"nodes": pending, "state": dict(state), "step": step}
            pending = self._next_nodes(pending, state)
            step += 1

    def invoke(
        self,
        input: dict[str, Any] | None,
        *,
        recursion_limit: int = DEFAULT_RECURSION_LIMIT,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """从初始状态 ``input`` 开始执行图，返回最终状态。

        Args:
            input: 初始状态；``None`` 表示从检查点续跑。
            recursion_limit: 最大执行步数。
            config: 含 ``thread_id`` 的配置，用于检查点。

        Returns:
            执行完后的最终状态。
        """
        final_state = dict(input) if input else {}
        for event in self.stream(
            input, recursion_limit=recursion_limit, config=config
        ):
            final_state = event["state"]
        return final_state

    def get_state_history(
        self, config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """列出该 thread 的所有检查点（按步数升序）。

        Args:
            config: 含 ``thread_id`` 的配置。

        Returns:
            检查点列表，每个是 ``{"thread_id", "step", "state", "pending"}``。
        """
        thread_id = self._get_thread_id(config)
        if not self._checkpointer or not thread_id:
            return []
        return list(self._checkpointer.list(thread_id))

    def update_state(
        self, config: dict[str, Any], values: dict[str, Any]
    ) -> None:
        """更新最新检查点的状态（人类输入，阶段 8）。

        在 interrupt 暂停后，调用方用此方法写入人类决策，再 ``invoke(None, config)`` 续跑。

        Args:
            config: 含 ``thread_id`` 的配置。
            values: 要合并进状态更新片段（用 Reducer 合并）。
        """
        thread_id = self._get_thread_id(config)
        if not self._checkpointer or not thread_id:
            raise ValueError("需要 checkpointer 和 thread_id 才能 update_state")
        cp = self._checkpointer.get(thread_id)
        if cp is None:
            raise ValueError(f"thread '{thread_id}' 没有检查点")
        new_state = dict(cp["state"])
        self._merge(new_state, values)
        self._checkpointer.put(thread_id, cp["step"], new_state, cp["pending"])

    @staticmethod
    def _get_thread_id(config: dict[str, Any] | None) -> str | None:
        if not config:
            return None
        thread_id = config.get("configurable", {}).get("thread_id")
        return thread_id if isinstance(thread_id, str) else None

    def _next_nodes(self, pending: set[str], state: dict[str, Any]) -> set[str]:
        """收集所有 pending 节点的后继，构成下一个超级步。

        - 条件边：路由选一个目标
        - 静态边：所有出边目标都走（fan-out）
        - END 被过滤掉
        """
        next_set: set[str] = set()
        for node in pending:
            if node in self._conditional_edges:
                router, mapping = self._conditional_edges[node]
                label = router(state)
                if label not in mapping:
                    raise ValueError(
                        f"节点 '{node}' 的路由返回了未知标签 '{label}'"
                    )
                target = mapping[label]
                if target != END:
                    next_set.add(target)
            else:
                for target in self._edges.get(node, []):
                    if target != END:
                        next_set.add(target)
        return next_set
