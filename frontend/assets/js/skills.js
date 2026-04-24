/**
 * Hermes WebUI - Skills Module
 * Skill management: list, create, edit, delete skills.
 * Window-exported for HTML onclick compatibility.
 */

import { apiFetch, apiUrl } from './api.js';
import { state } from './state.js';
import { escapeHtml, showToast } from './utils.js';

// ── Skills ──────────────────────────────────────────────────────

export async function loadSkills() {
    try {
        const resp = await apiFetch(apiUrl('/api/skills'));
        const data = await resp.json();
        renderSkills(data);
    } catch (e) { console.error('Load skills failed:', e); }
}

export function renderSkills(skills) {
    const container = document.getElementById('skillsList');
    if (!container) return;
    container.innerHTML = '';
    if (!skills || skills.length === 0) {
        container.innerHTML = '<div class="text-center text-on-surface-variant/50 py-12 text-sm">No skills yet. Click + to create one.</div>';
        return;
    }
    skills.forEach(skill => {
        const card = document.createElement('div');
        card.className = 'p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/20 hover:border-outline-variant/40 transition-all';
        card.innerHTML = `
            <div class="flex items-start justify-between">
                <div class="flex-1 min-w-0">
                    <h4 class="font-bold text-sm text-on-surface truncate">${escapeHtml(skill.name)}</h4>
                    <p class="text-xs text-on-surface-variant/70 mt-1 line-clamp-2">${escapeHtml(skill.description || '')}</p>
                </div>
                <div class="flex items-center gap-1 ml-2 shrink-0">
                    <button onclick="useSkill('${skill.id}')" class="w-8 h-8 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 flex items-center justify-center transition-colors" title="Use">
                        <span class="material-symbols-outlined text-[14px]">play_arrow</span>
                    </button>
                    <button onclick="showDeleteSkillConfirm('${skill.id}')" class="w-8 h-8 rounded-lg bg-error/10 text-error hover:bg-error/20 flex items-center justify-center transition-colors" title="Delete">
                        <span class="material-symbols-outlined text-[14px]">delete</span>
                    </button>
                </div>
            </div>
            <div class="text-[10px] text-on-surface-variant/40 mt-2">${escapeHtml(skill.id)}</div>
        `;
        container.appendChild(card);
    });
}

export function useSkill(skillId) {
    // Import dynamically to avoid circular dependency
    const sessions = document.querySelector('[data-tab="sessions"]');
    if (sessions) sessions.click();

    state.messageInput.value = `Use skill ${skillId}: `;
    state.messageInput.focus();

    // Switch to chat tab
    const chatTab = document.getElementById('tabChat');
    const chatNav = document.querySelector('[data-tab="chat"]');
    if (chatNav) chatNav.click();
}

export function showNewSkillModal() {
    document.getElementById('skillName').value = '';
    document.getElementById('skillDescription').value = '';
    document.getElementById('skillPrompt').value = '';
    document.getElementById('skillModalTitle').textContent = 'New Skill';
    document.getElementById('skillModal').classList.remove('hidden');
    document.getElementById('skillName').focus();
}

export function hideSkillModal() {
    document.getElementById('skillModal').classList.add('hidden');
}

export async function saveSkill() {
    const name = document.getElementById('skillName')?.value?.trim();
    const description = document.getElementById('skillDescription')?.value?.trim();
    const prompt = document.getElementById('skillPrompt')?.value?.trim();
    if (!name || !prompt) { showToast('Name and prompt are required'); return; }

    try {
        const resp = await apiFetch(apiUrl('/api/skills'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description, prompt }),
        });
        if (resp.ok) {
            showToast('Skill created!');
            hideSkillModal();
            loadSkills();
        } else {
            const err = await resp.json().catch(() => ({}));
            showToast('Error: ' + (err.detail || resp.status));
        }
    } catch (e) { showToast('Error: ' + e.message); }
}

export function showDeleteSkillConfirm(skillId) {
    if (confirm(`Delete skill "${skillId}"? This cannot be undone.`)) {
        deleteSkill(skillId);
    }
}

export async function deleteSkill(skillId) {
    try {
        const resp = await apiFetch(apiUrl('/api/skills/' + encodeURIComponent(skillId)), { method: 'DELETE' });
        if (resp.ok) {
            showToast('Skill deleted');
            loadSkills();
        } else {
            showToast('Delete failed');
        }
    } catch (e) { showToast('Error: ' + e.message); }
}

// ── Window Exports ──────────────────────────────────────────────

export function showSkillStore() {
    showToast('Skill store is not yet implemented');
}

export function importSkill(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.zip')) {
        showToast('Please select a .zip file');
        return;
    }
    const formData = new FormData();
    formData.append('file', file);
    apiFetch(apiUrl('/api/skills/import'), { method: 'POST', body: formData })
        .then(r => {
            if (r.ok) {
                showToast('Skill imported!');
                loadSkills();
            } else {
                return r.json().then(err => { throw new Error(err.detail || 'Import failed'); });
            }
        })
        .catch(e => showToast('Import failed: ' + e.message));
}

window.loadSkills = loadSkills;
window.renderSkills = renderSkills;
window.useSkill = useSkill;
window.showNewSkillModal = showNewSkillModal;
window.hideSkillModal = hideSkillModal;
window.saveSkill = saveSkill;
window.showDeleteSkillConfirm = showDeleteSkillConfirm;
window.deleteSkill = deleteSkill;
window.showSkillStore = showSkillStore;
window.importSkill = importSkill;
