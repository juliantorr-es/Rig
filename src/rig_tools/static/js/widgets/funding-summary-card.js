import { badge } from '../components/badges.js';
import { card } from '../components/cards.js';

/**
 * Render a funding summary card for proposal lifecycle.
 * 
 * This widget is DUMB:
 * - Renders projection data only
 * - No fetching
 * - No authority logic
 * - No local persistence
 * - No inference from frontend progress-store
 */
export function renderFundingSummaryCard(_id, data) {
  const el = card(data.title || 'Funding Summary');
  el.className = 'widget funding-summary-card';

  if (data.schema_version || data.projection_revision !== undefined) {
    const lineage = document.createElement('div');
    lineage.className = 'muted';
    lineage.style.fontSize = '12px';
    lineage.textContent = [
      data.schema_version ? `schema: ${data.schema_version}` : null,
      data.projection_revision !== undefined ? `revision: ${data.projection_revision}` : null,
    ].filter(Boolean).join(' · ');
    el.appendChild(lineage);
  }

  // Funding status badge
  const status = (data.funding_status || 'advisory_only').toString();
  const statusSeverity = status === 'funded' ? 'success' : (
    status === 'partially_funded' ? 'attention' : (
      status === 'unfunded' ? 'idle' : 'info'
    )
  );
  const statusLabel = status === 'advisory_only' ? 'Advisory Only' : (
    status === 'unfunded' ? 'Unfunded' : (
      status === 'partially_funded' ? 'Partially Funded' : (
        status === 'funding_open' ? 'Funding Open' : (
          status === 'funded' ? 'Funded' : status.replace(/_/g, ' ')
        )
      )
    )
  );
  el.appendChild(badge(statusLabel, statusSeverity));

  // Public visibility badge
  if (data.public_visibility) {
    const visibility = data.public_visibility.toString();
    const visibilitySeverity = visibility === 'public' ? 'success' : (
      visibility === 'internal' ? 'attention' : 'idle'
    );
    const visibilityLabel = visibility.replace(/_/g, ' ');
    el.appendChild(badge(visibilityLabel, visibilitySeverity));
  }

  // Summary line
  const summaryParts = [];
  if (data.pledge_totals) {
    const totalUsd = data.pledge_totals.total_usd || 0;
    const totalCount = data.pledge_totals.total_count || 0;
    const currency = data.pledge_totals.currency || 'USD';
    summaryParts.push(`${currency} ${totalUsd} pledged ${totalCount > 0 ? `(${totalCount} pledges)` : ''}`);
  }
  if (data.sponsor_count !== undefined) {
    const count = data.sponsor_count;
    summaryParts.push(`${count} ${count === 1 ? 'sponsor' : 'sponsors'}`);
  }
  if (summaryParts.length > 0) {
    const summary = document.createElement('p');
    summary.className = 'muted';
    summary.textContent = summaryParts.join(' · ');
    el.appendChild(summary);
  }

  // Priority/acceleration class
  if (data.requested_acceleration_class) {
    const accelClass = data.requested_acceleration_class;
    const accelSeverity = accelClass === 'urgent' ? 'danger' : (
      accelClass === 'high' ? 'attention' : (
        accelClass === 'elevated' ? 'info' : 'idle'
      )
    );
    el.appendChild(badge(accelClass === 'unscheduled' ? 'Unscheduled' : accelClass.replace(/_/g, ' '), accelSeverity));
  }

  // Community requested indicator
  if (data.is_community_requested === true) {
    const communityBadge = document.createElement('div');
    communityBadge.className = 'badge severity-success';
    communityBadge.textContent = 'Community Requested';
    el.appendChild(communityBadge);
  }

  // Details section
  const details = document.createElement('dl');
  details.className = 'funding-summary-details muted';

  // Add financing details
  if (data.pledge_totals && data.pledge_totals.total_usd !== undefined) {
    const totalUsd = data.pledge_totals.total_usd;
    const currency = data.pledge_totals.currency || 'USD';
    const totalLabel = document.createElement('dt');
    totalLabel.textContent = 'Total Pledged';
    const totalValue = document.createElement('dd');
    totalValue.textContent = `${currency} ${totalUsd}`;
    details.appendChild(totalLabel);
    details.appendChild(totalValue);
  }

  if (data.pledge_totals && data.pledge_totals.total_count !== undefined) {
    const count = data.pledge_totals.total_count;
    const countLabel = document.createElement('dt');
    countLabel.textContent = 'Total Pledges';
    const countValue = document.createElement('dd');
    countValue.textContent = String(count);
    details.appendChild(countLabel);
    details.appendChild(countValue);
  }

  if (data.sponsor_count !== undefined) {
    const sponsorLabel = document.createElement('dt');
    sponsorLabel.textContent = 'Sponsor Count';
    const sponsorValue = document.createElement('dd');
    sponsorValue.textContent = String(data.sponsor_count);
    details.appendChild(sponsorLabel);
    details.appendChild(sponsorValue);
  }

  if (data.funding_status) {
    const fsLabel = document.createElement('dt');
    fsLabel.textContent = 'Funding Status';
    const fsValue = document.createElement('dd');
    fsValue.textContent = data.funding_status.replace(/_/g, ' ');
    details.appendChild(fsLabel);
    details.appendChild(fsValue);
  }

  if (data.public_visibility) {
    const pvLabel = document.createElement('dt');
    pvLabel.textContent = 'Visibility';
    const pvValue = document.createElement('dd');
    pvValue.textContent = data.public_visibility.replace(/_/g, ' ');
    details.appendChild(pvLabel);
    details.appendChild(pvValue);
  }

  if (details.children.length > 0) {
    el.appendChild(details);
  }

  // Advisory only note
  if (data.advisory_only === true) {
    const note = document.createElement('div');
    note.className = 'muted funding-summary-note';
    note.textContent = 'Monetization metadata is advisory only.';
    el.appendChild(note);
  }

  return el;
}
