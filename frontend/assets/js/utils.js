/**
 * Hermes WebUI - Utility Functions
 */
globalThis.App = globalThis.App || {};
const App = globalThis.App;

export function escapeHtml(text) {
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}

export function showToast(msg) {
    const toast = document.getElementById('saveToast');
    document.getElementById('saveToastText').textContent = msg;
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-20px)';
    }, 2000);
}

export function scrollToBottom() {
    const chatTab = document.getElementById('tabChat');
    if (chatTab) {
        chatTab.scrollTo({ top: chatTab.scrollHeight, behavior: 'smooth' });
    }
}

export function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 128) + 'px';
}

// ── Global error notification ───────────────────────────────────

let _notifTimer = null;

window.showNotification = function showNotification(msg, type = 'error', duration = 6000) {
    const bar = document.getElementById('notificationBar');
    if (!bar) return;
    if (_notifTimer) clearTimeout(_notifTimer);

    const icon = document.getElementById('notificationIcon');
    const text = document.getElementById('notificationText');

    const configs = {
        error:   { icon: 'error',        cls: 'bg-error-container text-on-error border-error/20' },
        warning: { icon: 'warning',      cls: 'bg-tertiary-container text-on-tertiary border-tertiary/20' },
        success: { icon: 'check_circle', cls: 'bg-primary-container text-on-primary border-primary/20' },
        info:    { icon: 'info',         cls: 'bg-secondary-container text-on-secondary border-secondary/20' },
    };
    const cfg = configs[type] || configs.error;

    icon.textContent = cfg.icon;
    text.textContent = msg;
    // Strip old color classes, add new ones
    ['bg-error-container', 'bg-tertiary-container', 'bg-primary-container', 'bg-secondary-container',
     'text-on-error', 'text-on-tertiary', 'text-on-primary', 'text-on-secondary',
     'border-error/20', 'border-tertiary/20', 'border-primary/20', 'border-secondary/20',
    ].forEach(c => bar.classList.remove(c));
    bar.classList.add(...cfg.cls.split(' '));
    bar.classList.remove('hidden');
    bar.style.transform = 'translateX(-50%) translateY(0)';
    bar.style.opacity = '1';

    if (duration > 0) {
        _notifTimer = setTimeout(dismissNotification, duration);
    }
};

window.dismissNotification = function dismissNotification() {
    const bar = document.getElementById('notificationBar');
    if (!bar) return;
    bar.style.transform = 'translateX(-50%) translateY(100px)';
    bar.style.opacity = '0';
    if (_notifTimer) {
        clearTimeout(_notifTimer);
        _notifTimer = null;
    }
    setTimeout(() => bar.classList.add('hidden'), 500);
};

// ── Listen for apiFetch errors ──────────────────────────────────
document.addEventListener('api-error', (e) => {
    const { message, status, url } = e.detail;
    const short = status ? `${status}: ${message}` : message;
    showNotification(short, 'error', 6000);
});

// ── Window exports (for HTML onclick compatibility) ─────────────
window.autoResize = autoResize;
App.autoResize = autoResize;
window.showToast = showToast;
App.showToast = showToast;
window.escapeHtml = escapeHtml;
App.escapeHtml = escapeHtml;
window.scrollToBottom = scrollToBottom;
App.scrollToBottom = scrollToBottom;