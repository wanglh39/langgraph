# 快速上手

## 环境要求

- Python ≥ 3.10
- pip ≥ 23

## 安装

```bash
# 克隆（阶段 0）
git clone https://github.com/tiny-langgraph/langgraph.git
cd langgraph

# 开发模式安装（含测试、lint、文档工具）
pip install -e ".[dev,docs]"
```

## 跑测试

```bash
pytest
```

阶段 0 只验证骨架可导入：

```bash
python -c "import tiny_langgraph; print(tiny_langgraph.__version__)"
# 0.0.0
```

## 本地预览文档

```bash
mkdocs serve
```

浏览器打开 <http://127.0.0.1:8000>，修改 `docs/` 下任何 `.md` 会实时刷新。

## 切到某个阶段看代码

```bash
# 看阶段 2 的代码
git checkout stage-2

# 看阶段 2 相对阶段 1 加了什么
git diff stage-1..stage-2 -- src/
```

## 阶段 9：接真 LLM

阶段 9 才需要 LLM 依赖和 API Key：

```bash
pip install -e ".[dev,docs,llm]"
export OPENAI_API_KEY="sk-..."
```

## 常见问题

??? question "为什么不直接读 LangGraph 源码？"
    真实源码要兼顾生产级功能（分布式、流式协议、LangChain 生态兼容...），有大量"噪音"。造一个最小子集，能让你看到**骨架**，而不是被细节淹没。

??? question "为什么用 Pregel 模型而不是直接 DFS 跑图？"
    Pregel 的"超级步"模型天然支持**同层并行**和**检查点对齐**，这是 LangGraph 能做并行节点和时间旅行的根。阶段 6 会讲透。

??? question "和 LangChain 的 Chain 有什么关系？"
    Chain 是单链（线性图），LangGraph 把它推广到任意有向图（含循环）。所以 LangGraph 是 Chain 的超集。