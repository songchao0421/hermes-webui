# Hermes WebUI — Google Stitch 页面设计提示词

## 使用说明
每个页面独立一段提示词。将每段提示词粘贴到 Google Stitch 的输入框中生成设计稿。
生成后下载为 SVG/PNG，放到 `C:\Users\47291\Desktop\Github\hermes-webui\designs\` 目录下。

整体设计风格要求：暗色主题、科技感、Cyber-noir（观测虚空风）。
主色调参考 CSS 变量：--theme-primary: #e8a849（琥珀金）。

---

## 页面 1：引导设置页（Onboarding）

首次安装后或首次运行 /onboarding 时显示。覆盖全屏，不能跳过关键步骤。

Design a dark-themed, one-page setup wizard for an AI agent web interface called "Hermes WebUI". The page should have a full-screen dark background with a subtle ambient glow effect. 

### Layout (top to bottom):
1. **Top: Brand header** — "HERMES WEBUI" logo text in gold (#e8a849), small subtitle "The Dashboard for Hermes" below it
2. **Step indicator** — horizontal progress bar with 3 steps: "Connect Model" → "Configure" → "Ready"
3. **Step 1 content area**: A card showing auto-detection status. Left side: a list of detected Ollama models with checkmarks. Right side: a "Manual Configuration" button for users who want to add a remote API endpoint (OpenAI/Anthropic). At the bottom: "Skip" link in small text
4. **Step 2 content area** (shown after completing step 1): Form with fields:
   - "Agent Name" text input (placeholder: "Give your agent a name")
   - "Default Model" dropdown showing detected models
   - "Language" toggle: 中文 / English
   - A "Theme Preview" section showing 5 color swatches (amber, purple, green, cyan, rose) that preview on hover
5. **Step 3 content area**: A summary card showing all choices, with a "Complete Setup" button
6. **Bottom bar**: "Already configured? → Open Dashboard" link

### Functional Elements (every button):
- [Skip All] link at top-right corner during step 1
- [Back] button on steps 2 and 3
- [Next] primary button on steps 1 and 2
- [Scan Again] button next to detected models list
- Each model in the list has a radio selector
- [Complete Setup] big primary button on step 3

---

## 页面 2：聊天主界面（Chat）

这是用户使用最多的页面。包含侧边栏、对话区域、输入栏、状态栏。

Design a dark-themed AI chat interface for "Hermes WebUI". Full dark background with a cyber-noir aesthetic. 

### Left Sidebar (256px wide):
- **Top**: Agent avatar (rounded square, gold border glow), agent name in gold text, subtitle text below
- **Navigation items** (vertical):
  - Chat icon (active, highlighted in gold)
  - Skills icon (bolt symbol)
  - Memory icon (database symbol)
- **New Chat button** — prominent, gold background with "+" icon, centered
- **Search bar** — small search input with search icon, placeholder "搜索会话..."
- **Session list** — scrollable list of recent conversations, each showing:
  - Conversation title (bold)
  - Small preview text (1 line, dimmed)
  - Timestamp
  - A small colored dot indicating the model used (green=local, yellow=remote)
  - Hover effect: background highlight, delete button appears on right
- **Bottom section**: Settings icon button + Support/Help icon button

### Top Bar (56px, spans from sidebar right edge to screen right):
- **Status indicator**: A small colored dot + text ("Connected" / "Disconnected" / "Connecting...")
- **Model status**: A second colored dot + model name
- **Right side**: empty space or future additions

### Chat Area (main content):
- **When empty**: Center-aligned welcome message, suggestion cards below
- **Message bubbles**:
  - User messages: right-aligned, dark background, subtle border
  - AI messages: left-aligned, slightly lighter background, gold left border accent
  - Each AI message has a **bottom toolbar** with floating action buttons (appear on hover or always visible):
    - [Copy] icon
    - [Retry with different model] icon (a refresh/switch icon — this is the key "model correction" button)
  - Code blocks within messages: dark background, monospace, with a [Copy] button in top-right corner
- **Scroll**: auto-scroll to bottom on new messages, with a "Jump to bottom" floating button (appears when scrolled up)

### Bottom Input Bar (fixed at bottom, same width as chat area):
- **Attachment area** (above input, expanded when files are attached):
  - File chips showing filename + file size + remove button
  - "X file(s) attached" info text
- **Input row**: 
  - Paperclip icon (file attach button)
  - Text input area (auto-expanding textarea)
  - Microphone icon (press-and-hold for voice input, tooltip "按住录音，松开发送")
  - Send button (gold circle with up-arrow icon, OR red stop button when generating)
- **Status bar** (below input):
  - Token counter (small gold text)
  - Attachment count (if any)
  - Latency display (--ms format)
  - Current model name (clickable → dropdown to switch models)
  - Memory sync status
  - Right side: [Export] button, [Keyboard shortcuts] button, version text

### Modals (appear on top):
- **Model selector dropdown**: when clicking model name in status bar, shows a vertical list of available models with radio selectors and "Discover local models" button at bottom

---

## 页面 3：技能管理页（Skills）

列表+网格视图，展示已安装的技能，并提供导入和商店入口。

Design a dark-themed skills management page for "Hermes WebUI". Cyber-noir aesthetic with gold accents.

### Top Section:
- **Page header**: "Installed Skills" title in gold, with a subtle gold underline accent
- **Stats bar** below header: "X skills installed" text

### Skills Grid (2-column grid):
- Each skill card shows:
  - Skill icon (small colored icon)
  - Skill name (bold)
  - Brief description text (1-2 lines, dimmed)
  - Category tag/badge (small colored chip, e.g. "engineering", "devops")
  - Status indicator: enabled/disabled toggle switch
  - On hover: slight lift effect, border glow

### Bottom Section ("Expand Your Workshop"):
- A decorative card with gradient background, split into:
  - Left: "Expand Your Workshop" heading, description text, two buttons side by side:
    - [Open Skill Store] primary button (gold)
    - [Import Skill (.zip)] secondary button (outlined, with file input)
  - Right: A decorative placeholder image area showing "240+ New Skills" text

### Functional Elements:
- Each skill card has a three-dot context menu (on click): [View Details] [Disable] [Delete]
- Toggle switches are functional (not just decorative)
- Import button triggers hidden file input for .zip files
- Empty state design (when no skills installed)

---

## 页面 4：记忆管理页（Memory）

展示 SOUL.md / MEMORY.md / USER.md 三个卡片，支持编辑。

Design a dark-themed memory management page for "Hermes WebUI". Three memory file cards displayed vertically.

### Top Section:
- **Page header**: "Memory System" title in gold
- **Subtitle**: "These memory files are shared with Hermes CLI. Changes apply to both."
- **Action buttons** (top-right):
  - [Snapshot] button — icon + text, outlined style
  - [Extract from Chat] button — gold/amber background, sparkle icon

### Three Memory Cards (vertical stack, each similar layout):
1. **SOUL.md Card**:
   - Icon: person symbol in a bordered square
   - Title: "SOUL.md" (bold)
   - Subtitle: "Agent's core personality, name, behavior rules"
   - [Edit] button on right side (gold text, small)
   - Preview area: truncated content (max ~8 lines, with fade gradient at bottom), monospace font in a dark code-block box
   
2. **MEMORY.md Card** (same layout, different icon):
   - Icon: psychology/brain symbol
   - Title: "MEMORY.md"
   - Subtitle: "Accumulated knowledge and context"
   - Same preview + edit button

3. **USER.md Card** (same layout):
   - Icon: badge/ID symbol
   - Title: "USER.md"
   - Subtitle: "User profile information"
   - Same preview + edit button

### Memory Editor Modal (appears when clicking [Edit]):
- Full-screen overlay modal (centered, max-width 700px)
- Header bar: file name, [Save] button (gold), [X] close button
- Body: Large monospace textarea with full file content
- Footer: "Lines: X | Words: Y" metadata, "Autosave: Off" status

---

## 页面 5：设置页（Settings）

包含 Agent 身份、用户身份、主题、系统信息、记忆调试。

Design a dark-themed settings page for "Hermes WebUI". Cards arranged vertically in a single column, max-width container.

### Top Header:
- "Settings" title with settings icon in gold

### Identity Tabs:
- Two tab buttons side by side: [Agent] (active, gold background) [User] (inactive, dim)

### Card 1: Agent Identity (visible when Agent tab is active):
- **Avatar section** (left): Large upload zone (rounded square with dashed border), upload icon in center, "Avatar" label below, click to upload
- **Form section** (right): "Agent Name" label + text input

### Card 2: User Identity (visible when User tab is active):
- Same layout as Agent Identity but for user's name and avatar

### Card 3: Set Color (always visible):
- "Set Color" heading with palette icon
- 5 theme swatches displayed horizontally: amber(#e8a849), purple(#d0bcff), green(#81c784), cyan(#00daf3), rose(#f48fb1)
- Selected swatch has a border/glow, unselected are flat
- **On hover**: the entire page previews the theme color temporarily (this is the preview feature)

### Card 4: System Info:
- "System Info" heading with info icon
- A list of key-value pairs in monospace font:
  - Version
  - Backend URL
  - Python version
  - Platform
  - Config path
  - Skills count
  - Sessions count

### Card 5: Memory Debug (for developers):
- "Memory Debug" heading with psychology icon
- [Refresh] button on right side
- "Preview of SOUL.md content (used as system prompt in Chat mode):"
- A truncated preview box (scrollable, monospace, max 8 lines)
- Status indicator below: "Loaded" with green dot, "Error" with red dot

### Bottom: Save Button:
- [Save Changes] primary button, gold background, checkmark icon, right-aligned, with a shadow glow

---

## 页面 6：支持/关于弹窗（Support Modal）

点击侧边栏底部的 Support 按钮时弹出。

Design a dark-themed modal dialog for "Hermes WebUI" support/about page. Centered on screen, max-width 480px.

### Content (inside modal):
- **Header**: Question mark icon in gold, "Support" title, [X] close button top-right
- **Description**: "Hermes WebUI — The Dashboard for Hermes. Web interface for your local AI agent."
- **Section 1: Keyboard Shortcuts** (dark card with rounded corners):
  - "Send message" — Enter
  - "New line" — Shift + Enter
- **Section 2: Memory Files** (same card style):
  - "SOUL.md, MEMORY.md, and USER.md are shared with Hermes CLI."
  - Small text: "Located in: ~/.hermes/"
- **Section 3: Contact** (same card style):
  - Email link: songchao421@gmail.com in gold
- **Bottom section**:
  - Version text: "Version: x.x.x"
  - Two buttons side by side:
    - [Check for Updates] outlined button with sync icon
    - [Update & Restart] gold button with update icon (disabled when up-to-date)
  - Update status text (hidden by default, shows when checking/applying updates)
  - Update log area (hidden, dark monospace box, shows git output)
  - Restart countdown text (hidden, shows when restarting)

---

## 页面 7：认证弹窗（Auth Modal）

后端启用 Token 认证时，首次加载显示此弹窗。

Design a dark-themed authentication dialog for "Hermes WebUI". Centered on screen, max-width 420px.

### Content:
- **Lock icon** in a bordered square at top
- **Title**: "Authentication Required"
- **Description**: "Enter the API token shown in the server terminal."
- **Input**: Single password field centered, placeholder "Paste token here..."
- **Button**: [Authenticate] full-width button, gold background
- **Error message**: Hidden by default, red text "Invalid token. Please try again." appears on failed auth
