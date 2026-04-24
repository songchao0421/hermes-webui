/**
 * Hermes WebUI - Utility Functions
 */

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

// ── Window exports (for HTML onclick compatibility) ─────────────
window.autoResize = autoResize;
window.showToast = showToast;
window.escapeHtml = escapeHtml;
window.scrollToBottom = scrollToBottom;
