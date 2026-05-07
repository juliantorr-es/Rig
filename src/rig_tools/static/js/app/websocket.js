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
    socket.send(JSON.stringify({ kind: 'hello' }));
  };

  socket.onmessage = event => {
    const msg = JSON.parse(event.data);
    if (msg.kind === 'progress_event' && onProgress) {
      onProgress(msg.event || msg.data || {});
      return;
    }
    onMessage(msg);
  };
  socket.onclose = () => {
    if (onClose) onClose();
  };

  return socket;
}
