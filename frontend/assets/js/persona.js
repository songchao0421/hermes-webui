/**
 * Hermes WebUI - Persona Module
 * Persona loading, saving, avatar helpers, and UI updates.
 * Window-exported for HTML onclick compatibility.
 */

import { apiFetch, apiUrl } from './api.js';
import { state } from './state.js';
import { escapeHtml, showToast } from './utils.js';
import { applyThemeColor } from './theme.js';

// ── Avatar Helpers ──────────────────────────────────────────────

export function makeAvatarImg(src, fallbackIcon, sizeClass) {
    const img = document.createElement('img');
    img.src = src;
    img.className = 'w-full h-full object-cover';
    img.onerror = function () {
        const span = document.createElement('span');
        span.className = `material-symbols-outlined text-primary ${sizeClass}`;
        span.textContent = fallbackIcon;
        this.parentNode.replaceChild(span, this);
    };
    return img;
}

export function makeUserAvatarImg(src, sizeClass) {
    const img = document.createElement('img');
    img.src = src;
    img.className = 'w-full h-full object-cover';
    img.onerror = function () {
        const span = document.createElement('span');
        span.className = `material-symbols-outlined ${sizeClass}`;
        span.style.color = 'var(--theme-primary)';
        span.textContent = 'person';
        this.parentNode.replaceChild(span, this);
    };
    return img;
}

// ── Persona Display Update ──────────────────────────────────────

export function updateUIFromPersona() {
    const p = state.persona;
    const name = p.agent_name || 'My Agent';
    const sub = p.agent_subtitle || '';

    document.getElementById('navAgentName').textContent = name;
    document.getElementById('navAgentSub').textContent = sub;
    document.title = `${name} | Hermes WebUI`;

    // Sidebar avatar (80px version)
    const navAvatar = document.getElementById('navAvatar');
    navAvatar.innerHTML = '';
    if (p.avatar) {
        navAvatar.appendChild(makeAvatarImg(apiUrl('/api/persona/avatar/') + p.avatar, 'smart_toy', 'text-3xl'));
    } else if (p.avatar_preset) {
        const iconMap = { robot: 'smart_toy', face: 'face', bolt: 'bolt' };
        const span = document.createElement('span');
        span.className = 'material-symbols-outlined text-primary text-3xl';
        span.textContent = iconMap[p.avatar_preset] || 'smart_toy';
        navAvatar.appendChild(span);
    } else {
        navAvatar.appendChild(makeAvatarImg(apiUrl('/api/persona/avatar/logo.png'), 'smart_toy', 'text-3xl'));
    }

    const emptyText = document.getElementById('emptyStateText');
    if (emptyText) emptyText.textContent = `Start talking to ${name}`;

    // Settings page fields
    const nameField = document.getElementById('settingsName');
    if (nameField) nameField.value = p.agent_name || '';
    const subField = document.getElementById('settingsSubtitle');
    if (subField) subField.value = p.agent_subtitle || '';

    // Settings avatar zone
    const settingsZone = document.getElementById('settingsAvatarZone');
    if (settingsZone) {
        settingsZone.innerHTML = '';
        if (p.avatar) {
            settingsZone.appendChild(makeAvatarImg(apiUrl('/api/persona/avatar/') + p.avatar, 'smart_toy', 'text-3xl'));
        } else if (p.avatar_preset) {
            const iconMap = { robot: 'smart_toy', face: 'face', bolt: 'bolt' };
            settingsZone.innerHTML = `<div class="w-full h-full bg-surface-container-lowest flex items-center justify-center"><span class="material-symbols-outlined text-primary text-3xl">${iconMap[p.avatar_preset] || 'smart_toy'}</span></div>`;
        } else {
            settingsZone.appendChild(makeAvatarImg(apiUrl('/api/persona/avatar/logo.png'), 'smart_toy', 'text-3xl'));
        }
        // Re-add upload overlay
        const overlay = document.createElement('div');
        overlay.className = 'upload-overlay';
        overlay.innerHTML = '<span class="material-symbols-outlined text-white">upload</span><span class="text-[10px] text-white font-bold mt-1">UPDATE</span>';
        settingsZone.appendChild(overlay);
    }

    // User avatar zone
    const userZone = document.getElementById('userAvatarZone');
    if (userZone) {
        userZone.innerHTML = '';
        if (p.user_avatar) {
            userZone.appendChild(makeUserAvatarImg(apiUrl('/api/persona/avatar/') + p.user_avatar, 'text-3xl'));
        } else {
            userZone.innerHTML = '<span class="material-symbols-outlined text-outline text-3xl">upload</span><span class="text-[10px] text-outline font-bold mt-1 uppercase tracking-widest">Avatar</span>';
        }
        const uOverlay = document.createElement('div');
        uOverlay.className = 'upload-overlay';
        uOverlay.innerHTML = '<span class="material-symbols-outlined text-white">upload</span><span class="text-[10px] text-white font-bold mt-1">UPDATE</span>';
        userZone.appendChild(uOverlay);
    }

    // User name field
    const userNameField = document.getElementById('userName');
    if (userNameField) userNameField.value = p.user_display_name || '';

    // Theme swatch selection
    const preset = p.theme?.preset || 'amber';
    document.querySelectorAll('#settingsThemePicker .theme-swatch').forEach(s => {
        s.classList.toggle('selected', s.dataset.preset === preset);
    });
    if (preset === 'custom' && p.theme?.accent) {
        const cc = document.getElementById('settingsCustomColor');
        if (cc) cc.value = p.theme.accent;
    }

    // Apply theme color
    applyThemeColor(p.theme?.accent || '#e8a849');
}

// ── Persona Load / Save ─────────────────────────────────────────

export async function loadPersona() {
    try {
        const resp = await apiFetch(apiUrl('/api/persona'));
        const data = await resp.json();
        state.persona = data;
        // Add cache-buster to avatar URLs
        const ts = Date.now();
        if (state.persona.avatar && !state.persona.avatar.includes('?')) state.persona.avatar += '?t=' + ts;
        if (state.persona.user_avatar && !state.persona.user_avatar.includes('?')) state.persona.user_avatar += '?t=' + ts;
        updateUIFromPersona();
    } catch (e) { console.error('Load persona failed:', e); }
}

export async function savePersonaToServer(updates) {
    try {
        const resp = await apiFetch(apiUrl('/api/persona'), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates),
        });
        const data = await resp.json();
        if (data.persona) {
            const merged = { ...state.persona, ...data.persona };
            // Preserve local cache-busted avatar URLs
            if (state.persona.avatar) merged.avatar = state.persona.avatar;
            if (state.persona.user_avatar) merged.user_avatar = state.persona.user_avatar;
            state.persona = merged;
            updateUIFromPersona();
        }
        return true;
    } catch (e) { console.error('Save persona failed:', e); return false; }
}

// ── Identity Tab Switching ──────────────────────────────────────

export function switchIdentityTab(tab) {
    const agentCard = document.getElementById('agentIdentityCard');
    const userCard = document.getElementById('userIdentityCard');
    const agentBtn = document.getElementById('tabAgentBtn');
    const userBtn = document.getElementById('tabUserBtn');

    if (tab === 'agent') {
        agentCard?.classList.remove('hidden');
        userCard?.classList.add('hidden');
        agentBtn?.classList.add('bg-[#e8a849]', 'text-[#452b00]');
        agentBtn?.classList.remove('text-on-surface-variant');
        userBtn?.classList.remove('bg-[#e8a849]', 'text-[#452b00]');
        userBtn?.classList.add('text-on-surface-variant');
    } else {
        agentCard?.classList.add('hidden');
        userCard?.classList.remove('hidden');
        userBtn?.classList.add('bg-[#e8a849]', 'text-[#452b00]');
        userBtn?.classList.remove('text-on-surface-variant');
        agentBtn?.classList.remove('bg-[#e8a849]', 'text-[#452b00]');
        agentBtn?.classList.add('text-on-surface-variant');
    }
}

// ── Language Toggle ─────────────────────────────────────────────

const translations = {
    en: {
        chat: 'Chat', skills: 'Skills', memory: 'Memory', settings: 'Settings',
        newChat: 'New Chat', support: 'Support', langLabel: 'EN'
    },
    zh: {
        chat: '对话', skills: '技能', memory: '记忆', settings: '设置',
        newChat: '新对话', support: '帮助', langLabel: '中'
    }
};

let supportText = 'Support';

export function applyLanguage(lang) {
    state.currentLang = lang;
    const t = translations[lang] || translations.en;
    const langLabel = document.getElementById('langLabel');
    if (langLabel) langLabel.textContent = t.langLabel;

    const navItems = document.querySelectorAll('.nav-item');
    if (navItems[0]) navItems[0].innerHTML = `<span class="material-symbols-outlined text-[20px]">chat</span> ${t.chat}`;
    if (navItems[1]) navItems[1].innerHTML = `<span class="material-symbols-outlined text-[20px]">bolt</span> ${t.skills}`;
    if (navItems[2]) navItems[2].innerHTML = `<span class="material-symbols-outlined text-[20px]">database</span> ${t.memory}`;
    if (navItems[3]) navItems[3].innerHTML = `<span class="material-symbols-outlined text-[20px]">settings</span> ${t.settings}`;

    const newChatBtn = document.querySelector('button[onclick="newSession()"]');
    if (newChatBtn) newChatBtn.innerHTML = `<span class="material-symbols-outlined text-[20px]">add</span> ${t.newChat}`;

    supportText = t.support;
    const supportBtn = document.querySelector('button[onclick="showSupportModal()"]');
    if (supportBtn) {
        supportBtn.innerHTML = `<span class="material-symbols-outlined text-[20px]">help</span> ${supportText}`;
    }
}

export function toggleLanguage() {
    const newLang = state.currentLang === 'en' ? 'zh' : 'en';
    localStorage.setItem('hermes_webui_language', newLang);
    applyLanguage(newLang);
}

// ── Window Exports ──────────────────────────────────────────────

window.makeAvatarImg = makeAvatarImg;
window.makeUserAvatarImg = makeUserAvatarImg;
window.updateUIFromPersona = updateUIFromPersona;
window.loadPersona = loadPersona;
window.savePersonaToServer = savePersonaToServer;
window.switchIdentityTab = switchIdentityTab;
window.applyLanguage = applyLanguage;
window.toggleLanguage = toggleLanguage;
window.translations = translations;
