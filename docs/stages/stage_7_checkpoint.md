# 阶段 7：Checkpoint 持久化

> **目标**：每个超级步存一个状态快照，支持断点续跑和时间旅行。
>
> **git tag**：`stage-7` · **代码**：`src/tiny_langgraph/checkpoint.py`

## 这一阶段做了什么

```python
from tiny_langgraph import MemorySaver, SqliteSaver

saver = MemorySaver()
app = graph.compile(checkpointer=saver)
config = {"configurable": {"thread_id": "run-1"}}

# 第一次执行
app.invoke({"count": 0}, config=config)

# 续跑（从最新检查点恢复）
app.invoke(None, config=config)

# 时间旅行（列出所有历史状态）
for cp in app.get_state_history(config):
    print(cp["step"], cp["state"])
```

## 检查点存什么

每个超级步执行完，存一个四元组：

```python
{
    "thread_id": "run-1",   # 一次会话的标识
    "step": 3,              # 第几个超级步
    "state": {"count": 3},  # 该步执行完的完整状态
    "pending": {"loop"},    # 下一步要执行的节点（续跑的关键）
}
```

**为什么存 `pending`？** 续跑时不仅需要恢复状态，还需要知道"下一步该执行哪些节点"。没有 `pending`，续跑不知道从哪个节点继续。

## 两种存储

| 存储 | 用途 | 持久性 |
|------|------|--------|
| `MemorySaver` | 开发调试、单元测试 | 进程结束即丢失 |
| `SqliteSaver` | 生产持久化、跨进程续跑 | 写磁盘，进程结束仍保留 |

两者实现同一个接口 `BaseCheckpointSaver`：

```python
class BaseCheckpointSaver:
    def put(thread_id, step, state, pending) -> None: ...
    def get(thread_id) -> Checkpoint | None: ...      # 最新
    def get_at(thread_id, step) -> Checkpoint | None: ...
    def list(thread_id) -> Iterator[Checkpoint]: ...   # 历史
```

## 续跑机制

```python
def stream(self, input, *, config=None):
    thread_id = config["configurable"]["thread_id"]

    if input is None and self._checkpointer and thread_id:
        # 续跑：从检查点恢复
        cp = self._checkpointer.get(thread_id)
        state = cp["state"]
        pending = cp["pending"]
        step = cp["step"] + 1
    else:
        # 从头开始
        state = dict(input)
        pending = {self._entry_point}
        step = 0

    while pending:
        ...  # 执行超级步
        self._checkpointer.put(thread_id, step, state, pending)  # 存快照
        ...
```

**`input=None` 是续跑的信号**：不传初始状态，从检查点恢复。这和真实 LangGraph 的语义一致。

## 运行示例

```bash
python -m examples.stage_7_checkpoint.run
```

输出展示：
1. **MemorySaver 续跑**：第一次 recursion_limit=4 跑到 count=4，续跑到 count=10
2. **时间旅行**：列出每一步的 state 和 pending
3. **SqliteSaver 持久化**：存到磁盘，进程结束仍保留

## 对照真实 LangGraph

| 真实 LangGraph | 我们的阶段 7 | 说明 |
|----------------|-------------|------|
| `MemorySaver` / `SqliteSaver` | 同 | |
| `config["configurable"]["thread_id"]` | 同 | |
| `invoke(None, config)` 续跑 | 同 | |
| `get_state_history(config)` | 同 | |
| `put` 存 `(step, state, pending)` | 同 | pending 是续跑关键 |
| 支持 AsyncSqliteSaver / Postgres | ❌ | 我们只有同步 + SQLite |
| checkpoint 结构更复杂（metadata、channel_values） | 简化 | |

## 这一阶段的局限

| 局限 | 谁来解决 |
|------|----------|
| 不能在指定节点暂停等人输入 | 阶段 8 Interrupt |
| 流式只 yield 超级步事件，没有节点内流式 | 阶段 8 |

---

👉 下一阶段：[阶段 8 - Interrupt + 流式](stage_8_interrupt.md)——在指定节点暂停，等人类审批再继续。
