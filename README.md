# Deep Research Agent

基于 LangGraph 的联网研究助手，使用 DeepSeek API 生成搜索词、总结资料并补充研究。支持命令行和 LangGraph Studio，报告包含搜索来源。

本项目基于 [LangChain Local Deep Researcher](https://github.com/langchain-ai/local-deep-researcher) 改造，沿用 MIT 许可证并保留上游版权信息。

## 环境准备

当前开发环境是 Windows、Git Bash 和 Python 3.11。以下命令在项目根目录执行。

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e .
```

已有 `.venv` 时直接激活即可。Linux/macOS 使用 `source .venv/bin/activate`。

从 `.env.example` 创建本机配置，保留已有 `.env`，填写自己的 DeepSeek API Key。

```bash
cp -n .env.example .env
```

主要配置如下：

```dotenv
DEEPSEEK_API_KEY=your_deepseek_api_key
LLM_MODEL_NAME=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
SEARCH_API=duckduckgo
DDGS_BACKEND=yahoo
MAX_WEB_RESEARCH_LOOPS=0
FETCH_FULL_PAGE=false
```

模型和搜索请求需要联网。`.env` 包含本机密钥，应保留在 Git 忽略列表中。

## 命令行运行

```bash
PYTHONUTF8=1 .venv/Scripts/python.exe run_agent.py
```

输入研究主题，等待搜索和模型调用完成，终端会显示 Markdown 格式的报告和来源。每次启动脚本执行一次研究。

## LangGraph Studio

安装本地开发服务工具。Windows 彩色日志需要 `colorama`。

```bash
python -m pip install "langgraph-cli[inmem]" colorama
PYTHONUTF8=1 langgraph dev
```

在 Studio 中选择 `deep_research_agent`，输入 `research_topic` 并运行。启动日志会提供 Studio 地址，API 文档通常位于 [http://127.0.0.1:2024/docs](http://127.0.0.1:2024/docs)。

```json
{"research_topic": "CPU 的工作原理"}
```

同一 thread 会保留状态。研究独立的新主题时，新建 thread，避免之前的总结、来源和轮数影响新任务。

## 配置说明

配置字段定义在 `src/deep_research_agent/configuration.py`，由 LangGraph 生成 Studio 配置界面。三个模型节点读取同一组 DeepSeek 模型与接口设置，API Key 从 `DEEPSEEK_API_KEY` 环境变量读取。

环境变量优先于 Studio 或调用时提供的配置；使用 `.env` 和启动命令时都适用。若希望在 Studio 中调整某个字段，请先移除同名环境变量，再重启服务、刷新页面。

| 配置 | 作用 |
| --- | --- |
| `LLM_MODEL_NAME` | DeepSeek 模型名称 |
| `LLM_BASE_URL` | 模型 API 地址 |
| `SEARCH_API` | 搜索集成，支持 `duckduckgo`、`tavily`、`perplexity`、`searxng` |
| `DDGS_BACKEND` | DDGS 搜索后端，当前项目主要测试 Yahoo |
| `MAX_WEB_RESEARCH_LOOPS` | 新 thread 第一次搜索后的额外轮数，`0` 表示搜索一次 |
| `FETCH_FULL_PAGE` | 是否进一步下载网页内容，`false` 使用搜索摘要 |
| `DDGS_PROXY` | 可选代理地址；未设置时尝试已有的系统 HTTP/HTTPS 代理 |

`SEARCH_API=duckduckgo` 使用项目的 DDGS 包装函数，实际搜索引擎由 `DDGS_BACKEND` 决定。具体可用后端随 `ddgs` 版本变化，项目会校验请求的后端名称。

Yahoo 返回页面可能使用不同结构，项目对已观察到的两种结构提供兼容解析。搜索服务和页面结构仍可能变化。

## 执行流程

```text
生成搜索词 → 搜索网页 → 更新总结 → 反思并生成后续搜索词
                 ↑                         │
                 └──────── 继续搜索 ─────────┘
                                  ↓
                            整理报告和来源
```

搜索没有有效结果时进入结束分支。已有资料会保留，报告说明本轮未获得有效结果。

搜索日志包含 `search_id`、请求的后端、代理来源、耗时、原始及有效结果数、过滤情况和异常信息。`auto` 模式中的错误主机只表示异常观察到的主机，不能代表全部尝试过的搜索引擎。

## 自检

```bash
PYTHONUTF8=1 .venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py' -v
```

自检使用模拟模型和搜索响应，覆盖搜索诊断、Yahoo 解析、配置传递等行为。

## 来源与许可证

上游项目为 [langchain-ai/local-deep-researcher](https://github.com/langchain-ai/local-deep-researcher)。许可证和原作者版权信息见 `LICENSE`。
