"""Reducer 机制 - 阶段 5。

Reducer 声明状态字段怎么合并。例如消息列表应该**追加**而非覆盖：

    from typing import Annotated
    from operator import add

    class State(TypedDict):
        messages: Annotated[list, add]   # 追加
        count: int                       # 默认覆盖

节点只需返回 ``{"messages": [new_msg]}``，引擎会用 ``add`` 把它追加到
已有的 ``messages``，而不是覆盖。

本模块提供：
    - :func:`add_messages`：智能合并消息列表（按 id 覆盖、否则追加）
    - :func:`extract_reducers`：从 TypedDict 的 Annotated 注解提取 Reducer
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, get_args, get_origin, get_type_hints

__all__ = ["add_messages", "extract_reducers"]


def add_messages(
    old: list[Any] | None, new: list[Any] | None
) -> list[Any]:
    """智能合并消息列表。

    规则：
        - 新消息若是 dict 且有 ``"id"``，且旧列表有同 id 的消息：**覆盖**该条
        - 否则：**追加**到末尾

    这模拟真实 LangGraph 的 ``add_messages``：流式更新同一条消息时按 id 覆盖，
    新消息则追加。

    Args:
        old: 旧消息列表（可为 None）。
        new: 新消息列表（可为 None）。

    Returns:
        合并后的新列表（不修改输入）。
    """
    if not old:
        return list(new) if new else []
    if not new:
        return list(old)

    result = list(old)
    id_to_index: dict[Any, int] = {}
    for i, msg in enumerate(result):
        if isinstance(msg, dict) and "id" in msg:
            id_to_index[msg["id"]] = i

    for msg in new:
        msg_id = msg.get("id") if isinstance(msg, dict) else None
        if msg_id is not None and msg_id in id_to_index:
            result[id_to_index[msg_id]] = msg
        else:
            result.append(msg)
            if msg_id is not None:
                id_to_index[msg_id] = len(result) - 1
    return result


def extract_reducers(state_type: type) -> dict[str, Callable[[Any, Any], Any]]:
    """从 TypedDict 的 ``Annotated[T, reducer]`` 注解提取 Reducer。

    示例::

        class State(TypedDict):
            messages: Annotated[list, add]
            count: int

        extract_reducers(State)  # {"messages": add}

    Args:
        state_type: TypedDict 子类。

    Returns:
        ``{字段名: reducer 函数}``，没有 Reducer 的字段不在其中。
    """
    reducers: dict[str, Callable[[Any, Any], Any]] = {}
    try:
        hints = get_type_hints(state_type, include_extras=True)
    except Exception:
        return reducers

    for key, hint in hints.items():
        if get_origin(hint) is Annotated:
            _base, *metadata = get_args(hint)
            if metadata and callable(metadata[0]):
                reducers[key] = metadata[0]
    return reducers