/**
 * Hermes WebUI - Skills Module
 * 参考 Directus + Open WebUI + LobeChat 的设计模式重写
 * 技能管理：分类展示、搜索筛选、启用/禁用、创建、导入
 */

globalThis.App = globalThis.App || {};
const App = globalThis.App;

import { apiFetch, apiUrl } from './api.js';
import { state } from './state.js';
import { escapeHtml, showToast } from './utils.js';

let _currentTab = 'system';
let _allSkills = { system: [], custom: [], installed: [] };

// ── Load / Render ────────────────────────────────────────────────

export async function loadSkills() {
    try {
        const resp = await apiFetch(apiUrl('/api/skills'));
        const data = await resp.json();
        _allSkills = data.skills || { system: [], custom: [], installed: [] };
        renderCurrentTab();
    } catch (e) {
        console.error('Load skills failed:', e);
    }
}

function renderCurrentTab() {
    const skills = _allSkills[_currentTab] || [];
    const search = (document.getElementById('skillsSearch')?.value || '').toLowerCase();
    const filtered = search ? skills.filter(s =>
        (s.name || s.id).toLowerCase().includes(search) ||
        (s.description || '').toLowerCase().includes(search)
    ) : skills;

    const container = document.getElementById('skillsContainer');
    if (!container) return;
    container.innerHTML = '';

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="flex flex-col items-center justify-center py-16 text-on-surface-variant/40">
                <span class="material-symbols-outlined text-4xl mb-3">extension_off</span>
                <p class="text-sm font-bold">${search ? '没有匹配的技能' : '暂无' + tabLabel(_currentTab)}</p>
                <p class="text-xs mt-1 opacity-60">${search ? '试试其他关键词' : '点击右上角"创建技能"开始'}</p>
            </div>`;
        return;
    }

    filtered.forEach(skill => {
        const card = document.createElement('div');
        card.className = 'skill-card bg-surface-container-lowest rounded-xl border border-outline-variant/10 hover:border-outline-variant/30 transition-all';
        card.innerHTML = `
            <div class="flex items-center gap-4 px-5 py-4">
                <!-- Icon -->
                <div class="w-10 h-10 rounded-xl bg-surface-container-high flex items-center justify-center shrink-0">
                    <span class="material-symbols-outlined text-[18px] text-primary/60">auto_awesome</span>
                </div>
                <!-- Info -->
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                        <h4 class="font-bold text-sm text-on-surface truncate">${escapeHtml(skill.name || skill.id)}</h4>
                        <span class="text-[9px] px-2 py-0.5 rounded-full font-bold shrink-0 ${_currentTab === 'system' ? 'bg-primary/10 text-primary/70' : _currentTab === 'custom' ? 'bg-[#34c759]/10 text-[#34c759]' : 'bg-[#007aff]/10 text-[#007aff]'}">${tabLabel(_currentTab)}</span>
                    </div>
                    <p class="text-xs text-on-surface-variant/60 mt-0.5 line-clamp-1">${escapeHtml(skill.description || '暂无描述')}</p>
                </div>
                <!-- Actions -->
                <div class="flex items-center gap-2 shrink-0">
                    <button onclick="toggleSkill('${skill.id}')" class="w-8 h-8 rounded-lg bg-surface-container-high hover:bg-surface-container-highest flex items-center justify-center transition-all text-on-surface-variant/50 hover:text-on-surface" title="启用/禁用">
                        <span class="material-symbols-outlined text-[14px] skill-toggle-icon">toggle_off</span>
                    </button>
                    ${_currentTab !== 'system' ? `
                    <button onclick="deleteSkill('${skill.id}')" class="w-8 h-8 rounded-lg bg-error/5 hover:bg-error/15 flex items-center justify-center transition-all text-error/50 hover:text-error" title="删除">
                        <span class="material-symbols-outlined text-[14px]">delete</span>
                    </button>` : ''}
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

function tabLabel(type) {
    return type === 'system' ? '系统内置' : type === 'custom' ? '自建' : '已安装';
}

// ── Tab switching ────────────────────────────────────────────────

export function switchSkillTab(type) {
    _currentTab = type;
    document.querySelectorAll('.skill-tab').forEach(el => {
        const active = el.dataset.skillType === type;
        el.classList.toggle('bg-primary', active);
        el.classList.toggle('text-on-primary', active);
        el.classList.toggle('text-on-surface-variant', !active);
        el.classList.toggle('hover:bg-surface-container-highest', !active);
    });
    renderCurrentTab();
}

// ── Search ───────────────────────────────────────────────────────

export function filterSkills() {
    renderCurrentTab();
}

// ── Create / Toggle / Delete ─────────────────────────────────────

export function showCreateSkillModal() {
    showToast('创建技能功能开发中');
}

export async function toggleSkill(skillId) {
    try {
        const resp = await apiFetch(apiUrl(`/api/skills/${encodeURIComponent(skillId)}/toggle`), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: true }),
        });
        if (resp.ok) {
            showToast(`技能 "${skillId}" 已切换`);
            loadSkills();
        }
    } catch (e) {
        showToast('切换失败: ' + e.message);
    }
}

export async function deleteSkill(skillId) {
    if (!confirm(`确定删除技能 "${skillId}" 吗？此操作不可恢复。`)) return;
    try {
        const resp = await apiFetch(apiUrl(`/api/skills/${encodeURIComponent(skillId)}`), { method: 'DELETE' });
        if (resp.ok) {
            showToast('技能已删除');
            loadSkills();
        }
    } catch (e) {
        showToast('删除失败: ' + e.message);
    }
}

// ── Import ───────────────────────────────────────────────────────

export function importSkill(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.zip')) {
        showToast('请选择 .zip 文件');
        return;
    }
    const formData = new FormData();
    formData.append('file', file);
    apiFetch(apiUrl('/api/skills/import'), { method: 'POST', body: formData })
        .then(r => {
            if (r.ok) {
                showToast('技能导入成功');
                loadSkills();
            } else {
                return r.json().then(err => { throw new Error(err.detail || '导入失败'); });
            }
        })
        .catch(e => showToast('导入失败: ' + e.message));
    event.target.value = '';
}

// ── Window Exports ──────────────────────────────────────────────

window.loadSkills = loadSkills;
App.loadSkills = loadSkills;
window.switchSkillTab = switchSkillTab;
App.switchSkillTab = switchSkillTab;
window.filterSkills = filterSkills;
App.filterSkills = filterSkills;
window.showCreateSkillModal = showCreateSkillModal;
App.showCreateSkillModal = showCreateSkillModal;
window.toggleSkill = toggleSkill;
App.toggleSkill = toggleSkill;
window.deleteSkill = deleteSkill;
App.deleteSkill = deleteSkill;
window.importSkill = importSkill;
App.importSkill = importSkill;

window.skillsModule = { loadSkills, switchSkillTab, filterSkills };
App.skillsModule = { loadSkills, switchSkillTab, filterSkills };
