# 状态与 Reducer

> **在阶段 2、5 亲手实现。**

## 状态是什么

状态是**在节点间流动的共享数据**。每个节点读它、改它，引擎负责把改动合并回去。

```python
from typing import TypedDict

class AgentState(TypedDict):
    messages: list
    tool_calls: int
```

节点这样用：

```python
def my_node(state: AgentState) -> dict:
    # 读
    msgs = state["messages"]
    # 算
    new_msg = call_llm(msgs)
    # 返回更新片段
    return {"messages": [new_msg], "tool_calls": state["tool_calls"] + 1}
```

## 关键问题：状态怎么合并

节点返回 `{"messages": [new_msg]}`，引擎要把它合并进当前状态。**怎么合并？**

### 默认行为：覆盖

最朴素的做法——直接覆盖：

```python
state["messages"] = update["messages"]
```

但这对 Agent 是**错的**！Agent 的消息应该**追加**，不是覆盖。否则每轮 LLM 调用都把上一轮的消息丢了。

### Reducer：声明合并策略

LangGraph 的解法：**给每个字段声明一个 Reducer 函数**，告诉引擎这个字段该怎么合并。

```python
from typing import Annotated
from operator import add

class AgentState(TypedDict):
    messages: Annotated[list, add]      # 追加！
    tool_calls: Annotated[int, add]     # 累加！
```

`Annotated[list, add]` 的意思是：`messages` 字段用 `add` 函数合并——即 `state["messages"] = add(old, new)`。

引擎合并时：

```python
for key, value in update.items():
    reducer = get_reducer(key)  # 从 Annotated 元数据取
    if reducer is None:
        state[key] = value          # 默认覆盖
    else:
        state[key] = reducer(state[key], value)  # 用 Reducer
```

## 内置 Reducer

| Reducer | 行为 | 典型用途 |
|---------|------|----------|
| `operator.add` | `old + new` | 消息追加、计数累加 |
| `add_messages` | 智能合并消息（去重、按 id 覆盖） | LLM 消息列表 |
| 覆盖（默认） | `new` | 最新值覆盖 |

### `add_messages` 为什么不直接用 `+`

因为 LLM 消息有 `id`。如果一条消息被**修改**（比如流式补全中更新内容），应该按 `id` 覆盖而不是追加两条。`add_messages` 处理了这个细节。阶段 5 会实现一个简化版。

## 为什么这个设计重要

1. **并行安全**：多个节点同时返回对同一字段的更新，Reducer 定义了怎么合（`add` 天然可交换可结合）
2. **声明式**：合并策略写在类型注解里，节点代码不用关心合并
3. **可组合**：不同字段用不同 Reducer，各管各的

!!! tip "和 React 的 useReducer 类比"
    如果你写过前端，Reducer 这个词不陌生——同样是"给定旧状态和动作，算新状态"。LangGraph 把它用在**字段级**合并上。

## 在哪个阶段实现

| 概念 | 阶段 |
|------|:----:|
| 状态在节点间传递（覆盖合并） | [阶段 2](../stages/stage_2_state.md) |
| `Annotated` + Reducer 机制 | [阶段 5](../stages/stage_5_reducer.md) |

---

👉 上一篇：[图即程序](graph_as_program.md) · 下一篇：[Pregel 超级步](pregel.md)