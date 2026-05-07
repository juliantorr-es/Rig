# Context Pack: Local Server & WebSocket Security

## pywebview + Local Server

- **URL Mode**: Use `webview.create_window('Rig', url=url)` where `url` is a `localhost` or `127.0.0.1` address. Avoid `file://` protocols due to engine limitations.
- **SSL**: While `webview.start(ssl=True)` is available, it requires the `cryptography` library. For a local loopback-only app, a session token is often more practical for authentication.
- **Python-to-JS Bridge**: `js_api` is available but Rig prefers the **WebSocket** path for high-frequency streaming and consistency between TUI/Web.

## aiohttp WebSocket Server

- **Lifecycle**: Track clients in a `set` or `WeakSet`. Use `on_shutdown` signals to close all active `WebSocketResponse` objects gracefully with `WSCloseCode.GOING_AWAY`.
- **Broadcast**: Iterate through the client set, checking `client.closed` before sending.
- **Thread-Safety**: When updating state from a non-async thread (e.g., a long-running execution thread), use `loop.call_soon_threadsafe()` to schedule message sends back to the clients.
- **Static Files**: Use `app.add_routes([web.static('/static', path)])` for assets.

## WebSocket Security (Local-App Threat Model)

- **Loopback Binding**: Always bind to `127.0.0.1`. Never bind to `0.0.0.0` unless explicitly requested by the user (`--allow-lan`).
- **Session Tokens**: Every UI session must generate a unique, cryptographically strong `session_token` (UUID). The frontend must provide this token (e.g., in a URL parameter or subprotocol) to establish the WebSocket connection.
- **Origin Validation**: The WebSocket handler must verify the `Origin` header to prevent **Cross-Site WebSocket Hijacking (CSWH)**. In a local app, the origin should match the server's own address.
- **Message Validation**: Treat all data coming over the WebSocket (Intentions) as **untrusted**. Validate against a strict schema before dispatching to the domain layer.
- **Backpressure**: Be mindful of large message bursts (e.g., log streams). Use `ws.send_json` but monitor for client-side slowdowns.

## Agent Checklist
- [ ] Does the server bind to `127.0.0.1`?
- [ ] Is a session token required for connection?
- [ ] Is the `Origin` header validated?
- [ ] Are all incoming messages validated?
- [ ] Are WebSockets gracefully closed on shutdown?
- [ ] Is thread-safe scheduling used for background progress?
