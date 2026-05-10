export function renderReceiptList(_id, data) {
  const el = document.createElement('div');
  el.className = 'widget';
  const h2 = document.createElement('h2');
  h2.textContent = data.title || 'Receipts';
  el.appendChild(h2);
  if (data.schema_version || data.projection_revision !== undefined) {
    const lineage = document.createElement('div');
    lineage.className = 'muted';
    lineage.style.fontSize = '0.75rem';
    lineage.textContent = [
      data.schema_version ? `schema: ${data.schema_version}` : null,
      data.projection_revision !== undefined ? `revision: ${data.projection_revision}` : null,
    ].filter(Boolean).join(' · ');
    el.appendChild(lineage);
  }
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
      if (receipt.schema_version || receipt.projection_revision !== undefined) {
        const lineageDiv = document.createElement('div');
        lineageDiv.className = 'muted';
        lineageDiv.style.fontSize = '0.7rem';
        lineageDiv.textContent = [
          receipt.schema_version ? `schema: ${receipt.schema_version}` : null,
          receipt.projection_revision !== undefined ? `revision: ${receipt.projection_revision}` : null,
        ].filter(Boolean).join(' · ');
        itemDiv.appendChild(lineageDiv);
      }
      if (receipt.summary) {
        const summaryDiv = document.createElement('div');
        summaryDiv.style.fontSize = '0.75rem';
        summaryDiv.style.color = 'var(--muted)';
        summaryDiv.style.marginTop = '2px';
        summaryDiv.textContent = receipt.summary;
        itemDiv.appendChild(summaryDiv);
      }
      listDiv.appendChild(itemDiv);
    });
  }
  el.appendChild(listDiv);
  return el;
}
