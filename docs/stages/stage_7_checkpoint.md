# 阶段 7：Checkpoint 持久化

!!! info "待实现"
    本阶段将在 `stage-7` tag 实现。

## 目标

实现**检查点**：每个超级步存一个状态快照，支持断点续跑和时间旅行。

## 将实现的 API

```python
from tiny_langgraph.checkpoint import MemorySaver, SqliteSaver

saver = SqliteSaver("checkpoints.db")
app = graph.compile(checkpointer=saver)

config = {"configurable": {"thread_id": "t1"}}
app.invoke(initial_state, config)

# 列历史
for state in app.get_state_history(config):
    print(state.step, state.values)
```

## 核心问题

1. `BaseCheckpointSaver` 接口怎么设计？
2. `MemorySaver` 和 `SqliteSaver` 怎么实现？
3. 续跑时怎么从检查点恢复执行？