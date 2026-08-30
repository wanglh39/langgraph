# 阶段 8：Interrupt 人机协作 + 流式

!!! info "待实现"
    本阶段将在 `stage-8` tag 实现。

## 目标

- **Interrupt**：在指定节点前/后暂停，交回控制权，等人类输入后续跑
- **流式输出**：逐步 yield 执行过程，前端能实时展示

## 将实现的 API

```python
app = graph.compile(
    checkpointer=saver,
    interrupt_before=["human_review"],
)

# 跑到 human_review 前暂停
app.invoke(initial_state, config)

# 人类审批后续跑
app.invoke(None, config)
```

## 核心问题

1. 暂停时怎么存"执行到哪了"？
2. 续跑时怎么跳过已执行节点？
3. 流式怎么和超级步对齐？