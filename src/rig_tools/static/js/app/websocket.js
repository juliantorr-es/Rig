export function connectWebSocket({ sessionToken, socketRef, logger, onMessage, onClose }) {
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

  socket.onmessage = event => onMessage(JSON.parse(event.data));
  socket.onclose = () => {
    if (onClose) onClose();
  };

  return socket;
}
