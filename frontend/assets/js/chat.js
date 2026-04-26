/**
 * Hermes WebUI — Chat Module (V2.0)
 * Core chat functions: send/receive messages, SDK SSE streaming.
 * Only talks to the Agent — no more local model / API / routing.
 */
import { apiFetch, apiUrl, agentStream, agentAbort, sessionUndo, sessionRetry, sessionRename } from './api.js';
import { state } from './state.js';
import { escapeHtml, showToast, scrollToBottom, autoResize } from './utils.js';
import { createToolPanel } from './tool_panel.js';

// ── Status bar helpers ──────────────────────────────────────────

let _heartbeatTimer = null;
let _elapsedTimer = null;

function _startAgentTimers(statusEl) {
    state.agentStartTime = Date.now();
    clearInterval(_elapsedTimer);
    clearTimeout(_heartbeatTimer);
    _elapsedTimer = setInterval(() => {
        const sec = Math.floor((Date.now() - state.agentStartTime) / 1000);
        const elEl = statusEl?.querySelector('.agent-elapsed');
        if (elEl) elEl.textContent = '⏱ ' +
            String(Math.floor(sec / 60)).padStart(2, '0') + ':' +
            String(sec % 60).padStart(2, '0');
    }, 1000);
    _resetHeartbeatWatchdog(statusEl);
}

function _resetHeartbeatWatchdog(statusEl) {
    clearTimeout(_heartbeatTimer);
    _heartbeatTimer = setTimeout(() => {
        const warnEl = statusEl?.querySelector('.agent-hb-warn');
        if (warnEl) {
            warnEl.className = 'agent-timeout-warn';
            warnEl.textContent = '⚠ Agent 响应慢…';
        }
        _heartbeatTimer = setTimeout(() => {
            if (warnEl) {
                warnEl.className = 'agent-timeout-crit';
                warnEl.innerHTML = '🔴 Agent 可能卡住了 <button onclick="stopGeneration()" style="margin-left:8px;background:#ff5050;color:#fff;border:none;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:11px;">强制终止</button>';
            }
        }, 15000);
    }, 10000);
}

function _stopAgentTimers() {
    clearInterval(_elapsedTimer);
    clearTimeout(_heartbeatTimer);
    _elapsedTimer = null;
    _heartbeatTimer = null;
}

// ── User Message ────────────────────────────────────────────────

export function addUserMessage(message) {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer) return;
    const userName = state.persona?.user_display_name || 'You';
    const div = document.createElement('div');
    div.className = 'flex flex-col items-end gap-3 mb-8 user-message-group';
    div.innerHTML = `
        <div class="flex items-center gap-3">
            <span class="text-[10px] font-bold text-on-surface-variant/50 uppercase tracking-widest">${escapeHtml(userName)}</span>
            <button onclick="handleUndo()" class="undo-btn text-[10px] text-on-surface-variant/30 hover:text-on-surface-variant/80 transition-colors" title="撤回">
                <span class="material-symbols-outlined text-[14px]">undo</span>
            </button>
        </div>
        <div class="max-w-[80%] bg-primary/10 rounded-2xl rounded-tr-sm px-5 py-3">
            ${_buildUserContent(message)}
        </div>
    `;
    chatContainer.appendChild(div);
    scrollToBottom();
}

function _buildUserContent(message) {
    let parts = '';
    // Build image thumbnails from current attachments
    const atts = state.currentAttachments || [];
    for (const att of atts) {
        if (att.type?.startsWith('image/')) {
            const previewUrl = att.previewUrl || '';
            parts += `<img src="${previewUrl}" class="max-w-[120px] max-h-[90px] rounded-lg object-cover mb-1.5" alt="attachment">`;
        } else {
            parts += `<div class="flex items-center gap-2 text-xs text-on-surface-variant/70 mb-2 px-3 py-1.5 bg-surface-container-high rounded-lg"><span class="material-symbols-outlined text-[16px]">description</span>${escapeHtml(att.name)}</div>`;
        }
    }
    if (message) {
        parts += `<div class="text-sm text-on-surface leading-relaxed">${escapeHtml(message)}</div>`;
    } else if (!atts.length) {
        parts += '<span class="text-sm text-on-surface-variant/60">📎 附件已发送</span>';
    }
    return parts;
}

// ── Assistant Message (final) ───────────────────────────────────

export function addAssistantMessage(content, latency) {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer) return;
    const name = state.persona?.agent_name || 'Agent';
    const avatarWrap = _buildAgentAvatar();
    const div = document.createElement('div');
    div.className = 'flex flex-col items-start gap-3 mb-8 assistant-message-group';
    div.innerHTML = `
        <div class="flex items-center gap-3 mb-1">
            <div class="avatar-slot w-10 h-10 shrink-0"></div>
            <div class="flex items-baseline gap-2">
                <span class="font-headline text-[13px] font-extrabold uppercase tracking-widest" style="color: var(--theme-primary);">${escapeHtml(name)}</span>
                <span class="text-[11px] text-on-surface-variant/40">${latency ? latency + 'ms' : ''}</span>
                <button onclick="handleRetry()" class="retry-btn text-[10px] text-on-surface-variant/30 hover:text-on-surface-variant/80 transition-colors ml-2" title="重试">
                    <span class="material-symbols-outlined text-[14px]">replay</span>
                </button>
            </div>
        </div>
        <div class="pl-14 max-w-full">
            <div class="space-y-3 text-on-surface-variant leading-relaxed text-sm">${formatContent(content)}</div>
        </div>
    `;
    div.querySelector('.avatar-slot').replaceWith(avatarWrap);
    chatContainer.appendChild(div);
    scrollToBottom();
}

// ── Streaming assistant message ─────────────────────────────────

export function addAssistantMessageStreaming() {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer) return { contentEl: null, statusEl: null };
    const name = state.persona?.agent_name || 'Agent';
    const avatarWrap = _buildAgentAvatar();

    const div = document.createElement('div');
    div.className = 'flex flex-col items-start gap-3 mb-8 assistant-message';
    div.innerHTML = `
        <div class="flex items-center gap-3 mb-1">
            <div class="avatar-slot w-10 h-10 shrink-0"></div>
            <div class="flex items-baseline gap-2">
                <span class="font-headline text-[13px] font-extrabold uppercase tracking-widest" style="color: var(--theme-primary);">${escapeHtml(name)}</span>
            </div>
        </div>
        <div class="pl-14 max-w-full w-full">
            <div class="response-content space-y-3 text-on-surface-variant leading-relaxed text-sm"></div>
            <div class="agent-status flex items-center gap-3 flex-wrap mt-2 px-1">
                <span class="agent-phase text-[11px] text-on-surface-variant/60">启动中...</span>
                <span class="agent-elapsed text-[11px] text-on-surface-variant/60"></span>
                <span class="agent-hb-warn text-[11px]"></span>
            </div>
            <div class="agent-logs flex flex-wrap gap-1 mt-1 px-1"></div>
        </div>
        <div class="tool-call-panel pl-14 w-full"></div>
    `;
    div.querySelector('.avatar-slot').replaceWith(avatarWrap);
    chatContainer.appendChild(div);
    scrollToBottom();

    const contentEl = div.querySelector('.response-content');
    const statusEl = div.querySelector('.agent-status');
    const toolPanelEl = div.querySelector('.tool-call-panel');
    return { contentEl, statusEl, toolPanelEl, msgDiv: div };
}

// ── Thinking Indicator ──────────────────────────────────────────

export function addThinkingIndicator() {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer) return;
    const name = state.persona?.agent_name || 'Agent';
    const div = document.createElement('div');
    div.className = 'thinking-indicator flex flex-col items-start gap-4';
    div.innerHTML = `
        <div class="flex items-center gap-3 px-4 py-3 bg-surface-container-lowest rounded-2xl thinking-glow border" style="border-color: var(--theme-primary); border-opacity: 0.2;">
            <div class="relative w-5 h-5">
                <div class="absolute inset-0 border-2 rounded-full animate-spin" style="border-color: var(--theme-primary); opacity: 0.3; border-top-color: var(--theme-primary);"></div>
            </div>
            <span class="text-xs font-medium tracking-wide" style="color: var(--theme-primary);">${escapeHtml(name)} is thinking...</span>
        </div>
    `;
    chatContainer.appendChild(div);
    scrollToBottom();
}

export function removeThinkingIndicator() {
    const el = document.getElementById('chatContainer')?.querySelector('.thinking-indicator');
    if (el) el.remove();
}

// ── Session operations (undo / retry / rename) ──────────────────

/**
 * Undo the last user-assistant message pair.
 */
export async function handleUndo() {
    if (!state.currentSessionId) return;
    try {
        await sessionUndo(state.currentSessionId);
        // Remove last two message groups from DOM
        const container = document.getElementById('chatContainer');
        if (!container) return;
        const messages = container.querySelectorAll('.user-message-group, .assistant-message-group, .assistant-message, .thinking-indicator');
        // Remove last assistant + user pair (typically 2-3 elements)
        const last = messages[messages.length - 1];
        if (last && (last.classList.contains('assistant-message-group') || last.classList.contains('assistant-message'))) {
            last.remove();
        }
        const penultimate = messages[messages.length - 2];
        if (penultimate && penultimate.classList.contains('user-message-group')) {
            penultimate.remove();
        }
        showToast('已撤回');
    } catch (e) {
        showToast('撤回失败: ' + e.message, true);
    }
}

/**
 * Retry: undo + re-send the last user message.
 */
export async function handleRetry() {
    if (!state.currentSessionId) return;
    try {
        const result = await sessionRetry(state.currentSessionId);
        // Remove last assistant + user messages from DOM
        const container = document.getElementById('chatContainer');
        if (container) {
            const messages = container.querySelectorAll('.user-message-group, .assistant-message-group, .assistant-message, .thinking-indicator');
            const last = messages[messages.length - 1];
            if (last && (last.classList.contains('assistant-message-group') || last.classList.contains('assistant-message'))) {
                last.remove();
            }
            const penultimate = messages[messages.length - 2];
            if (penultimate && penultimate.classList.contains('user-message-group')) {
                penultimate.remove();
            }
        }
        // Re-send the last user message
        if (result?.last_user_message) {
            sendMessage(result.last_user_message);
        }
    } catch (e) {
        showToast('重试失败: ' + e.message, true);
    }
}

/**
 * Open rename modal for the current session.
 */
export function openRenameModal(currentTitle) {
    const modal = document.getElementById('renameModal');
    const input = document.getElementById('renameInput');
    if (!modal || !input) return;
    input.value = currentTitle || '';
    modal.classList.remove('hidden');
    setTimeout(() => input.focus(), 100);
}

/**
 * Confirm rename of current session.
 */
window.confirmRename = async function confirmRename() {
    const modal = document.getElementById('renameModal');
    const input = document.getElementById('renameInput');
    if (!modal || !input || !state.currentSessionId) return;
    const title = input.value.trim();
    if (!title) { showToast('请输入标题'); return; }
    try {
        await sessionRename(state.currentSessionId, title);
        modal.classList.add('hidden');
        refreshSessions();
        showToast('已重命名');
    } catch (e) {
        showToast('重命名失败: ' + e.message, true);
    }
};

// ── Token Estimate ──────────────────────────────────────────────

export function estimateTokens(text) {
    const chineseChars = (text.match(/[\u4e00-\u9fff]/g) || []).length;
    const otherChars = text.length - chineseChars;
    return Math.ceil(chineseChars / 1.5 + otherChars / 4);
}

export function updateTokenEstimate() {
    const input = document.getElementById('messageInput');
    const counter = document.getElementById('tokenCounter');
    if (!input || !counter) return;
    const tokens = estimateTokens(input.value);
    counter.textContent = tokens > 0 ? `~${tokens} tokens` : '';
}

// ── sendMessage (core — Agent only) ─────────────────────────────

export async function sendMessage() {
    const chatContainer = document.getElementById('chatContainer');
    const messageInput = document.getElementById('messageInput');
    if (!chatContainer || !messageInput) return;
    if (state.isProcessing) return;
    const message = messageInput.value.trim();
    // Allow sending with only attachments (no text) — like WeChat image paste
    if (!message && (!state.currentAttachments || state.currentAttachments.length === 0)) return;

    addUserMessage(message);
    messageInput.value = '';
    messageInput.style.height = 'auto';
    updateTokenEstimate();

    state.isProcessing = true;
    document.getElementById('sendButton')?.classList.add('hidden');
    const stopBtn = document.getElementById('stopButton');
    if (stopBtn) stopBtn.classList.remove('hidden');
    // Immediately hide attachment bar — don't wait for response
    document.getElementById('attachmentPreview')?.classList.add('hidden');
    addThinkingIndicator();

    try {
        // Upload attachments first if any
        let fileIds = [];
        if (state.currentAttachments && state.currentAttachments.length > 0) {
            const formData = new FormData();
            for (const att of state.currentAttachments) {
                formData.append('files', att.file, att.name);
            }
            try {
                const uploadResp = await apiFetch(apiUrl('/api/agent/attachments'), {
                    method: 'POST',
                    body: formData,
                });
                if (uploadResp.ok) {
                    const uploadResult = await uploadResp.json();
                    fileIds = (uploadResult.files || [])
                        .filter(f => f.file_id)
                        .map(f => f.file_id);
                }
            } catch (_) { /* upload fails silently */ }
        }

        // Build conversation history from current session messages
        const history = (state.messages || []).map(m => ({
            role: m.role,
            content: m.content,
        }));

        const resp = await agentStream(message, {
            sessionId: state.currentSessionId,
            history,
            fileIds: fileIds.length > 0 ? fileIds : undefined,
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: 'Request failed: ' + resp.status }));
            removeThinkingIndicator();
            addAssistantMessage('Error: ' + (err.detail || resp.status));
            return;
        }

        removeThinkingIndicator();
        const { contentEl, statusEl, toolPanelEl, msgDiv } = addAssistantMessageStreaming();
        if (statusEl) _startAgentTimers(statusEl);
        const toolPanel = createToolPanel(toolPanelEl);

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        const renderer = new StreamRenderer(contentEl);
        let fullContent = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();
            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                try {
                    const data = JSON.parse(line.slice(6));
                    const type = data.type;

                    if (type === 'token' && data.content) {
                        renderer.push(data.content);
                        fullContent += data.content;
                        scrollToBottom();
                    } else if (type === 'thinking') {
                        const phaseEl = statusEl?.querySelector('.agent-phase');
                        if (phaseEl) phaseEl.textContent = '🧠 ' + data.content;
                    } else if (type === 'reasoning') {
                        const phaseEl = statusEl?.querySelector('.agent-phase');
                        if (phaseEl) phaseEl.textContent = '📝 ' + (data.content || '推理中...');
                    } else if (type === 'status') {
                        const phaseEl = statusEl?.querySelector('.agent-phase');
                        if (phaseEl) phaseEl.textContent = data.message;
                    } else if (type === 'tool_start') {
                        const phaseEl = statusEl?.querySelector('.agent-phase');
                        if (phaseEl) phaseEl.textContent = '🔧 ' + data.name;
                        if (toolPanel) toolPanel.showStart(data);
                    } else if (type === 'tool_complete') {
                        if (toolPanel) toolPanel.showComplete(data);
                    } else if (type === 'done') {
                        renderer.finish();
                        _stopAgentTimers();
                        if (statusEl) {
                            const phaseEl = statusEl.querySelector('.agent-phase');
                            if (phaseEl) phaseEl.textContent = '✅ 完成 ' + (data.latency_ms || '') + 'ms';
                        }
                        // Save the message to session
                        if (state.currentSessionId && fullContent) {
                            state.messages = state.messages || [];
                            state.messages.push({ role: 'assistant', content: fullContent });
                        }
                        scrollToBottom();
                        // Add re-route button
                        try { addRerouteButton(); } catch (_) {}
                    } else if (type === 'routing') {
                        // Routing decision from backend
                        data._message = message;  // attach the original user message
                        if (typeof window.setLastRoutingDecision === 'function') {
                            window.setLastRoutingDecision(data);
                        }
                    } else if (type === 'error') {
                        renderer.finish();
                        _stopAgentTimers();
                        contentEl.innerHTML += '<br><span style="color:var(--error)">⚠ ' + escapeHtml(data.message) + '</span>';
                        if (statusEl) {
                            const phaseEl = statusEl.querySelector('.agent-phase');
                            if (phaseEl) phaseEl.textContent = '❌ 错误';
                        }
                    }
                } catch (e) { /* skip malformed */ }
            }
        }
    } catch (e) {
        removeThinkingIndicator();
        _stopAgentTimers();
        if (e.name !== 'AbortError') {
            addAssistantMessage('Error: ' + e.message);
        }
    } finally {
        state.isProcessing = false;
        document.getElementById('sendButton')?.classList.remove('hidden');
        document.getElementById('sendButton')?.removeAttribute('disabled');
        const stopBtn = document.getElementById('stopButton');
        if (stopBtn) stopBtn.classList.add('hidden');
        // Cleanup attachments
        state.currentAttachments.forEach(a => { if (a.previewUrl) URL.revokeObjectURL(a.previewUrl); });
        state.currentAttachments = [];
        const attachBar = document.getElementById('attachmentPreview');
        if (attachBar) attachBar.classList.add('hidden');
        const fileInput = document.getElementById('fileInput');
        if (fileInput) fileInput.value = '';
    }
}

// ── stopGeneration ──────────────────────────────────────────────

export function stopGeneration() {
    _stopAgentTimers();
    agentAbort().catch(() => {});
    state.isProcessing = false;
    document.getElementById('sendButton')?.classList.remove('hidden');
    const stopBtn = document.getElementById('stopButton');
    if (stopBtn) stopBtn.classList.add('hidden');
    removeThinkingIndicator();
    showToast('已停止生成', 'info');
}

window.stopGeneration = stopGeneration;

// ── StreamRenderer ──────────────────────────────────────────────

export class StreamRenderer {
    constructor(containerEl) {
        this.container = containerEl;
        this.buffer = '';
    }
    push(token) {
        this.buffer += token;
        const pieces = this._parseBlocks(this.buffer);
        this._render(pieces);
    }
    finish() {
        if (this.buffer) this.push('');
    }
    _parseBlocks(text) {
        const result = [];
        const parts = text.split(/(```[\s\S]*?```)/g);
        for (const part of parts) {
            if (!part) continue;
            if (part.startsWith('```')) {
                const lines = part.split('\n');
                const firstLine = lines[0];
                const lang = firstLine.replace(/^```/, '').trim();
                const code = lines.slice(1, lines[lines.length - 1].trim() === '```' ? -1 : lines.length).join('\n');
                result.push({ type: 'code', lang, code });
            } else {
                result.push({ type: 'text', content: part });
            }
        }
        return result;
    }
    _render(pieces) {
        this.container.innerHTML = pieces.map(p => {
            if (p.type === 'code') {
                const langLabel = p.lang ? `<span class="code-lang-label">${escapeHtml(p.lang)}</span>` : '';
                return `<div class="code-block-wrapper"><div class="code-header flex items-center justify-between px-4 py-2"><div class="flex items-center gap-3">${langLabel}</div><button onclick="cbCopy(this)" class="text-xs text-on-surface-variant hover:text-on-surface">复制</button></div><pre><code class="${p.lang ? 'language-' + escapeHtml(p.lang) : ''}">${escapeHtml(p.code)}</code></pre></div>`;
            }
            return p.content.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\*(.*?)\*/g, '<em>$1</em>');
        }).join('');
        if (window.hljs) {
            this.container.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
        }
    }
}

// ── formatContent ───────────────────────────────────────────────

export function formatContent(content) {
    if (!content) return '';
    const blocks = [];
    let lastIndex = 0;
    const regex = /```(\w*)\s*\n([\s\S]*?)```/g;
    let match;
    while ((match = regex.exec(content)) !== null) {
        if (match.index > lastIndex) {
            blocks.push({ type: 'text', content: content.slice(lastIndex, match.index) });
        }
        blocks.push({ type: 'code', lang: match[1], code: match[2] });
        lastIndex = match.index + match[0].length;
    }
    if (lastIndex < content.length) blocks.push({ type: 'text', content: content.slice(lastIndex) });
    if (!blocks.length) blocks.push({ type: 'text', content });
    return blocks.map(b => {
        if (b.type === 'code') {
            const langLabel = b.lang ? `<span class="code-lang-label">${escapeHtml(b.lang)}</span>` : '';
            return `<div class="code-block-wrapper"><div class="code-header flex items-center justify-between px-4 py-2"><div class="flex items-center gap-3">${langLabel}</div><button onclick="cbCopy(this)" class="text-xs text-on-surface-variant hover:text-on-surface">复制</button></div><pre><code class="${b.lang ? 'language-' + escapeHtml(b.lang) : ''}">${escapeHtml(b.code)}</code></pre></div>`;
        }
        return b.content.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\*(.*?)\*/g, '<em>$1</em>');
    }).join('');
}

// ── Clipboard ───────────────────────────────────────────────────

window.cbCopy = (btn) => {
    const code = btn.closest('.code-block-wrapper')?.querySelector('code');
    if (!code) return;
    navigator.clipboard.writeText(code.textContent).then(() => {
        const orig = btn.textContent;
        btn.textContent = '✅ 已复制!';
        setTimeout(() => { btn.textContent = orig; }, 2000);
    });
};

// ── Avatar builder ──────────────────────────────────────────────

function _buildAgentAvatar() {
    const wrap = document.createElement('div');
    wrap.className = 'w-10 h-10 rounded-xl overflow-hidden bg-surface-container flex items-center justify-center';
    wrap.style.boxShadow = '0 0 0 1.5px var(--theme-primary)';
    const p = state.persona || {};
    if (p.avatar) {
        const img = new Image();
        img.className = 'w-full h-full object-cover';
        img.src = apiUrl('/api/persona/avatar/') + p.avatar;
        img.onerror = function () {
            this.outerHTML = '<span class="material-symbols-outlined text-primary text-sm">smart_toy</span>';
        };
        wrap.appendChild(img);
    } else if (p.avatar_preset) {
        const iconMap = { robot: 'smart_toy', face: 'face', bolt: 'bolt' };
        const icon = document.createElement('span');
        icon.className = 'material-symbols-outlined text-primary text-sm';
        icon.textContent = iconMap[p.avatar_preset] || 'smart_toy';
        wrap.appendChild(icon);
    } else {
        const img = new Image();
        img.className = 'w-full h-full object-cover';
        img.src = apiUrl('/api/persona/avatar/logo.png');
        img.onerror = function () {
            this.outerHTML = '<span class="material-symbols-outlined text-primary text-sm">smart_toy</span>';
        };
        wrap.appendChild(img);
    }
    return wrap;
}

// ── Helpers ─────────────────────────────────────────────────────

export function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    } else if (event.key === 'Escape') {
        document.getElementById('messageInput')?.blur();
    }
}

export function autoResizeTextarea(textarea) {
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 128) + 'px';
}

export function handleFileSelect(event) {
    const files = event.target.files;
    if (!files || !files.length) return;
    _addAttachments(files);
}

// ── Paste image from clipboard (screenshot) ──────────────────────
export function handlePaste(event) {
    const items = event.clipboardData?.items;
    if (!items) return;
    let hasImage = false;
    for (const item of items) {
        if (item.type.startsWith('image/')) {
            hasImage = true;
            const file = item.getAsFile();
            if (file) {
                event.preventDefault();  // Block raw paste of image bytes into textarea
                // Give the file a meaningful name
                const namedFile = new File([file], 'screenshot.png', { type: file.type });
                _addAttachments([namedFile]);
                // Don't auto-send — user may want to type first
            }
            break;
        }
    }
    // If it's a file paste (not raw bytes), let the default handler deal with it
    if (!hasImage) {
        // Check for files in clipboard (e.g. copied from file explorer)
        const files = event.clipboardData?.files;
        if (files && files.length > 0) {
            event.preventDefault();
            _addAttachments(files);
        }
    }
}

export function removeAttachment() {
    state.currentAttachments.forEach(a => { if (a.previewUrl) URL.revokeObjectURL(a.previewUrl); });
    state.currentAttachments = [];
    const preview = document.getElementById('attachmentPreview');
    if (preview) preview.classList.add('hidden');
    const fileInput = document.getElementById('fileInput');
    if (fileInput) fileInput.value = '';
    _updateAttachCount();
}

// ── Enhanced Attachment Handling ──────────────────────────────

const ALLOWED_MIME_TYPES = [
    'image/', 'text/', 'application/pdf',
    'application/json', 'application/x-yaml', 'application/xml',
];
const ALLOWED_EXTENSIONS = ['.py', '.js', '.ts', '.json', '.yaml', '.yml', '.md', '.csv', '.txt', '.xml', '.toml', '.ini', '.cfg', '.env', '.sh', '.bat', '.ps1', '.html', '.css', '.scss', '.less'];
const MAX_FILE_SIZE_MB = 50;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const MAX_TOTAL_SIZE_MB = 100;
const MAX_FILES = 20;

function _isFileAllowed(file) {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    // Check by MIME type prefix
    for (const prefix of ALLOWED_MIME_TYPES) {
        if (file.type.startsWith(prefix)) return true;
    }
    // Check by extension
    if (ALLOWED_EXTENSIONS.includes(ext)) return true;
    return false;
}

/**
 * Compress image if it exceeds 1200px on either dimension or 500KB.
 * Returns the compressed File (or original if already small enough).
 */
function _compressImageIfNeeded(file) {
    return new Promise((resolve) => {
        if (!file.type.startsWith('image/')) {
            resolve(file);
            return;
        }
        // Skip small files
        if (file.size < 300 * 1024) {
            resolve(file);
            return;
        }
        const img = new Image();
        const url = URL.createObjectURL(file);
        img.onload = () => {
            URL.revokeObjectURL(url);
            let w = img.naturalWidth;
            let h = img.naturalHeight;
            const MAX = 1200;
            if (w <= MAX && h <= MAX && file.size < 500 * 1024) {
                resolve(file);
                return;
            }
            if (w > MAX || h > MAX) {
                const ratio = Math.min(MAX / w, MAX / h);
                w = Math.round(w * ratio);
                h = Math.round(h * ratio);
            }
            const canvas = document.createElement('canvas');
            canvas.width = w;
            canvas.height = h;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, w, h);
            // Determine output quality and format
            const isPng = file.type === 'image/png';
            canvas.toBlob((blob) => {
                if (!blob) { resolve(file); return; }
                const compressed = new File([blob], file.name, { type: isPng ? 'image/png' : 'image/jpeg' });
                resolve(compressed);
            }, isPng ? 'image/png' : 'image/jpeg', 0.85);
        };
        img.onerror = () => { URL.revokeObjectURL(url); resolve(file); };
        img.src = url;
    });
}

function _addAttachments(files) {
    const fileArray = Array.from(files);
    if (state.currentAttachments.length + fileArray.length > MAX_FILES) {
        showToast(`最多上传 ${MAX_FILES} 个文件`, 'warning');
        return;
    }

    const rejected = [];
    let totalBytes = state.currentAttachments.reduce((s, a) => s + (a.size || 0), 0);

    for (const rawFile of fileArray) {
        // Check file size
        if (rawFile.size > MAX_FILE_SIZE_BYTES) {
            rejected.push(`${rawFile.name} (超过 ${MAX_FILE_SIZE_MB}MB)`);
            continue;
        }
        // Check total size
        if (totalBytes + rawFile.size > MAX_TOTAL_SIZE_MB * 1024 * 1024) {
            rejected.push(`${rawFile.name} (总大小超限)`);
            continue;
        }
        // Check file type
        if (!_isFileAllowed(rawFile)) {
            rejected.push(`${rawFile.name} (不支持的文件类型)`);
            continue;
        }

        const previewUrl = rawFile.type.startsWith('image/')
            ? URL.createObjectURL(rawFile)
            : null;
        state.currentAttachments.push({
            file: rawFile,
            name: rawFile.name,
            path: rawFile.name,
            size: rawFile.size,
            type: rawFile.type,
            previewUrl,
        });
        totalBytes += rawFile.size;
    }

    _renderAttachmentPreview();

    if (rejected.length > 0) {
        showToast(`已忽略 ${rejected.length} 个文件:\n${rejected.join('\n')}`, 'warning');
    } else if (fileArray.length > 0) {
        showToast(`已添加 ${fileArray.length - rejected.length} 个附件`, 'success');
    }

    _updateAttachCount();
}

function _renderAttachmentPreview() {
    const preview = document.getElementById('attachmentPreview');
    if (!preview) return;
    const list = document.getElementById('attachmentList') || preview;
    const items = state.currentAttachments.map((a, i) => {
        const isImage = a.type?.startsWith('image/');
        const sizeStr = a.size ? _formatBytes(a.size) : '';
        return `
            <div class="attachment-chip group relative flex items-center gap-1.5 px-2.5 py-1.5 bg-surface-container-high rounded-lg border border-outline-variant/20 text-[11px] cursor-default hover:bg-surface-container-higher transition-colors">
                ${isImage && a.previewUrl
                    ? `<img src="${a.previewUrl}" class="w-5 h-5 rounded object-cover shrink-0" alt="">`
                    : `<span class="material-symbols-outlined text-[14px] text-on-surface-variant/60 shrink-0">${_fileIcon(a.name)}</span>`
                }
                <span class="max-w-[120px] truncate text-on-surface-variant">${escapeHtml(a.name)}</span>
                ${sizeStr ? `<span class="text-[9px] text-on-surface-variant/40 shrink-0">${sizeStr}</span>` : ''}
                <button onclick="removeAttachmentItem(${i})" class="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-error/80 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity" title="移除">
                    <span class="material-symbols-outlined text-[10px]">close</span>
                </button>
            </div>
        `;
    }).join('');
    list.innerHTML = items;
    preview.classList.remove('hidden');
}

function removeAttachmentItem(index) {
    const item = state.currentAttachments[index];
    if (item?.previewUrl) URL.revokeObjectURL(item.previewUrl);
    state.currentAttachments.splice(index, 1);
    if (state.currentAttachments.length === 0) {
        removeAttachment();
    } else {
        _renderAttachmentPreview();
        _updateAttachCount();
    }
}

window.removeAttachmentItem = removeAttachmentItem;

function _updateAttachCount() {
    const wrap = document.getElementById('attachCountWrap');
    const countEl = document.getElementById('attachCount');
    if (!wrap || !countEl) return;
    if (state.currentAttachments.length > 0) {
        wrap.classList.remove('hidden');
        countEl.textContent = `${state.currentAttachments.length} file(s) · ${_formatBytes(state.currentAttachments.reduce((s, a) => s + (a.size || 0), 0))}`;
    } else {
        wrap.classList.add('hidden');
    }
}

function _formatBytes(bytes) {
    if (!bytes) return '';
    if (bytes < 1024) return bytes + 'B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
    return (bytes / (1024 * 1024)).toFixed(1) + 'MB';
}

function _fileIcon(filename) {
    const ext = filename.split('.').pop()?.toLowerCase();
    const iconMap = {
        py: 'code', js: 'javascript', ts: 'javascript', json: 'data_object',
        yaml: 'settings', yml: 'settings', md: 'article', csv: 'table_rows',
        txt: 'description', pdf: 'picture_as_pdf', html: 'code', css: 'style',
        xml: 'code', sh: 'terminal', bat: 'terminal', ps1: 'terminal',
        toml: 'settings', ini: 'settings', env: 'settings',
    };
    return iconMap[ext] || 'insert_drive_file';
}

export function exportChat() {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer || !chatContainer.children.length) {
        showToast('没有可导出的对话', 'warning');
        return;
    }
    let markdown = '# 对话导出\n\n';
    chatContainer.querySelectorAll('.assistant-message, .flex.flex-col.items-end').forEach(el => {
        if (el.classList.contains('assistant-message')) {
            const name = state.persona?.agent_name || 'Agent';
            markdown += `**${name}**: `;
            const content = el.querySelector('.response-content');
            if (content) markdown += content.textContent.trim();
            markdown += '\n\n';
        } else {
            markdown += '**You**: ';
            const content = el.querySelector('.max-w-\\[80\\%\\]');
            if (content) markdown += content.textContent.trim();
            markdown += '\n\n';
        }
    });
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'chat-export.md';
    a.click();
    URL.revokeObjectURL(url);
    showToast('对话已导出', 'success');
}

// ── Window Exports ──────────────────────────────────────────────

window.sendMessage = sendMessage;
window.stopGeneration = stopGeneration;
window.handleKeyDown = handleKeyDown;
window.autoResizeTextarea = autoResizeTextarea;
window.handleFileSelect = handleFileSelect;
window.handlePaste = handlePaste;
window.removeAttachment = removeAttachment;
window.exportChat = exportChat;
window.updateTokenEstimate = updateTokenEstimate;
window.handleUndo = handleUndo;
window.handleRetry = handleRetry;
window.openRenameModal = openRenameModal;
window.initModelSelector = initModelSelector;

// ── Model Status Indicator (LED) ────────────────────────────────

const LED_COLORS = {
    local:  { bg: '#22c55e', text: 'LOCAL' },     // 🟢 Green
    remote: { bg: '#eab308', text: 'REMOTE' },     // 🟡 Yellow
    unknown: { bg: '#6b7280', text: '—' },         // ⚫ Gray
    error:  { bg: '#ef4444', text: 'ERROR' },      // 🔴 Red
    routing: { bg: '#3b82f6', text: 'ROUTING' },   // 🔵 Blue
};

/**
 * Update the model status LED indicator in the top bar.
 * @param {'local'|'remote'|'unknown'|'error'|'routing'} tier
 * @param {string} [reason] — hover text
 */
let _lastStableTier = null;
let _pendingTier = null;
let _pendingReason = null;
let _debounceTimer = null;

/**
 * Debounce tier changes: only apply status if it stays stable for 2 poll cycles.
 * The poll interval is 30 seconds, so a change takes ~60s to commit.
 */
export function updateModelStatus(tier, reason) {
    const dot = document.getElementById('modelStatusDot');
    const text = document.getElementById('modelStatusText');
    if (!dot || !text) return;

    // First update or same as current: apply immediately
    if (_lastStableTier === null || tier === _lastStableTier) {
        _lastStableTier = tier;
        _pendingTier = null;
        _pendingReason = null;
        if (_debounceTimer) { clearTimeout(_debounceTimer); _debounceTimer = null; }
        _applyModelStatus(dot, text, tier, reason);
        return;
    }

    // Pending change debounce: if same as pending, commit; else reset pending
    if (tier === _pendingTier) {
        // Stable for at least one extra poll — commit
        _lastStableTier = tier;
        _pendingTier = null;
        _pendingReason = null;
        if (_debounceTimer) { clearTimeout(_debounceTimer); _debounceTimer = null; }
        _applyModelStatus(dot, text, tier, reason);
    } else {
        // New tier appeared — start/restart debounce window
        _pendingTier = tier;
        _pendingReason = reason;
        if (_debounceTimer) clearTimeout(_debounceTimer);
        _debounceTimer = setTimeout(() => {
            _lastStableTier = _pendingTier;
            _applyModelStatus(dot, text, _pendingTier, _pendingReason);
            _pendingTier = null;
            _pendingReason = null;
            _debounceTimer = null;
        }, 10000);  // 10s fallback timeout
    }
}

function _applyModelStatus(dot, text, tier, reason) {
    const color = LED_COLORS[tier] || LED_COLORS.unknown;
    dot.style.backgroundColor = color.bg;
    dot.style.boxShadow = tier === 'routing'
        ? `0 0 6px ${color.bg}`
        : 'none';
    text.textContent = color.text;
    if (reason) {
        dot.title = reason;
        text.title = reason;
    }
}

/**
 * Poll routing status from backend and update LED.
 */
async function pollRoutingStatus() {
    try {
        if (typeof window.getRoutingStatus !== 'function') return;
        const status = await window.getRoutingStatus();
        if (status && status.tier) {
            const active = status.active_profile;
            const name = active ? active.name || active.model || '' : '';
            const reason = name ? `${name} (${status.tier})` : '';
            updateModelStatus(status.tier, reason);
        }
    } catch (e) {
        // Silently fail — LED stays as-is
    }
}

// ── Re-route button (appears after assistant response) ──────────

let _lastRoutingDecision = null;

/**
 * Store the routing decision from the SSE stream so we can offer re-route.
 */
export function setLastRoutingDecision(decision) {
    _lastRoutingDecision = decision;
    // If we have a routing decision, show the indicator briefly as "routing"
    if (decision && decision.target_tier) {
        updateModelStatus('routing', `Routing: ${decision.reason || ''}`);
        // After 2s, poll actual status
        setTimeout(pollRoutingStatus, 2000);
    }
}

/**
 * Add a re-route button to the last assistant message.
 */
function addRerouteButton() {
    if (!_lastRoutingDecision) return;
    const msgDivs = document.querySelectorAll('.assistant-message, .assistant-message-group');
    if (!msgDivs.length) return;
    const last = msgDivs[msgDivs.length - 1];
    if (!last || last.querySelector('.reroute-btn')) return;

    const btn = document.createElement('button');
    btn.className = 'reroute-btn text-[10px] text-on-surface-variant/40 hover:text-primary transition-colors ml-2';
    btn.title = '换模型重发';
    btn.innerHTML = '<span class="material-symbols-outlined text-[14px]">swap_horiz</span>';

    const targetTier = _lastRoutingDecision.target_tier === 'local' ? 'remote' : 'local';
    const targetLabel = targetTier === 'local' ? '本地模型' : 'DeepSeek';

    btn.addEventListener('click', async () => {
        try {
            // Record correction for learning
            if (typeof window.correctRouting === 'function') {
                await window.correctRouting(
                    _lastRoutingDecision.target_tier || 'unknown',
                    targetTier,
                    _lastRoutingDecision._message || '',
                );
            }
            showToast(`🔄 切换至${targetLabel}重发...`);
            // Trigger retry — the next message will be routed differently
            if (typeof handleRetry === 'function') {
                handleRetry();
            }
        } catch (e) {
            showToast('❌ 重发失败: ' + e.message);
        }
    });

    // Find the button row next to agent name and insert
    const nameRow = last.querySelector('.flex.items-baseline.gap-2');
    if (nameRow) {
        nameRow.appendChild(btn);
    }
}

window.updateModelStatus = updateModelStatus;
window.pollRoutingStatus = pollRoutingStatus;
window.setLastRoutingDecision = setLastRoutingDecision;

// ── Model Selector ──────────────────────────────────────────────

async function loadModelList() {
    const modelDisplay = document.getElementById('modelDisplay');
    const modelList = document.getElementById('modelList');
    if (!modelList || !modelDisplay) return;

    try {
        const data = await window.getModelProfiles();
        const profiles = data.profiles || [];
        modelList.innerHTML = '';

        // Find active
        const active = profiles.find(p => p.active);
        if (active) {
            modelDisplay.textContent = active.model;
            modelDisplay.title = `${active.name} (${active.type === 'local' ? '🏠' : '☁️'} ${active.cost_tier})`;
        }

        for (const p of profiles) {
            const item = document.createElement('div');
            const typeIcon = p.type === 'local' ? '🖥' : '☁️';
            const costIcon = p.cost_tier === 'paid' ? '💰' : '🆓';
            item.className = `flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer text-[10px] transition-colors ${
                p.active ? 'bg-primary/15 text-primary font-bold' : 'text-on-surface-variant/80 hover:bg-surface-container-hover'
            }`;
            item.innerHTML = `<span>${typeIcon} ${costIcon}</span><span>${p.model}</span>`;
            item.addEventListener('click', async () => {
                if (p.active) return;
                try {
                    const result = await window.switchModel(p.id);
                    if (result.success) {
                        modelDisplay.textContent = result.profile.model;
                        modelDisplay.title = `${result.profile.name} (${result.profile.type === 'local' ? '🏠' : '☁️'} ${result.profile.cost_tier})`;
                        document.getElementById('modelSelector')?.classList.add('hidden');
                        showToast(`✅ Switched to ${result.profile.name}`, 2000);
                        await loadModelList(); // Refresh active states
                    }
                } catch (e) {
                    showToast('❌ Switch failed: ' + e.message);
                }
            });
            modelList.appendChild(item);
        }
    } catch (e) {
        modelDisplay.textContent = '--';
        modelDisplay.title = '';
    }
}

function initModelSelector() {
    const modelDisplay = document.getElementById('modelDisplay');
    const modelSelector = document.getElementById('modelSelector');
    const discoverBtn = document.getElementById('discoverModelsBtn');
    if (!modelDisplay || !modelSelector) return;

    // Toggle dropdown on click
    modelDisplay.addEventListener('click', (e) => {
        e.stopPropagation();
        const isHidden = modelSelector.classList.contains('hidden');
        if (isHidden) {
            loadModelList();
        }
        modelSelector.classList.toggle('hidden');
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
        if (!modelSelector.contains(e.target) && e.target !== modelDisplay) {
            modelSelector.classList.add('hidden');
        }
    });

    // Discover button
    if (discoverBtn) {
        discoverBtn.addEventListener('click', async () => {
            discoverBtn.disabled = true;
            discoverBtn.innerHTML = '<span class="material-symbols-outlined text-[11px]">sync</span>Scanning...';
            try {
                const result = await window.discoverModels();
                showToast(`🔍 Found ${result.discovered} new model(s)`, 3000);
                await loadModelList();
            } catch (e) {
                showToast('❌ Discovery failed: ' + e.message);
            } finally {
                discoverBtn.disabled = false;
                discoverBtn.innerHTML = '<span class="material-symbols-outlined text-[11px]">search</span>Discover local models';
            }
        });
    }

    // Load initial model list
    loadModelList();
}

// ── Drag & Drop Upload ──────────────────────────────────────────

function _initDragDrop() {
    const dropZone = document.getElementById('tabChat');
    const inputBar = document.getElementById('inputBar');
    if (!dropZone) return;

    let dragCounter = 0;

    const showOverlay = () => {
        let overlay = document.getElementById('dragOverlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'dragOverlay';
            overlay.innerHTML = `
                <div class="fixed inset-0 z-[500] flex items-center justify-center pointer-events-none">
                    <div class="bg-surface-container/95 backdrop-blur-xl border-2 border-dashed border-primary/60 rounded-3xl p-12 flex flex-col items-center gap-4 shadow-2xl">
                        <span class="material-symbols-outlined text-5xl text-primary/60">cloud_upload</span>
                        <span class="text-lg font-bold text-on-surface">释放以上传文件</span>
                        <span class="text-xs text-on-surface-variant/60">支持文档、代码、图片（单文件 ≤50MB）</span>
                    </div>
                </div>
            `;
            document.body.appendChild(overlay);
        }
        overlay.classList.remove('hidden');
    };

    const hideOverlay = () => {
        const overlay = document.getElementById('dragOverlay');
        if (overlay) overlay.classList.add('hidden');
    };

    dropZone.addEventListener('dragenter', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounter++;
        if (dragCounter === 1) showOverlay();
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounter--;
        if (dragCounter <= 0) {
            dragCounter = 0;
            hideOverlay();
        }
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounter = 0;
        hideOverlay();
        const files = e.dataTransfer?.files;
        if (files && files.length > 0) {
            _addAttachments(files);
        }
    });
}

// Initialize on DOMContentLoaded if document ready, else defer
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _initDragDrop);
} else {
    _initDragDrop();
}
