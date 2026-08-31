# 从零实现 LangGraph

> 渐进式理解图执行引擎的底层原理与设计原则

<p align="center">
  <a href="https://wanglh39.github.io/langgraph/"><strong>📖 在线文档</strong></a>
  &nbsp;|&nbsp;
  <a href="https://github.com/wanglh39/langgraph">GitHub 仓库</a>
  &nbsp;|&nbsp;
  <a href="https://wanglh39.github.io/langgraph/principles/">核心原理</a>
  &nbsp;|&nbsp;
  <a href="https://wanglh39.github.io/langgraph/stages/stage_9_agent/">阶段 9：完整 Agent</a>
</p>

---

本项目通过 **10 个阶段**，从零手写一个 LangGraph，把"写 Agent"这件事从一坨 prompt 拼接，变成"画一张状态机"，再用一个通用的 Pregel 引擎去跑这张图。

## 为什么做这个

LangGraph 的本质是一个**基于图的有状态执行引擎**，受 Google Pregel 启发。它的"图"不是装饰，而是执行模型本身。市面上的教程多停留在"怎么用"，而这个项目要回答的是"**它到底怎么做到的**"——所以我们从空文件开始，一层层把它造出来。

## 渐进式路线

| 阶段 | 内容 | 新增概念 |
|------|------|----------|
| 0 | 项目骨架 + 文档站点 | MkDocs Material |
| 1 | 最小 DAG 执行器 | Node=函数, 拓扑排序 |
| 2 | 共享状态 | StateGraph |
| 3 | 条件边 | 路由分支 |
| 4 | 循环图 | ReAct 雏形, 终止条件 |
| 5 | Reducer | `Annotated` + `add_messages` |
| 6 | Pregel 超级步 | 通道, 并行层 |
| 7 | Checkpoint | 内存→SQLite, 时间旅行 |
| 8 | Interrupt + 流式 | 人机协作 |
| 9 | 完整 Tool Agent | 接 OpenAI, 对比真 LangGraph |

每个阶段对应一个 **git tag**（`stage-0`, `stage-1`, ...），可以 `git diff stage-1..stage-2` 看每一层到底加了什么。

## 快速开始

```bash
# 安装（开发模式）
pip install -e ".[dev,docs]"

# 跑测试
pytest

# 本地预览文档
mkdocs serve
```

## 项目结构

```
src/tiny_langgraph/   # 我们的实现（逐阶段演进）
tests/                # 测试（镜像 src 结构）
docs/                 # MkDocs 文档
examples/             # 每阶段可运行示例
```

## 设计原则

- **纯标准库优先**：阶段 1-8 只用 Python 标准库，底层原理不被框架噪音淹没
- **每个概念只做一件事**：每阶段只引入一个新概念，可独立运行
- **对照真实源码**：每阶段文档会对照 LangGraph 真实源码的关键行
- **可运行 > 可读 > 完备**：所有代码都能 `python -m` 跑起来看效果

## 许可证

MIT