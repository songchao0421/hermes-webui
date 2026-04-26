/**
 * Hermes WebUI — Tool Call Panel (V2.0)
 * Visualizes Agent tool calls with expandable arguments, status updates,
 * timing, and collapsible grouping.
 *
 * Imported dynamically by chat.js via tool_panel.js API.
 */
globalThis.App = globalThis.App || {};
const App = globalThis.App;

// ── State ────────────────────────────────────────────────────────

const toolMap = new Map(); // toolId -> { wrapperEl, name, startTime }

// ── Core API ─────────────────────────────────────────────────────

/**
 * Attach a tool call panel to an assistant message element.
 * Returns an object with { showStart, showComplete, showError, reset } methods.
 *
 * @param {HTMLElement} panelEl - The .tool-call-panel container in the message
 */
export function createToolPanel(panelEl) {
    if (!panelEl) return null;

    return {
        showStart(data) { _renderToolCallStart(panelEl, data); },
        showComplete(data) { _renderToolCallComplete(panelEl, data); },
        showError(data) { _renderToolCallError(panelEl, data); },
        reset() { panelEl.innerHTML = ''; toolMap.clear(); },
    };
}

// ── Rendering ────────────────────────────────────────────────────

function _renderToolCallStart(panelEl, data) {
    const wrapper = document.createElement('div');
    wrapper.className = 'tool-call-item';
    wrapper.dataset.toolId = data.id;
    wrapper.dataset.toolName = data.name || 'unknown';
    wrapper.style.marginTop = (panelEl.children.length === 0 ? '0' : '8px');

    wrapper.innerHTML = `
        <div class="tool-call-header flex items-center gap-2 px-3 py-2 rounded-t-lg bg-surface-container-lowest border border-surface-container-high cursor-pointer select-none hover:bg-surface-container-lowest/80 transition-colors" title="点击显示/隐藏参数">
            <span class="material-symbols-outlined text-sm" style="color: var(--theme-primary);">call_made</span>
            <span class="tool-call-name text-xs font-bold text-on-surface truncate max-w-[180px]">${escapeHtml(data.name || 'tool')}</span>
            <span class="tool-call-duration text-[10px] text-on-surface-variant/40 ml-1">⏱ --s</span>
            <span class="tool-call-status text-[10px] ml-auto shrink-0" style="color: var(--theme-primary);">
                <span class="loading-dots">运行中</span>
            </span>
            <span class="material-symbols-outlined text-sm text-on-surface-variant/30 tool-call-chevron">expand_more</span>
        </div>
        <div class="tool-call-args hidden px-3 py-2 text-[11px] bg-surface-dim rounded-b-lg border-x border-b border-surface-container-high">
            <pre class="text-on-surface-variant/70 overflow-auto max-h-40 whitespace-pre-wrap break-all font-mono">${escapeHtml(_formatArgs(data.args || {}))}</pre>
        </div>
    `;

    // Toggle args on header click
    wrapper.querySelector('.tool-call-header').addEventListener('click', () => {
        const argsEl = wrapper.querySelector('.tool-call-args');
        const chevron = wrapper.querySelector('.tool-call-chevron');
        const isHidden = argsEl.classList.toggle('hidden');
        if (chevron) chevron.style.transform = isHidden ? 'rotate(0deg)' : 'rotate(180deg)';
    });

    panelEl.appendChild(wrapper);
    toolMap.set(data.id, { wrapperEl: wrapper, name: data.name, startTime: Date.now() });

    // Start duration timer
    _startDurationTimer(data.id, wrapper);
}

function _startDurationTimer(toolId, wrapper) {
    const durEl = wrapper.querySelector('.tool-call-duration');
    if (!durEl) return;
    let elapsed = 0;
    const interval = setInterval(() => {
        const entry = toolMap.get(toolId);
        if (!entry) { clearInterval(interval); return; }
        elapsed = Math.floor((Date.now() - entry.startTime) / 1000);
        durEl.textContent = `⏱ ${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}s`;
    }, 1000);
    // Store reference for cleanup
    const entry = toolMap.get(toolId);
    if (entry) entry._timer = interval;
}

function _renderToolCallComplete(panelEl, data) {
    const wrapper = _findWrapper(panelEl, data.id);
    if (!wrapper) return;

    const statusEl = wrapper.querySelector('.tool-call-status');
    const durEl = wrapper.querySelector('.tool-call-duration');
    const entry = toolMap.get(data.id);

    // Stop timer
    if (entry && entry._timer) {
        clearInterval(entry._timer);
        delete entry._timer;
    }

    // Update duration with final time
    if (entry && durEl) {
        const elapsed = Math.floor((Date.now() - entry.startTime) / 1000);
        durEl.textContent = `${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}s`;
    }

    if (statusEl) {
        const resultText = data.result
            ? (typeof data.result === 'string' ? data.result.slice(0, 100) : JSON.stringify(data.result).slice(0, 100))
            : '完成';
        statusEl.className = 'tool-call-status text-[10px] text-green-500/80 ml-auto shrink-0';
        statusEl.textContent = '✅ ' + escapeHtml(resultText);
    }
}

function _renderToolCallError(panelEl, data) {
    const wrapper = _findWrapper(panelEl, data.id);
    if (!wrapper) return;

    const statusEl = wrapper.querySelector('.tool-call-status');
    const entry = toolMap.get(data.id);
    if (entry && entry._timer) {
        clearInterval(entry._timer);
        delete entry._timer;
    }
    if (statusEl) {
        statusEl.className = 'tool-call-status text-[10px] text-red-400/90 ml-auto shrink-0';
        statusEl.textContent = '❌ ' + escapeHtml(data.error || data.message || '失败');
    }
}

// ── Helpers ──────────────────────────────────────────────────────

function _findWrapper(panelEl, toolId) {
    if (!panelEl || !toolId) return null;
    return panelEl.querySelector(`[data-tool-id="${toolId}"]`);
}

function _formatArgs(args) {
    if (!args) return '{}';
    try {
        const str = JSON.stringify(args, null, 2);
        // Truncate excessively long args
        return str.length > 2000 ? str.slice(0, 2000) + '\n... (truncated)' : str;
    } catch {
        return String(args);
    }
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ── Window export ────────────────────────────────────────────────

window.createToolPanel = createToolPanel;
App.createToolPanel = createToolPanel;