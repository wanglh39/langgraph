"""tiny_langgraph - 从零渐进式实现 LangGraph。

当前阶段：0（项目骨架）

后续阶段将逐步引入：
    - 阶段 1：DAG 执行器（Node + 拓扑排序）
    - 阶段 2：共享状态 StateGraph
    - 阶段 3：条件边与路由
    - 阶段 4：循环图
    - 阶段 5：Reducer 机制
    - 阶段 6：Pregel 超级步引擎
    - 阶段 7：Checkpoint 持久化
    - 阶段 8：Interrupt + 流式
    - 阶段 9：完整 Tool-calling Agent
"""

__version__ = "0.0.0"
__all__ = ["__version__"]