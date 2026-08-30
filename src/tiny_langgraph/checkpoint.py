"""检查点持久化 - 阶段 7。

每个超级步执行完，把 ``(thread_id, step, state, pending)`` 存一个快照。
这让图能：

    - **断点续跑**：挂了从上次接着跑
    - **时间旅行**：回到第 N 步的状态重跑
    - **人机协作**：在某个节点暂停，等人类输入再继续（阶段 8）

本模块提供：
    - :class:`BaseCheckpointSaver`：接口
    - :class:`MemorySaver`：存内存（开发调试）
    - :class:`SqliteSaver`：存 SQLite（持久化）
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from typing import Any

__all__ = ["BaseCheckpointSaver", "MemorySaver", "SqliteSaver"]


class BaseCheckpointSaver:
    """检查点存储接口。

    检查点是一个 dict：``{"thread_id", "step", "state", "pending"}``。
    ``pending`` 是下一步要执行的节点集合（续跑的关键）。
    """

    def put(
        self,
        thread_id: str,
        step: int,
        state: dict[str, Any],
        pending: set[str],
    ) -> None:
        """存一个检查点。"""
        raise NotImplementedError

    def get(self, thread_id: str) -> dict[str, Any] | None:
        """取该 thread 最新的检查点。"""
        raise NotImplementedError

    def get_at(self, thread_id: str, step: int) -> dict[str, Any] | None:
        """取该 thread 指定步的检查点。"""
        raise NotImplementedError

    def list(self, thread_id: str) -> Iterator[dict[str, Any]]:
        """按步数升序列出该 thread 的所有检查点。"""
        raise NotImplementedError


def _make_checkpoint(
    thread_id: str, step: int, state: dict[str, Any], pending: set[str]
) -> dict[str, Any]:
    return {
        "thread_id": thread_id,
        "step": step,
        "state": state,
        "pending": pending,
    }


class MemorySaver(BaseCheckpointSaver):
    """内存检查点存储。

    用 ``dict[thread_id, list[checkpoint]]`` 存储。进程结束即丢失。
    适合开发调试和单元测试。
    """

    def __init__(self) -> None:
        self._storage: dict[str, list[dict[str, Any]]] = {}

    def put(self, thread_id: str, step: int, state: dict[str, Any], pending: set[str]) -> None:
        history = self._storage.setdefault(thread_id, [])
        history.append(_make_checkpoint(thread_id, step, state, pending))

    def get(self, thread_id: str) -> dict[str, Any] | None:
        history = self._storage.get(thread_id, [])
        return history[-1] if history else None

    def get_at(self, thread_id: str, step: int) -> dict[str, Any] | None:
        for cp in self._storage.get(thread_id, []):
            if cp["step"] == step:
                return cp
        return None

    def list(self, thread_id: str) -> Iterator[dict[str, Any]]:
        yield from self._storage.get(thread_id, [])


class SqliteSaver(BaseCheckpointSaver):
    """SQLite 检查点存储。

    用 sqlite3 持久化到磁盘。进程结束仍保留，支持跨进程续跑。

    Args:
        path: SQLite 数据库文件路径。``":memory:"`` 为内存数据库。
    """

    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                thread_id TEXT NOT NULL,
                step      INTEGER NOT NULL,
                state     TEXT NOT NULL,
                pending   TEXT NOT NULL,
                PRIMARY KEY (thread_id, step)
            )
            """
        )
        self._conn.commit()

    def put(self, thread_id: str, step: int, state: dict[str, Any], pending: set[str]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO checkpoints VALUES (?, ?, ?, ?)",
            (
                thread_id,
                step,
                json.dumps(state, ensure_ascii=False),
                json.dumps(sorted(pending), ensure_ascii=False),
            ),
        )
        self._conn.commit()

    def _row_to_checkpoint(self, row: tuple[str, int, str, str]) -> dict[str, Any]:
        thread_id, step, state_json, pending_json = row
        return {
            "thread_id": thread_id,
            "step": step,
            "state": json.loads(state_json),
            "pending": set(json.loads(pending_json)),
        }

    def get(self, thread_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM checkpoints WHERE thread_id=? ORDER BY step DESC LIMIT 1",
            (thread_id,),
        ).fetchone()
        return self._row_to_checkpoint(row) if row else None

    def get_at(self, thread_id: str, step: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM checkpoints WHERE thread_id=? AND step=?",
            (thread_id, step),
        ).fetchone()
        return self._row_to_checkpoint(row) if row else None

    def list(self, thread_id: str) -> Iterator[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM checkpoints WHERE thread_id=? ORDER BY step ASC",
            (thread_id,),
        ).fetchall()
        for row in rows:
            yield self._row_to_checkpoint(row)

    def close(self) -> None:
        self._conn.close()