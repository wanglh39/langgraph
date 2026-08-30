# 阶段 4：循环图

!!! info "待实现"
    本阶段将在 `stage-4` tag 实现。

## 目标

允许图里有**环**，实现循环执行。配合条件边做终止，跑出 ReAct 雏形。

## 将实现的 API

```python
# 循环：agent -> (需要工具?) -> tool -> agent -> ...
graph.add_edge("agent", "check")
graph.add_conditional_edges("check", router, {
    "tool": "tool_node",
    "end": END,
})
graph.add_edge("tool_node", "agent")   # 回边！构成环

app = graph.compile()
app.invoke(initial_state, {"recursion_limit": 25})
```

## 核心问题

1. 有环图不能拓扑排序了，怎么调度？
2. 怎么防止死循环？（`recursion_limit`）
3. ReAct 的"思考→行动→观察"怎么映射到这个环？