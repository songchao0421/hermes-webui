/**
 * Hermes WebUI - Sessions Module
 * Session management: list, create, switch, delete sessions + tab switching.
 * Window-exported for HTML onclick compatibility.
 */

import { apiFetch, apiUrl } from './api.js';
import { state, setState } from './state.js';
import { showToast, escapeHtml } from './utils.js';
import { loadPersona } from './persona.js';

// ── Tab Switching ───────────────────────────────────────────────

export function switchTab(tab) {
    setState('currentTab', tab);
    const tabs = ['chat', 'skills', 'memory', 'settings'];
    tabs.forEach(t => {
        const panel = document.getElementById('tab' + t.charAt(0).toUpperCase() + t.slice(1));
        if (panel) panel.classList.toggle('hidden', t !== tab);
    });
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.tab === tab);
    });

    // Load content on first access
    if (tab === 'skills') {
        const { loadSkills } = window.skillsModule || {};
        if (typeof loadSkills === 'function') loadSkills();
    }
    if (tab === 'memory') {
        const { loadMemories } = window.memoriesModule || {};
        if (typeof loadMemories === 'function') loadMemories();
    }

    // Scroll chat to bottom when switching to chat
    if (tab === 'chat') {
        setTimeout(() => {
            const chatTab = document.getElementById('tabChat');
            if (chatTab) chatTab.scrollTop = chatTab.scrollHeight;
        }, 50);
    }
}

// ── Sessions ────────────────────────────────────────────────────

export async function loadSessionList() {
    try {
        const resp = await apiFetch(apiUrl('/api/sessions'));
        const data = await resp.json();
        renderSessionList(data);
    } catch (e) { console.error('Load sessions failed:', e); }
}

export function renderSessionList(sessions) {
    const container = document.getElementById('sessionList');
    if (!container) return;
    container.innerHTML = '';

    if (!sessions || sessions.length === 0) {
        container.innerHTML = '<div class="text-center text-on-surface-variant/50 py-6 text-xs">No sessions yet</div>';
        return;
    }

    const currentId = state.currentSessionId;
    sessions.forEach(s => {
        const isActive = s.id === currentId;
        const item = document.createElement('div');
        item.className = `session-item ${isActive ? 'active bg-surface-container-highest' : 'hover:bg-surface-container-highest/50'} rounded-xl transition-colors cursor-pointer`;
        item.setAttribute('data-session-id', s.id);
        item.innerHTML = `
            <div class="flex items-center gap-3 px-4 py-3" onclick="switchSession('${s.id}')">
                <span class="material-symbols-outlined text-[18px] text-on-surface-variant/50">chat</span>
                <div class="flex-1 min-w-0">
                    <div class="text-xs font-medium text-on-surface truncate">${escapeHtml(s.title || 'New Chat')}</div>
                    <div class="text-[10px] text-on-surface-variant/50 mt-0.5">${s.message_count || 0} messages</div>
                </div>
                <button onclick="event.stopPropagation();openRenameModal('${escapeHtml(s.title || '')}')" class="text-on-surface-variant/30 hover:text-primary transition-colors mr-1">
                    <span class="material-symbols-outlined text-[14px]">edit</span>
                </button>
                <button onclick="event.stopPropagation();deleteSessionConfirm('${s.id}')" class="text-on-surface-variant/30 hover:text-error transition-colors">
                    <span class="material-symbols-outlined text-[14px]">close</span>
                </button>
            </div>
        `;
        container.appendChild(item);
    });

    // Scroll active session into view
    const active = container.querySelector('.session-item.active');
    if (active) active.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

export async function newSession() {
    try {
        const resp = await apiFetch(apiUrl('/api/sessions'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: 'New Chat' }),
        });
        const data = await resp.json();
        if (data.session_id) {
            state.currentSessionId = data.session_id;
            clearChatContainer();
            updateSessionIdDisplay();
            loadSessionList();
            showToast('New session created');
        }
    } catch (e) { showToast('Error: ' + e.message); }
}

export async function switchSession(sessionId) {
    if (sessionId === state.currentSessionId) return;
    state.currentSessionId = sessionId;
    updateSessionIdDisplay();
    loadSessionList();
    await loadChatHistory(sessionId);
}

export async function deleteSessionConfirm(sessionId) {
    if (!confirm('Delete this session? History will be lost.')) return;
    await deleteSession(sessionId);
}

export async function deleteSession(sessionId) {
    try {
        const resp = await apiFetch(apiUrl('/api/sessions/' + sessionId), { method: 'DELETE' });
        if (resp.ok) {
            if (sessionId === state.currentSessionId) {
                state.currentSessionId = '';
                clearChatContainer();
            }
            loadSessionList();
            showToast('Session deleted');
        }
    } catch (e) { showToast('Error: ' + e.message); }
}

export async function loadChatHistory(sessionId) {
    if (!sessionId) return;
    try {
        const resp = await apiFetch(apiUrl('/api/sessions/' + sessionId));
        const data = await resp.json();
        renderChatHistory(data);
    } catch (e) { console.error('Load history failed:', e); }
}

export function renderChatHistory(session) {
    clearChatContainer();
    if (!session?.messages || session.messages.length === 0) {
        showEmptyState();
        return;
    }
    const container = document.getElementById('chatContainer');
    if (!container) return;

    session.messages.forEach(msg => {
        if (msg.role === 'user') {
            // Render user message
            const div = document.createElement('div');
            div.className = 'flex flex-col items-end gap-3 mb-8';
            const userName = (state.persona?.user_display_name || 'You');
            div.innerHTML = `
                <div class="flex items-center gap-3">
                    <span class="text-xs font-bold text-on-surface-variant/50 uppercase tracking-widest">${escapeHtml(userName)}</span>
                </div>
                <div class="max-w-[80%] bg-primary/10 rounded-2xl rounded-tr-sm px-5 py-3">
                    <div class="text-sm text-on-surface leading-relaxed">${escapeHtml(msg.content || '')}</div>
                </div>
            `;
            container.appendChild(div);
        } else {
            // Import and use chat rendering
            const { addAssistantMessage } = window.chatModule || {};
            if (typeof addAssistantMessage === 'function') {
                addAssistantMessage(msg.content || '', msg.model || '', 0);
            }
        }
    });
    setTimeout(scrollToBottom, 50);
}

export function clearChatContainer() {
    const container = document.getElementById('chatContainer');
    if (container) container.innerHTML = '';
    showEmptyState();
}

function showEmptyState() {
    const container = document.getElementById('chatContainer');
    if (!container) return;
    const name = state.persona?.agent_name || 'Agent';
    const hasMessages = container.querySelector('.flex');
    if (!hasMessages) {
        container.innerHTML = `
            <div class="flex flex-col items-center justify-center h-full text-center px-8">
                <div class="text-5xl mb-4 opacity-30">🐴</div>
                <h3 class="text-on-surface-variant/70 text-base font-bold">${escapeHtml(name)}</h3>
                <p class="text-on-surface-variant/40 text-xs mt-2">Start a conversation</p>
            </div>
        `;
    }
}

function updateSessionIdDisplay() {
    const el = document.getElementById('currentSessionId');
    if (el) el.textContent = state.currentSessionId ? state.currentSessionId.slice(0, 8) + '...' : '--';
}

function scrollToBottom() {
    const chatTab = document.getElementById('tabChat');
    if (chatTab) {
        chatTab.scrollTo({ top: chatTab.scrollHeight, behavior: 'smooth' });
    }
}

// ── Session Filtering (Mobile friendly) ─────────────────────────

export function filterSessions(query) {
    const sessionList = document.getElementById('sessionList');
    if (!sessionList) return;
    const items = sessionList.children;
    for (let i = 0; i < items.length; i++) {
        const item = items[i];
        const titleEl = item.querySelector('.font-medium');
        const title = titleEl ? titleEl.textContent || '' : '';
        const match = !query || title.toLowerCase().includes(query.toLowerCase());
        item.style.display = match ? 'block' : 'none';
    }
}

export function toggleMobileNav() {
    const nav = document.getElementById('sideNav');
    const overlay = document.getElementById('sideNavOverlay');
    if (!nav || !overlay) return;
    if (window.innerWidth < 769) {
        nav.classList.toggle('mobile-open');
        overlay.classList.toggle('active');
    } else {
        // Desktop: ensure it's closed
        nav.classList.remove('mobile-open');
        overlay.classList.remove('active');
    }
}

// ── Window Exports ──────────────────────────────────────────────

window.switchTab = switchTab;
window.loadSessionList = loadSessionList;
window.renderSessionList = renderSessionList;
window.newSession = newSession;
window.switchSession = switchSession;
window.deleteSessionConfirm = deleteSessionConfirm;
window.deleteSession = deleteSession;
window.loadChatHistory = loadChatHistory;
window.renderChatHistory = renderChatHistory;
window.clearChatContainer = clearChatContainer;
window.filterSessions = filterSessions;
window.toggleMobileNav = toggleMobileNav;
