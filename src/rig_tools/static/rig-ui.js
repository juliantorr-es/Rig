(function() {
    let socket = null;
    let projection = null;
    let streamBuffers = {};
    const MAX_STREAM_BUFFERS = 10;
    const MAX_BUFFER_BYTES = 10000; // 10KB per stream buffer
    const sessionToken = new URLSearchParams(window.location.search).get('rig_session');

    function connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        RigLog.debug('WS', 'Connecting to UI websocket', {
            protocol,
            host: window.location.host,
            hasSessionToken: Boolean(sessionToken)
        });
        socket = new WebSocket(`${protocol}//${window.location.host}/ui/ws?rig_session=${sessionToken}`);

        socket.onopen = () => {
            RigLog.info('WS', 'WebSocket connected');
            socket.send(JSON.stringify({ kind: 'hello' }));
        };

        socket.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.kind === 'projection') {
                projection = msg.data;
                RigLog.debug('Projection', 'Received projection', {
                    revision: projection.revision,
                    screen: projection.screen,
                    widgetCount: projection.widgets ? Object.keys(projection.widgets).length : 0
                });
                // Clear pending intents - projection is authoritative state
                pendingIntents.clear();
                render();
            } else if (msg.kind === 'intent_result') {
                console.log('Intent result:', msg.data);
                const data = msg.data;
                if (!data.accepted) {
                    showError(`Action rejected: ${data.reason || 'Unknown reason'}`);
                }
                // Clear pending intent for this intent kind
                for (const [actionId, pending] of pendingIntents.entries()) {
                    if (projection.intents && projection.intents[actionId] && 
                        projection.intents[actionId].kind === msg.data.intent_kind) {
                        pendingIntents.delete(actionId);
                        break;
                    }
                }
            } else if (msg.kind === 'stream_chunk') {
                handleStreamChunk(msg.data);
            } else if (msg.kind === 'error') {
                showError(`Server error: ${msg.message}`);
                pendingIntents.clear();
            } else if (msg.kind === 'event') {
                handleEvent(msg.data);
            }
        };

        socket.onclose = () => {
            console.log('WebSocket closed, reconnecting in 2s...');
            setTimeout(connect, 2000);
        };
    }

    function showError(message) {
        const errEl = document.createElement('div');
        errEl.className = 'error-notification';
        errEl.setAttribute('role', 'alert');
        errEl.textContent = message;
        document.body.appendChild(errEl);
        setTimeout(() => errEl.remove(), 5000);
    }

    function handleEvent(data) {
        const type = data.type;
        if (type === 'validator_started') {
            // Validator started - will be reflected in projection
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
        // Always re-render to show stream output
        render();
    }

    let globalLogs = [];
    const lastSequenceNumbers = {}; // Track last sequence per stream for monotonic validation

    function handleStreamChunk(data) {
        // Validate required fields - must have stream_id, sequence, content, channel
        if (!data.stream_id || data.sequence === undefined || !data.content || !data.channel) {
            console.warn('Invalid stream chunk: missing required fields');
            return;
        }
        
        // Validate sequence is monotonic per stream
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
            // Initialize buffer if it doesn't exist
            if (!streamBuffers[streamId]) {
                streamBuffers[streamId] = { content: '', channel: data.channel || 'assistant' };
            }
            
            // Check buffer size bounds
            const buffer = streamBuffers[streamId];
            if (buffer.content.length + content.length > MAX_BUFFER_BYTES) {
                // Truncate to make room for new content
                buffer.content = buffer.content.substring(0, Math.max(0, MAX_BUFFER_BYTES - content.length - 100));
            }
            buffer.content += content;
        } else {
            // Append to logs
            const logEntry = `[${data.channel || 'unknown'}] ${content}`;
            globalLogs.push(logEntry);
            if (globalLogs.length > MAX_LOG_LINES) {
                globalLogs.shift();
            }
        }
        render(); // Re-render everything to show progress
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    const pendingIntents = new Map(); // Track pending intent actionIds

    function sendIntent(actionId, target = null) {
        const intentRef = projection.intents[actionId];
        if (!intentRef || !intentRef.enabled || pendingIntents.has(actionId)) return;

        const idempotencyKey = Math.random().toString(36).substring(7);
        pendingIntents.set(actionId, { status: 'pending', idempotency_key: idempotencyKey });
        
        // Disable the button and show running state
        const btn = document.querySelector(`button[onclick=\"window.sendRigIntent('${actionId}')\"]`);
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Running...';
        }

        // New protocol: rig.ui.message.v1 envelope with nested intent
        const msg = {
            schema_version: 'rig.ui.message.v1',
            kind: 'intent',
            intent: {
                schema_version: 'rig.ui.intent.v1',
                intent_id: idempotencyKey,
                kind: intentRef.kind,
                target: target || intentRef.target,
                observed_projection_revision: projection.revision,
                idempotency_key: idempotencyKey,
                submitted_at: new Date().toISOString(),
                client: { kind: 'pywebview' }
            }
        };
        socket.send(JSON.stringify(msg));
    }

    function sendManualRepoIntent(actionId, workspacePath) {
        const intentRef = projection && projection.intents ? projection.intents[actionId] : null;
        const path = String(workspacePath || '').trim();
        if (!intentRef || !path) return;

        RigLog.info('RepoSelect', 'Submitting manual repository path', {
            actionId,
            path: RigLog._redactSecrets(path)
        });

        const idempotencyKey = Math.random().toString(36).substring(7);
        const msg = {
            schema_version: 'rig.ui.message.v1',
            kind: 'intent',
            intent: {
                schema_version: 'rig.ui.intent.v1',
                intent_id: idempotencyKey,
                kind: intentRef.kind,
                target: {
                    workspace_path: path,
                    source: 'manual_path_input'
                },
                observed_projection_revision: projection.revision,
                idempotency_key: idempotencyKey,
                submitted_at: new Date().toISOString(),
                client: { kind: 'pywebview' }
            }
        };
        socket.send(JSON.stringify(msg));
    }

    const MAX_LOG_LINES = 100;
    const MAX_BUFFER_BYTES = 10000; // 10KB per stream buffer

    function truncateText(text, maxLen = 500) {
        if (!text) return '';
        const str = String(text);
        return str.length > maxLen ? str.substring(0, maxLen) + '...' : str;
    }

    const widgetRenderers = {
        AppTitle: (id, data) => {
            const el = document.createElement('div');
            const title = document.createElement('div');
            title.className = 'title';
            title.style.fontWeight = 'bold';
            title.style.letterSpacing = '0.1em';
            title.textContent = data.title || '';
            const subtitle = document.createElement('div');
            subtitle.className = 'muted';
            subtitle.style.fontSize = '0.8rem';
            subtitle.style.color = 'var(--muted)';
            subtitle.textContent = data.subtitle || '';
            el.appendChild(title);
            el.appendChild(subtitle);
            return el;
        },
        GateBadge: (id, data) => {
            const el = document.createElement('span');
            el.className = `badge severity-${data.severity || 'info'}`;
            el.textContent = data.label || '';
            return el;
        },
        MetricStack: (id, data) => {
            const el = document.createElement('div');
            el.className = 'widget';
            const h2 = document.createElement('h2');
            h2.textContent = data.title || '';
            el.appendChild(h2);
            (data.items || []).forEach(item => {
                const div = document.createElement('div');
                div.className = 'metric-item';
                const label = document.createElement('span');
                label.className = 'label';
                label.textContent = item.label || '';
                const value = document.createElement('span');
                value.className = `value severity-${item.severity || 'info'}`;
                value.textContent = item.value !== undefined ? String(item.value) : '';
                div.appendChild(label);
                div.appendChild(value);
                el.appendChild(div);
            });
            return el;
        },
        EmptyStateCard: (id, data, actions) => {
            const el = document.createElement('div');
            el.className = 'widget';
            const h2 = document.createElement('h2');
            h2.textContent = data.title || '';
            el.appendChild(h2);
            const p = document.createElement('p');
            p.textContent = data.body || '';
            el.appendChild(p);
            const disabledReasons = [];
            (actions || []).forEach(actionId => {
                const intent = projection.intents[actionId];
                if (intent && !intent.enabled && intent.disabled_reason) {
                    disabledReasons.push(intent.disabled_reason);
                }
            });
            if (disabledReasons.length > 0) {
                const reasonsEl = document.createElement('div');
                reasonsEl.className = 'empty-state-reasons';
                reasonsEl.textContent = disabledReasons.join(' ');
                el.appendChild(reasonsEl);
            }
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'actions';
            (actions || []).forEach(actionId => {
                const intent = projection.intents[actionId];
                if (!intent) return;
                const btn = document.createElement('button');
                btn.onclick = () => window.sendRigIntent(actionId);
                if (!intent.enabled) {
                    btn.disabled = true;
                    if (intent.disabled_reason) {
                        btn.title = intent.disabled_reason;
                    }
                }
                btn.textContent = intent.label || actionId;
                actionsDiv.appendChild(btn);
            });
            el.appendChild(actionsDiv);
            if (id === 'workspace.empty') {
                const manualDiv = document.createElement('div');
                manualDiv.className = 'manual-repo-input';

                const label = document.createElement('label');
                label.textContent = 'Enter repository path:';
                manualDiv.appendChild(label);

                const input = document.createElement('input');
                input.type = 'text';
                input.id = 'manual-repo-path';
                input.placeholder = '/path/to/rig';
                manualDiv.appendChild(input);

                const manualBtn = document.createElement('button');
                manualBtn.textContent = 'Open Repository';
                manualBtn.onclick = () => {
                    const path = input.value.trim();
                    if (!path) {
                        showError('Enter a repository path first.');
                        return;
                    }
                    if (!projection.intents['intent.open_workspace']) {
                        showError('Repository selection intent is unavailable.');
                        return;
                    }
                    sendManualRepoIntent('intent.open_workspace', path);
                };
                manualDiv.appendChild(manualBtn);

                const hint = document.createElement('p');
                hint.className = 'empty-state-reasons';
                hint.textContent = 'Manual path input is available when native file dialogs are unavailable.';
                manualDiv.appendChild(hint);

                el.appendChild(manualDiv);
            }
            return el;
        },
        EvidenceCard: (id, data) => {
            const el = document.createElement('div');
            el.className = 'widget';
            const h2 = document.createElement('h2');
            h2.textContent = data.title || '';
            el.appendChild(h2);
            if (data.state) {
                const badge = document.createElement('div');
                badge.className = `badge severity-${data.state.severity || 'info'}`;
                badge.textContent = data.state.label || '';
                el.appendChild(badge);
            }
            const p = document.createElement('p');
            p.className = 'muted';
            p.textContent = data.body || '';
            el.appendChild(p);
            return el;
        },
        ActivityFeed: (id, data) => {
            const el = document.createElement('div');
            el.className = 'widget';
            const h2 = document.createElement('h2');
            h2.textContent = data.title || '';
            el.appendChild(h2);
            const p = document.createElement('p');
            p.className = 'muted';
            p.textContent = 'No recent activity.';
            el.appendChild(p);
            return el;
        },
        LogStream: (id, data) => {
            const el = document.createElement('div');
            el.className = 'widget';
            const h2 = document.createElement('h2');
            h2.textContent = data.title || '';
            el.appendChild(h2);
            const streamDiv = document.createElement('div');
            streamDiv.className = 'log-stream';
            streamDiv.setAttribute('aria-live', 'polite');
            if (globalLogs.length > 0) {
                // Show only most recent logs, bounded
                const recentLogs = globalLogs.slice(-MAX_LOG_LINES);
                recentLogs.forEach(log => {
                    const div = document.createElement('div');
                    div.textContent = truncateText(log);
                    streamDiv.appendChild(div);
                });
            } else {
                const p = document.createElement('p');
                p.className = 'muted';
                p.textContent = 'No recent logs.';
                streamDiv.appendChild(p);
            }
            el.appendChild(streamDiv);
            return el;
        },
        ValidatorStack: (id, data, actions) => {
            const el = document.createElement('div');
            el.className = 'widget';
            const headerDiv = document.createElement('div');
            headerDiv.style.display = 'flex';
            headerDiv.style.justifyContent = 'space-between';
            headerDiv.style.alignItems = 'baseline';
            const h2 = document.createElement('h2');
            h2.textContent = data.title || '';
            headerDiv.appendChild(h2);
            const badge = document.createElement('span');
            badge.className = `badge severity-${data.state.severity || 'info'}`;
            badge.textContent = data.state ? (data.state.label || '') : '';
            headerDiv.appendChild(badge);
            el.appendChild(headerDiv);
            
            // Show running indicator if validation is in progress
            if (data.run_in_progress) {
                const runningDiv = document.createElement('div');
                runningDiv.className = 'validator-running';
                runningDiv.style.color = 'var(--attention)';
                runningDiv.style.fontSize = '0.85rem';
                runningDiv.style.marginBottom = '8px';
                const spinner = document.createElement('span');
                spinner.textContent = '● ';
                const runningText = document.createElement('span');
                runningText.textContent = data.running_validator_id 
                    ? `Running: ${data.running_validator_id}` 
                    : 'Validating...';
                runningDiv.appendChild(spinner);
                runningDiv.appendChild(runningText);
                el.appendChild(runningDiv);
            }
            
            if (data.summary) {
                const summaryDiv = document.createElement('div');
                summaryDiv.className = 'muted';
                summaryDiv.style.marginBottom = '8px';
                summaryDiv.textContent = truncateText(data.summary);
                el.appendChild(summaryDiv);
            }
            const listDiv = document.createElement('div');
            listDiv.className = 'validator-list';
            (data.items || []).forEach(item => {
                const itemDiv = document.createElement('div');
                itemDiv.className = `validator-item state-${item.state || 'unknown'}`;
                const itemHeader = document.createElement('div');
                itemHeader.style.display = 'flex';
                itemHeader.style.justifyContent = 'space-between';
                // Updated symbols to include running state
                const symbol = item.state === 'passed' ? '✓ ' : 
                              item.state === 'failed' ? '✗ ' :
                              item.state === 'running' ? '→ ' :
                              '○ ';
                const labelSpan = document.createElement('span');
                labelSpan.textContent = symbol + (item.label || '');
                const stateSpan = document.createElement('span');
                stateSpan.className = 'muted';
                stateSpan.textContent = item.state || '';
                itemHeader.appendChild(labelSpan);
                itemHeader.appendChild(stateSpan);
                itemDiv.appendChild(itemHeader);
                if (item.detail) {
                    const pre = document.createElement('pre');
                    pre.className = 'validator-detail';
                    pre.textContent = truncateText(item.detail, 200);
                    itemDiv.appendChild(pre);
                }
                listDiv.appendChild(itemDiv);
            });
            el.appendChild(listDiv);
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'actions';
            actionsDiv.style.marginTop = '12px';
            (actions || []).forEach(actionId => {
                const intent = projection.intents[actionId];
                if (!intent) return;
                const btn = document.createElement('button');
                btn.onclick = () => window.sendRigIntent(actionId);
                // Also disable if validation is running
                if (!intent.enabled || data.run_in_progress) {
                    btn.disabled = true;
                }
                // Show running text if validation is in progress
                if (data.run_in_progress && intent.kind === 'rig.intent.run_validators') {
                    btn.textContent = 'Running...';
                } else {
                    btn.textContent = intent.label || actionId;
                }
                actionsDiv.appendChild(btn);
            });
            el.appendChild(actionsDiv);
            return el;
        },
        ReceiptList: (id, data) => {
            const el = document.createElement('div');
            el.className = 'widget';
            const h2 = document.createElement('h2');
            h2.textContent = data.title || 'Receipts';
            el.appendChild(h2);

            const listDiv = document.createElement('div');
            listDiv.className = 'receipt-list';
            listDiv.style.fontSize = '0.8rem';
            listDiv.style.maxHeight = '200px';
            listDiv.style.overflowY = 'auto';

            const receipts = data.receipts || [];
            if (receipts.length === 0) {
                const p = document.createElement('p');
                p.className = 'muted';
                p.textContent = 'No receipts yet.';
                listDiv.appendChild(p);
            } else {
                receipts.forEach(receipt => {
                    const itemDiv = document.createElement('div');
                    itemDiv.className = 'receipt-item';
                    itemDiv.style.padding = '4px 0';
                    itemDiv.style.borderBottom = '1px solid var(--border)';

                    const headerDiv = document.createElement('div');
                    headerDiv.style.display = 'flex';
                    headerDiv.style.justifyContent = 'space-between';

                    const labelSpan = document.createElement('span');
                    labelSpan.style.fontWeight = '500';
                    labelSpan.textContent = receipt.id || receipt.receipt_id || 'Unknown';

                    const kindSpan = document.createElement('span');
                    kindSpan.className = 'muted';
                    kindSpan.style.fontSize = '0.7rem';
                    kindSpan.textContent = receipt.kind || '';

                    headerDiv.appendChild(labelSpan);
                    headerDiv.appendChild(kindSpan);
                    itemDiv.appendChild(headerDiv);

                    if (receipt.summary) {
                        const summaryDiv = document.createElement('div');
                        summaryDiv.style.fontSize = '0.75rem';
                        summaryDiv.style.color = 'var(--muted)';
                        summaryDiv.style.marginTop = '2px';
                        summaryDiv.textContent = truncateText(receipt.summary, 100);
                        itemDiv.appendChild(summaryDiv);
                    }

                    listDiv.appendChild(itemDiv);
                });
            }
            el.appendChild(listDiv);
            return el;
        },
        BackendStatus: (id, data) => {
            const el = document.createElement('div');
            el.style.display = 'flex';
            el.style.justifyContent = 'space-between';
            el.style.padding = '4px';
            const leftSpan = document.createElement('span');
            leftSpan.textContent = (data.title || '') + ': ' + (data.body || '');
            el.appendChild(leftSpan);
            const rightSpan = document.createElement('span');
            rightSpan.textContent = 'Rev: ' + (data.revision !== undefined ? String(data.revision) : '');
            el.appendChild(rightSpan);
            return el;
        }
    };

    window.sendRigIntent = sendIntent;

    function render() {
        if (!projection) return;

        Object.keys(projection.layout.regions).forEach(regionId => {
            if (regionId === 'inspector') return; // Handled specially for chat

            const el = document.getElementById(regionId);
            if (!el) return;

            // Clear existing content
            el.innerHTML = '';

            const widgetIds = projection.layout.regions[regionId];
            widgetIds.forEach(widgetId => {
                const widget = projection.widgets[widgetId];
                const renderer = widgetRenderers[widget.type];
                if (renderer) {
                    const widgetEl = renderer(widgetId, widget.data, widget.actions);
                    if (widgetEl) {
                        el.appendChild(widgetEl);
                    }
                } else {
                    const div = document.createElement('div');
                    div.className = 'widget';
                    div.textContent = 'Unknown widget: ' + (widget.type || 'unknown');
                    el.appendChild(div);
                }
            });
        });

        renderChat();
    }

    function renderChat() {
        const inspector = document.getElementById('inspector');
        if (!inspector) return;

        // Create container
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

        // Add inspector widgets from projection
        const widgetIds = projection.layout.regions['inspector'] || [];
        const widgetsDiv = document.createElement('div');
        widgetsDiv.style.flex = '0 0 auto';
        widgetsDiv.style.overflowY = 'auto';
        widgetIds.forEach(widgetId => {
            const widget = projection.widgets[widgetId];
            const renderer = widgetRenderers[widget.type];
            if (renderer) {
                const widgetEl = renderer(widgetId, widget.data, widget.actions);
                if (widgetEl) {
                    widgetsDiv.appendChild(widgetEl);
                }
            }
        });
        container.appendChild(widgetsDiv);

        if (projection.chat) {
            const messagesDiv = document.createElement('div');
            messagesDiv.className = 'chat-messages';
            messagesDiv.id = 'chat-messages';

            // Add messages from chat history
            (projection.chat.messages || []).forEach(msg => {
                const msgDiv = document.createElement('div');
                msgDiv.className = 'message message-' + (msg.role || 'unknown');
                msgDiv.textContent = msg.content || '';
                messagesDiv.appendChild(msgDiv);
            });

            // Add streaming chunks
            Object.values(streamBuffers).forEach(buf => {
                const msgDiv = document.createElement('div');
                msgDiv.className = 'message message-' + (buf.channel || 'unknown') + ' streaming-message';
                msgDiv.textContent = (buf.content || '') + '...';
                messagesDiv.appendChild(msgDiv);
            });

            container.appendChild(messagesDiv);

            // Add chat composer
            const chatIntent = projection.intents['intent.chat.submit'];
            const composerDiv = document.createElement('div');
            composerDiv.className = 'chat-composer';

            const input = document.createElement('input');
            input.type = 'text';
            input.id = 'chat-input';
            input.placeholder = projection.chat.composer_placeholder || '';
            if (!chatIntent || !chatIntent.enabled) {
                input.disabled = true;
            }

            const sendBtn = document.createElement('button');
            sendBtn.id = 'chat-send';
            sendBtn.textContent = 'Send';
            if (!chatIntent || !chatIntent.enabled) {
                sendBtn.disabled = true;
            }

            composerDiv.appendChild(input);
            composerDiv.appendChild(sendBtn);
            container.appendChild(composerDiv);

            // Wire up event handlers
            input.onkeypress = (e) => {
                if (e.key === 'Enter') {
                    const text = input.value.trim();
                    if (text) {
                        sendIntent('intent.chat.submit', { text });
                        input.value = '';
                    }
                }
            };

            sendBtn.onclick = () => {
                const text = input.value.trim();
                if (text) {
                    sendIntent('intent.chat.submit', { text });
                    input.value = '';
                }
            };

            // Scroll chat to bottom
            setTimeout(() => {
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }, 0);
        }

        // Clear and repopulate inspector
        inspector.innerHTML = '';
        inspector.appendChild(container);
    }

    connect();
})();
