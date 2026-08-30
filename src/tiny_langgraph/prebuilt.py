"""预构建 Agent - 阶段 9：完整 Tool-calling Agent。

用阶段 1-8 搭好的引擎，拼出一个**完整的 ReAct Agent**：

    用户消息 → agent 节点（调 LLM）→ 有工具调用？→ tools 节点（执行工具）→ agent ...
                                         → 无工具调用 → END

这用了之前所有阶段的能力：

    - 阶段 2 共享状态：``messages`` 列表在节点间传递
    - 阶段 3 条件边：``should_continue`` 根据 LLM 回复决定走 tools 还是 END
    - 阶段 4 循环：agent → tools → agent 的 ReAct 循环
    - 阶段 5 Reducer：``add_messages`` 智能追加消息
    - 阶段 7 检查点：配合 ``MemorySaver`` 保存对话历史
    - 阶段 8 Interrupt：可在工具执行前暂停，让人类审批

用法::

    from openai import OpenAI
    from tiny_langgraph import MemorySaver, create_react_agent, Tool

    @Tool("search", "搜索网络", {"type": "object", "properties": {"q": {"type": "string"}}})
    def search(q: str) -> str:
        return f"搜索结果: {q}"

    agent = create_react_agent(
        OpenAI(),
        tools=[search],
        system_prompt="你是一个助手",
        checkpointer=MemorySaver(),
    )
    result = agent.invoke({"messages": [{"role": "user", "content": "你好"}]})
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any

from tiny_langgraph.graph import END, START, CompiledStateGraph, StateGraph
from tiny_langgraph.reducers import add_messages

if TYPE_CHECKING:
    from openai import OpenAI

__all__ = ["Tool", "AgentState", "create_react_agent"]


class AgentState(dict[str, Any]):
    """ReAct Agent 的状态：一个消息列表。

    ``messages`` 用 :func:`add_messages` Reducer 合并——节点返回
    ``{"messages": [new_msg]}``，引擎自动追加到已有列表。
    """

    messages: Annotated[list[dict[str, Any]], add_messages]


class Tool:
    """把一个 Python 函数包装成 LLM 可调用的工具。

    用法 1（装饰器）::

        @Tool("calculator", "计算数学表达式", {
            "type": "object",
            "properties": {"expr": {"type": "string"}},
            "required": ["expr"],
        })
        def calculator(expr: str) -> str:
            return str(eval(expr))

    用法 2（直接构造）::

        calculator = Tool("calculator", "计算", params, func=lambda expr: str(eval(expr)))
    """

    def __init__(
        self,
        name: str | None = None,
        description: str = "",
        parameters: dict[str, Any] | None = None,
        *,
        func: Callable[..., Any] | None = None,
    ) -> None:
        self.name = name or "tool"
        self.description = description
        self.parameters = parameters or {
            "type": "object",
            "properties": {},
            "required": [],
        }
        self._func = func

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if self._func is None and len(args) == 1 and callable(args[0]) and not kwargs:
            self._func = args[0]
            if self.name == "tool":
                self.name = args[0].__name__
            if not self.description:
                self.description = args[0].__doc__ or ""
            return self
        if self._func is None:
            raise RuntimeError(f"Tool '{self.name}' 没有绑定函数")
        return self._func(*args, **kwargs)

    def to_openai_schema(self) -> dict[str, Any]:
        """转成 OpenAI tools API 的 JSON schema。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __repr__(self) -> str:
        return f"Tool(name={self.name!r}, description={self.description!r})"


def _message_to_dict(message: Any) -> dict[str, Any]:
    """把 OpenAI 消息对象（Pydantic model 或 dict）统一转成 dict。"""
    if isinstance(message, dict):
        return dict(message)
    if hasattr(message, "model_dump"):
        return dict(message.model_dump())
    if hasattr(message, "to_dict"):
        return dict(message.to_dict())
    return dict(message)


def create_react_agent(
    llm: OpenAI,
    tools: list[Tool],
    *,
    model: str = "gpt-4o-mini",
    system_prompt: str | None = None,
    checkpointer: Any = None,
    interrupt_before_tools: bool = False,
) -> CompiledStateGraph:
    """创建一个 ReAct Agent（Reasoning + Acting 循环）。

    图结构::

        START → agent → (有工具调用?) → tools → agent → ...
                        → (无工具调用?) → END

    Args:
        llm: OpenAI 客户端（``openai.OpenAI()``）。
        tools: 工具列表。
        model: 模型名。
        system_prompt: 系统提示词（每次调 LLM 时前置，不存入状态）。
        checkpointer: 检查点存储，用于保存对话历史。
        interrupt_before_tools: 在执行工具前暂停（人机协作审批）。

    Returns:
        编译后的图，用 ``.invoke({"messages": [...]})`` 或 ``.stream(...)`` 执行。
    """
    tool_map = {t.name: t for t in tools}
    openai_tools = [t.to_openai_schema() for t in tools]

    def agent_node(state: dict[str, Any]) -> dict[str, Any]:
        messages = list(state["messages"])
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}, *messages]
        response = llm.chat.completions.create(
            model=model,
            messages=messages,
            tools=openai_tools,  # type: ignore[arg-type]
        )
        msg = _message_to_dict(response.choices[0].message)
        return {"messages": [msg]}

    def tool_node(state: dict[str, Any]) -> dict[str, Any]:
        last = state["messages"][-1]
        results: list[dict[str, Any]] = []
        for tc in last.get("tool_calls", []):
            tool_name = tc["function"]["name"]
            tool = tool_map[tool_name]
            args = json.loads(tc["function"]["arguments"])
            output = tool(**args)
            results.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(output),
                }
            )
        return {"messages": results}

    def should_continue(state: dict[str, Any]) -> str:
        last = state["messages"][-1]
        if isinstance(last, dict) and last.get("tool_calls"):
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent", should_continue, {"tools": "tools", END: END}
    )
    graph.add_edge("tools", "agent")

    interrupt_before = ["tools"] if interrupt_before_tools else None
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
    )