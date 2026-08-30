# 阶段 2：共享状态

!!! info "待实现"
    本阶段将在 `stage-2` tag 实现。

## 目标

引入**共享状态**：节点不再接收裸值，而是接收一个 `state` 字典，返回更新片段，引擎负责合并。

## 将实现的 API

```python
from typing import TypedDict

class State(TypedDict):
    count: int
    messages: list

def node_a(state: State) -> dict:
    return {"count": state["count"] + 1}

def node_b(state: State) -> dict:
    return {"messages": state["messages"] + ["b ran"]}

graph = StateGraph(State)
graph.add_node("a", node_a)
graph.add_node("b", node_b)
graph.add_edge(START, "a")
graph.add_edge("a", "b")
graph.add_edge("b", END)

app = graph.compile()
result = app.invoke({"count": 0, "messages": []})
# {"count": 1, "messages": ["b ran"]}
```

## 核心问题

1. 状态怎么在节点间传递？
2. 节点返回"更新片段"，引擎怎么合并进完整状态？（本阶段：覆盖）
3. `StateGraph` 和阶段 1 的 `Graph` 什么关系？