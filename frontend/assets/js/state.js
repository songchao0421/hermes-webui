/**
 * Hermes WebUI - Global State
 * Centralized reactive state object.
 * Modules import `state` and access state.X directly for internal
 * state that doesn't cross module boundaries.
 *
 * setState(key, value) — unified mutation entry for state that is
 * shared across modules. Provides a single point for future logging,
 * validation, or reactive hooks without requiring a full rewrite.
 */
const App = globalThis.App = globalThis.App || {};

// ── The State Object ────────────────────────────────────────────
// All mutable application state lives here as properties.
// Modules mutate internal state directly (low overhead, no framework).
// For cross-module shared state, prefer setState() for auditability.

const state = {
    // Persona
    persona: {},
    // Current model selection
    currentModel: '',
    // Session management
    currentSessionId: '',
    // Processing lock
    isProcessing: false,
    // Agent state
    HERMES_AVAILABLE: false,
    // Routing
    manualRouteOverride: null,
    routingConfig: null,
    // Agent timer state
    agentStartTime: 0,
    agentElapsedTimer: null,
    agentHeartbeatTimer: null,
    // Abort controller for HTTP stream
    abortController: null,
    // Agent job tracking
    currentAgentJobId: null,
    // UI state
    currentTab: 'chat',
    currentLang: 'zh',
    currentMode: 'auto',
    // Onboarding
    onboardStep: 1,
    onboardTheme: '#ffc676',
    onboardAvatar: null,
    // File upload state
    pendingAgentAvatarFile: null,
    pendingUserAvatarFile: null,
    // Attachments
    currentAttachment: null,
    currentAttachments: [],
    // Session cache
    _allSessions: [],
    // Context menu
    ctxTarget: null,
    // Voice
    voiceRecognition: null,
    isVoiceActive: false,
    _voicePressing: false,
    // Memory editor
    editingMemoryFile: null,
    // Auto-scroll
    autoScrollTimer: null,
    lastSessionRefresh: 0,
    // Token estimate (debounce)
    _tokenEstimateTimer: null,
};

/**
 * Unified state mutation entry point.
 * Use this for cross-module state changes to keep a single
 * place for future logging, validation, or reactive hooks.
 * Direct state.X = Y is still valid for module-local state
 * that doesn't cross module boundaries.
 */
function setState(key, value) {
    if (!(key in state)) {
        console.warn(`setState: unknown key "${key}"`);
    }
    state[key] = value;
}

export { state, setState };

// ── Window & App Exports ────────────────────────────────────────

window.state = state;
// Also export individual variables for inline onclick code that references them directly
window.persona = state.persona;
window.currentModel = () => state.currentModel;
window.currentSessionId = () => state.currentSessionId;
window.isProcessing = () => state.isProcessing;
window.HERMES_AVAILABLE = state.HERMES_AVAILABLE;
window.currentAgentJobId = () => state.currentAgentJobId;
window.abortController = () => state.abortController;

// ── App namespace sync ──────────────────────────────────────────
App.state = state;
Object.defineProperty(App, 'persona', { get: () => state.persona });
Object.defineProperty(App, 'currentModel', { get: () => state.currentModel });
Object.defineProperty(App, 'currentSessionId', { get: () => state.currentSessionId });
Object.defineProperty(App, 'isProcessing', { get: () => state.isProcessing });
Object.defineProperty(App, 'HERMES_AVAILABLE', { get: () => state.HERMES_AVAILABLE });
Object.defineProperty(App, 'currentAgentJobId', { get: () => state.currentAgentJobId });
Object.defineProperty(App, 'abortController', { get: () => state.abortController });