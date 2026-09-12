const form = document.querySelector('#upload-form');
const fileInput = document.querySelector('#file-input');
const fileLabel = document.querySelector('#file-label');
const docTypeSelect = document.querySelector('#document-type');
const statusMsg = document.querySelector('#status-message');
const historyList = document.querySelector('#history-list');
const historyCount = document.querySelector('#history-count');

const resultSection = document.querySelector('#result-section');
const resDocName = document.querySelector('#res-doc-name');
const resStatusBadge = document.querySelector('#res-status-badge');
const resultContentBody = document.querySelector('#result-content-body');
const rawJsonBtn = document.querySelector('#raw-json-btn');
const rawJsonDisplay = document.querySelector('#raw-json-display');

fileInput.addEventListener('change', () => {
  fileLabel.textContent = fileInput.files[0]?.name || 'Select or drop document file';
});

rawJsonBtn.addEventListener('click', () => {
  rawJsonDisplay.classList.toggle('hidden');
});

async function loadHistory() {
  try {
    const res = await fetch('/api/v1/documents');
    const items = await res.json();
    historyCount.textContent = items.length;

    if (!items.length) {
      historyList.innerHTML = '<p class="empty-state">No processed documents yet.</p>';
      return;
    }

    historyList.innerHTML = items.map(item => `
      <article class="history-item" data-name="${encodeURIComponent(item.document_name)}">
        <div>
          <div class="history-name">${escapeHtml(item.document_name)}</div>
          <div class="history-meta">${item.document_type} • ${new Date(item.processed_at).toLocaleString()}</div>
        </div>
        <span class="badge ${item.processing_status === 'FAILED' ? 'failed' : 'PASS'}">${item.processing_status}</span>
      </article>
    `).join('');

    historyList.querySelectorAll('.history-item').forEach(el => {
      el.addEventListener('click', () => openDocument(decodeURIComponent(el.dataset.name)));
    });
  } catch (err) {
    console.error("Failed to load history:", err);
  }
}

async function openDocument(docName) {
  try {
    const res = await fetch(`/api/v1/documents/${encodeURIComponent(docName)}`);
    if (!res.ok) throw new Error("Document not found");
    const data = await res.json();
    renderResult(data);
  } catch (err) {
    alert(err.message);
  }
}

function renderResult(data) {
  resultSection.classList.remove('hidden');
  resDocName.textContent = data.document_name;
  resStatusBadge.textContent = data.processing_status;
  resStatusBadge.className = `badge ${data.processing_status === 'FAILED' ? 'failed' : 'PASS'}`;

  rawJsonDisplay.textContent = JSON.stringify(data, null, 2);

  const extracted = data.extracted_data || {};
  const fields = Object.entries(extracted).filter(([k]) => k !== 'line_items' && k !== 'periods' && k !== 'raw_text' && k !== 'page_texts');

  const fieldsMarkup = fields.map(([key, obj]) => {
    const val = obj?.value;
    const valStr = (val === null || val === undefined) ? 'Not Found' : String(val);
    const isNull = val === null || val === undefined;
    return `
      <div class="field-card">
        <div class="field-label">${key.replaceAll('_', ' ')}</div>
        <div class="field-value ${isNull ? 'null' : ''}">${escapeHtml(valStr)}</div>
      </div>
    `;
  }).join('');

  const pageTexts = extracted.page_texts || [];
  const sourceMarkup = pageTexts.length ? `
    <details class="source-text-panel">
      <summary>OCR source text (${pageTexts.length} page${pageTexts.length === 1 ? '' : 's'})</summary>
      <pre class="json-box">${escapeHtml(pageTexts.join('\n\n'))}</pre>
    </details>
  ` : '';

  // Line items
  const lineItems = extracted.line_items || [];
  let lineItemsMarkup = '';
  if (lineItems.length) {
    const rows = lineItems.map(item => `
      <tr>
        <td>${escapeHtml(item.description || item.line_item || 'Item')}</td>
        <td>${item.quantity ?? 1}</td>
        <td>${item.unit_price ?? item.value ?? '-'}</td>
        <td>${item.amount ?? item.value ?? '-'}</td>
      </tr>
    `).join('');

    lineItemsMarkup = `
      <div style="margin-top: 24px;">
        <h3 style="font-size: 14px; color: #94a3b8; margin-bottom: 12px; font-weight: 600;">LINE ITEMS / TABLES</h3>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr><th>Description</th><th>Quantity</th><th>Unit Price</th><th>Amount</th></tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>
    `;
  }

  // Financial Validation Checks
  const checks = data.validation?.checks || [];
  const checksMarkup = checks.map(c => `
    <div class="check-item">
      <div>
        <strong style="color: #fff; font-size: 14px;">${escapeHtml(c.name)}</strong>
        <div class="check-formula">${escapeHtml(c.formula)}</div>
        <small style="color: #94a3b8;">Calculated: ${c.calculated_value ?? 'N/A'} | Reported: ${c.reported_value ?? 'N/A'} (Diff: ${c.variance ?? 0})</small>
      </div>
      <span class="badge ${c.status === 'PASS' ? 'PASS' : 'failed'}">${c.status}</span>
    </div>
  `).join('');

  resultContentBody.innerHTML = `
    <h3 style="font-size: 14px; color: #94a3b8; margin-bottom: 12px; font-weight: 600;">KEY EXTRACTED FIELDS</h3>
    <div class="fields-grid">${fieldsMarkup}</div>
    ${sourceMarkup}
    ${lineItemsMarkup}
    <h3 style="font-size: 14px; color: #94a3b8; margin-top: 24px; margin-bottom: 12px; font-weight: 600;">FINANCIAL VALIDATION</h3>
    <div class="checks-list">${checksMarkup || '<p style="color: #94a3b8;">No checks performed.</p>'}</div>
  `;

  resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

form.addEventListener('submit', async e => {
  e.preventDefault();
  if (!fileInput.files.length) return;

  statusMsg.textContent = 'Scanning document and parsing fields with EasyOCR...';
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  formData.append('document_type', docTypeSelect.value);

  try {
    const res = await fetch('/api/v1/documents/process', { method: 'POST', body: formData });
    const responseText = await res.text();
    let data = {};
    if (responseText.trim()) {
      try {
        data = JSON.parse(responseText);
      } catch {
        throw new Error(`Server returned invalid JSON (HTTP ${res.status})`);
      }
    }
    if (!res.ok) {
      throw new Error(data.detail || data.error?.message || `Upload & parsing failed (HTTP ${res.status})`);
    }
    if (!responseText.trim()) throw new Error(`Server returned an empty response (HTTP ${res.status})`);
    statusMsg.textContent = 'Processing completed!';
    renderResult(data);
    await loadHistory();
  } catch (err) {
    statusMsg.textContent = 'Error: ' + err.message;
  }
});

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}

fetch('/api/v1/health')
  .then(r => r.ok ? 'API Online' : 'API Unavailable')
  .then(txt => document.querySelector('#health-pill').textContent = txt)
  .catch(() => document.querySelector('#health-pill').textContent = 'API Offline');

loadHistory();
