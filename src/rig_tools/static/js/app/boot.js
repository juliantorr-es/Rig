import { RigLog } from './logging.js';
import { clearProjection, getProjection, setProjection } from './projection-store.js';
import { createIntentDispatcher } from './intent-dispatch.js';
import { connectWebSocket } from './websocket.js';
import { appendProgressEvent, clearProgress, getProgressOperations } from './progress-store.js';
import { buildWidgetRegistry } from '../widgets/registry.js';
import { renderRoot } from './render-root.js';

export const BootState = {
  IDLE: 'IDLE',
  CONNECTING: 'CONNECTING',
  LOADING: 'LOADING',
  READY: 'READY',
  RECONNECTING: 'RECONNECTING',
  ERROR: 'ERROR'
};

let currentState = BootState.IDLE;

export function getBootState() {
  return currentState;
}

function setBootState(newState) {
  console.log(`[BOOT] Transition: ${currentState} -> ${newState}`);
  currentState = newState;
  
  const statusEl = document.getElementById('boot-status');
  if (statusEl) {
    statusEl.textContent = `Status: ${newState.toLowerCase().replace('_', ' ')}...`;
  }

  // Handle Overlay visibility
  let overlay = document.getElementById('rig-reconnect-overlay');
  if (newState === BootState.RECONNECTING || newState === BootState.CONNECTING) {
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'rig-reconnect-overlay';
      overlay.className = 'rig-overlay';
      overlay.innerHTML = `
        <div class="rig-overlay-content">
          <div class="rig-spinner"></div>
          <div class="rig-overlay-text">Establishing runtime connection...</div>
          <div class="rig-overlay-subtext">Rig is stabilizing the environment.</div>
        </div>
      `;
      document.body.appendChild(overlay);
    }
    overlay.style.display = 'flex';
  } else if (overlay) {
    overlay.style.display = 'none';
  }
}

export function bootRigUI() {
  let socket = null;
  const socketRef = { current: null };
  const streamBuffers = {};
  const pendingIntents = new Map();
  const MAX_STREAM_BUFFERS = 10;
  const MAX_BUFFER_BYTES = 10000;
  const sessionToken = new URLSearchParams(window.location.search).get('rig_session');
  const globalLogs = [];
  const lastSequenceNumbers = {};

  setBootState(BootState.CONNECTING);

  function showError(message) {
    const errEl = document.createElement('div');
    errEl.className = 'error-notification';
    errEl.setAttribute('role', 'alert');
    errEl.textContent = message;
    document.body.appendChild(errEl);
    setTimeout(() => errEl.remove(), 5000);
  }

  const dispatcher = createIntentDispatcher({
    projection: getProjection,
    socketRef,
    pendingIntents,
    showError,
    render,
    logger: RigLog,
  });

  clearProgress();

  function truncateText(text, maxLen = 500) {
    if (!text) return '';
    const str = String(text);
    return str.length > maxLen ? str.substring(0, maxLen) + '...' : str;
  }

  const widgetRegistry = buildWidgetRegistry({
    projection: getProjection,
    sendIntent: dispatcher.sendIntent,
    showError,
    globalLogs: () => globalLogs,
    truncateText,
  });

  function handleEvent(data) {
    const type = data.type;
    if (type === 'validator_started') {
      console.log('Validator started:', data.validator_id);
    } else if (type === 'validator_finished') {
      console.log('Validator finished:', data.validator_id, 'status:', data.status);
    } else if (type === 'validator_run_complete') {
      console.log('Validator run complete:', data.status, 'receipt:', data.receipt_id);
    } else if (type === 'validator_config_empty') {
      showError('No validators configured for this workspace');
    } else if (type === 'validator_error') {
      showError(`Validator ${data.validator_id} error: ${data.error || 'Unknown error'}`);
    }
    render();
  }

  function handleStreamChunk(data) {
    if (!data.stream_id || data.sequence === undefined || !data.content || !data.channel) {
      console.warn('Invalid stream chunk: missing required fields');
      return;
    }
    const streamId = data.stream_id;
    const sequence = data.sequence;
    const prevSeq = lastSequenceNumbers[streamId] || 0;
    if (sequence <= prevSeq) {
      console.warn(`Out of order sequence for stream ${streamId}: ${sequence} <= ${prevSeq}`);
      return;
    }
    lastSequenceNumbers[streamId] = sequence;
    const content = data.content || '';
    if (data.channel === 'assistant') {
      if (!streamBuffers[streamId]) {
        streamBuffers[streamId] = { content: '', channel: data.channel || 'assistant' };
      }
      const buffer = streamBuffers[streamId];
      if (buffer.content.length + content.length > MAX_BUFFER_BYTES) {
        buffer.content = buffer.content.substring(0, Math.max(0, MAX_BUFFER_BYTES - content.length - 100));
      }
      buffer.content += content;
    } else {
      const logEntry = `[${data.channel || 'unknown'}] ${content}`;
      globalLogs.push(logEntry);
      if (globalLogs.length > MAX_STREAM_BUFFERS) {
        globalLogs.shift();
      }
    }
    render();
  }

  function renderChat() {
    const inspector = document.getElementById('inspector');
    if (!inspector) return;
    const container = document.createElement('div');
    container.id = 'chat-container';
    const headerSection = document.createElement('section');
    headerSection.className = 'region';
    headerSection.style.padding = '12px';
    headerSection.style.borderBottom = '1px solid var(--border)';
    const h2 = document.createElement('h2');
    h2.textContent = 'Inspector';
    headerSection.appendChild(h2);
    container.appendChild(headerSection);
    const widgetIds = getProjection().layout.regions['inspector'] || [];
    const widgetsDiv = document.createElement('div');
    widgetsDiv.style.flex = '0 0 auto';
    widgetsDiv.style.overflowY = 'auto';
    widgetIds.forEach(widgetId => {
      const widget = getProjection().widgets[widgetId];
      const renderer = widgetRegistry[widget.type] || widgetRegistry._fallback;
      let widgetEl = null;
      try {
        widgetEl = renderer(widgetId, widget.data, widget.actions);
      } catch (error) {
        console.error(`Failed to render inspector widget ${widgetId} (${widget.type}):`, error);
        widgetEl = widgetRegistry._fallback(widget);
      }
      if (widgetEl) widgetsDiv.appendChild(widgetEl);
    });
    container.appendChild(widgetsDiv);
    if (getProjection().chat) {
      const messagesDiv = document.createElement('div');
      messagesDiv.className = 'chat-messages';
      messagesDiv.id = 'chat-messages';
      (getProjection().chat.messages || []).forEach(msg => {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message message-' + (msg.role || 'unknown');
        msgDiv.textContent = msg.content || '';
        messagesDiv.appendChild(msgDiv);
      });
      Object.values(streamBuffers).forEach(buf => {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message message-' + (buf.channel || 'unknown') + ' streaming-message';
        msgDiv.textContent = (buf.content || '') + '...';
        messagesDiv.appendChild(msgDiv);
      });
      container.appendChild(messagesDiv);
      const chatIntent = getProjection().intents['intent.chat.submit'];
      const composerDiv = document.createElement('div');
      composerDiv.className = 'chat-composer';
      const input = document.createElement('input');
      input.type = 'text';
      input.id = 'chat-input';
      input.placeholder = getProjection().chat.composer_placeholder || '';
      if (!chatIntent || !chatIntent.enabled) input.disabled = true;
      const sendBtn = document.createElement('button');
      sendBtn.id = 'chat-send';
      sendBtn.textContent = 'Send';
      if (!chatIntent || !chatIntent.enabled) sendBtn.disabled = true;
      composerDiv.appendChild(input);
      composerDiv.appendChild(sendBtn);
      container.appendChild(composerDiv);
      input.onkeypress = e => {
        if (e.key === 'Enter') {
          const text = input.value.trim();
          if (text) {
            dispatcher.sendIntent('intent.chat.submit', { text });
            input.value = '';
          }
        }
      };
      sendBtn.onclick = () => {
        const text = input.value.trim();
        if (text) {
          dispatcher.sendIntent('intent.chat.submit', { text });
          input.value = '';
        }
      };
      setTimeout(() => { messagesDiv.scrollTop = messagesDiv.scrollHeight; }, 0);
    }
    inspector.innerHTML = '';
    inspector.appendChild(container);
  }

  function render() {
    if (currentState !== BootState.READY && currentState !== BootState.LOADING) {
        console.warn(`[BOOT] Skipping render in state: ${currentState}`);
        return;
    }
    renderRoot({ projection: getProjection, widgetRegistry, pendingIntents, renderChat, renderProgress });
  }

  function renderProgress(events) {
    const widgetHost = document.getElementById('workspace.command_progress');
    if (!widgetHost) return;
    widgetHost.innerHTML = '';
    const operations = events && events.length ? events : getProgressOperations();
    if (!operations || operations.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = 'No active command progress yet.';
      widgetHost.appendChild(empty);
      return;
    }
    operations.slice(0, 3).forEach(operation => {
      const renderer = widgetRegistry.CommandProgressCard || widgetRegistry._fallback;
      let widgetEl = null;
      try {
        widgetEl = renderer(`progress.${operation.operation_id}`, operation, []);
      } catch (error) {
        console.error('Failed to render command progress widget:', error);
        widgetEl = widgetRegistry._fallback(operation);
      }
      if (widgetEl) widgetHost.appendChild(widgetEl);
    });
  }

  function onMessage(msg) {
    if (msg.kind === 'projection') {
      if (currentState === BootState.CONNECTING || currentState === BootState.RECONNECTING) {
        setBootState(BootState.LOADING);
      }
      
      setProjection(msg.data);
      pendingIntents.clear();
      
      // Transition from boot fallback to app
      const fallback = document.getElementById('boot-fallback');
      const status = document.getElementById('boot-status');
      const app = document.getElementById('app');
      
      if (fallback) fallback.hidden = true;
      if (status) status.hidden = true;
      if (app) app.hidden = false;

      if (currentState === BootState.LOADING) {
        setBootState(BootState.READY);
      }

      try {
        render();
      } catch (e) {
        console.error('[BOOT] Render failed:', e);
        showError('Render failed: ' + e.message);
        setBootState(BootState.ERROR);
      }
    } else if (msg.kind === 'intent_result') {
      dispatcher.handleIntentResult(msg.data);
    } else if (msg.kind === 'progress_event') {
      appendProgressEvent(msg.event || msg.data || {});
      render();
    } else if (msg.kind === 'stream_chunk') {
      handleStreamChunk(msg.data);
    } else if (msg.kind === 'error') {
      dispatcher.handleError(msg);
    } else if (msg.kind === 'event') {
      handleEvent(msg.data);
    }
  }

  function connect() {
    socket = connectWebSocket({
      sessionToken,
    socketRef,
    logger: RigLog,
    onMessage,
    onProgress: progress => {
      appendProgressEvent(progress);
      render();
    },
    onClose: () => {
      setBootState(BootState.RECONNECTING);
      console.log('WebSocket closed, reconnecting in 2s...');
      setTimeout(connect, 2000);
      },
    });
    return socket;
  }

  window.sendRigIntent = dispatcher.sendIntent;
  window.sendManualRepoIntent = dispatcher.sendManualRepoIntent;
  connect();
  return { connect, render, showError, clearProjection };
}
