# 阶段 5：Reducer 机制

!!! info "待实现"
    本阶段将在 `stage-5` tag 实现。

## 目标

实现 **Reducer**：用 `Annotated` 给状态字段声明合并策略，让消息能追加而不是覆盖。

## 将实现的 API

```python
from typing import Annotated
from operator import add

class State(TypedDict):
    messages: Annotated[list, add]   # 追加！
    count: int                       # 默认覆盖

def node(state):
    return {"messages": [new_msg]}   # 只声明要追加的

app.invoke({"messages": [], "count": 0})
# messages 会被 append，而不是覆盖
```

## 核心问题

1. 怎么从 `Annotated[T, reducer]` 的类型注解里把 `reducer` 提出来？
2. `add_messages` 怎么实现（按 id 去重/覆盖）？
3. Reducer 和阶段 6 的通道什么关系？