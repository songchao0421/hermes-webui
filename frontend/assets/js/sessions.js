/**
 * Hermes WebUI - Sessions Module
 * Session management: list, create, switch, delete sessions + tab switching.
 * Window-exported for HTML onclick compatibility.
 */
globalThis.App = globalThis.App || {};
const App = globalThis.App;

import { apiFetch, apiUrl } from './api.js';
import { state, setState } from './state.js';
import { showToast, escapeHtml } from './utils.js';
import { loadPersona } from './persona.js';

// ── Tab Switching ───────────────────────────────────────────────

export function switchTab(tab) {
    setState('currentTab', tab);
    const tabs = ['chat', 'skills', 'memory', 'files', 'settings'];
    tabs.forEach(t => {
        const panel = document.getElementById('tab' + t.charAt(0).toUpperCase() + t.slice(1));
        if (panel) panel.classList.toggle('hidden', t !== tab);
    });
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.tab === tab);
    });

    // Hide input bar when not on chat tab
    const inputBar = document.getElementById('inputBar');
    if (inputBar) inputBar.classList.toggle('hidden', tab !== 'chat');

    // Load content on first access
    if (tab === 'skills') {
        const { loadSkills } = window.skillsModule || {};
        if (typeof loadSkills === 'function') loadSkills();
        // Reset search
        const search = document.getElementById('skillsSearch');
        if (search) search.value = '';
    }
    if (tab === 'memory') {
        const { loadMemories } = window.memoriesModule || {};
        if (typeof loadMemories === 'function') loadMemories();
    }
    if (tab === 'files') {
        loadFileList();
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
        renderSessionList(data.sessions);
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
                    <div class="text-xs font-medium text-on-surface truncate">${escapeHtml(s.name || 'New Chat')}</div>
                    <div class="text-[10px] text-on-surface-variant/50 mt-0.5">${s.message_count || 0} messages</div>
                </div>
                <button onclick="event.stopPropagation();openRenameModal('${escapeHtml(s.name || '')}')" class="text-on-surface-variant/30 hover:text-primary transition-colors mr-1">
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
        const resp = await apiFetch(apiUrl('/api/sessions/new'), {
            method: 'POST',
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
            const wasCurrent = sessionId === state.currentSessionId;
            if (wasCurrent) {
                state.currentSessionId = '';
                clearChatContainer();
            }
            // Reload list, then select first session if current was deleted
            await loadSessionList();
            if (wasCurrent) {
                // Auto-select the new session that backend created
                const listResp = await apiFetch(apiUrl('/api/sessions'));
                const listData = await listResp.json();
                const sessions = listData.sessions || [];
                if (sessions.length > 0) {
                    state.currentSessionId = sessions[0].id;
                    updateSessionIdDisplay();
                }
            }
            showToast('对话已删除');
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
App.switchTab = switchTab;
window.loadSessionList = loadSessionList;
App.loadSessionList = loadSessionList;
window.renderSessionList = renderSessionList;
App.renderSessionList = renderSessionList;
window.newSession = newSession;
App.newSession = newSession;
window.switchSession = switchSession;
App.switchSession = switchSession;
window.deleteSessionConfirm = deleteSessionConfirm;
App.deleteSessionConfirm = deleteSessionConfirm;
window.deleteSession = deleteSession;
App.deleteSession = deleteSession;
window.loadChatHistory = loadChatHistory;
App.loadChatHistory = loadChatHistory;
window.renderChatHistory = renderChatHistory;
App.renderChatHistory = renderChatHistory;
window.clearChatContainer = clearChatContainer;
App.clearChatContainer = clearChatContainer;
window.filterSessions = filterSessions;

// ── File List ────────────────────────────────────────────────────

export async function loadFileList() {
    const container = document.getElementById('fileList');
    if (!container) return;
    container.innerHTML = '<div class="text-center text-on-surface-variant/50 py-20"><span class="material-symbols-outlined text-4xl mb-2 block">folder_off</span>Loading files...</div>';

    try {
        const resp = await apiFetch('/api/files/list');
        const data = await resp.json();
        renderFileList(container, data.files || []);
    } catch (e) {
        container.innerHTML = `<div class="text-center text-error/80 py-20">
            <span class="material-symbols-outlined text-4xl mb-2 block">error</span>
            Failed to load files: ${escapeHtml(e.message || 'Unknown error')}
        </div>`;
    }
}

function renderFileList(container, files) {
    if (!files.length) {
        container.innerHTML = '<div class="text-center text-on-surface-variant/50 py-20"><span class="material-symbols-outlined text-4xl mb-2 block">inbox</span>No files yet. Upload files via Chat.</div>';
        return;
    }

    // Group by source
    const groups = {};
    files.forEach(f => {
        if (!groups[f.source]) groups[f.source] = [];
        groups[f.source].push(f);
    });

    let html = '';
    for (const [source, items] of Object.entries(groups)) {
        const sourceIcon = source.includes('upload') ? 'cloud_upload' :
                           source.includes('已完成') ? 'check_circle' : 'hourglass_empty';
        html += `<div class="mb-6">
            <h3 class="text-sm font-bold text-on-surface-variant/60 uppercase tracking-wider mb-3 flex items-center gap-2">
                <span class="material-symbols-outlined text-[16px]">${sourceIcon}</span>
                ${escapeHtml(source)}
                <span class="text-[10px] text-on-surface-variant/30">(${items.length})</span>
            </h3>
            <div class="space-y-1">`;
        items.forEach(f => {
            const icon = _fileIcon(f.name);
            const size = f.size_hr || _fmtSize(f.size);
            html += `<div class="file-row flex items-center gap-3 px-4 py-3 rounded-xl bg-[#1f1f22] hover:bg-[#2a2a2e] border border-outline-variant/10 transition-colors group">
                <span class="material-symbols-outlined text-[20px] text-on-surface-variant/60">${icon}</span>
                <div class="flex-1 min-w-0">
                    <div class="text-sm text-on-surface truncate">${escapeHtml(f.name)}</div>
                    <div class="text-[10px] text-on-surface-variant/40">${size} · ${_fmtTime(f.mtime)}</div>
                </div>
                <a href="${f.download_url}" download="${escapeHtml(f.name)}"
                   class="btn-download opacity-0 group-hover:opacity-100 transition-opacity bg-[#e8a849] hover:bg-[#ffc676] text-[#452b00] px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1">
                    <span class="material-symbols-outlined text-[14px]">download</span>
                    Download
                </a>
            </div>`;
        });
        html += `</div></div>`;
    }
    container.innerHTML = html;
}

function _fileIcon(name) {
    const ext = name.split('.').pop().toLowerCase();
    const map = {
        pdf: 'picture_as_pdf', doc: 'description', docx: 'description',
        xls: 'table_chart', xlsx: 'table_chart', ppt: 'slideshow', pptx: 'slideshow',
        png: 'image', jpg: 'image', jpeg: 'image', gif: 'gif', svg: 'image',
        mp4: 'videocam', mov: 'videocam', avi: 'videocam',
        mp3: 'audio_file', wav: 'audio_file', flac: 'audio_file',
        zip: 'folder_zip', rar: 'folder_zip', '7z': 'folder_zip',
        py: 'code', js: 'javascript', ts: 'code', json: 'data_object',
        yaml: 'data_object', yml: 'data_object', md: 'article', txt: 'article',
    };
    return map[ext] || 'insert_drive_file';
}

function _fmtSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

function _fmtTime(ts) {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

window.loadFileList = loadFileList;
App.loadFileList = loadFileList;
App.filterSessions = filterSessions;
window.toggleMobileNav = toggleMobileNav;
App.toggleMobileNav = toggleMobileNav;