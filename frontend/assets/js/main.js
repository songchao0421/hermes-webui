/**
 * Hermes WebUI - Main Entry Point
 * Imports all modules and handles DOMContentLoaded initialization.
 * Creates the `App` namespace singleton for organized module access.
 * Each module exports its functions to window AND App for compatibility.
 */

// ── App namespace singleton ──────────────────────────────────────
window.App = {};

// ── Signal that JS has loaded (guards against white-screen fallback) ──
window.__hermesLoaded = true;

// ── Module imports ───────────────────────────────────────────────
// Each module handles its own window.fn = fn assignments internally.

import '/assets/js/api.js';
import '/assets/js/state.js';
import '/assets/js/persona.js';
import '/assets/js/settings.js';
import '/assets/js/skills.js';
import '/assets/js/memories.js';
import '/assets/js/sessions.js';
import '/assets/js/chat.js';
import '/assets/js/voice.js';
import '/assets/js/extract.js';
import '/assets/js/utils.js';
import '/assets/js/theme.js';
import '/assets/js/tool_panel.js';

// ── DOM Ready — ES modules are deferred, DOM is already parsed ──
const App = window.App;
// Load persona and update UI
if (typeof App.loadPersona === 'function') {
    App.loadPersona();
}

// Load session list
if (typeof App.loadSessionList === 'function') {
    App.loadSessionList();
}

// Initialize memory keyboard shortcuts
if (typeof App.setupKeyboardShortcuts === 'function') {
    App.setupKeyboardShortcuts();
}

// Initialize notifications
if (typeof App.initNotifications === 'function') {
    App.initNotifications();
}

// Initialize model selector
if (typeof App.initModelSelector === 'function') {
    App.initModelSelector();
}

// Poll initial routing status for LED indicator
if (typeof App.pollRoutingStatus === 'function') {
    setTimeout(App.pollRoutingStatus, 1000);
    setInterval(App.pollRoutingStatus, 30000);
}

// ── Onboarding / initialization guide ──────────────────────────
(async function checkOnboarding() {
    try {
        const resp = await fetch('/api/onboarding/status');
        const status = await resp.json();
        if (status.completed) return;

        const st = status; // use same response

        // Create overlay
        const overlay = document.createElement('div');
        overlay.id = 'onboarding-overlay';
        overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:#131316;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:2rem;';

        const envText = [];
        if (st.ollama_running) envText.push('✅ Ollama 已运行 (' + (st.ollama_models[0] || '') + ')');
        else envText.push('❌ Ollama 未运行 — 请先启动 Ollama');
        if (st.has_deepseek_key) envText.push('✅ DeepSeek API Key 已配置');
        else envText.push('⚠ 未配置远程 API Key');
        if (st.has_any_profile) envText.push('✅ 已有模型配置');
        else envText.push('⚠ 未检测到模型配置');

        overlay.innerHTML = [
            '<div style="max-width:440px;width:100%;">',
            '  <div style="text-align:center;margin-bottom:2rem;">',
            '    <div style="width:64px;height:64px;margin:0 auto 1rem;border-radius:16px;background:linear-gradient(135deg,#7c3aed,#6366f1);display:flex;align-items:center;justify-content:center;font-size:32px;color:#fff;">🐎</div>',
            '    <h1 style="font-size:1.5rem;font-weight:700;color:#fff;margin:0 0 .25rem;">Hermes WebUI</h1>',
            '    <p style="font-size:.875rem;color:rgba(255,255,255,.5);margin:0;">AI Agent 驾驶舱 · 初始化</p>',
            '  </div>',
            '  <div style="background:rgba(255,255,255,.04);border-radius:12px;padding:1.25rem;margin-bottom:1rem;">',
            '    <h3 style="font-size:.75rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:rgba(255,255,255,.3);margin:0 0 .75rem;">环境检测</h3>',
            '    <div style="display:flex;flex-direction:column;gap:.5rem;">',
            envText.map(t => '<div style="font-size:.8125rem;color:rgba(255,255,255,.7);">' + t + '</div>').join(''),
            '    </div>',
            '  </div>',
            '  <div style="background:rgba(255,255,255,.04);border-radius:12px;padding:1.25rem;margin-bottom:1rem;" id="onboarding-key-section">',
            '    <h3 style="font-size:.75rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:rgba(255,255,255,.3);margin:0 0 .75rem;">配置 API Key</h3>',
            '    <div style="display:flex;flex-direction:column;gap:.5rem;">',
            '      <select id="onboarding-provider" style="background:#1e1e24;border:1px solid rgba(255,255,255,.1);border-radius:8px;padding:.5rem .75rem;font-size:.8125rem;color:#fff;outline:none;">',
            '        <option value="deepseek">DeepSeek</option>',
            '        <option value="openai">OpenAI</option>',
            '      </select>',
            '      <input id="onboarding-key-input" type="password" placeholder="sk-..." style="background:#1e1e24;border:1px solid rgba(255,255,255,.1);border-radius:8px;padding:.5rem .75rem;font-size:.8125rem;color:#fff;outline:none;"/>',
            '      <button id="onboarding-save-key" style="background:linear-gradient(135deg,#7c3aed,#6366f1);border:none;border-radius:8px;padding:.5rem .75rem;font-size:.8125rem;font-weight:600;color:#fff;cursor:pointer;">保存 Key</button>',
            '      <div id="onboarding-key-msg" style="font-size:.75rem;color:rgba(255,255,255,.4);min-height:1.2em;"></div>',
            '    </div>',
            '  </div>',
            '  <div style="display:flex;gap:.5rem;">',
            '    <button id="onboarding-skip" style="flex:1;background:transparent;border:1px solid rgba(255,255,255,.15);border-radius:8px;padding:.5rem .75rem;font-size:.8125rem;color:rgba(255,255,255,.5);cursor:pointer;">跳过 →</button>',
            '    <button id="onboarding-recheck" style="flex:1;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:8px;padding:.5rem .75rem;font-size:.8125rem;color:#fff;cursor:pointer;">重新检测</button>',
            '  </div>',
            '</div>',
        ].join('');

        document.body.appendChild(overlay);

        // ── Event handlers ──
        document.getElementById('onboarding-save-key').addEventListener('click', async () => {
            const provider = document.getElementById('onboarding-provider').value;
            const key = document.getElementById('onboarding-key-input').value.trim();
            if (!key) {
                document.getElementById('onboarding-key-msg').textContent = '请输入 API Key';
                return;
            }
            try {
                const resp = await fetch('/api/onboarding/save-key', {
                    method: 'POST',
                    headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({provider, api_key: key}),
                });
                const data = await resp.json();
                if (data.status === 'ok') {
                    document.getElementById('onboarding-key-msg').textContent = '✅ Key 已保存';
                    document.getElementById('onboarding-key-input').value = '';
                } else {
                    document.getElementById('onboarding-key-msg').textContent = '❌ 保存失败: ' + (data.message || '');
                }
            } catch (e) {
                document.getElementById('onboarding-key-msg').textContent = '❌ 请求失败: ' + e.message;
            }
        });

        document.getElementById('onboarding-skip').addEventListener('click', async () => {
            try { await fetch('/api/onboarding/dismiss', {method:'POST'}); } catch(_) {}
            overlay.remove();
        });

        document.getElementById('onboarding-recheck').addEventListener('click', () => {
            location.reload();
        });
    } catch (e) {
        console.warn('Onboarding check failed (server may not be running):', e);
    }
})();
