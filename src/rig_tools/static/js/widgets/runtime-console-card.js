/** Runtime Console Card Widget
 *
 * Renders a console-style display for runtime stream output.
 * 
 * Core doctrine:
 * - Projection-only rendering (never fetches data)
 * - No authority inference
 * - No timers
 * - Deterministic rendering
 * - Safe truncation
 * - textContent-only rendering
 * - Replay-safe rendering
 * - Advisory indicators
 *
 * This widget displays:
 * - Stream chunks as console output
 * - Runtime status
 * - Capability usage
 * - Diagnostics
 * - Replay linkage
 */

export function renderRuntimeConsoleCard(id, data, context) {
  const el = document.createElement('div');
  el.className = 'widget runtime-console-card';
  el.setAttribute('role', 'region');
  el.setAttribute('aria-label', 'Runtime Console');
  el.setAttribute('aria-live', 'polite');

  // Title
  const title = data.title || 'Runtime Console';
  const subtitle = data.subtitle || '';
  
  const header = document.createElement('div');
  header.className = 'widget-header';
  
  const titleEl = document.createElement('h2');
  titleEl.textContent = title;
  header.appendChild(titleEl);
  
  if (subtitle) {
    const subtitleEl = document.createElement('div');
    subtitleEl.className = 'widget-subtitle';
    subtitleEl.textContent = subtitle;
    header.appendChild(subtitleEl);
  }
  el.appendChild(header);

  // Status badge
  if (data.status) {
    const statusBadge = document.createElement('div');
    statusBadge.className = 'badge severity-' + (data.status.severity || 'info');
    statusBadge.textContent = data.status.label || data.status;
    if (typeof data.status === 'string') {
      statusBadge.textContent = data.status;
    }
    header.appendChild(statusBadge);
  }

  // Console content area
  const consoleContent = document.createElement('div');
  consoleContent.className = 'runtime-console-content';
  consoleContent.style.overflowY = 'auto';
  consoleContent.style.maxHeight = '400px';
  consoleContent.style.fontFamily = 'monospace';
  consoleContent.style.fontSize = '12px';
  consoleContent.style.whiteSpace = 'pre-wrap';
  consoleContent.style.wordBreak = 'break-word';
  consoleContent.style.backgroundColor = 'var(--bg-secondary, #1e1e1e)';
  consoleContent.style.color = 'var(--text-primary, #e0e0e0)';
  consoleContent.style.padding = '8px';
  consoleContent.style.borderRadius = '4px';
  consoleContent.style.border = '1px solid var(--border, #404040)';

  // Get chunks from data
  const chunks = data.chunks || [];
  
  if (chunks.length === 0) {
    const emptyEl = document.createElement('p');
    emptyEl.className = 'muted';
    emptyEl.textContent = data.empty_message || 'No stream output yet.';
    consoleContent.appendChild(emptyEl);
  } else {
    // Render chunks
    const maxVisible = data.max_lines || 100;
    const displayChunks = chunks.slice(-maxVisible);
    
    for (const chunk of displayChunks) {
      const chunkEl = renderConsoleChunk(chunk, data);
      consoleContent.appendChild(chunkEl);
    }
  }
  
  el.appendChild(consoleContent);

  // Metadata footer
  if (data.metadata && Object.keys(data.metadata).length > 0) {
    const footer = document.createElement('div');
    footer.className = 'widget-footer';
    footer.style.marginTop = '8px';
    footer.style.fontSize = '11px';
    footer.style.color = 'var(--text-secondary, #888)';
    
    const metadataParts = [];
    if (data.metadata.provider_id) {
      metadataParts.push('Runtime: ' + data.metadata.provider_id);
    }
    if (data.metadata.invocation_id) {
      metadataParts.push('Invocation: ' + truncateId(data.metadata.invocation_id));
    }
    if (data.metadata.stream_id) {
      metadataParts.push('Stream: ' + truncateId(data.metadata.stream_id));
    }
    if (data.metadata.timestamp) {
      metadataParts.push('At: ' + formatTimestamp(data.metadata.timestamp));
    }
    if (data.metadata.total_bytes) {
      metadataParts.push('Size: ' + formatBytes(data.metadata.total_bytes));
    }
    
    footer.textContent = metadataParts.join(' | ');
    el.appendChild(footer);
  }

  // Advisory notice
  const advisoryEl = document.createElement('div');
  advisoryEl.className = 'advisory-notice';
  advisoryEl.style.marginTop = '8px';
  advisoryEl.style.fontSize = '11px';
  advisoryEl.style.color = 'var(--text-secondary, #888)';
  advisoryEl.style.fontStyle = 'italic';
  advisoryEl.textContent = 'Output is advisory evidence only. Only receipts become authoritative.';
  el.appendChild(advisoryEl);

  // Replay link if available
  if (data.replay_ref) {
    const replayEl = document.createElement('div');
    replayEl.style.marginTop = '4px';
    replayEl.style.fontSize = '11px';
    replayEl.textContent = 'Replay: ' + truncateId(data.replay_ref);
    el.appendChild(replayEl);
  }

  return el;
}

function renderConsoleChunk(chunk, widgetData) {
  const chunkEl = document.createElement('div');
  chunkEl.className = 'runtime-console-chunk';
  
  // Channel indicator
  const channel = chunk.channel || 'assistant';
  const channelClass = 'channel-' + channel;
  
  // Timestamp prefix if available
  let content = '';
  if (chunk.timestamp) {
    content += '[' + formatTimestamp(chunk.timestamp) + '] ';
  }
  
  // Channel prefix
  const channelLabels = {
    assistant: 'ASSISTANT',
    user: 'USER',
    system: 'SYSTEM',
    tool: 'TOOL',
    proposal: 'PROPOSAL',
    diagnostic: 'DIAGNOSTIC',
    status: 'STATUS',
    heartbeat: 'HEARTBEAT',
    warning: 'WARNING',
    error: 'ERROR',
    completion: 'COMPLETION',
    meta: 'META'
  };
  const channelLabel = channelLabels[channel] || channel.toUpperCase();
  content += '[' + channelLabel + '] ';
  
  // Actual content
  content += chunk.content || '';
  
  // Truncate if needed
  const maxLength = widgetData.max_chunk_length || 2000;
  if (content.length > maxLength) {
    content = content.substring(0, maxLength) + '...';
  }
  
  // Set text content (safe rendering)
  chunkEl.textContent = content;
  
  // Style based on severity or channel
  const severity = chunk.severity || (channel === 'error' ? 'error' : 
                     channel === 'warning' ? 'warning' : 
                     channel === 'diagnostic' ? 'info' : 'info');
  
  chunkEl.style.color = getColorForSeverity(severity);
  
  return chunkEl;
}

function truncateId(id, length = 8) {
  if (!id) return '';
  const str = String(id);
  return str.length <= length ? str : str.substring(0, length) + '...';
}

function formatTimestamp(ts) {
  if (!ts) return '';
  // Convert ISO timestamp to readable format
  try {
    const date = new Date(ts);
    return date.toLocaleTimeString();
  } catch {
    return ts;
  }
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function getColorForSeverity(severity) {
  const colors = {
    debug: 'var(--color-debug, #888)',
    info: 'var(--color-info, #e0e0e0)',
    warning: 'var(--color-warning, #ffa500)',
    error: 'var(--color-error, #ff5555)',
    critical: 'var(--color-critical, #ff4444)',
  };
  return colors[severity] || colors.info;
}

// Register widget
export function registerRuntimeConsoleCard(registry) {
  if (registry) {
    registry.RuntimeConsoleCard = renderRuntimeConsoleCard;
  }
}
