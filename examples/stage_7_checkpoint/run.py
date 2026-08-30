"""阶段 7 示例：检查点持久化 —— 断点续跑。

一个循环图累加 count 到 10。第一次用 recursion_limit 限制只跑 4 步，
然后从检查点续跑完成。

运行::

    python -m examples.stage_7_checkpoint.run
"""

from __future__ import annotations

from typing import TypedDict

from tiny_langgraph import END, START, MemorySaver, SqliteSaver, StateGraph


class State(TypedDict):
    count: int


def make_graph() -> StateGraph:
    graph = StateGraph(State)
    graph.add_node("loop", lambda s: {"count": s["count"] + 1})
    graph.add_edge(START, "loop")
    graph.add_conditional_edges(
        "loop",
        lambda s: "again" if s["count"] < 10 else "done",
        {"again": "loop", "done": END},
    )
    return graph


def main() -> None:
    print("=" * 60)
    print("示例 1：MemorySaver 断点续跑")
    print("=" * 60)

    app = make_graph().compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "run-1"}}

    print("第一次执行（recursion_limit=4，跑到 count=4 就停）：")
    try:
        app.invoke({"count": 0}, recursion_limit=4, config=config)
    except RecursionError:
        print("  → 触发 recursion_limit，已存检查点")

    history = app.get_state_history(config)
    print(f"  已存 {len(history)} 个检查点，最新 count={history[-1]['state']['count']}")

    print("\n续跑（invoke(None, config)）：")
    result = app.invoke(None, config=config, recursion_limit=25)
    print(f"  续跑完成，最终 count={result['count']}")

    print()
    print("=" * 60)
    print("示例 2：时间旅行 —— 查看每一步的状态")
    print("=" * 60)

    full_history = app.get_state_history(config)
    for cp in full_history:
        print(f"  step {cp['step']}: count={cp['state']['count']}, pending={cp['pending']}")

    print()
    print("=" * 60)
    print("示例 3：SqliteSaver 持久化到磁盘")
    print("=" * 60)

    import os
    import tempfile

    db_path = os.path.join(tempfile.gettempdir(), "tiny_langgraph_demo.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    app2 = make_graph().compile(checkpointer=SqliteSaver(db_path))
    config2 = {"configurable": {"thread_id": "run-2"}}

    print(f"用 SqliteSaver 存到 {db_path}")
    result2 = app2.invoke({"count": 0}, config=config2)
    print(f"  执行完成，count={result2['count']}")

    history2 = app2.get_state_history(config2)
    print(f"  磁盘上存了 {len(history2)} 个检查点")
    print("  → 进程结束后仍保留，可跨进程续跑")

    print()
    print("=" * 60)
    print("关键观察：检查点 = 每超级步一个快照")
    print("=" * 60)
    print("  - put(thread_id, step, state, pending) 存快照")
    print("  - invoke(None, config) 从最新快照续跑")
    print("  - get_state_history(config) 列历史，能时间旅行")
    print("  - MemorySaver 调试用，SqliteSaver 持久化")


if __name__ == "__main__":
    main()