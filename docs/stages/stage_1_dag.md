# 阶段 1：最小 DAG 执行器

!!! info "待实现"
    本阶段将在 `stage-1` tag 实现。此处先放设计预告。

## 目标

实现一个最小的**有向无环图（DAG）执行器**：

- 节点 = 函数
- 边 = 静态跳转
- 拓扑排序执行
- **无状态**（纯函数链）

## 将实现的 API

```python
from tiny_langgraph import Graph, END

graph = Graph()
graph.add_node("a", lambda x: x + 1)
graph.add_node("b", lambda x: x * 2)
graph.add_edge("a", "b")
graph.set_entry_point("a")
graph.set_finish_point("b")

app = graph.compile()
result = app.invoke(3)   # 3 -> a:4 -> b:8
```

## 核心问题

1. 怎么存图结构？（邻接表）
2. 怎么检测非法图？（环、孤立节点、缺入口）
3. 怎么拓扑排序？
4. `compile()` 做了什么？为什么不是直接跑？

## 对照真实 LangGraph

真实 `Graph` 类在 [`langgraph/graph/graph.py`](https://github.com/langchain-ai/langgraph/blob/main/libs/langgraph/langgraph/graph/graph.py)。我们会实现它的 1/10，但骨架一致。