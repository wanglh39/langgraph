# 阶段 0：项目骨架

> **本阶段目标**：搭好项目骨架、文档站点、测试框架、CI/CD，让后续 9 个阶段能在稳固的地基上逐层加概念。

## 这一阶段做了什么

```
langgraph/
├── pyproject.toml          # 项目配置（hatchling 构建）
├── mkdocs.yml              # 文档站点配置（Material 主题）
├── README.md
├── src/
│   └── tiny_langgraph/
│       ├── __init__.py     # 包入口（版本号）
│       ├── graph.py        # 图引擎（阶段 1 起填充）
│       └── py.typed        # PEP 561 类型标记
├── tests/
│   └── tiny_langgraph/
│       └── test_graph.py   # 测试（镜像 src 结构）
├── docs/                   # MkDocs 文档源
│   ├── index.md
│   ├── getting_started.md
│   ├── principles/         # 核心原理（4 篇）
│   ├── stages/             # 阶段文档（10 篇）
│   └── api.md
├── examples/
└── .github/workflows/      # CI + Pages 部署
    ├── ci.yml
    └── docs.yml
```

## 关键设计决策

### 为什么用 `src/` 布局

把包放在 `src/tiny_langgraph/` 而不是根目录的 `tiny_langgraph/`，是为了**防止隐式导入**——根目录跑测试时不会意外导入到源码而非已安装的包。这是 Python 打包的现代最佳实践。

### 为什么用 hatchling

`pyproject.toml` + `hatchling` 是当前最简洁的纯 Python 构建后端，不需要 `setup.py` / `setup.cfg`。配置全在 `pyproject.toml` 一个文件里。

### 为什么测试镜像 src 结构

`tests/tiny_langgraph/test_graph.py` 对应 `src/tiny_langgraph/graph.py`。这样：

- 测试文件和源码文件一一对应，找测试不会迷路
- 后续模块多了不会乱
- 符合企业级项目的测试组织规范

### 为什么 MkDocs Material 而不是 Docusaurus

- Python 生态，和项目语言一致
- Markdown 编写，不用学 MDX
- `mkdocs gh-deploy` 一键发 GitHub Pages
- Material 主题开箱即用支持 mermaid 图、代码高亮、搜索、深色模式

## 验证骨架

```bash
# 1. 安装
pip install -e ".[dev,docs]"

# 2. 包可导入
python -c "import tiny_langgraph; print(tiny_langgraph.__version__)"
# 输出: 0.0.0

# 3. 测试通过
pytest
# 输出: no tests ran（阶段 0 没有实质测试，正常）

# 4. 文档可构建
mkdocs serve
# 浏览器打开 http://127.0.0.1:8000
```

## 对照真实 LangGraph

真实 LangGraph 的项目结构（简化）：

```
langgraph/
├── libs/langgraph/langgraph/
│   ├── graph.py          # StateGraph
│   ├── pregel/
│   │   ├── __init__.py   # Pregel 执行循环
│   │   └── read.py       # 通道读取
│   ├── checkpoint/
│   │   ├── base.py       # BaseCheckpointSaver
│   │   ├── memory.py     # MemorySaver
│   │   └── sqlite.py     # SqliteSaver
│   └── types/
└── docs/
```

我们的 `tiny_langgraph/` 会逐步长成类似的形状，但**砍掉所有生产级噪音**（分布式、LangChain 生态兼容、流式协议细节...），只留骨架。

## 下一阶段

👉 [阶段 1：最小 DAG 执行器](stage_1_dag.md)——从空文件开始写第一个能跑的图引擎。