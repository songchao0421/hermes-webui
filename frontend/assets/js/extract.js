/**
 * Hermes WebUI - Extract Module
 * Memory extraction + utility helpers.
 * Window-exported for HTML onclick compatibility.
 */
globalThis.App = globalThis.App || {};
const App = globalThis.App;

import { apiFetch, apiUrl } from './api.js';
import { state } from './state.js';
import { showToast } from './utils.js';

// ── extractMemory ───────────────────────────────────────────────

export async function extractMemory() {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer || chatContainer.querySelectorAll('.assistant-message').length === 0) {
        showToast('没有可提取的对话内容', 'warning');
        return;
    }
    showToast('正在提取记忆...', 'info');
    const extractBtn = document.getElementById('extractMemoryBtn');
    if (extractBtn) extractBtn.disabled = true;

    try {
        const resp = await apiFetch(apiUrl('/api/memory/extract'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: state.currentSessionId }),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            showToast('提取失败: ' + (err.detail || err.message || resp.statusText), 'error');
            return;
        }
        const data = await resp.json();
        showToast('记忆提取完成: ' + (data.count + ' 条' || '成功'), 'success');
        if (typeof loadMemories === 'function') loadMemories();
    } catch (e) {
        showToast('提取失败: ' + e.message, 'error');
    } finally {
        if (extractBtn) extractBtn.disabled = false;
    }
}

// ── Extract Modal ───────────────────────────────────────────────

export function openExtractModal() {
    // Close other open dialogs first
    const dialogs = document.querySelectorAll('.fixed.inset-0.z-50');
    dialogs.forEach(d => d.classList.add('hidden'));

    // Check if an extract dialog already exists; if not, create one
    let dlg = document.getElementById('extractDialog');
    if (!dlg) {
        dlg = document.createElement('div');
        dlg.id = 'extractDialog';
        dlg.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm';
        dlg.innerHTML = `
            <div class="bg-surface-container rounded-2xl p-8 max-w-md w-full mx-4 border border-outline-variant/20 shadow-2xl">
                <div class="flex items-center justify-between mb-6">
                    <h3 class="text-lg font-bold text-on-surface">Extract Memories</h3>
                    <button onclick="closeDialog('extractDialog')" class="w-8 h-8 rounded-lg bg-surface-container-high hover:bg-surface-container-highest flex items-center justify-center transition-colors">
                        <span class="material-symbols-outlined text-[18px] text-on-surface-variant">close</span>
                    </button>
                </div>
                <p class="text-sm text-on-surface-variant mb-6">Extract memories from the current conversation to enhance agent context.</p>
                <div class="flex gap-3 justify-end">
                    <button onclick="closeDialog('extractDialog')" class="px-5 py-2.5 rounded-xl bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest text-sm font-bold transition-all">Cancel</button>
                    <button onclick="extractFromDialog()" class="px-5 py-2.5 rounded-xl font-bold text-sm transition-all active:scale-95" style="background:var(--theme-primary);color:#1a1a1a;">Extract Now</button>
                </div>
            </div>
        `;
        document.body.appendChild(dlg);

        // Register close handler on backdrop click
        dlg.addEventListener('click', (e) => {
            if (e.target === dlg) dlg.classList.add('hidden');
        });
    }

    dlg.classList.remove('hidden');
}

// Helper called from the extract dialog button
window.extractFromDialog = async function() {
    const dlg = document.getElementById('extractDialog');
    if (dlg) dlg.classList.add('hidden');
    // Use the existing extractMemory function
    await extractMemory();
};

export function openUploadDialog() {
    const dialogs = document.querySelectorAll('.fixed.inset-0.z-50');
    dialogs.forEach(d => { if (d.id !== 'uploadDialog') d.classList.add('hidden'); });
    const dlg = document.getElementById('uploadDialog');
    if (dlg) dlg.classList.remove('hidden');
}

export function closeUploadDialog() {
    const dlg = document.getElementById('uploadDialog');
    if (dlg) dlg.classList.add('hidden');
}

// ── Open Avatar Dialog ──────────────────────────────────────────

export function openAvatarDialog() {
    const dialogs = document.querySelectorAll('.fixed.inset-0.z-50');
    dialogs.forEach(d => d.classList.add('hidden'));
    const dlg = document.getElementById('avatarDialog');
    if (dlg) dlg.classList.remove('hidden');
}

export function closeAvatarDialog() {
    const dlg = document.getElementById('avatarDialog');
    if (dlg) dlg.classList.add('hidden');
}

// ── General Dialog Helpers ──────────────────────────────────────

export function openDialog(dialogId) {
    const dialogs = document.querySelectorAll('.fixed.inset-0.z-50');
    dialogs.forEach(d => { if (d.id !== dialogId) d.classList.add('hidden'); });
    const dlg = document.getElementById(dialogId);
    if (dlg) dlg.classList.remove('hidden');
}

export function closeDialog(dialogId) {
    const dlg = document.getElementById(dialogId);
    if (dlg) dlg.classList.add('hidden');
}

// ── Notifications ───────────────────────────────────────────────

export function initNotifications() {
    if (!('Notification' in window)) return;
    if (Notification.permission === 'default') {
        Notification.requestPermission();
    }
}

export function sendNotification(title, body) {
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    try {
        new Notification(title, { body, icon: '/assets/favicon.ico' });
    } catch (e) { /* ignore */ }
}

// ── Keyboard Shortcuts ──────────────────────────────────────────

export function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+Enter or Cmd+Enter to send
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            sendMessage();
        }
        // Escape to close modals
        if (e.key === 'Escape') {
            const openDialogs = document.querySelectorAll('.fixed.inset-0.z-50:not(.hidden)');
            openDialogs.forEach(d => d.classList.add('hidden'));
            if (document.getElementById('routeDropdown')?.classList.contains('hidden') === false) {
                document.getElementById('routeDropdown').classList.add('hidden');
            }
            if (document.getElementById('themePanel')?.classList.contains('hidden') === false) {
                document.getElementById('themePanel').classList.add('hidden');
            }
            if (document.getElementById('sidebar')?.classList.contains('-translate-x-full') === false) {
                toggleSidebar();
            }
        }
        // Ctrl+K for commands
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            // Focus message input
            const input = document.getElementById('messageInput');
            if (input) input.focus();
        }
    });
}

// ── Window Exports ──────────────────────────────────────────────

window.extractMemory = extractMemory;
App.extractMemory = extractMemory;
window.openUploadDialog = openUploadDialog;
App.openUploadDialog = openUploadDialog;
window.closeUploadDialog = closeUploadDialog;
App.closeUploadDialog = closeUploadDialog;
window.openAvatarDialog = openAvatarDialog;
App.openAvatarDialog = openAvatarDialog;
window.closeAvatarDialog = closeAvatarDialog;
App.closeAvatarDialog = closeAvatarDialog;
window.openDialog = openDialog;
App.openDialog = openDialog;
window.closeDialog = closeDialog;
App.closeDialog = closeDialog;
window.openExtractModal = openExtractModal;
App.openExtractModal = openExtractModal;
window.initNotifications = initNotifications;
App.initNotifications = initNotifications;
window.sendNotification = sendNotification;
App.sendNotification = sendNotification;
window.setupKeyboardShortcuts = setupKeyboardShortcuts;
App.setupKeyboardShortcuts = setupKeyboardShortcuts;
App.extractFromDialog = window.extractFromDialog;