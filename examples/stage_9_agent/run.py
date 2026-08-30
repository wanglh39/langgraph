"""阶段 9 示例：完整 Tool-calling Agent。

用我们手写的引擎 + OpenAI API，拼出一个真实的 ReAct Agent。

运行方式::

    # 需要先安装 openai: pip install tiny-langgraph[llm]
    # 并设置 OPENAI_API_KEY 环境变量

    python examples/stage_9_agent/run.py

如果没有 API Key，脚本会用 FakeLLM 演示同样的图执行流程。
"""

from __future__ import annotations

import json
import os
from typing import Any

from tiny_langgraph import MemorySaver, Tool, create_react_agent


def _separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(title)
    print("=" * 60)


def _print_messages(messages: list[dict[str, Any]]) -> None:
    for i, msg in enumerate(messages):
        role = msg.get("role", "?")
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls")
        print(f"  [{i}] {role}: {content or '(无文字，有工具调用)'}")
        if tool_calls:
            for tc in tool_calls:
                fn = tc["function"]
                args = json.loads(fn["arguments"])
                print(f"       → 调用工具 {fn['name']}({args})")


def demo_with_fake_llm() -> None:
    """用 FakeLLM 演示 ReAct Agent（不需要 API Key）。"""

    class FakeMessage:
        def __init__(self, content=None, tool_calls=None):
            self.role = "assistant"
            self.content = content
            self.tool_calls = tool_calls

        def model_dump(self):
            d = {"role": self.role, "content": self.content}
            if self.tool_calls:
                d["tool_calls"] = self.tool_calls
            return d

    class FakeResponse:
        def __init__(self, msg):
            self.choices = [type("C", (), {"message": msg})()]

    class FakeLLM:
        def __init__(self, responses):
            self._r = list(responses)
            self._i = 0

        @property
        def chat(self):
            return self

        @property
        def completions(self):
            return self

        def create(self, **kw):
            msg = self._r[self._i]
            self._i += 1
            return FakeResponse(msg)

    def tc(cid, name, args):
        return {
            "id": cid,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)},
        }

    _separator("阶段 9：ReAct Agent（FakeLLM 演示）")

    @Tool(
        "calculator",
        "计算数学表达式",
        {
            "type": "object",
            "properties": {"expr": {"type": "string", "description": "数学表达式"}},
            "required": ["expr"],
        },
    )
    def calculator(expr: str) -> str:
        try:
            return str(eval(expr))  # noqa: S307
        except Exception as e:
            return f"错误: {e}"

    @Tool(
        "get_weather",
        "查询城市天气",
        {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "城市名"}},
            "required": ["city"],
        },
    )
    def get_weather(city: str) -> str:
        return f"{city}今天晴，25°C"

    llm = FakeLLM(
        [
            FakeMessage(
                content=None,
                tool_calls=[tc("c1", "calculator", {"expr": "12 * 7 + 3"})],
            ),
            FakeMessage(
                content=None,
                tool_calls=[tc("c2", "get_weather", {"city": "北京"})],
            ),
            FakeMessage(content="12×7+3=87，北京今天晴25°C。还有什么需要帮助的吗？"),
        ]
    )

    agent = create_react_agent(
        llm,
        tools=[calculator, get_weather],
        system_prompt="你是一个有用的助手，可以计算和查天气。",
        checkpointer=MemorySaver(),
    )

    config = {"configurable": {"thread_id": "demo"}}

    print("\n图结构: START → agent → (有工具调用?) → tools → agent → ...")
    print("                                → (无工具调用?) → END\n")

    print("第一次调用（用户提问）：")
    print("-" * 60)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "算 12×7+3，再查北京天气"}]},
        config=config,
    )
    _print_messages(result["messages"])

    print("\n✓ Agent 完成了 2 次工具调用 + 1 次最终回复")
    print("✓ 消息历史保存在 MemorySaver 中（thread_id=demo）")


def demo_with_real_openai() -> None:
    """用真 OpenAI API 演示 ReAct Agent。"""

    try:
        from openai import OpenAI
    except ImportError:
        print("\n请先安装 openai: pip install tiny-langgraph[llm]")
        return

    _separator("阶段 9：ReAct Agent（真 OpenAI API）")

    @Tool(
        "calculator",
        "计算数学表达式",
        {
            "type": "object",
            "properties": {"expr": {"type": "string", "description": "数学表达式"}},
            "required": ["expr"],
        },
    )
    def calculator(expr: str) -> str:
        try:
            return str(eval(expr))  # noqa: S307
        except Exception as e:
            return f"错误: {e}"

    @Tool(
        "get_weather",
        "查询城市天气（模拟）",
        {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "城市名"}},
            "required": ["city"],
        },
    )
    def get_weather(city: str) -> str:
        return f"{city}今天晴，25°C"

    llm = OpenAI()
    agent = create_react_agent(
        llm,
        tools=[calculator, get_weather],
        system_prompt="你是一个有用的助手。请用中文回答。",
        checkpointer=MemorySaver(),
    )

    config = {"configurable": {"thread_id": "real"}}

    print("\n图结构: START → agent → (有工具调用?) → tools → agent → ...")
    print("                                → (无工具调用?) → END\n")

    print("流式执行（逐步 yield）：")
    print("-" * 60)
    for event in agent.stream(
        {"messages": [{"role": "user", "content": "算 17 * 23，再查上海天气"}]},
        config=config,
    ):
        nodes = event["nodes"]
        step = event["step"]
        interrupt = event.get("interrupt")
        tag = f" [interrupt: {interrupt}]" if interrupt else ""
        print(f"  超级步 {step}: 执行 {nodes}{tag}")

    state = agent.get_state_history(config)
    if state:
        _print_messages(state[-1]["state"]["messages"])

    print("\n✓ 真实 LLM 驱动的 ReAct 循环完成")


def demo_human_in_the_loop() -> None:
    """演示人机协作：工具执行前暂停，人类审批。"""

    class FakeMessage:
        def __init__(self, content=None, tool_calls=None):
            self.role = "assistant"
            self.content = content
            self.tool_calls = tool_calls

        def model_dump(self):
            d = {"role": self.role, "content": self.content}
            if self.tool_calls:
                d["tool_calls"] = self.tool_calls
            return d

    class FakeResponse:
        def __init__(self, msg):
            self.choices = [type("C", (), {"message": msg})()]

    class FakeLLM:
        def __init__(self, responses):
            self._r = list(responses)
            self._i = 0

        @property
        def chat(self):
            return self

        @property
        def completions(self):
            return self

        def create(self, **kw):
            msg = self._r[self._i]
            self._i += 1
            return FakeResponse(msg)

    def tc(cid, name, args):
        return {
            "id": cid,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)},
        }

    _separator("阶段 9：人机协作（工具执行前审批）")

    @Tool("send_email", "发送邮件", {
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
        },
        "required": ["to", "subject"],
    })
    def send_email(to: str, subject: str) -> str:
        return f"已发送邮件到 {to}：{subject}"

    llm = FakeLLM(
        [
            FakeMessage(
                content=None,
                tool_calls=[tc("c1", "send_email", {
                    "to": "boss@company.com",
                    "subject": "请假申请",
                })],
            ),
            FakeMessage(content="邮件已发送。"),
        ]
    )

    agent = create_react_agent(
        llm,
        tools=[send_email],
        system_prompt="你是邮件助手。",
        checkpointer=MemorySaver(),
        interrupt_before_tools=True,
    )

    config = {"configurable": {"thread_id": "hitl"}}

    print("\n第一次执行（agent 决定发邮件，但在执行前暂停）：")
    print("-" * 60)
    events = list(
        agent.stream(
            {"messages": [{"role": "user", "content": "帮我给老板发请假邮件"}]},
            config=config,
        )
    )
    for e in events:
        tag = f" [interrupt: {e.get('interrupt')}]" if e.get("interrupt") else ""
        print(f"  超级步 {e['step']}: 执行 {e['nodes']}{tag}")

    last_msg = events[-1]["state"]["messages"][-1]
    if last_msg.get("tool_calls"):
        tc_info = last_msg["tool_calls"][0]["function"]
        print(f"\n  ⚠ Agent 想调用 {tc_info['name']}({json.loads(tc_info['arguments'])})")
    print("  ⚠ 已暂停！等待人类审批...")

    print("\n人类审批通过，续跑：")
    print("-" * 60)
    result = agent.invoke(None, config=config)
    _print_messages(result["messages"])

    print("\n✓ 人机协作完成：人类在工具执行前有否决权")


def main() -> None:
    if os.environ.get("OPENAI_API_KEY"):
        demo_with_real_openai()
    else:
        print("未检测到 OPENAI_API_KEY，使用 FakeLLM 演示。")
        demo_with_fake_llm()

    demo_human_in_the_loop()

    _separator("关键观察：9 个阶段如何拼出一个 Agent")
    print("""
  阶段 1  最小 DAG     → 图的基本执行能力
  阶段 2  共享状态     → messages 在节点间传递
  阶段 3  条件边       → should_continue: 有工具调用? → tools : → END
  阶段 4  循环图       → agent → tools → agent 的 ReAct 循环
  阶段 5  Reducer      → add_messages 智能追加消息
  阶段 6  Pregel       → 超级步执行模型（虽然 Agent 是线性的）
  阶段 7  Checkpoint   → MemorySaver 保存对话历史
  阶段 8  Interrupt    → 工具执行前暂停，人类审批
  阶段 9  Agent        → 把上面所有能力组装成一个完整的 Agent

  这就是 LangGraph 的核心：一个图执行引擎，Agent 只是图的一种模式。
""")


if __name__ == "__main__":
    main()