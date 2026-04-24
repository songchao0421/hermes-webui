/**
 * Hermes WebUI - Main Entry Point
 * Imports all modules and handles DOMContentLoaded initialization.
 * Each module exports its own functions to window for HTML onclick compatibility.
 */

// ── Module imports ───────────────────────────────────────────────
// Each module handles its own window.fn = fn assignments internally.

import '/assets/js/api.js';
import '/assets/js/state.js';
import '/assets/js/persona.js';
import '/assets/js/settings.js';
import '/assets/js/skills.js';
import '/assets/js/memories.js';
import '/assets/js/sessions.js';
import '/assets/js/chat.js';
import '/assets/js/voice.js';
import '/assets/js/extract.js';
import '/assets/js/utils.js';
import '/assets/js/theme.js';
import '/assets/js/tool_panel.js';

// ── DOM Ready — ES modules are deferred, DOM is already parsed ──
// Load persona and update UI
if (typeof window.loadPersona === 'function') {
    window.loadPersona();
}

// Load session list
if (typeof window.loadSessionList === 'function') {
    window.loadSessionList();
}

// Initialize memory keyboard shortcuts
if (typeof window.setupKeyboardShortcuts === 'function') {
    window.setupKeyboardShortcuts();
}

// Initialize notifications
if (typeof window.initNotifications === 'function') {
    window.initNotifications();
}

// Initialize model selector
if (typeof window.initModelSelector === 'function') {
    window.initModelSelector();
}

// Poll initial routing status for LED indicator
if (typeof window.pollRoutingStatus === 'function') {
    setTimeout(window.pollRoutingStatus, 1000);
    setInterval(window.pollRoutingStatus, 30000);
}
