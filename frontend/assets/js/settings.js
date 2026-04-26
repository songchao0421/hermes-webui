/**
 * Hermes WebUI - Settings Module
 * Settings panel: persona form, avatar uploads, theme/color picker, config.
 * Window-exported for HTML onclick compatibility.
 */
const App = globalThis.App = globalThis.App || {};

import { apiFetch, apiUrl } from './api.js';
import { state } from './state.js';
import { showToast, escapeHtml } from './utils.js';
import { applyThemeColor } from './theme.js';
import { savePersonaToServer, loadPersona, updateUIFromPersona } from './persona.js';

// ── Settings Save ───────────────────────────────────────────────

export async function saveSettings() {
    const name = document.getElementById('settingsName')?.value?.trim();
    const subtitle = document.getElementById('settingsSubtitle')?.value?.trim();
    const userName = document.getElementById('userName')?.value?.trim();

    const updates = {};
    if (name !== undefined) updates.agent_name = name || 'My Agent';
    if (subtitle !== undefined) updates.agent_subtitle = subtitle;
    if (userName !== undefined) updates.user_display_name = userName;

    const selectedSwatch = document.querySelector('#settingsThemePicker .theme-swatch.selected');
    let preset = selectedSwatch?.dataset?.preset || 'amber';
    let accent = state.persona?.theme?.accent || '#e8a849';

    if (preset === 'custom') {
        const customColor = document.getElementById('settingsCustomColor');
        if (customColor) accent = customColor.value;
    } else {
        const presetColors = {
            amber: '#e8a849',
            purple: '#d0bcff',
            green: '#81c784',
            cyan: '#00daf3',
            rose: '#f48fb1'
        };
        accent = presetColors[preset] || '#e8a849';
    }

    updates.theme = { accent, preset };

    const ok = await savePersonaToServer(updates);
    if (ok) {
        applyThemeColor(accent);
        showToast('Settings saved!');
    } else {
        showToast('Save failed');
    }
}

// ── Avatar Upload ───────────────────────────────────────────────

let pendingAgentAvatarFile = null;
let pendingUserAvatarFile = null;

export function handleSettingsAvatar(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    pendingAgentAvatarFile = file;
    const reader = new FileReader();
    reader.onload = (e) => {
        const zone = document.getElementById('settingsAvatarZone');
        if (zone) zone.style.backgroundImage = 'url(' + e.target.result + ')';
    };
    reader.readAsDataURL(file);
}

export function handleUserAvatar(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    pendingUserAvatarFile = file;
    const reader = new FileReader();
    reader.onload = (e) => {
        const zone = document.getElementById('userAvatarZone');
        if (zone) zone.style.backgroundImage = 'url(' + e.target.result + ')';
    };
    reader.readAsDataURL(file);
}

export function uploadAgentAvatar(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('avatar', file);
    apiFetch(apiUrl('/api/persona/avatar'), { method: 'POST', body: formData })
        .then(r => r.json())
        .then(data => {
            if (data.avatar) {
                state.persona.avatar = data.avatar + '?t=' + Date.now();
                updateUIFromPersona();
                showToast('Agent avatar updated!');
            }
        })
        .catch(e => showToast('Upload failed: ' + e.message));
}

export function uploadUserAvatar(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('avatar', file);
    apiFetch(apiUrl('/api/persona/user-avatar'), { method: 'POST', body: formData })
        .then(r => r.json())
        .then(data => {
            if (data.avatar) {
                state.persona.user_avatar = data.avatar + '?t=' + Date.now();
                updateUIFromPersona();
                showToast('User avatar updated!');
            }
        })
        .catch(e => showToast('Upload failed: ' + e.message));
}

// ── Theme Swatch Selection ──────────────────────────────────────

let themePresets = {};

export function selectTheme(preset) {
    // Accept both string preset name and DOM element
    if (preset?.dataset?.preset) {
        preset = preset.dataset.preset;
    }
    document.querySelectorAll('#settingsThemePicker .theme-swatch').forEach(s => {
        s.classList.toggle('selected', s.dataset.preset === preset);
    });
    if (preset === 'custom') {
        const el = document.getElementById('settingsCustomColor');
        if (el) el.classList.remove('hidden');
    } else {
        const el = document.getElementById('settingsCustomColor');
        if (el) el.classList.add('hidden');
        const presetColors = {
            amber: '#e8a849',
            purple: '#d0bcff',
            green: '#81c784',
            cyan: '#00daf3',
            rose: '#f48fb1'
        };
        const color = presetColors[preset] || '#e8a849';
        applyThemeColor(color);
    }
}

// ── Routing Config Save ─────────────────────────────────────────

export async function saveRoutingConfig() {
    const configData = {
        routing: {
            mode: document.getElementById('routingMode')?.value || 'auto',
            rules: {
                has_attachment: document.getElementById('routingAttach')?.value || 'api',
                length_threshold: parseInt(document.getElementById('routingLength')?.value) || 500,
                code_threshold: document.getElementById('routingCodeToggle')?.checked || false,
            },
        },
    };
    try {
        const resp = await apiFetch(apiUrl('/api/config'), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(configData),
        });
        if (resp.ok) {
            state.routingConfig = configData;
            showToast('Routing config saved!');
        } else {
            showToast('Save failed');
        }
    } catch (e) { showToast('Save error: ' + e.message); }
}

// ── API Key Management ─────────────────────────────────────────

export function showApiKeys() {
    // Load current keys from backend
    apiFetch(apiUrl('/api/config'))
        .then(r => r.json())
        .then(data => {
            const keys = data.api_keys || {};
            const container = document.getElementById('apiKeyList');
            if (!container) return;
            container.innerHTML = '';
            const providers = [
                { key: 'deepseek', label: 'DeepSeek' },
                { key: 'openai', label: 'OpenAI' },
                { key: 'openrouter', label: 'OpenRouter' },
            ];
            providers.forEach(p => {
                const row = document.createElement('div');
                row.className = 'flex items-center gap-3 py-2';
                row.innerHTML = `
                    <span class="text-sm text-on-surface-variant w-24">${p.label}</span>
                    <input type="password" id="apikey_${p.key}" value="${escapeHtml(keys[p.key] || '')}" class="flex-1 px-3 py-2 bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-sm text-on-surface outline-none focus:border-primary" placeholder="sk-...">
                    <button onclick="toggleApiKeyVisibility('${p.key}')" class="text-on-surface-variant/50 hover:text-on-surface text-sm material-symbols-outlined">visibility</button>
                `;
                container.appendChild(row);
            });
        })
        .catch(() => {});
    const modal = document.getElementById('apiKeyModal');
    if (modal) modal.classList.remove('hidden');
}

export function toggleApiKeyVisibility(key) {
    const input = document.getElementById('apikey_' + key);
    if (input) input.type = input.type === 'password' ? 'text' : 'password';
}

export async function saveApiKeys() {
    const providers = ['deepseek', 'openai', 'openrouter'];
    const keys = {};
    providers.forEach(p => {
        const input = document.getElementById('apikey_' + p);
        if (input?.value?.trim()) keys[p] = input.value.trim();
    });
    try {
        const resp = await apiFetch(apiUrl('/api/config'), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_keys: keys }),
        });
        if (resp.ok) {
            showToast('API keys saved!');
            const modal = document.getElementById('apiKeyModal');
            if (modal) modal.classList.add('hidden');
        } else {
            showToast('Save failed');
        }
    } catch (e) { showToast('Save error: ' + e.message); }
}

export function hideApiKeys() {
    const modal = document.getElementById('apiKeyModal');
    if (modal) modal.classList.add('hidden');
}

// ── Support Modal ───────────────────────────────────────────────

export function hideSupportModal() {
    const modal = document.getElementById('supportModal');
    if (modal) modal.classList.remove('active');
}

export function closeSupportModal() {
    return hideSupportModal();
}

// ── Window Exports ──────────────────────────────────────────────

window.saveSettings = saveSettings;
App.saveSettings = saveSettings;
window.uploadAgentAvatar = uploadAgentAvatar;
App.uploadAgentAvatar = uploadAgentAvatar;
window.uploadUserAvatar = uploadUserAvatar;
App.uploadUserAvatar = uploadUserAvatar;
window.selectTheme = selectTheme;
App.selectTheme = selectTheme;
window.saveRoutingConfig = saveRoutingConfig;
App.saveRoutingConfig = saveRoutingConfig;
window.showApiKeys = showApiKeys;
App.showApiKeys = showApiKeys;
window.toggleApiKeyVisibility = toggleApiKeyVisibility;
App.toggleApiKeyVisibility = toggleApiKeyVisibility;
window.saveApiKeys = saveApiKeys;
App.saveApiKeys = saveApiKeys;
window.hideApiKeys = hideApiKeys;
App.hideApiKeys = hideApiKeys;
window.closeSupportModal = closeSupportModal;
App.closeSupportModal = closeSupportModal;
window.hideSupportModal = hideSupportModal;
App.hideSupportModal = hideSupportModal;
window.handleSettingsAvatar = handleSettingsAvatar;
App.handleSettingsAvatar = handleSettingsAvatar;
window.handleUserAvatar = handleUserAvatar;
App.handleUserAvatar = handleUserAvatar;

// ── HTML onclick aliases ─────────────────────────────────────────
window.selectSettingsTheme = selectTheme;
App.selectSettingsTheme = selectTheme;

// ── Update / Self-Upgrade ────────────────────────────────────

/**
 * Refresh version display when Support modal opens.
 * Override existing showSupportModal to add auto-check.
 */
export function showSupportModal() {
    const modal = document.getElementById('supportModal');
    if (modal) modal.classList.add('active');
    refreshVersion();
}
window.showSupportModal = showSupportModal;
App.showSupportModal = showSupportModal;

export async function refreshVersion() {
    try {
        const data = await checkUpdate();
        const el = document.getElementById('localVersion');
        if (el) {
            el.textContent = data.local_commit
                ? data.local_commit + (data.has_update ? ' (update available)' : ' (latest)')
                : 'unknown';
        }
    } catch {
        const el = document.getElementById('localVersion');
        if (el) el.textContent = 'unavailable';
    }
}

window.handleCheckUpdate = handleCheckUpdate;
App.handleCheckUpdate = handleCheckUpdate;
async function handleCheckUpdate() {
    const btn = document.getElementById('checkUpdateBtn');
    const applyBtn = document.getElementById('applyUpdateBtn');
    const status = document.getElementById('updateStatus');
    const statusMsg = document.getElementById('updateStatusMsg');
    const statusIcon = document.getElementById('updateStatusIcon');

    // Loading state
    btn.disabled = true;
    btn.innerHTML = '<span class="material-symbols-outlined text-sm animate-spin">sync</span> Checking...';
    status.classList.remove('hidden');
    statusMsg.textContent = 'Checking for updates...';
    statusIcon.textContent = 'sync';
    statusIcon.className = 'material-symbols-outlined text-sm text-on-surface-variant/60 animate-spin';

    try {
        const data = await checkUpdate();

        if (data.error) {
            statusIcon.textContent = 'error';
            statusIcon.className = 'material-symbols-outlined text-sm text-error';
            statusMsg.textContent = 'Error: ' + data.error;
            applyBtn.disabled = true;
        } else if (data.has_update) {
            statusIcon.textContent = 'new_releases';
            statusIcon.className = 'material-symbols-outlined text-sm text-[#f0c040]';
            statusMsg.innerHTML = `Update available: <strong>${data.remote_commit}</strong> — ${data.remote_message}`;
            applyBtn.disabled = false;
        } else {
            statusIcon.textContent = 'check_circle';
            statusIcon.className = 'material-symbols-outlined text-sm text-[#6abf69]';
            statusMsg.textContent = data.local_commit
                ? `Latest (${data.local_commit})`
                : 'Up to date';
            applyBtn.disabled = true;
        }
    } catch (e) {
        statusIcon.textContent = 'error';
        statusIcon.className = 'material-symbols-outlined text-sm text-error';
        statusMsg.textContent = 'Network error: ' + e.message;
        applyBtn.disabled = true;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="material-symbols-outlined text-sm">sync</span> Check for Updates';
    }
}

window.handleApplyUpdate = handleApplyUpdate;
App.handleApplyUpdate = handleApplyUpdate;
async function handleApplyUpdate() {
    const checkBtn = document.getElementById('checkUpdateBtn');
    const applyBtn = document.getElementById('applyUpdateBtn');
    const status = document.getElementById('updateStatus');
    const statusMsg = document.getElementById('updateStatusMsg');
    const statusIcon = document.getElementById('updateStatusIcon');
    const logEl = document.getElementById('updateLog');
    const countdown = document.getElementById('restartCountdown');

    // Disable both buttons
    checkBtn.disabled = true;
    applyBtn.disabled = true;
    applyBtn.innerHTML = '<span class="material-symbols-outlined text-sm animate-spin">sync</span> Updating...';

    // Show log area
    logEl.classList.remove('hidden');
    logEl.innerHTML = '';
    statusIcon.textContent = 'downloading';
    statusIcon.className = 'material-symbols-outlined text-sm text-[#f0c040] animate-spin';
    statusMsg.textContent = 'Updating...';

    try {
        const response = await applyUpdate();
        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: response.statusText }));
            appendLog(logEl, `[ERROR] ${err.detail || 'Request failed'}`);
            statusIcon.textContent = 'error';
            statusIcon.className = 'material-symbols-outlined text-sm text-error';
            statusMsg.textContent = 'Update failed';
            enableButtons(checkBtn, applyBtn);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                try {
                    const data = JSON.parse(line.slice(6));

                    if (data.log) {
                        appendLog(logEl, data.log);
                    }

                    if (data.error) {
                        appendLog(logEl, `[ERROR] ${data.error}`);
                        statusIcon.textContent = 'error';
                        statusIcon.className = 'material-symbols-outlined text-sm text-error';
                        statusMsg.textContent = 'Update failed';
                        enableButtons(checkBtn, applyBtn);
                        return;
                    }

                    if (data.restart) {
                        statusIcon.textContent = 'restart_alt';
                        statusIcon.className = 'material-symbols-outlined text-sm text-primary';
                        statusMsg.textContent = 'Restarting...';
                        countdown.classList.remove('hidden');
                        // Page will automatically refresh after restart
                        // Poll until server is back up
                        pollServer(data.host || 'localhost', data.port || 8080);
                        return;
                    }
                } catch {
                    // skip unparseable lines
                }
            }
        }
    } catch (e) {
        appendLog(logEl, `[ERROR] ${e.message}`);
        statusIcon.textContent = 'error';
        statusIcon.className = 'material-symbols-outlined text-sm text-error';
        statusMsg.textContent = 'Connection lost during update';
        enableButtons(checkBtn, applyBtn);
    }
}

function appendLog(el, text) {
    const div = document.createElement('div');
    div.textContent = text;
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
}

function enableButtons(checkBtn, applyBtn) {
    checkBtn.disabled = false;
    applyBtn.disabled = true;
    applyBtn.innerHTML = '<span class="material-symbols-outlined text-sm">system_update</span> Update & Restart';
}

function pollServer(host, port, attempt = 0) {
    const maxAttempts = 30;
    const wait = attempt === 0 ? 2000 : 1000;
    setTimeout(async () => {
        try {
            const resp = await fetch(`http://${host}:${port}/api/update/check`);
            if (resp.ok) {
                // Server is back — reload the page
                window.location.reload();
                return;
            }
        } catch {
            // server not up yet
        }
        if (attempt < maxAttempts) {
            pollServer(host, port, attempt + 1);
        } else {
            document.getElementById('restartCountdown').textContent =
                'Server took too long to restart. Please refresh the page manually.';
        }
    }, wait);
}