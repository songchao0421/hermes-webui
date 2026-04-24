/**
 * Hermes WebUI - Memories Module
 * Memory management: list, search, create, edit, delete memories.
 * Window-exported for HTML onclick compatibility.
 */

import { apiFetch, apiUrl } from './api.js';
import { escapeHtml, showToast } from './utils.js';
import { state } from './state.js';

// ── Memories ────────────────────────────────────────────────────

export async function loadMemories(group) {
    try {
        let url = '/api/memories';
        if (group) url += '?group=' + encodeURIComponent(group);
        const resp = await apiFetch(apiUrl(url));
        const data = await resp.json();
        renderMemories(data);
    } catch (e) { console.error('Load memories failed:', e); }
}

export function renderMemories(memories) {
    const container = document.getElementById('memoriesList');
    if (!container) return;
    container.innerHTML = '';
    if (!memories || memories.length === 0) {
        container.innerHTML = '<div class="text-center text-on-surface-variant/50 py-12 text-sm">No memories yet.</div>';
        return;
    }
    memories.forEach(mem => {
        const card = document.createElement('div');
        card.className = 'p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/20 hover:border-outline-variant/40 transition-all';
        card.innerHTML = `
            <div class="flex items-start justify-between">
                <div class="flex-1 min-w-0">
                    <p class="text-xs text-on-surface-variant/60 font-mono truncate">${escapeHtml(mem.path || '')}</p>
                    <div class="text-sm text-on-surface-variant mt-1 line-clamp-3">${escapeHtml(mem.content || '')}</div>
                </div>
                <div class="flex items-center gap-1 ml-2 shrink-0">
                    <button onclick="editMemory('${escapeHtml(mem.path)}')" class="w-8 h-8 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 flex items-center justify-center transition-colors" title="Edit">
                        <span class="material-symbols-outlined text-[14px]">edit</span>
                    </button>
                    <button onclick="deleteMemory('${escapeHtml(mem.path)}')" class="w-8 h-8 rounded-lg bg-error/10 text-error hover:bg-error/20 flex items-center justify-center transition-colors" title="Delete">
                        <span class="material-symbols-outlined text-[14px]">delete</span>
                    </button>
                </div>
            </div>
            ${mem.tags ? `<div class="flex flex-wrap gap-1 mt-2">${mem.tags.map(t => `<span class="text-[10px] px-2 py-0.5 bg-primary/10 text-primary rounded-full">#${escapeHtml(t)}</span>`).join('')}</div>` : ''}
            <div class="text-[10px] text-on-surface-variant/40 mt-2">${mem.updated_at || ''}</div>
        `;
        container.appendChild(card);
    });
}

export async function searchMemory(query) {
    if (!query?.trim()) { loadMemories(); return; }
    try {
        const resp = await apiFetch(apiUrl('/api/memories/search?q=' + encodeURIComponent(query)));
        const data = await resp.json();
        renderMemories(data);
    } catch (e) { console.error('Search memory failed:', e); }
}

export function showMemoryEditor(path) {
    state.editingMemoryFile = path || '';
    document.getElementById('memoryEditorPath').value = path || '';
    document.getElementById('memoryEditorContent').value = '';
    document.getElementById('memoryEditorTitle').textContent = path ? 'Edit Memory' : 'New Memory';

    if (path) {
        // Load existing content
        apiFetch(apiUrl('/api/memories/file?path=' + encodeURIComponent(path)))
            .then(r => r.json())
            .then(data => {
                document.getElementById('memoryEditorContent').value = data.content || '';
            })
            .catch(() => {});
    }
    document.getElementById('memoryEditor').classList.remove('hidden');
    document.getElementById('memoryEditorContent').focus();
}

export function hideMemoryEditor() {
    document.getElementById('memoryEditor').classList.add('hidden');
}

export async function saveMemory() {
    const path = document.getElementById('memoryEditorPath')?.value?.trim();
    const content = document.getElementById('memoryEditorContent')?.value?.trim();
    if (!path || !content) { showToast('Path and content are required'); return; }

    try {
        const resp = await apiFetch(apiUrl('/api/memories'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path, content }),
        });
        if (resp.ok) {
            showToast('Memory saved!');
            hideMemoryEditor();
            loadMemories();
        } else {
            showToast('Save failed');
        }
    } catch (e) { showToast('Error: ' + e.message); }
}

export async function deleteMemory(path) {
    if (!confirm(`Delete memory "${path}"?`)) return;
    try {
        const resp = await apiFetch(apiUrl('/api/memories?path=' + encodeURIComponent(path)), { method: 'DELETE' });
        if (resp.ok) {
            showToast('Memory deleted');
            loadMemories();
        } else {
            showToast('Delete failed');
        }
    } catch (e) { showToast('Error: ' + e.message); }
}

export function editMemory(path) {
    showMemoryEditor(path);
}

// ── Memory Debug ────────────────────────────────────────────────

export async function refreshMemoryDebug() {
    const contentEl = document.getElementById('memoryDebugContent');
    const statusEl = document.getElementById('memoryDebugStatus');
    if (!contentEl) return;

    contentEl.innerHTML = '<span class="text-outline italic">Loading...</span>';
    if (statusEl) {
        statusEl.innerHTML = '<span class="w-2 h-2 rounded-full bg-warning"></span><span class="text-on-surface-variant">Loading...</span>';
    }

    try {
        // Try to load SOUL.md content
        const resp = await apiFetch(apiUrl('/api/memories/file?path=SOUL.md'));
        const data = await resp.json();
        const content = data.content || '';

        if (content) {
            contentEl.innerHTML = '<pre class="whitespace-pre-wrap break-words">' + escapeHtml(content) + '</pre>';
            if (statusEl) {
                statusEl.innerHTML = '<span class="w-2 h-2 rounded-full bg-success"></span><span class="text-on-surface-variant">Loaded (' + content.length + ' chars)</span>';
            }
        } else {
            contentEl.innerHTML = '<span class="text-outline italic">SOUL.md is empty or not found</span>';
            if (statusEl) {
                statusEl.innerHTML = '<span class="w-2 h-2 rounded-full bg-outline"></span><span class="text-on-surface-variant">No content</span>';
            }
        }
    } catch (e) {
        contentEl.innerHTML = '<span class="text-error italic">Failed to load: ' + escapeHtml(e.message) + '</span>';
        if (statusEl) {
            statusEl.innerHTML = '<span class="w-2 h-2 rounded-full bg-error"></span><span class="text-on-surface-variant">Error loading</span>';
        }
    }
}

// ── Memory Snapshot ─────────────────────────────────────────────

export async function snapshotMemory() {
    try {
        const resp = await window.apiFetch(window.apiUrl('/api/memories/snapshot'), { method: 'POST' });
        if (resp.ok) {
            showToast('Snapshot saved!');
        } else {
            showToast('Snapshot failed');
        }
    } catch (e) {
        showToast('Snapshot failed: ' + e.message);
    }
}

// ── Alias ───────────────────────────────────────────────────────

export function closeMemoryModal() {
    return hideMemoryEditor();
}

// ── Window Exports ──────────────────────────────────────────────

window.loadMemories = loadMemories;
window.renderMemories = renderMemories;
window.searchMemory = searchMemory;
window.showMemoryEditor = showMemoryEditor;
window.hideMemoryEditor = hideMemoryEditor;
window.saveMemory = saveMemory;
window.deleteMemory = deleteMemory;
window.editMemory = editMemory;
window.refreshMemoryDebug = refreshMemoryDebug;
window.snapshotMemory = snapshotMemory;
window.closeMemoryModal = closeMemoryModal;
