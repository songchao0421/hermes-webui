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

export function getAuthUsername() {
    return localStorage.getItem('hermes_webui_username') || '';
}

export function setAuthUsername(name) {
    localStorage.setItem('hermes_webui_username', name);
}

export function clearAuth() {
    localStorage.removeItem('hermes_webui_token');
    localStorage.removeItem('hermes_webui_username');
}

function authHeaders(extra = {}) {
    const token = getAuthToken();
    const headers = { ...extra };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    return headers;
}

// Login/Register API
export async function apiLogin(username, password) {
    const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || '登录失败');
    return data;
}

export async function apiRegister(username, password) {
    const resp = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || '注册失败');
    return data;
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

export function showLoginForm() {
    document.getElementById('loginForm').classList.remove('hidden');
    document.getElementById('registerForm').classList.add('hidden');
    document.getElementById('authModalTitle').textContent = '员工登录';
    document.getElementById('authModalSub').textContent = '请输入你的账号密码';
    document.getElementById('authError').classList.add('hidden');
}

export function showRegisterForm() {
    document.getElementById('loginForm').classList.add('hidden');
    document.getElementById('registerForm').classList.remove('hidden');
    document.getElementById('authModalTitle').textContent = '注册账号';
    document.getElementById('authModalSub').textContent = '创建你的专属工作空间';
    document.getElementById('regError').classList.add('hidden');
}

export async function submitLogin() {
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    const errEl = document.getElementById('authError');
    if (!username || !password) { errEl.textContent = '请输入用户名和密码'; errEl.classList.remove('hidden'); return; }
    try {
        const result = await apiLogin(username, password);
        setAuthToken(result.token);
        setAuthUsername(result.username);
        hideAuthModal();
        localStorage.setItem('hermes_webui_last_activity', Date.now().toString());
        if (typeof window.startSessionMonitor === 'function') window.startSessionMonitor();
        // 登录成功，不刷新页面，直接使用
    } catch (e) {
        errEl.textContent = e.message;
        errEl.classList.remove('hidden');
    }
}

export async function submitRegister() {
    const username = document.getElementById('regUsername').value.trim();
    const password = document.getElementById('regPassword').value;
    const confirm = document.getElementById('regPasswordConfirm').value;
    const errEl = document.getElementById('regError');
    if (!username) { errEl.textContent = '请输入真实姓名'; errEl.classList.remove('hidden'); return; }
    if (password.length < 4) { errEl.textContent = '密码至少4位'; errEl.classList.remove('hidden'); return; }
    if (password !== confirm) { errEl.textContent = '两次密码不一致'; errEl.classList.remove('hidden'); return; }
    try {
        const result = await apiRegister(username, password);
        setAuthToken(result.token);
        setAuthUsername(result.username);
        // 注册成功，自动切换到登录页让用户手动登录
        showLoginForm();
        document.getElementById('loginUsername').value = username;
        document.getElementById('loginPassword').value = '';
        document.getElementById('loginPassword').focus();
    } catch (e) {
        errEl.textContent = e.message;
        errEl.classList.remove('hidden');
    }
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
window.submitLogin = submitLogin;
App.submitLogin = submitLogin;
window.submitRegister = submitRegister;
App.submitRegister = submitRegister;
window.showLoginForm = showLoginForm;
App.showLoginForm = showLoginForm;
window.showRegisterForm = showRegisterForm;
App.showRegisterForm = showRegisterForm;
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

// ── Session Timeout ──────────────────────────────────────────────

let _sessionTimer = null;
const TIMEOUT_KEY = 'hermes_webui_timeout_minutes';
const LAST_ACTIVITY_KEY = 'hermes_webui_last_activity';

export function getSessionTimeoutMinutes() {
    const v = localStorage.getItem(TIMEOUT_KEY);
    return v ? parseInt(v, 10) : 30;
}

export function saveSessionTimeout() {
    const select = document.getElementById('sessionTimeoutSelect');
    if (!select) return;
    const minutes = parseFloat(select.value);
    localStorage.setItem(TIMEOUT_KEY, String(minutes));
    const msg = document.getElementById('sessionTimeoutMsg');
    if (msg) {
        if (minutes === 0) msg.textContent = '✅ 已保存（永不超时）';
        else if (minutes < 1) msg.textContent = `✅ 已保存（${Math.round(minutes * 60)} 秒无操作自动退出）`;
        else msg.textContent = `✅ 已保存（${minutes} 分钟无操作自动退出）`;
    }
    // Reset activity timer
    localStorage.setItem(LAST_ACTIVITY_KEY, Date.now().toString());
    startSessionMonitor();
}

function _renewActivity() {
    localStorage.setItem(LAST_ACTIVITY_KEY, Date.now().toString());
}

export function startSessionMonitor() {
    if (_sessionTimer) clearInterval(_sessionTimer);
    _sessionTimer = setInterval(() => {
        const token = localStorage.getItem('hermes_webui_token');
        if (!token) return; // Not logged in

        const minutes = getSessionTimeoutMinutes();
        if (minutes <= 0) return; // Never timeout

        const last = parseInt(localStorage.getItem(LAST_ACTIVITY_KEY) || '0', 10);
        const elapsed = (Date.now() - last) / 60000;
        if (elapsed >= minutes) {
            // Timeout — clear auth and show login
            localStorage.removeItem('hermes_webui_token');
            localStorage.removeItem('hermes_webui_username');
            localStorage.removeItem(LAST_ACTIVITY_KEY);
            const modal = document.getElementById('authModal');
            if (modal) modal.classList.remove('hidden');
            if (_sessionTimer) clearInterval(_sessionTimer);
        }
    }, 10000); // Check every 10 seconds
}

// Track user activity — renew on any interaction
['click', 'keydown', 'mousemove', 'touchstart', 'scroll'].forEach(evt => {
    document.addEventListener(evt, _renewActivity, { passive: true });
});

window.saveSessionTimeout = saveSessionTimeout;
App.saveSessionTimeout = saveSessionTimeout;
window.startSessionMonitor = startSessionMonitor;
App.startSessionMonitor = startSessionMonitor;