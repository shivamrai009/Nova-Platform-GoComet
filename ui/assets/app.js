const ingestForm = document.getElementById('ingestForm');
const queryForm = document.getElementById('queryForm');
const sampleCleanBtn = document.getElementById('sampleCleanBtn');
const sampleMessyBtn = document.getElementById('sampleMessyBtn');
const statusEl = document.getElementById('status');
const resultEl = document.getElementById('result');
const queryResultEl = document.getElementById('queryResult');
const decisionBadgeEl = document.getElementById('decisionBadge');
const incomingStateEl = document.getElementById('incomingState');
const discrepancyDetailEl = document.getElementById('discrepancyDetail');
const draftReplyEl = document.getElementById('draftReply');

let activeSelectedField = null;
let activeRun = null;
let validationFilterActive = false;

ingestForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  statusEl.textContent = 'Processing incoming email...';

  const payload = new FormData(ingestForm);
  const response = await fetch('/api/inbox/ingest', { method: 'POST', body: payload });
  if (!response.ok) {
    statusEl.textContent = `Error: ${await response.text()}`;
    return;
  }

  const ingestResult = await response.json();
  activeSelectedField = null;
  statusEl.textContent = `Email processed. Run ID: ${ingestResult.run.run_id}`;
  renderResponse(ingestResult);
});

sampleCleanBtn.addEventListener('click', () => loadSampleScenario('clean_shipment'));
sampleMessyBtn.addEventListener('click', () => loadSampleScenario('messy_shipment'));

queryForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const question = document.getElementById('question').value.trim();
  if (!question) return;

  const response = await fetch(`/api/query?q=${encodeURIComponent(question)}`);
  const data = await response.json();
  queryResultEl.textContent = `${data.answer}\n\nSQL: ${data.sql}\n\nRows: ${JSON.stringify(data.rows, null, 2)}`;
});

async function loadSampleScenario(scenarioId) {
  statusEl.textContent = `Loading sample: ${scenarioId}...`;
  const response = await fetch(`/api/inbox/simulate/${encodeURIComponent(scenarioId)}`, { method: 'POST' });
  if (!response.ok) {
    statusEl.textContent = `Error: ${await response.text()}`;
    return;
  }

  const payload = await response.json();
  activeSelectedField = null;
  statusEl.textContent = `Sample loaded. Run ID: ${payload.run.run_id}`;
  renderResponse(payload);
}

function renderResponse(payload) {
  activeRun = payload.run;
  validationFilterActive = false;
  renderIncoming(payload.incoming_email);
  renderRun(payload.run);
  draftReplyEl.value = payload.editable_draft_reply || payload.run.decision.draft_message;
  if (!activeSelectedField) {
    renderDiscrepancyPlaceholder(payload.run);
  }
}

function renderIncoming(incomingEmail) {
  if (!incomingStateEl || !incomingEmail) {
    if (incomingStateEl) {
      incomingStateEl.className = 'state-card muted';
      incomingStateEl.textContent = 'Incoming state will appear here after you process or load a sample.';
    }
    return;
  }

  const attachments = incomingEmail.attachments.map((item) => item.filename).join(', ');
  incomingStateEl.className = 'state-card';
  incomingStateEl.innerHTML = `
    <div class="incoming-grid">
      <div><span>From</span><strong>${incomingEmail.sender}</strong></div>
      <div><span>Subject</span><strong>${incomingEmail.subject}</strong></div>
      <div><span>Customer</span><strong>${incomingEmail.customer_id}</strong></div>
      <div><span>Attachments</span><strong>${attachments}</strong></div>
    </div>
    <p>${incomingEmail.body}</p>
  `;
}

function renderRun(run) {
  updateDecisionBadge(run);
  const fields = bestFieldMap(run.extractions);

  const extractionRows = Object.keys(fields).map((name) => {
    const item = fields[name];
    return `<tr><td>${name}</td><td>${item.value ?? ''}</td><td>${item.confidence.toFixed(2)}</td><td>${item.source_doc}</td><td>${item.evidence ?? ''}</td></tr>`;
  }).join('');

  const validationItems = Object.values(run.validation.field_results)
    .filter((item) => shouldShowValidationRow(item, run.decision.decision));

  const validationRows = validationItems.map((item) => {
    return `<tr data-field="${item.field}" class="${item.status} clickable-row">
      <td>${item.field}</td>
      <td><span class="badge ${item.status}">${item.status}</span></td>
      <td>${item.found ?? ''}</td>
      <td>${item.expected ?? ''}</td>
      <td>${item.confidence.toFixed(2)}</td>
      <td>${item.reason}</td>
    </tr>`;
  }).join('');

  const validationMode = validationFilterActive && canFilterForDecision(run.decision.decision)
    ? 'Showing only exception fields.'
    : 'Showing all validation fields.';

  const crossDoc = run.validation.cross_doc_issues.length
    ? `<h4>Cross-document issues</h4><ul>${run.validation.cross_doc_issues.map((x) => `<li>${x}</li>`).join('')}</ul>`
    : '<h4>Cross-document issues</h4><p>None</p>';

  resultEl.innerHTML = `
    <p>${validationMode}</p>
    <table>
      <thead><tr><th>Field</th><th>Value</th><th>Confidence</th><th>Source Doc</th><th>Evidence</th></tr></thead>
      <tbody>${extractionRows}</tbody>
    </table>

    <h3>Validation</h3>
    <table>
      <thead><tr><th>Field</th><th>Status</th><th>Found</th><th>Expected</th><th>Confidence</th><th>Reason</th></tr></thead>
      <tbody>${validationRows}</tbody>
    </table>

    ${crossDoc}

    <h3>Decision</h3>
    <p><strong>${run.decision.decision}</strong></p>
    <p>${run.decision.reasoning}</p>
  `;

  resultEl.querySelectorAll('.clickable-row').forEach((row) => {
    row.addEventListener('click', () => {
      activeSelectedField = row.dataset.field;
      renderDiscrepancyDetail(run, activeSelectedField);
    });
  });
}

function updateDecisionBadge(run) {
  if (!decisionBadgeEl) return;

  const decision = run?.decision?.decision;
  const known = ['auto_approve', 'human_review', 'amendment_request'];
  if (!decision || !known.includes(decision)) {
    decisionBadgeEl.className = 'decision-pill muted';
    decisionBadgeEl.textContent = 'No run yet';
    decisionBadgeEl.title = 'Run the pipeline to enable quick filtering.';
    return;
  }

  const filtered = validationFilterActive && canFilterForDecision(decision);
  const interactiveClass = canFilterForDecision(decision) ? 'interactive' : '';
  const filteredClass = filtered ? 'is-filtered' : '';
  decisionBadgeEl.className = `decision-pill ${decision} ${interactiveClass} ${filteredClass}`.trim();
  const totals = summarizeValidationTotals(run);
  const decisionLabel = decision.replace('_', ' ').toUpperCase();
  decisionBadgeEl.textContent = `${decisionLabel} · ${totals.mismatches} mismatches · ${totals.uncertain} uncertain`;
  decisionBadgeEl.title = canFilterForDecision(decision)
    ? (filtered
      ? 'Click to show all validation fields.'
      : 'Click to show only uncertain and mismatch fields.')
    : 'No exception filter needed for auto-approved runs.';
}

function summarizeValidationTotals(run) {
  const items = Object.values(run?.validation?.field_results || {});
  const mismatches = items.filter((item) => item.status === 'mismatch').length + (run?.validation?.cross_doc_issues?.length || 0);
  const uncertain = items.filter((item) => item.status === 'uncertain').length;
  return { mismatches, uncertain };
}

function canFilterForDecision(decision) {
  return decision === 'human_review' || decision === 'amendment_request';
}

function shouldShowValidationRow(item, decision) {
  if (!item) {
    return false;
  }
  if (!validationFilterActive || !canFilterForDecision(decision)) {
    return true;
  }
  return item.status !== 'match';
}

function bestFieldMap(extractions) {
  const best = {};
  for (const ext of extractions) {
    for (const [name, field] of Object.entries(ext.fields)) {
      if (!best[name] || field.confidence > best[name].confidence) {
        best[name] = field;
      }
    }
  }
  return best;
}

function renderDiscrepancyPlaceholder(run) {
  const firstIssue = Object.values(run.validation.field_results).find((item) => item.status !== 'match') || null;
  if (!firstIssue) {
    discrepancyDetailEl.className = 'state-card';
    discrepancyDetailEl.textContent = 'No discrepancies. Select a field only if you want to inspect a matched value.';
    return;
  }

  renderDiscrepancyDetail(run, firstIssue.field);
}

function renderDiscrepancyDetail(run, fieldName) {
  const validation = run.validation.field_results[fieldName];
  if (!validation) return;

  const extracted = locateBestExtraction(run.extractions, fieldName);
  const snippet = extracted?.evidence || 'No source snippet captured for this field.';

  discrepancyDetailEl.className = 'state-card';
  discrepancyDetailEl.innerHTML = `
    <div class="detail-header">
      <h3>${fieldName}</h3>
      <span class="badge ${validation.status}">${validation.status}</span>
    </div>
    <p><strong>Found:</strong> ${validation.found ?? '—'}</p>
    <p><strong>Expected:</strong> ${validation.expected ?? '—'}</p>
    <p><strong>Confidence:</strong> ${validation.confidence.toFixed(2)}</p>
    <p><strong>Reason:</strong> ${validation.reason}</p>
    <p><strong>Source snippet:</strong></p>
    <pre>${snippet}</pre>
  `;
}

function locateBestExtraction(extractions, fieldName) {
  let best = null;
  for (const extraction of extractions) {
    const field = extraction.fields[fieldName];
    if (!field) continue;
    if (!best || field.confidence > best.confidence) {
      best = field;
    }
  }
  return best;
}

if (decisionBadgeEl) {
  decisionBadgeEl.addEventListener('click', () => {
    if (!activeRun || !canFilterForDecision(activeRun?.decision?.decision)) {
      return;
    }
    validationFilterActive = !validationFilterActive;
    renderRun(activeRun);
    if (activeSelectedField && !shouldShowValidationRow(activeRun.validation.field_results[activeSelectedField], activeRun.decision.decision)) {
      activeSelectedField = null;
      renderDiscrepancyPlaceholder(activeRun);
    }
  });
}

window.addEventListener('DOMContentLoaded', () => {
  renderDiscrepancyPlaceholder({ validation: { field_results: {} } });
});
