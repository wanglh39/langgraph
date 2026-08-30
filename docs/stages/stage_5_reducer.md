# 阶段 5：Reducer 机制

> **目标**：让状态字段能声明合并策略——消息自动追加，而非覆盖。
>
> **git tag**：`stage-5` · **代码**：`src/tiny_langgraph/reducers.py`

## 这一阶段做了什么

引入 Reducer：用 `Annotated[T, reducer]` 给状态字段声明合并策略。

```python
from typing import Annotated
from operator import add
from tiny_langgraph import add_messages

class AgentState(TypedDict):
    messages: Annotated[list[str], add]            # 自动追加
    tool_messages: Annotated[list[dict], add_messages]  # 按 id 智能合并
    count: int                                     # 默认覆盖
```

节点只返回新消息，引擎自动追加：

```python
# 阶段 4（手动拼）：
def node(state):
    return {"messages": state["messages"] + [new_msg]}

# 阶段 5（Reducer 自动追加）：
def node(state):
    return {"messages": [new_msg]}   # 引擎用 add 合并
```

## 核心机制：从类型注解提取 Reducer

### 声明

```python
class State(TypedDict):
    messages: Annotated[list, add]   # add 是 reducer
    count: int                       # 没有 reducer = 覆盖
```

`Annotated[list, add]` 的第二个元素 `add` 就是 Reducer。它是一个二元函数：`reducer(old, new) -> merged`。

### 提取

```python
from typing import get_type_hints, get_args, get_origin, Annotated

def extract_reducers(state_type):
    hints = get_type_hints(state_type, include_extras=True)  # 保留 Annotated 元数据
    reducers = {}
    for key, hint in hints.items():
        if get_origin(hint) is Annotated:
            _base, *metadata = get_args(hint)
            if metadata and callable(metadata[0]):
                reducers[key] = metadata[0]
    return reducers
```

**关键**：`get_type_hints` 默认会**剥掉** `Annotated` 的元数据，必须传 `include_extras=True`（Python 3.9+）才能拿到 reducer。

### 合并

```python
def _merge(self, state, update):
    for key, value in update.items():
        if key in self._reducers:
            state[key] = self._reducers[key](state.get(key), value)  # 用 Reducer
        else:
            state[key] = value                                       # 覆盖
```

阶段 1-4 的 `state.update(update)` 被替换成 `self._merge(state, update)`。

## `add_messages`：智能合并

`operator.add` 对列表是简单拼接。但 LLM 消息需要更智能的合并——**按 id 覆盖**：

```python
def add_messages(old, new):
    # 新消息有 id 且旧列表有同 id → 覆盖那条
    # 否则 → 追加
```

为什么需要按 id 覆盖？**流式补全**：LLM 流式生成一条消息时，会多次发送**同 id** 的部分内容（越来越长）。这时应该覆盖同 id 的旧版本，而不是追加多条半成品。

```
旧: [{"id": 1, "content": "Hel"}]
新: [{"id": 1, "content": "Hello"}]
→  [{"id": 1, "content": "Hello"}]   # 覆盖，不是两条
```

## 为什么这个设计重要

1. **节点代码更简洁**：不用每次 `state["messages"] + [new]`，只返回新消息
2. **声明式**：合并策略写在类型注解里，和字段定义在一起，一目了然
3. **为并行铺路**：多个节点同时返回对同一字段的更新，Reducer 定义了怎么合（`add` 天然可交换可结合）——这是阶段 6 Pregel 并行的基础

## 运行示例

```bash
python -m examples.stage_5_reducer.run
```

输出展示：
- 示例 1：ReAct 循环中 messages 自动追加（对比阶段 4 的手动拼）
- 示例 2：`add_messages` 按 id 覆盖（草稿→完整内容，不变成两条）

## 对照真实 LangGraph

| 真实 LangGraph | 我们的阶段 5 | 说明 |
|----------------|-------------|------|
| `Annotated[list, add]` | 同 | |
| `add_messages` 按 id 覆盖 | 同（简化版） | 真实版处理 AIMessage/ToolMessage 等类型 |
| `get_type_hints(include_extras=True)` | 同 | 提取方式一致 |
| Reducer 存在 Channel 里 | 我们存在 CompiledStateGraph._reducers | 阶段 6 会统一到 Channel |

## 这一阶段的局限

| 局限 | 谁来解决 |
|------|----------|
| 同层多个节点不能并行执行 | 阶段 6 Pregel 超级步 |
| Reducer 和 Channel 还是两个概念 | 阶段 6 统一 |

---

👉 下一阶段：[阶段 6 - Pregel 超级步](stage_6_pregel.md)——把执行模型升级为"一层一层执行，同层并行"。
