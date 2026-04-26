/**
 * Hermes WebUI — Voice Input Module (V2.0)
 * Web Speech API with visual feedback: waveform animation,
 * recording indicator, auto-send on release.
 * Exports to window for HTML onclick compatibility.
 */
globalThis.App = globalThis.App || {};
const App = globalThis.App;
import { state } from './state.js';
import { showToast } from './utils.js';

let recognition = null;
let isListening = false;

export function toggleVoiceInput(btn) {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        showToast('浏览器不支持语音输入', 'warning');
        return;
    }
    if (isListening) {
        stopVoiceInput();
        return;
    }
    _startVoice();
}

// ── Start ────────────────────────────────────────────────────

function _startVoice() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.lang = state.persona?.voice_lang || 'zh-CN';
    recognition.continuous = true;
    recognition.interimResults = true;

    const msgInput = document.getElementById('messageInput');
    const voiceBtn = document.getElementById('voiceBtn');

    recognition.onresult = (e) => {
        let finalText = '';
        let interimText = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
            if (e.results[i].isFinal) {
                finalText += e.results[i][0].transcript;
            } else {
                interimText += e.results[i][0].transcript;
            }
        }
        if (msgInput) {
            if (finalText) {
                msgInput.value += finalText + ' ';
            }
            msgInput.placeholder = interimText
                ? '🎤 ' + interimText + '…'
                : '🎤 正在聆听...';
            msgInput.dispatchEvent(new Event('input'));
        }
    };

    recognition.onend = () => {
        if (isListening && recognition) {
            try { recognition.start(); } catch (_) { }
        }
    };

    recognition.onerror = (e) => {
        if (e.error === 'no-speech' || e.error === 'aborted') return;
        _stopVisualFeedback(voiceBtn, msgInput);
        showToast('语音识别错误: ' + e.error, 'error');
    };

    recognition.start();
    isListening = true;
    _startVisualFeedback(voiceBtn, msgInput);
}

// ── Visual Feedback ──────────────────────────────────────────

function _createWaveform() {
    let wave = document.getElementById('voiceWaveform');
    if (wave) return wave;
    wave = document.createElement('div');
    wave.id = 'voiceWaveform';
    wave.className = 'fixed inset-0 z-[400] pointer-events-none flex items-center justify-center';
    wave.innerHTML = [
        '<div class="voice-wave-container flex items-center justify-center gap-[3px]">',
        ...Array.from({ length: 7 }, (_, i) =>
            `<div class="voice-bar w-[4px] rounded-full bg-primary/60 animate-voice-wave" style="animation-delay:${i * 0.12}s"></div>`
        ),
        '</div>',
    ].join('');
    document.body.appendChild(wave);
    return wave;
}

function _removeWaveform() {
    const wave = document.getElementById('voiceWaveform');
    if (wave) wave.remove();
}

function _startVisualFeedback(voiceBtn, msgInput) {
    if (voiceBtn) {
        voiceBtn.classList.add('recording');
        voiceBtn.classList.add('animate-pulse');
    }
    if (msgInput) msgInput.placeholder = '🎤 正在聆听...';
    _createWaveform();
}

function _stopVisualFeedback(voiceBtn, msgInput) {
    if (voiceBtn) {
        voiceBtn.classList.remove('recording');
        voiceBtn.classList.remove('animate-pulse');
        const icon = voiceBtn.querySelector('.material-symbols-outlined');
        if (icon) icon.textContent = 'mic';
    }
    if (msgInput) {
        msgInput.placeholder = state.persona?.input_placeholder || '输入消息...';
    }
    _removeWaveform();
    isListening = false;
    if (recognition) {
        try { recognition.stop(); } catch (_) { }
        recognition = null;
    }
}

// ── Stop ─────────────────────────────────────────────────────

export function stopVoiceInput() {
    const voiceBtn = document.getElementById('voiceBtn');
    const msgInput = document.getElementById('messageInput');
    _stopVisualFeedback(voiceBtn, msgInput);
}

// ── Push-to-Talk (press & hold) ──────────────────────────────

export function voicePressStart(event) {
    event.preventDefault();
    const voiceBtn = document.getElementById('voiceBtn');
    if (voiceBtn) {
        const icon = voiceBtn.querySelector('.material-symbols-outlined');
        if (icon) icon.textContent = 'mic_off';
    }
    if (!recognition || !isListening) {
        _startVoice();
    }
}

export function voicePressEnd(event) {
    event.preventDefault();
    stopVoiceInput();
    const msgInput = document.getElementById('messageInput');
    if (msgInput && msgInput.value.trim()) {
        window.sendMessage();
    }
}

// ── Window exports ──────────────────────────────────────────
window.toggleVoiceInput = toggleVoiceInput;
App.toggleVoiceInput = toggleVoiceInput;
window.voicePressStart = voicePressStart;
App.voicePressStart = voicePressStart;
window.voicePressEnd = voicePressEnd;
App.voicePressEnd = voicePressEnd;