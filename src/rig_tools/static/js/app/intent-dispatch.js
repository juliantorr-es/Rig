export function createIntentDispatcher({ projection, socketRef, pendingIntents, showError, render, logger }) {
  function sendIntent(actionId, target = null) {
    const current = projection();
    const intentRef = current && current.intents ? current.intents[actionId] : null;
    if (!intentRef || !intentRef.enabled || pendingIntents.has(actionId)) return;

    const idempotencyKey = Math.random().toString(36).substring(7);
    pendingIntents.set(actionId, { status: 'pending', idempotency_key: idempotencyKey });

    const btn = document.querySelector(`button[onclick=\"window.sendRigIntent('${actionId}')\"]`);
    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Running...';
    }

    const msg = {
      schema_version: 'rig.ui.message.v1',
      kind: 'intent',
      intent: {
        schema_version: 'rig.ui.intent.v1',
        intent_id: idempotencyKey,
        kind: intentRef.kind,
        target: target || intentRef.target,
        observed_projection_revision: current.revision,
        idempotency_key: idempotencyKey,
        submitted_at: new Date().toISOString(),
        client: { kind: 'pywebview' },
      },
    };
    socketRef.current.send(JSON.stringify(msg));
  }

  function sendManualRepoIntent(actionId, workspacePath) {
    const current = projection();
    const intentRef = current && current.intents ? current.intents[actionId] : null;
    const path = String(workspacePath || '').trim();
    if (!intentRef || !path) return;
    logger.info('RepoSelect', 'Submitting manual repository path', {
      actionId,
      path: logger._redactSecrets(path),
    });
    const idempotencyKey = Math.random().toString(36).substring(7);
    const msg = {
      schema_version: 'rig.ui.message.v1',
      kind: 'intent',
      intent: {
        schema_version: 'rig.ui.intent.v1',
        intent_id: idempotencyKey,
        kind: intentRef.kind,
        target: { workspace_path: path, source: 'manual_path_input' },
        observed_projection_revision: current.revision,
        idempotency_key: idempotencyKey,
        submitted_at: new Date().toISOString(),
        client: { kind: 'pywebview' },
      },
    };
    socketRef.current.send(JSON.stringify(msg));
  }

  function handleIntentResult(data) {
    if (!data.accepted) {
      const reason = data.reason || 'Unknown reason';
      const status = data.status || '';
      const displayReason = status === 'unsupported' ? `Not available: ${reason}` : `Rejected: ${reason}`;
      showError(displayReason);
    }
    const current = projection();
    if (current && current.intents) {
      for (const [actionId] of pendingIntents.entries()) {
        if (current.intents[actionId] && current.intents[actionId].kind === data.intent_kind) {
          pendingIntents.delete(actionId);
          const btn = document.querySelector(`button[onclick=\"window.sendRigIntent('${actionId}')\"]`);
          if (btn) {
            btn.disabled = false;
            const intentRef = current.intents[actionId];
            btn.textContent = intentRef ? (intentRef.label || actionId) : actionId;
          }
          break;
        }
      }
    }
  }

  function handleError(data) {
    logger.warn('ServerError', 'Received error message', data);
    const detail = data.intent_kind ? `Intent '${data.intent_kind}': ${data.message}` : `Server error: ${data.message}`;
    showError(detail);
    pendingIntents.clear();
    const current = projection();
    if (current && current.intents) {
      Object.keys(current.intents).forEach(actionId => {
        const btn = document.querySelector(`button[onclick=\"window.sendRigIntent('${actionId}')\"]`);
        if (btn) {
          btn.disabled = false;
          const intentRef = current.intents[actionId];
          btn.textContent = intentRef ? (intentRef.label || actionId) : actionId;
        }
      });
    }
  }

  function handleUnhandledIntent(data) {
    handleIntentResult(data);
  }

  return { sendIntent, sendManualRepoIntent, handleIntentResult, handleError, handleUnhandledIntent };
}
