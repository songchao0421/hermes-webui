/**
 * Hermes WebUI - Theme Engine
 * Dynamic theme color application via CSS variables.
 */

export function applyThemeColor(accentColor) {
    const root = document.documentElement;
    root.style.setProperty('--theme-primary', accentColor);
    const dimColor = adjustBrightness(accentColor, -40);
    root.style.setProperty('--theme-primary-dim', dimColor);
}

export function adjustBrightness(hex, percent) {
    const num = parseInt(hex.replace('#', ''), 16);
    const amt = Math.round(2.55 * percent);
    const R = Math.max(0, Math.min(255, (num >> 16) + amt));
    const G = Math.max(0, Math.min(255, ((num >> 8) & 0x00FF) + amt));
    const B = Math.max(0, Math.min(255, (num & 0x0000FF) + amt));
    return '#' + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
}

export function hexToTint(hex, ratio) {
    hex = hex.replace('#', '');
    if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    const baseR = 28, baseG = 28, baseB = 32;
    return `rgb(${Math.round(r * ratio + baseR * (1 - ratio))},${Math.round(g * ratio + baseG * (1 - ratio))},${Math.round(b * ratio + baseB * (1 - ratio))})`;
}
