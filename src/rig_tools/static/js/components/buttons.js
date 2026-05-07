export function actionButton(label, actionId, intent, onClick) {
  const btn = document.createElement('button');
  btn.onclick = () => onClick(actionId);
  if (!intent.enabled) {
    btn.disabled = true;
    if (intent.disabled_reason) btn.title = intent.disabled_reason;
  }
  btn.textContent = label || actionId;
  return btn;
}
