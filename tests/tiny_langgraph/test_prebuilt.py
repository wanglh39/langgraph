"""预构建 ReAct Agent 的测试 - 阶段 9。

用 FakeLLM 模拟 OpenAI 客户端，不依赖真实 API。
"""

from __future__ import annotations

from typing import Any

from tiny_langgraph import MemorySaver, create_react_agent
from tiny_langgraph.prebuilt import Tool


class _FakeMessage:
    """模拟 OpenAI ChatCompletionMessage。"""

    def __init__(
        self,
        role: str = "assistant",
        content: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        self.role = role
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        return d


class _FakeResponse:
    """模拟 OpenAI ChatCompletion。"""

    def __init__(self, message: _FakeMessage) -> None:
        self.choices = [type("Choice", (), {"message": message})()]


class FakeLLM:
    """模拟 ``openai.OpenAI``，按预设顺序返回响应。

    用法::

        llm = FakeLLM([
            _FakeMessage(content="调用工具", tool_calls=[...]),
            _FakeMessage(content="最终回复"),
        ])
        agent = create_react_agent(llm, tools=[...])
    """

    def __init__(self, responses: list[_FakeMessage]) -> None:
        self._responses = list(responses)
        self._idx = 0
        self.calls: list[dict[str, Any]] = []

    @property
    def chat(self) -> FakeLLM:
        return self

    @property
    def completions(self) -> FakeLLM:
        return self

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        msg = self._responses[self._idx]
        self._idx += 1
        return _FakeResponse(msg)


def _make_tool_call(
    call_id: str, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    import json

    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


class TestTool:
    """Tool 包装测试。"""

    def test_basic_tool(self) -> None:
        def add(a: int, b: int) -> int:
            return a + b

        t = Tool("add", "加法", {"type": "object"}, func=add)
        assert t.name == "add"
        assert t(a=1, b=2) == 3

    def test_openai_schema(self) -> None:
        t = Tool("echo", "回声", {"type": "object"}, func=lambda x: x)
        schema = t.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "echo"
        assert schema["function"]["description"] == "回声"


class TestReActAgent:
    """ReAct Agent 端到端测试（用 FakeLLM）。"""

    def test_no_tool_call(self) -> None:
        llm = FakeLLM([_FakeMessage(content="你好！我是助手。")])
        agent = create_react_agent(llm, tools=[])
        result = agent.invoke({"messages": [{"role": "user", "content": "你好"}]})
        assert len(result["messages"]) == 2
        assert result["messages"][1]["content"] == "你好！我是助手。"

    def test_single_tool_call(self) -> None:
        calc = Tool("calc", "计算器", {"type": "object"}, func=lambda expr: str(eval(expr)))

        llm = FakeLLM(
            [
                _FakeMessage(
                    content=None,
                    tool_calls=[_make_tool_call("c1", "calc", {"expr": "2 + 3"})],
                ),
                _FakeMessage(content="2 + 3 = 5"),
            ]
        )
        agent = create_react_agent(llm, tools=[calc])
        result = agent.invoke({"messages": [{"role": "user", "content": "算 2+3"}]})

        messages = result["messages"]
        assert len(messages) == 4
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["tool_calls"] is not None
        assert messages[2]["role"] == "tool"
        assert messages[2]["content"] == "5"
        assert messages[3]["content"] == "2 + 3 = 5"

    def test_multi_tool_call(self) -> None:
        search = Tool("search", "搜索", {"type": "object"}, func=lambda q: f"结果: {q}")

        llm = FakeLLM(
            [
                _FakeMessage(
                    content=None,
                    tool_calls=[
                        _make_tool_call("c1", "search", {"q": "天气"}),
                        _make_tool_call("c2", "search", {"q": "新闻"}),
                    ],
                ),
                _FakeMessage(content="天气晴，新闻无大事"),
            ]
        )
        agent = create_react_agent(llm, tools=[search])
        result = agent.invoke({"messages": [{"role": "user", "content": "查天气和新闻"}]})

        messages = result["messages"]
        assert len(messages) == 5
        assert messages[2]["role"] == "tool"
        assert messages[2]["content"] == "结果: 天气"
        assert messages[3]["role"] == "tool"
        assert messages[3]["content"] == "结果: 新闻"

    def test_react_loop(self) -> None:
        """多轮工具调用：agent → tools → agent → tools → agent → END。"""
        echo = Tool("echo", "回声", {"type": "object"}, func=lambda x: x)

        llm = FakeLLM(
            [
                _FakeMessage(
                    content=None,
                    tool_calls=[_make_tool_call("c1", "echo", {"x": "第一次"})],
                ),
                _FakeMessage(
                    content=None,
                    tool_calls=[_make_tool_call("c2", "echo", {"x": "第二次"})],
                ),
                _FakeMessage(content="完成"),
            ]
        )
        agent = create_react_agent(llm, tools=[echo])
        result = agent.invoke({"messages": [{"role": "user", "content": "开始"}]})

        messages = result["messages"]
        assert len(messages) == 6
        assert messages[5]["content"] == "完成"

    def test_system_prompt(self) -> None:
        llm = FakeLLM([_FakeMessage(content="收到")])
        agent = create_react_agent(llm, tools=[], system_prompt="你是中文助手")
        agent.invoke({"messages": [{"role": "user", "content": "hi"}]})
        sent_messages = llm.calls[0]["messages"]
        assert sent_messages[0]["role"] == "system"
        assert sent_messages[0]["content"] == "你是中文助手"

    def test_with_checkpoint(self) -> None:
        llm = FakeLLM([_FakeMessage(content="第一轮回复")])
        agent = create_react_agent(
            llm, tools=[], checkpointer=MemorySaver()
        )
        config = {"configurable": {"thread_id": "t1"}}
        result = agent.invoke(
            {"messages": [{"role": "user", "content": "第一轮"}]}, config=config
        )
        assert result["messages"][-1]["content"] == "第一轮回复"

    def test_interrupt_before_tools(self) -> None:
        echo = Tool("echo", "回声", {"type": "object"}, func=lambda x: x)

        llm = FakeLLM(
            [
                _FakeMessage(
                    content=None,
                    tool_calls=[_make_tool_call("c1", "echo", {"x": "test"})],
                ),
                _FakeMessage(content="工具执行完毕"),
            ]
        )
        agent = create_react_agent(
            llm,
            tools=[echo],
            checkpointer=MemorySaver(),
            interrupt_before_tools=True,
        )
        config = {"configurable": {"thread_id": "t1"}}

        events = list(
            agent.stream(
                {"messages": [{"role": "user", "content": "调用 echo"}]}, config=config
            )
        )
        assert events[-1].get("interrupt") == "before"

        result = agent.invoke(None, config=config)
        assert result["messages"][-1]["content"] == "工具执行完毕"