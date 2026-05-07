import { RigLog } from './logging.js';
import { clearProjection, getProjection, setProjection } from './projection-store.js';
import { createIntentDispatcher } from './intent-dispatch.js';
import { connectWebSocket } from './websocket.js';
import { appendProgressEvent, clearProgress } from './progress-store.js';
import { buildWidgetRegistry } from '../widgets/registry.js';
import { renderRoot } from './render-root.js';

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
      const widgetEl = renderer(widgetId, widget.data, widget.actions);
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
    renderRoot({ projection: getProjection, widgetRegistry, pendingIntents, renderChat, renderProgress });
  }

  function renderProgress(events) {
    const footer = document.getElementById('footer');
    if (!footer) return;
    let progressContainer = document.getElementById('progress');
    if (!progressContainer) {
      progressContainer = document.createElement('div');
      progressContainer.id = 'progress';
      footer.appendChild(progressContainer);
    }
    progressContainer.innerHTML = '';
    if (!events || events.length === 0) return;
    const latest = events.slice(-3);
    latest.forEach(event => {
      const renderer = widgetRegistry.CommandProgressCard || widgetRegistry._fallback;
      const widgetEl = renderer(`progress.${event.operation_id}`, event, []);
      if (widgetEl) progressContainer.appendChild(widgetEl);
    });
  }

  function onMessage(msg) {
    if (msg.kind === 'projection') {
      setProjection(msg.data);
      pendingIntents.clear();
      render();
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
      console.log('WebSocket closed, reconnecting in 2s...');
      setTimeout(connect, 2000);
      },
    });
    return socket;
  }

  window.sendRigIntent = dispatcher.sendIntent;
  window.sendManualRepoIntent = dispatcher.sendManualRepoIntent;
  connect();
  render();
  return { connect, render, showError, clearProjection };
}
