export function connectWebSocket({ sessionToken, socketRef, logger, onMessage, onProgress, onClose }) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  logger.debug('WS', 'Connecting to UI websocket', {
    protocol,
    host: window.location.host,
    hasSessionToken: Boolean(sessionToken),
  });
  const socket = new WebSocket(`${protocol}//${window.location.host}/ui/ws?rig_session=${sessionToken}`);
  socketRef.current = socket;

  socket.onopen = () => {
    logger.info('WS', 'WebSocket connected');
    console.log('[DEBUG-ws] WebSocket connected, sending hello');
    socket.send(JSON.stringify({ kind: 'hello' }));
  };

  socket.onmessage = event => {
    console.log('[DEBUG-ws] Raw message received');
    const msg = JSON.parse(event.data);
    const schemaVersion = msg.schema_version || msg.schemaVersion || 'rig.ui.message.v1';
    const normalized = {
      ...msg,
      schema_version: schemaVersion,
    };
    if (normalized.kind === 'progress_event' && onProgress) {
      const progressEvent = normalized.event || normalized.data || {};
      onProgress({
        ...progressEvent,
        schema_version: progressEvent.schema_version || progressEvent.schemaVersion || 'rig.ui.progress_event.v1',
      });
      return;
    }
    onMessage(normalized);
  };
  socket.onclose = () => {
    console.log('[DEBUG-ws] WebSocket closed');
    if (onClose) onClose();
  };
  socket.onerror = (err) => {
    console.error('[DEBUG-ws] WebSocket error:', err);
  };

  return socket;
}
