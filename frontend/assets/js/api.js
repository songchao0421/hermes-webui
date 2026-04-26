/**
 * Hermes WebUI — API Client (V2.0)
 * Centralized API calls with auth token injection.
 * Dropped: model listing, routing, plain chat, update checks.
 */
globalThis.App = globalThis.App || {};
const App = globalThis.App;
import { escapeHtml, showToast } from './utils.js';
import { state } from './state.js';

const API_BASE = (window.location.protocol === 'file:') ? 'http://localhost:8080' : '';

export function apiUrl(path) {
    return API_BASE + path;
}

// ── Authentication ──────────────────────────────────────────────

export function getAuthToken() {
    return localStorage.getItem('hermes_webui_token') || '';
}

export function setAuthToken(token) {
    localStorage.setItem('hermes_webui_token', token);
}

function authHeaders(extra = {}) {
    const token = getAuthToken();
    const headers = { ...extra };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    return headers;
}

export async function apiFetch(url, options = {}) {
    options.headers = authHeaders(options.headers || {});
    try {
        const resp = await fetch(url, options);
        if (resp.status === 401) {
            window.dispatchEvent(new CustomEvent('auth-required'));
            throw new Error('Authentication required');
        }
        if (!resp.ok) {
            const errBody = await resp.json().catch(() => ({}));
            const detail = errBody.detail || errBody.error || resp.statusText;
            window.dispatchEvent(new CustomEvent('api-error', {
                detail: { message: detail, status: resp.status, url },
            }));
            throw new Error(detail);
        }
        return resp;
    } catch (e) {
        if (e.name === 'TypeError' && e.message.includes('fetch')) {
            // Network error — server unreachable
            window.dispatchEvent(new CustomEvent('api-error', {
                detail: { message: '无法连接服务器，请检查后端是否运行', status: 0, url },
            }));
        }
        throw e; // let callers also handle it
    }
}

export function showAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) modal.classList.remove('hidden');
}

export function hideAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) modal.classList.add('hidden');
}

export async function submitAuthToken() {
    const input = document.getElementById('authTokenInput');
    const token = input?.value?.trim();
    if (!token) { showToast('请输入 Access Token'); return; }
    setAuthToken(token);
    hideAuthModal();
    location.reload();
}

// ── Agent / Chat ────────────────────────────────────────────────

/**
 * POST /api/agent/stream — start an SDK-streaming conversation turn.
 * Returns a Response whose body is an SSE stream.
 */
export async function agentStream(message, { sessionId, systemMessage, history, fileIds } = {}) {
    return apiFetch(apiUrl('/api/agent/stream'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message,
            session_id: sessionId,
            system_message: systemMessage,
            history,
            file_ids: fileIds,
        }),
    });
}

/**
 * POST /api/agent/abort — abort the running conversation.
 */
export async function agentAbort() {
    return apiFetch(apiUrl('/api/agent/abort'), { method: 'POST' });
}

// ── Persona ─────────────────────────────────────────────────────

export async function getPersona() {
    const resp = await apiFetch(apiUrl('/api/persona'));
    return resp.json();
}

export async function updatePersona(updates) {
    const resp = await apiFetch(apiUrl('/api/persona'), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
    });
    return resp.json();
}

export async function uploadAvatar(file, type = 'agent') {
    const formData = new FormData();
    formData.append('file', file);
    if (type === 'user') formData.append('type', 'user');
    const resp = await apiFetch(apiUrl('/api/persona/avatar'), { method: 'POST', body: formData });
    return resp.json();
}

// ── Memories ───────────────────────────────────────────────────

export async function getMemories() {
    const resp = await apiFetch(apiUrl('/api/memories'));
    return resp.json();
}

export async function updateMemory(filename, content) {
    const resp = await apiFetch(apiUrl(`/api/memories/${filename}`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
    });
    return resp.json();
}

// ── Skills ──────────────────────────────────────────────────────

export async function getSkills() {
    const resp = await apiFetch(apiUrl('/api/skills'));
    return resp.json();
}

export async function importSkillZip(file) {
    const formData = new FormData();
    formData.append('file', file);
    const resp = await apiFetch(apiUrl('/api/skills/import'), { method: 'POST', body: formData });
    return resp.json();
}

// ── Sessions ────────────────────────────────────────────────────

export async function getSessions() {
    const resp = await apiFetch(apiUrl('/api/sessions'));
    return resp.json();
}

export async function createSession() {
    const resp = await apiFetch(apiUrl('/api/sessions/new'), { method: 'POST' });
    return resp.json();
}

export async function deleteSession(sessionId) {
    const resp = await apiFetch(apiUrl(`/api/sessions/${sessionId}`), { method: 'DELETE' });
    return resp.json();
}

export async function getSessionMessages(sessionId) {
    const resp = await apiFetch(apiUrl(`/api/sessions/${sessionId}/messages`));
    return resp.json();
}

// ── Session operations (undo / retry / rename) ────────────────

/**
 * POST /api/agent/session/undo — remove the last user+assistant message pair.
 */
export async function sessionUndo(sessionId) {
    return apiFetch(apiUrl('/api/agent/session/undo'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
    });
}

/**
 * POST /api/agent/session/retry — undo + re-send the last user message.
 */
export async function sessionRetry(sessionId) {
    const resp = await apiFetch(apiUrl('/api/agent/session/retry'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
    });
    return resp.json();
}

/**
 * POST /api/agent/session/rename — rename a conversation session.
 */
export async function sessionRename(sessionId, title) {
    return apiFetch(apiUrl('/api/agent/session/rename'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, title }),
    });
}

// ── Window Exports ──────────────────────────────────────────────

// ── Model Switching ────────────────────────────────────────────

/**
 * GET /api/models/profiles — list all model profiles.
 */
export async function getModelProfiles() {
    const resp = await apiFetch(apiUrl('/api/models/profiles'));
    return resp.json();
}

/**
 * POST /api/models/switch — switch to a model profile.
 */
export async function switchModel(profileId) {
    const resp = await apiFetch(apiUrl('/api/models/switch'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_id: profileId }),
    });
    return resp.json();
}

/**
 * GET /api/models/active — get the currently active model.
 */
export async function getActiveModel() {
    const resp = await apiFetch(apiUrl('/api/models/active'));
    return resp.json();
}

/**
 * POST /api/models/discover — query local Ollama for new models.
 */
export async function discoverModels() {
    const resp = await apiFetch(apiUrl('/api/models/discover'), { method: 'POST' });
    return resp.json();
}

window.apiUrl = apiUrl;
App.apiUrl = apiUrl;
window.apiFetch = apiFetch;
App.apiFetch = apiFetch;
window.getAuthToken = getAuthToken;
App.getAuthToken = getAuthToken;
window.setAuthToken = setAuthToken;
App.setAuthToken = setAuthToken;
window.showAuthModal = showAuthModal;
App.showAuthModal = showAuthModal;
window.hideAuthModal = hideAuthModal;
App.hideAuthModal = hideAuthModal;
window.submitAuthToken = submitAuthToken;
App.submitAuthToken = submitAuthToken;
window.getPersona = getPersona;
App.getPersona = getPersona;
window.updatePersona = updatePersona;
App.updatePersona = updatePersona;
window.uploadAvatar = uploadAvatar;
App.uploadAvatar = uploadAvatar;
window.agentStream = agentStream;
App.agentStream = agentStream;
window.agentAbort = agentAbort;
App.agentAbort = agentAbort;
window.getMemories = getMemories;
App.getMemories = getMemories;
window.updateMemory = updateMemory;
App.updateMemory = updateMemory;
window.getSkills = getSkills;
App.getSkills = getSkills;
window.importSkillZip = importSkillZip;
App.importSkillZip = importSkillZip;
window.getSessions = getSessions;
App.getSessions = getSessions;
window.createSession = createSession;
App.createSession = createSession;
window.deleteSession = deleteSession;
App.deleteSession = deleteSession;
window.getSessionMessages = getSessionMessages;
App.getSessionMessages = getSessionMessages;
window.sessionUndo = sessionUndo;
App.sessionUndo = sessionUndo;
window.sessionRetry = sessionRetry;
App.sessionRetry = sessionRetry;
window.sessionRename = sessionRename;
App.sessionRename = sessionRename;
window.getModelProfiles = getModelProfiles;
App.getModelProfiles = getModelProfiles;
window.switchModel = switchModel;
App.switchModel = switchModel;
window.getActiveModel = getActiveModel;
App.getActiveModel = getActiveModel;
window.discoverModels = discoverModels;
App.discoverModels = discoverModels;

// ── Task Routing ────────────────────────────────────────────────

/**
 * GET /api/agent/routing/status — get current routing status for LED indicator.
 */
export async function getRoutingStatus() {
    const resp = await apiFetch(apiUrl('/api/agent/routing/status'));
    return resp.json();
}

/**
 * POST /api/agent/routing/correct — record a user correction for learning.
 */
export async function correctRouting(originalTier, correctedTier, message) {
    return apiFetch(apiUrl('/api/agent/routing/correct'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ original_tier: originalTier, corrected_tier: correctedTier, message }),
    });
}

window.getRoutingStatus = getRoutingStatus;
App.getRoutingStatus = getRoutingStatus;
window.correctRouting = correctRouting;
App.correctRouting = correctRouting;

// ── Update (Self-Upgrade) ─────────────────────────────────────

/**
 * GET /api/update/check — check for new version on GitHub.
 */
export async function checkUpdate() {
    const resp = await apiFetch(apiUrl('/api/update/check'));
    return resp.json();
}

/**
 * POST /api/update/apply — pull latest + install deps + restart.
 * Returns an SSE stream. Caller must read the response body.
 */
export async function applyUpdate() {
    return apiFetch(apiUrl('/api/update/apply'), { method: 'POST' });
}

window.checkUpdate = checkUpdate;
App.checkUpdate = checkUpdate;
window.applyUpdate = applyUpdate;
App.applyUpdate = applyUpdate;