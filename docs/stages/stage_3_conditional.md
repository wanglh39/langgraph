# 阶段 3：条件边与路由

!!! info "待实现"
    本阶段将在 `stage-3` tag 实现。

## 目标

实现**条件边**：执行完一个节点后，根据状态决定跳哪个节点。这就是 `if/else` 在图里的表达。

## 将实现的 API

```python
def router(state) -> str:
    if state["count"] < 3:
        return "loop"
    return "done"

graph.add_conditional_edges("check", router, {
    "loop": "increment",
    "done": END,
})
```

## 核心问题

1. 条件边的返回值怎么映射到目标节点？
2. 一个节点可以同时有静态边和条件边吗？
3. 路由函数抛异常怎么办？