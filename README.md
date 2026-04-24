<div align="center">

<img src="docs/banner.png" alt="Hermes WebUI 马鞍" width="800">

# Hermes WebUI — 马鞍 Saddle

**The Saddle for Hermes — 给你的本地 AI Agent 一张脸**  
*Give your local AI agent a face*

[![License: MIT](https://img.shields.io/badge/License-MIT-cyan.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org)
[![Hermes](https://img.shields.io/badge/Hermes-Agent-purple.svg)](https://github.com/NousResearch/hermes-agent)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-green.svg)](https://ollama.ai)

</div>

---

## 这是什么？/ What is this?

[Hermes](https://github.com/NousResearch/hermes-agent) 是一个强大的开源 AI Agent，但它只能在终端里用。**Hermes WebUI（马鞍）** 给它加了一个好看的网页界面——你可以在浏览器里驱动 Agent 执行任务，编辑它的记忆，管理它的技能，还能给它起名字、换头像、改主题色。

[Hermes](https://github.com/NousResearch/hermes-agent) is a powerful open-source AI Agent that lives in the terminal. **Hermes WebUI** gives it a proper web interface — drive the agent to execute real tasks in the browser, edit its memory, manage skills, and make it truly yours with a custom name, avatar, and color theme.

> **Hermes WebUI 不替代 Hermes，它是你使用 Hermes 的界面。**  
> *Hermes WebUI doesn't replace Hermes — it's the interface you use it through.*

### 🤖 真正的 Agent，不只是聊天 / Real Agent, Not Just Chat

WebUI 通过 SDK 桥接层（`_hermes_sdk_bridge.py`）直接调用 Hermes Agent 的 `AIAgent.run_conversation()`，让 Agent 真正执行操作：

- 📁 **文件操作** — 创建、读取、修改文件
- 💻 **代码执行** — 运行 Python、Bash 脚本
- 🌐 **浏览器控制** — 自动化网页操作
- 🧠 **任务规划** — 多步骤任务自动完成
- 🔧 **技能调用** — 使用所有已安装的 Hermes Skills

只需在运行 WebUI 的机器上安装 Hermes Python 包，WebUI 就会自动检测并启用 Agent 模式。

*The WebUI calls Hermes Agent directly through the SDK bridge (`_hermes_sdk_bridge.py`), enabling real agent actions — file operations, code execution, browser control, and more. Install the Hermes Python package on the same machine as the WebUI, and Agent mode activates automatically.*

---

## 核心亮点 / Highlights

### 🧠 与 Hermes CLI 共享同一个大脑
WebUI 和命令行读写的是**完全相同的文件**。在网页里改了记忆，终端里立刻生效；在终端里跑了任务，网页里也能看到。没有同步延迟，没有数据孤岛。

**Shares the same brain as Hermes CLI.** The WebUI and CLI read/write the exact same files. Edit memory in the browser, see it in the terminal instantly — and vice versa. No sync delay, no data silos.

### 🎨 完全属于你的 Agent 身份
给你的 Agent 起任何名字（支持中文、emoji、符号），上传任意头像，从 5 种主题色中选一个或者自定义颜色。整个界面会实时跟着变。

**A fully personalized agent identity.** Name it anything — Chinese, emoji, symbols all work. Upload any avatar. Pick from 5 color themes or go fully custom. The entire UI updates in real-time.

### 🔒 100% 本地运行，数据不出门
所有数据存在你自己的机器上（`~/.hermes/` 和 `~/.maan/`），没有云端服务器，没有账号注册，没有数据上传。断网也能用。

**Runs 100% locally.** All data lives on your machine (`~/.hermes/` and `~/.maan/`). No cloud server, no account, no data upload. Works offline.

### 📦 完全离线运行，无需 CDN
所有前端资源（样式、字体、图标）全部自托管——Tailwind v4 CLI 预构建、Google Fonts 自托管、Material Symbols 自托管。断网也能加载完整 UI，不再依赖任何外部 CDN。

**Runs fully offline, no CDN required.** All frontend assets — CSS, fonts, icons — are self-hosted. Tailwind v4 is pre-built via CLI, Google Fonts and Material Symbols are downloaded and served locally. The UI loads completely without internet.

### 🔐 Token 认证保护 API
后端默认启用 Bearer Token 认证，Token 自动生成并存储在 `~/.maan/auth_token`，启动日志中会打印。可通过 `--no-auth` 参数禁用。

**Token-based API auth.** The backend auto-generates a Bearer token stored at `~/.maan/auth_token`. Shown in startup logs. Disable with `--no-auth`.

### 🤖 智能路由 + 美化的 Agent 输出
所有对话统一走 Hermes Agent，由智能路由模块自动判断：简单问答直接让 Agent 回复、代码/文件操作等复杂任务自动调用工具。Agent 的原始终端输出（ANSI 颜色码、进度条、banner）经过后端过滤和前端 StreamRenderer 渲染，以干净的 Markdown + 代码块形式呈现，对普通用户完全友好。

**Smart routing + clean Agent output.** All conversations go through Hermes Agent. Simple Q&A gets direct replies; complex tasks (code, file ops) auto-invoke tools. Raw terminal output (ANSI codes, spinners, banners) is filtered server-side and rendered client-side as clean Markdown with syntax-highlighted code blocks.

### ⚡ 一键启动，开箱即用
Windows 双击 `launch.bat`，Linux/Mac 运行 `./scripts/start.sh`，自动创建虚拟环境、安装依赖、启动服务。

**One-click start.** Double-click `launch.bat` on Windows or run `./scripts/start.sh` on Linux/Mac. Auto-creates venv, installs deps, starts the server.

---

## 快速开始 / Quick Start

### 环境要求 / Prerequisites

| 组件 | 必需 | 说明 |
|------|------|------|
| [Python 3.10+](https://www.python.org) | ✅ | 运行后端服务 |
| [Ollama](https://ollama.ai) | ✅ | 本地模型推理 |
| [Hermes](https://github.com/NousResearch/hermes-agent) | 推荐 | Agent 执行引擎（文件操作、代码执行等） |

> **没有 Hermes CLI 也能启动**，但只能查看记忆和技能，无法执行 Agent 任务。  
> *WebUI starts without Hermes CLI, but Agent execution requires it.*

### 安装并启动 / Install & Start

```bash
# 1. 克隆项目
git clone https://github.com/songchao4218/hermes-webui.git
cd hermes-webui

# 2. 启动
# Windows: 双击 launch.bat
# macOS:   ./scripts/install-macos.sh
# Linux:   ./scripts/start.sh
```

**启动方式 / Launch:**

| 平台 | 命令 | 说明 |
|-----|------|------|
| Windows | 双击 `launch.bat` | 自动检测 WSL2 / Hermes / Ollama，找空闲端口，启动服务（`scripts/start-windows.bat` 的快捷入口）|
| macOS | `./scripts/install-macos.sh` | 智能检测：硬件评分 → 推荐模型 → 自动安装 → 配置远程（可选）|
| Linux | `./scripts/start.sh` | 标准启动，需提前安装 Hermes 和 Ollama |

然后打开浏览器访问 **http://localhost:8080**

首次启动会进入引导设置向导，帮你配置 Agent 名称、头像和主题色。

### 手动启动后端 / Manual Start

```bash
cd backend
pip install -r requirements.txt
python app.py
# 或禁用认证（开发/测试用）
python app.py --no-auth
```

启动日志中会打印 Auth Token，前端会自动从 `localStorage` 读取并注入请求头。

### 下载模型 / Pull a Model

```bash
ollama pull gemma3:12b    # 推荐
ollama pull llama3.2:3b
ollama pull qwen2.5:7b
ollama pull deepseek-r1:8b
```

---

## 功能列表 / Features

| 功能 | 说明 |
|------|------|
| 💬 **聊天界面** | 多会话、历史持久化、延迟显示、流式响应（SSE）；撤回与重试；图片粘贴与文件附件上传 |
| 🚦 **LED 路由指示灯** | 智能模型路由状态可视化：🟢 本地免费、🟡 远程花钱、🔵 自动决策中、🔴 余额不足/Key失效、⚫ 未连接 |
| 🔍 **会话搜索** | 左侧边栏实时搜索过滤会话，按名称即时定位 |
| 🔀 **智能模型路由** | 自动判断任务类型：简单对话走本地 Ollama，代码/长文走云端 API，文件操作切换 Agent；🔄 纠偏按钮让错误分配自动学习纠正 |
| 🐴 **Agent 控制台** | 状态栏实时显示执行阶段和耗时；心跳检测（10s 响应慢提醒 / 25s 卡死警告）；■ 终止按钮随时中止；折叠式过程日志 + Agent 工具面板 |
| 🛠️ **Agent 工具面板** | 实时展示 Agent 调用的工具名称、参数和结果，折叠式查看，调试友好 |
| 🧠 **记忆编辑器** | 直接编辑 SOUL.md、MEMORY.md、USER.md，与 Hermes CLI 实时同步 |
| ✨ **从对话提炼记忆** | AI 自动从聊天历史中提取关键事实，逐条审核后一键写入记忆文件 |
| 📸 **记忆快照** | 一键创建带时间戳的记忆文件备份，防止误操作丢失 |
| ⚡ **技能管理器** | 查看已安装 Skill、启用/禁用开关、查看 SKILL.md 文档、删除，支持 ZIP 包导入 |
| 🎙 **语音输入** | 点击麦克风图标，直接语音输入消息（Web Speech API，推荐 Chrome/Edge）|
| 🎨 **动态主题** | 5 种预设主题色（amber/cyan/purple/green/rose）+ 自定义颜色 |
| 👤 **身份定制** | Agent 名称、头像、副标题；User 名称、头像，全部可配置 |
| 🔄 **模型切换** | 顶栏下拉菜单，随时切换 Ollama 模型，无需重启；模型自动发现 |
| 🔐 **Token 认证** | Bearer Token 保护所有 API，自动生成，支持 `--no-auth` 禁用 |
| 🚦 **API 限流** | 记忆操作 10次/分钟（memories 路由），防批量请求过载 |
| 📱 **移动端适配** | 响应式布局（768px 断点），侧边栏滑入动画 + 遮罩层，汉堡菜单 |
| 🔄 **一键自动更新** | Support 页面检测 GitHub 新版本，流式输出 git pull 日志，一键更新 |
| 🪟 **WSL2 路径转换** | 自动检测 WSL2 环境，Windows 路径与 WSL 路径双向转换 |
| ☁️ **云端 API 支持** | 填入 OpenAI / Anthropic / 自定义 endpoint 的 Key，复杂任务自动路由到云端 |
| 📦 **CDN 离线化** | 全部前端资源本地化（Tailwind v4 CLI 预构建、Google Fonts 自托管、Material Symbols 自托管），断网也能加载完整 UI |

---

## 记忆系统 / Memory System

Hermes WebUI 直接读写 Hermes 的记忆文件，CLI 和 WebUI 共享同一份数据：

| 文件 | 用途 | 路径 |
|------|------|------|
| `SOUL.md` | Agent 的个性、价值观、行为规则 | `~/.hermes/SOUL.md` |
| `MEMORY.md` | 累积的知识和上下文 | `~/.hermes/memories/MEMORY.md` |
| `USER.md` | 用户信息 | `~/.hermes/memories/USER.md` |

在网页的 Memory 标签页里编辑这些文件，Hermes CLI 会立即看到变化。

---

## 架构 / Architecture

```
┌─────────────────┐    ┌─────────────────────────────────────────┐
│   Browser       │    │            FastAPI Backend (WSL2)         │
│  ┌───────────┐  │    │  ┌─────────────┐  ┌───────────────────┐  │
│  │ Chat      │  │SSE │  │ /api/agent  │  │  TaskRouter        │  │
│  │ Agent控制台│◀─┼────┼─▶│ /api/agent/ │  │  Auto-detect       │  │
│  │ Skills    │  │    │  │   stream    │  │  Ollama URL        │  │
│  │ Memory    │  │    │  │ /api/agent/ │  └────────┬──────────┘  │
│  │ Settings  │  │    │  │   upload    │           │             │
│  └───────────┘  │    │  │ /api/persona│     ┌─────▼──────────┐  │
│                 │    │  │ /api/system │     │  HermesBridge   │  │
│                 │    │  │ /api/memories│     │  (SDK直接调用)  │  │
│                 │    │  │ /api/sessions│     └─────┬──────────┘  │
│                 │    │  │ /api/skills │           │             │
│                 │    │  └──────┬──────┘     ┌─────▼──────────┐  │
│                 │    │         │            │  Hermes Agent   │  │
│                 │    │         │            │  (WSL2内 SDKAIAgent) │
└─────────────────┘    │         │            └────────────────┘  │
                        └─────────┼──────────────────────────────┘
                 ┌─────────────────┼──────────────────┐
                 │                 │                  │
     ┌───────────▼──┐   ┌─────────▼────┐   ┌─────────▼───────────┐
     │  ~/.hermes/  │   │  ~/.maan/   │   │  Ollama API           │
     │  ├─ SOUL.md  │   │  ├─ persona │   │  localhost:11434      │
     │  ├─ memories/│   │  ├─ sessions│   │  (自动检测 NAT/       │
     │  ├─ skills/  │   │  ├─ uploads │   │   mirrored/远程)      │
     │  └─ config   │   │  ├─ webui_  │   │                       │
     │  (与CLI共享)  │   │  │  config  │   │  云端 API (可选)      │
     └──────────────┘   │  └─ snapshots│  │  OpenAI/Anthropic/    │
                         └─────────────┘   │  自定义 endpoint     │
                                            └──────────────────────┘
```

---

## 配置 / Configuration

Hermes WebUI 会自动读取 Hermes 的配置，通常不需要手动配置。数据目录默认在 `~/.maan/`（旧安装的用户从 `~/.hermes-webui/` 自动迁移）。如需自定义：

```yaml
# ~/.maan/config.yaml 或参考 config/maan.yaml

server:
  host: 0.0.0.0
  port: 8080

# 手动指定 Ollama 地址（远程服务器或 WSL 网络）
# ollama_url: http://192.168.1.100:11434
```

也可通过环境变量覆盖（优先级最高）：

```bash
OLLAMA_BASE_URL=http://192.168.1.100:11434
HERMES_CORS_ORIGINS=http://192.168.1.100:8080
```

---

## 项目结构 / Project Structure

```
hermes-webui/
├── backend/                          # FastAPI 后端
│   ├── app.py                        # 入口 + lifespan（会话加载/持久化 + 依赖注入）
│   ├── auth.py                       # Token 认证模块（Bearer Token）
│   ├── config.py                     # 路径管理 + 目录初始化
│   ├── models.py                     # Pydantic 请求/响应模型
│   ├── ratelimit.py                  # 限流模块（memories 路由 10次/分钟）
│   ├── _hermes_sdk_bridge.py         # Hermes Agent SDK 桥接层（AIAgent.run_conversation() 封装）
│   ├── hermes_wrapper.bat            # Windows 下调用 WSL Hermes 的包装脚本（备用）
│   ├── requirements.txt
│   ├── routers/                      # API 路由模块（6 个文件）
│   │   ├── agent.py                  #   /api/agent/ — 聊天、文件上传、Agent 执行
│   │   ├── memories.py               #   /api/memories — 记忆读写
│   │   ├── persona.py                #   /api/persona — 身份配置
│   │   ├── sessions.py               #   /api/sessions — 会话管理
│   │   ├── skills.py                 #   /api/skills — 技能管理
│   │   └── system.py                 #   /api/system — 系统信息、模型切换
│   └── services/                     # 业务逻辑服务（7 个模块）
│       ├── model_switch.py           #   模型切换逻辑
│       ├── persona_service.py        #   身份读写
│       ├── session_manager.py        #   会话 CRUD + 过期清理
│       ├── static_files.py           #   静态文件服务（无缓存）
│       ├── task_router.py            #   智能路由（Ollama 自动检测、任务分发）
│       └── webui_config.py           #   WebUI 配置持久化
├── frontend/                         # 浏览器 SPA
│   ├── index.html                    # SPA 入口（4个标签页：聊天、技能、记忆、设置）
│   ├── css/
│   │   └── input.css                 # Tailwind v4 入口（@import "tailwindcss" + @theme）
│   └── assets/
│       ├── css/
│       │   ├── tailwind.css           # Tailwind v4 CLI 预构建产物
│       │   ├── custom.css            # 自定义全局样式
│       │   └── fonts.css             # 自托管字体 @font-face
│       ├── js/
│       │   ├── main.js               # 前端入口模块
│       │   └── ...                   # 各功能模块（api.js, chat.js, state.js 等）
│       ├── fonts/                    # 自托管 Google Fonts + Material Symbols woff2
│       └── img/                      # 图片资源
├── skills/
│   └── model-router/                 # Model Router Skill
│       ├── SKILL.md
│       ├── hermes_skill.json
│       ├── router_config.json
│       └── README.md
├── tests/                            # pytest 测试套件
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_memories.py
│   ├── test_persona.py
│   ├── test_security.py
│   └── test_sessions.py
├── config/                           # 配置模板
│   ├── maan.yaml                     # WebUI 完整配置模板
│   └── hermes-webui.yaml             # 旧名称配置模板（兼容）
├── scripts/                          # 启动/安装脚本
│   ├── start-windows.bat             # Windows 主启动脚本
│   ├── start.sh                      # Linux 启动脚本
│   ├── install.sh                    # Linux 安装脚本
│   └── install-macos.sh              # macOS 专用安装脚本
├── docs/
│   ├── DESIGN.md                     # UI 设计系统文档
│   └── banner.png
├── launch.bat                        # Windows 双击入口
└── .env.example                      # 环境变量示例
```

---

## 测试 / Testing

项目使用 **pytest** + **FastAPI TestClient**，覆盖认证、记忆、身份、安全、会话五个模块。

### 安装测试依赖

```bash
pip install -r backend/requirements.txt
# 已包含 pytest>=7.0 和 pytest-asyncio>=0.21
```

### 运行所有测试

```bash
pytest tests/ -v
```

### 运行单个模块

```bash
pytest tests/test_auth.py -v        # 认证测试
pytest tests/test_memories.py -v    # 记忆 + 技能测试
pytest tests/test_persona.py -v     # 身份定制测试
pytest tests/test_security.py -v    # 安全测试
pytest tests/test_sessions.py -v    # 会话管理测试
```

### 测试覆盖范围

| 测试文件 | 覆盖内容 |
|---------|---------|
| `test_auth.py` | Token 生成、持久化、Bearer 认证、401 拒绝 |
| `test_memories.py` | 读写 SOUL/MEMORY/USER.md、非法文件名拒绝、内容长度校验 |
| `test_persona.py` | 获取/更新 Agent 名称、主题预设、自定义颜色、setup_complete |
| `test_security.py` | 头像路径穿越防护、空消息拒绝、超长输入拒绝 |
| `test_sessions.py` | 创建/列出/获取消息/删除会话 |

> 测试默认禁用认证（`conftest.py` 中 `autouse` fixture 自动处理），无需手动传 Token。

---

## 路线图 / Roadmap

- [x] **后端架构重构 v0.8.0** — app.py 精简至 140 行，领域逻辑拆入 6 个 service 模块 + 6 个 router 模块，lifespan 中通过模块变量注入依赖（2026 年计划重构为 FastAPI Depends 模式），独立 webui_config.py 自包含路径，新增 config.py / ratelimit.py
- [x] **CDN 离线化 v0.7.0** — Tailwind v4 CLI 预构建 + Google Fonts 自托管 + Material Symbols 自托管，全离线可用
- [x] 聊天界面 + 记忆同步
- [x] Agent / User 身份定制（名称、头像、主题色）
- [x] 引导式设置向导（Onboarding Wizard）
- [x] 记忆编辑器（SOUL.md / MEMORY.md / USER.md）
- [x] 技能浏览器 + ZIP 导入
- [x] 模型切换器
- [x] 多会话 + 历史持久化（`~/.maan/sessions/`）
- [x] 动态主题引擎（5 预设 + 自定义）
- [ ] 中英双语界面（自动检测浏览器语言）
- [x] 流式响应（SSE）
- [x] Token 认证（Bearer Token，支持 `--no-auth`）
- [x] Windows 全自动安装向导（WSL2 + Hermes + Ollama + 模型）
- [x] WSL2 Windows 路径自动转换
- [x] macOS 即开即用（硬件检测 + 智能模型推荐 + 远程 Ollama）
- [x] 一键自动更新（流式输出 git pull 日志）
- [x] 完整测试套件（pytest，覆盖认证/记忆/安全/会话）
- [x] **智能路由**（关键词+LLM意图分类，自动切换 Chat / Agent 模式）
- [x] **WSL2 Windows 路径注入**（Agent 模式自动感知 Windows 文件系统）
- [x] **移动端响应式适配**（768px 断点，侧边栏滑入动画，汉堡菜单，遮罩层）
- [x] **会话搜索**（左侧边栏实时过滤会话列表，无需刷新）
- [x] **API 限流**（memories 路由 10次/分钟，可扩展）
- [x] 语音输入（Web Speech API，Chrome/Edge）
- [ ] **模型路由选择器**（自动纠偏按钮，取代手动切换）
- [x] **云端 API 支持**（OpenAI / Anthropic / 自定义 endpoint）
- [x] **Agent 进程管理**（job_id + abort + watchdog 防死机）
- [x] **Agent 状态栏**（心跳检测、耗时计时、超时警告、一键终止）
- [x] **从对话提炼记忆**（AI 自动提取 + 人工审核）
- [x] **记忆快照**（带时间戳备份）
- [x] **技能管理增强**（启用/禁用、SKILL.md 查看、删除）
- [x] **Model Router Skill**（可独立发布供社区使用）
- [x] **CDN 离线化**（Tailwind v4 CLI 预构建 + Google Fonts 自托管 + Material Symbols 自托管，断网可用）
- [ ] 语音输出（TTS）
- [ ] Setup Wizard（首次启动引导 — 模型选择、API Key 配置）
- [ ] 图像生成集成

---

## 致谢 / Credits

- [Hermes](https://github.com/NousResearch/hermes-agent) — Agent 框架
- [Ollama](https://ollama.ai) — 本地模型推理
- [FastAPI](https://fastapi.tiangolo.com) — 后端框架
- [Tailwind CSS](https://tailwindcss.com) — 前端样式
- [Google Fonts](https://fonts.google.com) — 字体
- [Material Symbols](https://fonts.google.com/icons) — 图标
- [Google Stitch](https://stitch.withgoogle.com) — UI 设计灵感

---

## 许可证 / License

MIT — 随便用，随便改。详见 [LICENSE](LICENSE)。  
*MIT — use it, fork it, build on it. See [LICENSE](LICENSE).*

---

<div align="center">

**你的 Agent，你的数据，你的机器。**  
*Your agent. Your data. Your machine.*

</div>
