/**
 * Hermes WebUI - Settings Module
 * Settings panel: persona form, avatar uploads, theme/color picker, config.
 * Window-exported for HTML onclick compatibility.
 */

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
            amber: '#e8a849', green: '#a6e3a1', blue: '#89b4fa', pink: '#f38ba8',
            purple: '#cba6f7', teal: '#94e2d5', peach: '#fab387', yellow: '#f9e2af'
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
    document.querySelectorAll('#settingsThemePicker .theme-swatch').forEach(s => {
        s.classList.toggle('selected', s.dataset.preset === preset);
    });
    if (preset === 'custom') {
        document.getElementById('settingsCustomColor').classList.remove('hidden');
    } else {
        document.getElementById('settingsCustomColor').classList.add('hidden');
        const presetColors = {
            amber: '#e8a849', green: '#a6e3a1', blue: '#89b4fa', pink: '#f38ba8',
            purple: '#cba6f7', teal: '#94e2d5', peach: '#fab387', yellow: '#f9e2af'
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

export function showSupportModal() {
    const modal = document.getElementById('supportModal');
    if (modal) modal.classList.remove('hidden');
}

export function hideSupportModal() {
    const modal = document.getElementById('supportModal');
    if (modal) modal.classList.add('hidden');
}

export function closeSupportModal() {
    return hideSupportModal();
}

// ── Window Exports ──────────────────────────────────────────────

window.saveSettings = saveSettings;
window.uploadAgentAvatar = uploadAgentAvatar;
window.uploadUserAvatar = uploadUserAvatar;
window.selectTheme = selectTheme;
window.saveRoutingConfig = saveRoutingConfig;
window.showApiKeys = showApiKeys;
window.toggleApiKeyVisibility = toggleApiKeyVisibility;
window.saveApiKeys = saveApiKeys;
window.hideApiKeys = hideApiKeys;
window.showSupportModal = showSupportModal;
window.hideSupportModal = hideSupportModal;
window.closeSupportModal = closeSupportModal;
window.handleSettingsAvatar = handleSettingsAvatar;
window.handleUserAvatar = handleUserAvatar;

// ── HTML onclick aliases ─────────────────────────────────────────
window.selectSettingsTheme = selectTheme;
