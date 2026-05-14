/**
 * Hermes WebUI - Memories Module
 * SOUL 配置：选项卡 + 纯文本预览（过滤markdown符号）+ EasyMDE编辑
 */

globalThis.App = globalThis.App || {};
const App = globalThis.App;

import { apiFetch, apiUrl } from './api.js';
import { escapeHtml, showToast } from './utils.js';

let _soulTab = 'company';
let _soulEditor = null;

export async function loadMemories(group) {
    loadSoulContent('company');
    loadSoulContent('local');
    loadPreviewFile('MEMORY.md', 'memoryMemory');
    loadPreviewFile('USER.md', 'memoryUser');
}

async function loadPreviewFile(name, elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    try {
        const resp = await apiFetch(apiUrl(`/api/memories/file?path=${name}`));
        const data = await resp.json();
        el.textContent = data.content ? stripMarkdown(data.content) : '(空)';
    } catch (e) {
        el.textContent = '加载失败';
    }
}

// ── Markdown filter ──────────────────────────────────────────────

function stripMarkdown(text) {
    return text
        .replace(/^#{1,6}\s+/gm, '')       // # 标题
        .replace(/\*\*(.+?)\*\*/g, '$1')    // **加粗**
        .replace(/\*(.+?)\*/g, '$1')         // *斜体*
        .replace(/~~(.+?)~~/g, '$1')         // ~~删除线~~
        .replace(/`{1,3}[^`]*`{1,3}/g, '')   // `代码`
        .replace(/^[-*+]\s+/gm, '  • ')      // 无序列表
        .replace(/^\d+\.\s+/gm, '  ')        // 有序列表
        .replace(/^>\s+/gm, '')              // 引用
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // [链接](url)
        .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1') // ![图片](url)
        .replace(/---+/g, '────────────────────') // 分割线
        .replace(/\|/g, ' ')                 // 表格
        .replace(/:----?:/g, '')
        .trim();
}

// ── SOUL Content ─────────────────────────────────────────────────

function destroyEditor() {
    if (_soulEditor) {
        _soulEditor.toTextArea();
        _soulEditor = null;
    }
}

function initEditor(content, readOnly) {
    destroyEditor();
    const textarea = document.getElementById('soulContent');
    if (!textarea) return;
    textarea.value = content || '';
    _soulEditor = new EasyMDE({
        element: textarea,
        autofocus: false,
        spellChecker: false,
        forceSync: true,
        status: false,
        toolbar: readOnly ? false : ['bold', 'italic', 'heading', '|', 'quote', 'unordered-list', 'ordered-list', '|', 'code', 'horizontal-rule', '|', 'preview', 'guide'],
        renderingConfig: { singleLineBreaks: true, codeSyntaxHighlighting: false },
    });
    if (readOnly) {
        _soulEditor.codemirror.setOption('readOnly', true);
        _soulEditor.toolbar = null;
    }
}

function showPreview(rawContent) {
    const preview = document.getElementById('soulPreview');
    const editorWrap = document.getElementById('soulEditorWrap');
    const editBtn = document.getElementById('soulEditModeBtn');
    const saveBtn = document.getElementById('soulSaveBtn');
    if (!preview) return;

    preview.classList.remove('hidden');
    if (editorWrap) editorWrap.classList.add('hidden');
    if (editBtn) editBtn.classList.remove('hidden');
    if (saveBtn) saveBtn.classList.add('hidden');

    preview.textContent = rawContent ? stripMarkdown(rawContent) : '(空)';
}

function showEditMode(readOnly) {
    const preview = document.getElementById('soulPreview');
    const editorWrap = document.getElementById('soulEditorWrap');
    const editBtn = document.getElementById('soulEditModeBtn');
    const cancelBtn = document.getElementById('soulCancelBtn');
    const saveBtn = document.getElementById('soulSaveBtn');
    if (!editorWrap) return;

    preview.classList.add('hidden');
    editorWrap.classList.remove('hidden');
    if (editBtn) editBtn.classList.add('hidden');
    if (cancelBtn) cancelBtn.classList.remove('hidden');

    if (readOnly) {
        if (saveBtn) saveBtn.classList.add('hidden');
    } else {
        if (saveBtn) saveBtn.classList.remove('hidden');
    }
}

function showPreviewMode() {
    const preview = document.getElementById('soulPreview');
    const editorWrap = document.getElementById('soulEditorWrap');
    const editBtn = document.getElementById('soulEditModeBtn');
    const cancelBtn = document.getElementById('soulCancelBtn');
    const saveBtn = document.getElementById('soulSaveBtn');
    if (!preview) return;

    preview.classList.remove('hidden');
    if (editorWrap) editorWrap.classList.add('hidden');
    if (editBtn) editBtn.classList.remove('hidden');
    if (cancelBtn) cancelBtn.classList.add('hidden');
    if (saveBtn) saveBtn.classList.add('hidden');
}

export function cancelSoulEdit() {
    destroyEditor();
    // Reload current content from saved state
    loadSoulContent(_soulTab);
    showPreviewMode();
}

export function toggleSoulEditMode() {
    const content = _soulEditor ? _soulEditor.value() : document.getElementById('soulContent')?.value || '';
    const readOnly = _soulTab === 'company';
    showEditMode(readOnly);
    initEditor(content, readOnly);
}

async function loadSoulContent(type) {
    if (type === 'company') {
        const content = '量子数字员工行为规则文件（待创建）\n\n存放在：~/Shared/公司公共SOUL.md\n\n此文件对所有员工只读。';
        showPreview(content);
        // Pre-fill editor too
        const textarea = document.getElementById('soulContent');
        if (textarea) textarea.value = content;
        updateSoulStatus('info', '公司公共 SOUL · 只读');
    } else {
        try {
            const resp = await apiFetch(apiUrl('/api/memories/file?path=SOUL.md'));
            const data = await resp.json();
            const content = data.content || '';
            showPreview(content);
            const textarea = document.getElementById('soulContent');
            if (textarea) textarea.value = content;
            const len = content.length;
            updateSoulStatus(len > 0 ? 'success' : 'outline',
                len > 0 ? `本机 SOUL · ${len} 字符` : '内容为空');
        } catch (e) {
            showPreview('加载失败: ' + e.message);
            updateSoulStatus('error', '加载失败');
        }
    }
}

function updateSoulStatus(color, text) {
    const dot = document.querySelector('#soulStatus span:first-child');
    const label = document.querySelector('#soulStatus span:last-child');
    if (dot) dot.className = `w-2 h-2 rounded-full bg-${color}`;
    if (label) label.textContent = text;
}

// ── Tab switching ────────────────────────────────────────────────

export function switchSoulTab(type) {
    _soulTab = type;
    destroyEditor();
    document.querySelectorAll('.soul-tab').forEach(el => {
        const active = el.dataset.soulType === type;
        el.classList.toggle('bg-primary', active);
        el.classList.toggle('text-on-primary', active);
        el.classList.toggle('text-on-surface-variant', !active);
        el.classList.toggle('hover:bg-surface-container-highest', !active);
    });

    const icon = document.getElementById('soulIcon');
    const title = document.getElementById('soulTitle');
    const badge = document.getElementById('soulBadge');
    const editBtn = document.getElementById('soulEditModeBtn');
    const saveBtn = document.getElementById('soulSaveBtn');

    if (type === 'company') {
        icon.textContent = 'group';
        title.textContent = '量子数字员工';
        badge.textContent = '只读';
        badge.className = 'text-[10px] px-2 py-0.5 rounded-full font-bold bg-primary/10 text-primary/70';
        if (editBtn) editBtn.classList.add('hidden');
        if (saveBtn) saveBtn.classList.add('hidden');
    } else {
        icon.textContent = 'person';
        title.textContent = '本机 SOUL.md';
        badge.textContent = '可编辑';
        badge.className = 'text-[10px] px-2 py-0.5 rounded-full font-bold bg-[#34c759]/10 text-[#34c759]';
        if (editBtn) editBtn.classList.remove('hidden');
        if (saveBtn) saveBtn.classList.add('hidden');
    }

    loadSoulContent(type);
}

// ── Save ─────────────────────────────────────────────────────────

export async function saveSoul() {
    if (!_soulEditor) return;
    const content = _soulEditor.value();
    const btn = document.getElementById('soulSaveBtn');
    btn.textContent = '保存中...';
    btn.disabled = true;
    try {
        const resp = await apiFetch(apiUrl('/api/memories/SOUL.md'), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content }),
        });
        if (resp.ok) {
            showToast('本机 SOUL 已保存');
            // Switch back to preview
            showPreviewMode();
            updateSoulStatus('success', `本机 SOUL · ${content.length} 字符 · 已保存`);
        } else {
            showToast('保存失败');
        }
    } catch (e) {
        showToast('保存失败: ' + e.message);
    } finally {
        btn.textContent = '保存';
        btn.disabled = false;
    }
}

// ── Memory & User file editing ────────────────────────────────────

const _memoryEditors = {};

function getMemoryEditorId(filename) {
    return filename === 'MEMORY.md' ? 'memoryMemoryEditor' : 'memoryUserEditor';
}

function getPreviewId(filename) {
    return filename === 'MEMORY.md' ? 'memoryMemory' : 'memoryUser';
}

export function toggleMemoryEdit(filename) {
    const editorId = getMemoryEditorId(filename);
    const previewId = getPreviewId(filename);
    const preview = document.getElementById(previewId);
    const wrap = document.getElementById(editorId + 'Wrap');
    const editBtn = document.querySelector(`[onclick="toggleMemoryEdit('${filename}')"]`);
    const cancelBtn = document.querySelector(`[onclick="cancelMemoryEdit('${filename}')"]`);
    const saveBtn = document.querySelector(`[onclick="saveMemoryFile('${filename}')"]`);
    if (!preview || !wrap) return;

    // Destroy previous editor for this file
    if (_memoryEditors[filename]) {
        _memoryEditors[filename].toTextArea();
    }

    preview.classList.add('hidden');
    wrap.classList.remove('hidden');
    if (editBtn) editBtn.classList.add('hidden');
    if (cancelBtn) cancelBtn.classList.remove('hidden');
    if (saveBtn) saveBtn.classList.remove('hidden');

    const textarea = document.getElementById(editorId);
    // Load current content from the preview's text
    textarea.value = preview.textContent || '';

    _memoryEditors[filename] = new EasyMDE({
        element: textarea,
        autofocus: false,
        spellChecker: false,
        forceSync: true,
        status: false,
        toolbar: ['bold', 'italic', 'heading', '|', 'quote', 'unordered-list', 'ordered-list', '|', 'code', 'horizontal-rule', '|', 'preview', 'guide'],
        renderingConfig: { singleLineBreaks: true, codeSyntaxHighlighting: false },
    });
}

export function cancelMemoryEdit(filename) {
    const editorId = getMemoryEditorId(filename);
    const previewId = getPreviewId(filename);
    const preview = document.getElementById(previewId);
    const wrap = document.getElementById(editorId + 'Wrap');
    const editBtn = document.querySelector(`[onclick="toggleMemoryEdit('${filename}')"]`);
    const cancelBtn = document.querySelector(`[onclick="cancelMemoryEdit('${filename}')"]`);
    const saveBtn = document.querySelector(`[onclick="saveMemoryFile('${filename}')"]`);

    if (_memoryEditors[filename]) {
        _memoryEditors[filename].toTextArea();
        delete _memoryEditors[filename];
    }

    preview.classList.remove('hidden');
    wrap.classList.add('hidden');
    if (editBtn) editBtn.classList.remove('hidden');
    if (cancelBtn) cancelBtn.classList.add('hidden');
    if (saveBtn) saveBtn.classList.add('hidden');
}

export async function saveMemoryFile(filename) {
    const editor = _memoryEditors[filename];
    if (!editor) return;
    const content = editor.value();
    const saveBtn = document.querySelector(`[onclick="saveMemoryFile('${filename}')"]`);
    if (saveBtn) { saveBtn.textContent = '保存中...'; saveBtn.disabled = true; }
    try {
        const resp = await apiFetch(apiUrl(`/api/memories/${filename}`), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content }),
        });
        if (resp.ok) {
            showToast(`${filename} 已保存`);
            // Reload preview with filtered text
            const previewId = getPreviewId(filename);
            const preview = document.getElementById(previewId);
            if (preview) preview.textContent = stripMarkdown(content);
            cancelMemoryEdit(filename);
        } else {
            showToast('保存失败');
        }
    } catch (e) {
        showToast('保存失败: ' + e.message);
    } finally {
        if (saveBtn) { saveBtn.textContent = '保存'; saveBtn.disabled = false; }
    }
}

// ── Legacy exports ──────────────────────────────────────────────

export function editMemory(path) { showToast('编辑 ' + path); }

// ── Window Exports ──────────────────────────────────────────────

window.loadMemories = loadMemories;
App.loadMemories = loadMemories;
window.switchSoulTab = switchSoulTab;
App.switchSoulTab = switchSoulTab;
window.saveSoul = saveSoul;
App.saveSoul = saveSoul;
window.toggleSoulEditMode = toggleSoulEditMode;
App.toggleSoulEditMode = toggleSoulEditMode;
window.cancelSoulEdit = cancelSoulEdit;
App.cancelSoulEdit = cancelSoulEdit;
window.toggleMemoryEdit = toggleMemoryEdit;
App.toggleMemoryEdit = toggleMemoryEdit;
window.cancelMemoryEdit = cancelMemoryEdit;
App.cancelMemoryEdit = cancelMemoryEdit;
window.saveMemoryFile = saveMemoryFile;
App.saveMemoryFile = saveMemoryFile;
window.editMemory = editMemory;
App.editMemory = editMemory;
window.snapshotMemory = window.snapshotMemory || (() => {});
App.snapshotMemory = window.snapshotMemory;
window.openExtractModal = window.openExtractModal || (() => {});
App.openExtractModal = window.openExtractModal;

window.memoriesModule = { loadMemories };
App.memoriesModule = { loadMemories };
