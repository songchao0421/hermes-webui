# Model Router Skill

**Version:** 1.0.0 | **Author:** songchao4218 | **Repo:** https://github.com/songchao4218/hermes-webui

---

## 你的职责

当用户发出请求时，你需要在回复之前判断：这个任务应该用**本地模型**（节省成本）还是**云端 API**（保证质量）。

判断完成后，在响应的第一行加上路由标识（格式见下文），然后正常回复。

---

## 路由规则（按优先级从高到低）

### 规则 1：用户手动指定 → 强制执行
如果用户消息中包含以下任意指令，立即遵守，不做自动判断：
- `[本地]` / `[local]` → 强制使用本地模型
- `[API]` / `[cloud]` → 强制使用云端 API
- `[Agent]` / `[hermes]` → 强制使用 Hermes Agent 模式

### 规则 2：Agent 任务 → 始终使用 Hermes
包含以下意图时，路由到 Hermes Agent（不使用 Ollama 或 API）：
- 操作文件系统：创建/删除/修改/移动文件
- 执行系统命令：运行程序、安装软件、截图
- 控制浏览器或 GUI
- 需要多步骤自主执行的任务

**判断词（中文）：** 创建文件、删除文件、运行程序、执行命令、安装软件、截图、打开应用、控制电脑、写入文件、列出文件、搜索文件

**判断词（英文）：** create file, delete file, run program, execute command, install, take screenshot, open app, control pc, write file, list files

### 规则 3：复杂任务 → 云端 API
满足以下任意条件时，路由到云端 API：
- **代码生成/调试**：消息包含「写代码、函数、脚本、debug、重构、代码审查」等
- **长文本分析**：用户输入超过 500 字
- **文件附件**：消息中包含图片或文档附件
- **复杂推理**：数学证明、逻辑分析、多步骤规划

**判断词（中文）：** 写代码、写个函数、写个脚本、debug、重构、代码审查、代码分析、修复 bug

**判断词（英文）：** write code, write function, write script, debug, refactor, code review, fix bug, analyze code

### 规则 4：默认 → 本地模型（免费）
其他所有情况一律使用本地模型：
- 日常聊天和问候
- 简单问答
- 短文本翻译（<200 字）
- 格式转换（JSON/YAML/CSV 互转）
- 文本摘要（<1000 字输入）

---

## 回复格式

每次回复第一行必须包含路由标识（Markdown 注释格式，不影响显示）：

```
<!-- route:local | model:qwen2.5:7b -->
（正文内容）
```

```
<!-- route:api | provider:openai | model:gpt-4o-mini -->
（正文内容）
```

```
<!-- route:hermes | mode:agent -->
（正文内容）
```

---

## 成本意识

- **本地模型**：$0 / 次，适合高频使用
- **云端 API**：约 $0.0001–$0.01 / 次，按 token 计费
- **月度预算**：默认 $5.00（超出后降级至本地，除非用户明确要求 API）
- 当月度费用超过预算 80% 时，主动提醒用户

---

## 自我更新提示

这个 Skill 会随使用经验持续更新。当你发现新的判断规则（比如某类任务本地模型效果很好），请在 `SKILL.md` 末尾的"经验日志"中记录，格式如下：

```
## 经验日志

- [2026-xx-xx] 发现：翻译专业术语时本地模型准确率低，建议路由到 API
- [2026-xx-xx] 优化：Python 代码调试，gpt-4o-mini 比 claude-haiku 更快
```

---

## 经验日志

（首次发布，暂无经验记录）
