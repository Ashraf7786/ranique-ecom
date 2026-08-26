'use strict';
/* ================================================================
   app.js — Ranique Store Toolkit
   Handles: Tab Switching, Label Stamper, and Address Verifier
   ================================================================ */

const $ = id => document.getElementById(id);

// ── Tab Navigation ──────────────────────────────────────────────────────────
const tabStamper   = $('tab-stamper');
const tabVerifier  = $('tab-verifier');
const panelStamper = $('panel-stamper');
const panelVerifier= $('panel-verifier');
const heroStamper  = $('hero-stamper');
const heroVerifier = $('hero-verifier');
const stepsStamper = $('steps-stamper');
const stepsVerifier= $('steps-verifier');

function switchTab(target) {
  if (target === 'stamper') {
    tabStamper.classList.add('active');
    tabStamper.setAttribute('aria-selected', 'true');
    tabVerifier.classList.remove('active');
    tabVerifier.setAttribute('aria-selected', 'false');

    panelStamper.classList.remove('hidden');
    panelVerifier.classList.add('hidden');
    
    heroStamper.classList.remove('hidden');
    heroVerifier.classList.add('hidden');

    stepsStamper.classList.remove('hidden');
    stepsVerifier.classList.add('hidden');
  } else {
    tabVerifier.classList.add('active');
    tabVerifier.setAttribute('aria-selected', 'true');
    tabStamper.classList.remove('active');
    tabStamper.setAttribute('aria-selected', 'false');

    panelVerifier.classList.remove('hidden');
    panelStamper.classList.add('hidden');

    heroVerifier.classList.remove('hidden');
    heroStamper.classList.add('hidden');

    stepsVerifier.classList.remove('hidden');
    stepsStamper.classList.add('hidden');
  }
}

tabStamper.addEventListener('click', () => switchTab('stamper'));
tabVerifier.addEventListener('click', () => switchTab('verifier'));


// ── Label Stamper Logic ─────────────────────────────────────────────────────
const uploadZone  = $('upload-zone');
const fileInput   = $('file-input');
const uzIdle      = $('uz-idle');
const uzReady     = $('uz-ready');
const uzFilename  = $('uz-filename');
const btnChange   = $('btn-change');

const inpName     = $('inp-name');
const inpLink     = $('inp-link');
const presets     = document.querySelectorAll('.preset');

const btnStamp    = $('btn-stamp');
const stampLabel  = $('stamp-label');

const loading     = $('loading');
const successCard = $('success-card');
const btnAnother  = $('btn-another');

const toast       = $('toast');
const toastMsg    = $('toast-msg');
const toastClose  = $('toast-close');

let selectedFile  = null;
let toastTimer    = null;

function setFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showToast('Please select a PDF file.');
    return;
  }
  if (file.size > 30 * 1024 * 1024) {
    showToast('File too large — maximum 30 MB.');
    return;
  }
  selectedFile = file;
  uzFilename.textContent = file.name;
  uzIdle.classList.add('hidden');
  uzReady.classList.remove('hidden');
  validate();
}

function clearFile() {
  selectedFile = null;
  fileInput.value = '';
  uzIdle.classList.remove('hidden');
  uzReady.classList.add('hidden');
  validate();
}

uploadZone.addEventListener('click', e => {
  if (e.target === btnChange || btnChange.contains(e.target)) return;
  if (!selectedFile) fileInput.click();
});
uploadZone.addEventListener('keydown', e => {
  if ((e.key === 'Enter' || e.key === ' ') && !selectedFile) {
    e.preventDefault();
    fileInput.click();
  }
});
fileInput.addEventListener('change', e => {
  if (e.target.files?.[0]) setFile(e.target.files[0]);
});
btnChange.addEventListener('click', e => { e.stopPropagation(); clearFile(); });

uploadZone.addEventListener('dragover', e => {
  e.preventDefault();
  uploadZone.classList.add('drag-over');
});
['dragleave','dragend'].forEach(ev =>
  uploadZone.addEventListener(ev, () => uploadZone.classList.remove('drag-over'))
);
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  const file = e.dataTransfer.files?.[0];
  if (file) setFile(file);
});

presets.forEach(btn => {
  btn.addEventListener('click', () => {
    const prefix  = btn.dataset.prefix;
    const current = inpLink.value.trim();
    if (!current || !current.startsWith(prefix)) {
      inpLink.value = prefix;
    }
    inpLink.focus();
    inpLink.setSelectionRange(inpLink.value.length, inpLink.value.length);
    validate();
  });
});

function validate() {
  const ok = selectedFile && inpLink.value.trim().length > 5;
  btnStamp.disabled = !ok;
}

inpLink.addEventListener('input', validate);
inpName.addEventListener('input', validate);

let stampedPdfBlobUrl = null;

btnStamp.addEventListener('click', async () => {
  if (!selectedFile) return;

  const link = inpLink.value.trim();
  const name = inpName.value.trim() || 'RANIQUE LIFESTYLE';
  if (!link) { showToast('Please enter your store link.'); return; }

  const convert4x6 = document.getElementById('inp-convert-4x6').checked ? 'true' : 'false';

  const fd = new FormData();
  fd.append('pdf',        selectedFile);
  fd.append('store_link', link);
  fd.append('store_name', name);
  fd.append('convert_4x6', convert4x6);

  loading.classList.remove('hidden');
  successCard.classList.add('hidden');
  stampLabel.textContent = 'Processing…';

  try {
    const res = await fetch('/api/stamp', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Server error ${res.status}`);
    }
    const blob = await res.blob();
    
    // Revoke any previous URL
    if (stampedPdfBlobUrl) {
      URL.revokeObjectURL(stampedPdfBlobUrl);
    }
    
    // Create new URL and set preview iframe source
    stampedPdfBlobUrl = URL.createObjectURL(blob);
    const iframe = document.getElementById('stamper-pdf-iframe');
    iframe.src = stampedPdfBlobUrl;
    iframe.classList.remove('hidden');
    document.getElementById('stamper-preview-placeholder').classList.add('hidden');
    
    successCard.classList.remove('hidden');
    successCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (err) {
    showToast(`Failed: ${err.message}`);
  } finally {
    loading.classList.add('hidden');
    stampLabel.textContent = 'Stamp & Preview Label';
  }
});

// Download button inside success card
document.getElementById('btn-download-pdf').addEventListener('click', () => {
  if (!stampedPdfBlobUrl) return;
  const a = Object.assign(document.createElement('a'), {
    href: stampedPdfBlobUrl,
    download: 'ranique_branded_label.pdf',
  });
  document.body.appendChild(a);
  a.click();
  a.remove();
});

// Fullscreen View button inside success card
document.getElementById('btn-tab-preview').addEventListener('click', () => {
  if (!stampedPdfBlobUrl) return;
  window.open(stampedPdfBlobUrl, '_blank');
});

btnAnother.addEventListener('click', () => {
  successCard.classList.add('hidden');
  if (stampedPdfBlobUrl) {
    URL.revokeObjectURL(stampedPdfBlobUrl);
    stampedPdfBlobUrl = null;
  }
  const iframe = document.getElementById('stamper-pdf-iframe');
  iframe.src = "";
  iframe.classList.add('hidden');
  document.getElementById('stamper-preview-placeholder').classList.remove('hidden');
  clearFile();
  uploadZone.scrollIntoView({ behavior: 'smooth', block: 'center' });
});


// ── Address Verifier Logic ──────────────────────────────────────────────────
const inpAddress           = $('inp-address');
const btnVerify            = $('btn-verify');
const cardVerifyResults    = $('card-verify-results');
const statusBadge          = $('verify-status-badge');

// Verifier Dropzone Refs
const verifierDropzone     = $('verifier-dropzone');
const verifierFileInput    = $('verifier-file-input');
const vdIdle               = $('vd-idle');
const vdReady              = $('vd-ready');
const vdFilename           = $('vd-filename');
const btnChangeVerifierFile= $('btn-change-verifier-file');

// Dashboard Summary Badges
const batchTotalBadge      = $('batch-total-badge');
const batchPassBadge       = $('batch-pass-badge');
const batchFailBadge       = $('batch-fail-badge');
const verifierBatchTbody   = $('verifier-batch-tbody');

// Batch Action Buttons
const btnCopyAllPassed     = $('btn-copy-all-passed');
const btnResetVerifier     = $('btn-reset-verifier');

let verifierFiles = [];
let verifiedAddresses = []; // to cache correct addresses for batch copying

// File Input events
verifierDropzone.addEventListener('click', e => {
  if (e.target === btnChangeVerifierFile || btnChangeVerifierFile.contains(e.target)) return;
  if (verifierFiles.length === 0) verifierFileInput.click();
});
verifierFileInput.addEventListener('change', e => {
  if (e.target.files && e.target.files.length > 0) {
    setVerifierFiles(e.target.files);
  }
});
btnChangeVerifierFile.addEventListener('click', e => {
  e.stopPropagation();
  clearVerifierFiles();
});

function setVerifierFiles(files) {
  verifierFiles = Array.from(files);
  vdFilename.textContent = `${verifierFiles.length} file(s) selected`;
  vdIdle.classList.add('hidden');
  vdReady.classList.remove('hidden');
  inpAddress.value = ''; // clear pasted address since file is used
  inpAddress.disabled = true;
}

function clearVerifierFiles() {
  verifierFiles = [];
  verifierFileInput.value = '';
  vdIdle.classList.remove('hidden');
  vdReady.classList.add('hidden');
  inpAddress.disabled = false;
}

// Drag & drop
verifierDropzone.addEventListener('dragover', e => {
  e.preventDefault();
  verifierDropzone.classList.add('drag-over');
});
['dragleave','dragend'].forEach(ev =>
  verifierDropzone.addEventListener(ev, () => verifierDropzone.classList.remove('drag-over'))
);
verifierDropzone.addEventListener('drop', e => {
  e.preventDefault();
  verifierDropzone.classList.remove('drag-over');
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    setVerifierFiles(e.dataTransfer.files);
  }
});

// Trigger Bulk Verify
btnVerify.addEventListener('click', async () => {
  const addressText = inpAddress.value.trim();
  if (verifierFiles.length === 0 && !addressText) {
    showToast('Please paste an address or drop label files/images to verify.');
    return;
  }

  // Show loading
  loading.classList.remove('hidden');
  cardVerifyResults.classList.add('hidden');
  verifierBatchTbody.innerHTML = ''; // reset grid
  applyFilter('all'); // reset active filter

  verifiedAddresses = [];
  let passCount = 0;
  let failCount = 0;
  let totalCount = 0;

  const loadingTitle = document.querySelector('.loading-title');
  const loadingSub = document.querySelector('.loading-sub');

  try {
    if (verifierFiles.length > 0) {
      // A. Bulk Files Verification
      for (let i = 0; i < verifierFiles.length; i++) {
        const file = verifierFiles[i];
        
        // Update loading progress message
        loadingTitle.textContent = `Verifying label ${i + 1} of ${verifierFiles.length}…`;
        loadingSub.textContent = `Processing OCR & extraction on: ${file.name}`;

        const fd = new FormData();
        fd.append('file', file);

        try {
          const res = await fetch('/api/verify-address', {
            method: 'POST',
            body: fd
          });

          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            appendErrorRow(file.name, err.error || `Server error ${res.status}`);
            failCount++;
            totalCount++;
            continue;
          }

          const data = await res.json();
          const reports = Array.isArray(data) ? data : [data];
          
          for (let pageIdx = 0; pageIdx < reports.length; pageIdx++) {
            const report = reports[pageIdx];
            const displayName = reports.length > 1 ? `${file.name} (Page ${pageIdx + 1})` : file.name;
            appendResultRow(displayName, report);
            
            totalCount++;
            if (report.recommendation === 'shipped_parcel' || report.recommendation === 'low_risk_shipped') {
              passCount++;
              verifiedAddresses.push(report.suggested_address || report.raw_address);
            } else {
              failCount++;
            }
          }
        } catch (err) {
          appendErrorRow(file.name, err.message);
          failCount++;
          totalCount++;
        }
      }
    } else {
      // B. Single Pasted Text Verification
      loadingTitle.textContent = "Verifying address…";
      loadingSub.textContent = "Checking details with Indian Post database";

      try {
        const res = await fetch('/api/verify-address', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ address: addressText })
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          appendErrorRow("Pasted Text Input", err.error || `Server error ${res.status}`);
          failCount++;
          totalCount++;
        } else {
          const data = await res.json();
          const reports = Array.isArray(data) ? data : [data];
          
          for (let pageIdx = 0; pageIdx < reports.length; pageIdx++) {
            const report = reports[pageIdx];
            const displayName = reports.length > 1 ? `Pasted Text Input (Page ${pageIdx + 1})` : "Pasted Text Input";
            appendResultRow(displayName, report);
            
            totalCount++;
            if (report.recommendation === 'shipped_parcel' || report.recommendation === 'low_risk_shipped') {
              passCount++;
              verifiedAddresses.push(report.suggested_address || report.raw_address);
            } else {
              failCount++;
            }
          }
        }
      } catch (err) {
        appendErrorRow("Pasted Text Input", err.message);
        failCount++;
        totalCount++;
      }
    }

    // Update summary badges
    batchTotalBadge.textContent = `${totalCount} Label(s) Verified`;
    batchPassBadge.textContent = `${passCount} Safe`;
    batchFailBadge.textContent = `${failCount} Warning/Fail`;

    // Show result card dashboard
    cardVerifyResults.classList.remove('hidden');
    cardVerifyResults.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  } catch (err) {
    showToast(`Verification process error: ${err.message}`);
  } finally {
    // Reset loader text
    loading.classList.add('hidden');
    loadingTitle.textContent = "Stamping your label…";
    loadingSub.textContent = "Generating QR + adding branding strip";
  }
});

// Append verified row to table
function appendResultRow(sourceName, data) {
  const tr = document.createElement('tr');
  tr.style.borderBottom = '1px solid var(--b1)';
  tr.dataset.recommendation = data.recommendation; // 'shipped_parcel', 'low_risk_shipped', 'do_not_ship'
  
  // Clean file name
  const sourceNameEscaped = sourceName.replace(/</g, "&lt;").replace(/>/g, "&gt;");
  
  // Address candidate column
  const addrClean = (data.raw_address || '—').replace(/</g, "&lt;").replace(/>/g, "&gt;");
  
  // Pincode cell
  let pinCellHtml = "";
  if (data.pincode_valid) {
    pinCellHtml = `<span style="color: var(--success); font-weight: 700; display: inline-flex; align-items: center; gap: 4px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 5 12"/></svg>${data.pincode}</span>`;
  } else {
    pinCellHtml = `<span style="color: var(--error); font-weight: 700; display: inline-flex; align-items: center; gap: 4px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>${data.pincode || 'Missing'}</span>`;
  }

  // Matches cell
  let matchCellHtml = "";
  if (data.state_match === true && data.district_match === true) {
    matchCellHtml = `<span style="color: var(--success); display: inline-flex; align-items: center; gap: 4px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 5 12"/></svg>State &amp; District Verified</span>`;
  } else {
    let parts = [];
    if (data.state_match === false) {
      parts.push(`<span style="color: var(--error); display: inline-flex; align-items: center; gap: 4px;"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>State Mismatch</span>`);
    }
    if (data.district_match === false) {
      parts.push(`<span style="color: var(--error); display: inline-flex; align-items: center; gap: 4px;"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>District Mismatch</span>`);
    }
    if (parts.length === 0) {
      parts.push(`<span style="color: var(--t3);">Verification Partial</span>`);
    }
    matchCellHtml = parts.join("<br>");
  }

  // Hub cell
  const hubEscaped = (data.delivery_hub || '—').replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const courierEscaped = (data.courier_name || '—').replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const hubCellHtml = `<strong>${hubEscaped}</strong><br><span style="font-size:11px; color:var(--t3);">${courierEscaped}</span>`;

  // Map Link Cell
  let mapCellHtml = "—";
  if (data.google_maps_link) {
    mapCellHtml = `
      <a href="${data.google_maps_link}" target="_blank" style="color: var(--gold-1); display: inline-flex; align-items: center; gap: 6px; text-decoration: none; font-weight: 700; transition: var(--t);" class="map-link-btn">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
          <circle cx="12" cy="10" r="3"/>
        </svg>
        Verify Map
      </a>
    `;
  }

  // Recommendation Badge
  let recHtml = "";
  if (data.recommendation === 'shipped_parcel') {
    recHtml = `<span style="color: var(--success); background: var(--success-bg); border: 1px solid rgba(12,176,130,0.3); padding: 4px 10px; border-radius: 99px; font-weight: 700; font-size:11px; display:inline-flex; align-items:center; gap:5px;"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><polyline points="20 6 9 17 5 12"/></svg>Safe to Ship</span>`;
  } else if (data.recommendation === 'low_risk_shipped') {
    recHtml = `<span style="color: #ee7540; background: var(--gold-dim); border: 1px solid var(--b-gold); padding: 4px 10px; border-radius: 99px; font-weight: 700; font-size:11px; display:inline-flex; align-items:center; gap:5px;"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>Low Risk Warning</span>`;
  } else {
    recHtml = `<span style="color: var(--error); background: var(--error-bg); border: 1px solid rgba(229,62,62,0.3); padding: 4px 10px; border-radius: 99px; font-weight: 700; font-size:11px; display:inline-flex; align-items:center; gap:5px;"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>Do Not Ship (High Risk)</span>`;
  }

  // Reasons Cell
  let reasonHtml = "";
  if (data.detailed_reasons && data.detailed_reasons.length > 0) {
    reasonHtml = `<ul style="padding-left: 14px; margin: 0; font-size: 11.5px; color: var(--t2); display:flex; flex-direction:column; gap:2px;">`;
    data.detailed_reasons.forEach(r => {
      reasonHtml += `<li>${r.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</li>`;
    });
    reasonHtml += `</ul>`;
  } else {
    reasonHtml = `<span style="color: var(--success); display: inline-flex; align-items: center; gap: 4px;"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 5 12"/></svg>All parameters valid. Safe routing.</span>`;
  }

  tr.innerHTML = `
    <td style="padding: 12px 16px; font-weight: 600; color: var(--t2); max-width: 140px; word-break: break-all;">${sourceNameEscaped}</td>
    <td style="padding: 12px 16px; font-size: 12px; max-width: 250px; word-break: break-word;">${addrClean}</td>
    <td style="padding: 12px 16px; font-family: var(--mono);">${pinCellHtml}</td>
    <td style="padding: 12px 16px; font-size: 12px;">${matchCellHtml}</td>
    <td style="padding: 12px 16px; font-size: 12px;">${hubCellHtml}</td>
    <td style="padding: 12px 16px; font-size: 12px; white-space: nowrap;">${mapCellHtml}</td>
    <td style="padding: 12px 16px;">${recHtml}</td>
    <td style="padding: 12px 16px; font-size: 12px; max-width: 300px;">${reasonHtml}</td>
  `;
  verifierBatchTbody.appendChild(tr);
}

// Append error row
function appendErrorRow(sourceName, errorMsg) {
  const tr = document.createElement('tr');
  tr.style.borderBottom = '1px solid var(--b1); background: rgba(229,62,62,0.02);';
  tr.dataset.recommendation = 'do_not_ship'; // failures are high risk
  const nameEsc = sourceName.replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const errEsc = errorMsg.replace(/</g, "&lt;").replace(/>/g, "&gt;");

  tr.innerHTML = `
    <td style="padding: 12px 16px; font-weight: 600; color: var(--error);">${nameEsc}</td>
    <td style="padding: 12px 16px; color: var(--error);" colspan="5">Processing Failed</td>
    <td style="padding: 12px 16px;"><span style="color: var(--error); background: var(--error-bg); border: 1px solid rgba(229,62,62,0.3); padding: 4px 10px; border-radius: 99px; font-weight: 700; font-size:11px; display:inline-flex; align-items:center; gap:5px;"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>Do Not Ship (High Risk)</span></td>
    <td style="padding: 12px 16px; font-size: 12.5px; color: #ffb3c0;">${errEsc}</td>
  `;
  verifierBatchTbody.appendChild(tr);
}

// Copy all safe addresses
btnCopyAllPassed.addEventListener('click', () => {
  if (verifiedAddresses.length === 0) {
    showToast('No safe addresses to copy.');
    return;
  }
  const text = verifiedAddresses.join("\n---\n");
  navigator.clipboard.writeText(text).then(() => {
    showToast(`Copied ${verifiedAddresses.length} safe address(es) to clipboard!`);
  }).catch(() => {
    showToast('Failed to copy to clipboard.');
  });
});

// Reset verifier
btnResetVerifier.addEventListener('click', () => {
  cardVerifyResults.classList.add('hidden');
  clearVerifierFiles();
  inpAddress.value = '';
  inpAddress.focus();
});

// Interactive Table Filtering
let currentFilter = 'all';

function applyFilter(filter) {
  currentFilter = filter;
  
  // Update badge active styles
  batchTotalBadge.classList.remove('active-filter');
  batchPassBadge.classList.remove('active-filter');
  batchFailBadge.classList.remove('active-filter');
  
  if (filter === 'all') {
    batchTotalBadge.classList.add('active-filter');
  } else if (filter === 'safe') {
    batchPassBadge.classList.add('active-filter');
  } else if (filter === 'high_risk') {
    batchFailBadge.classList.add('active-filter');
  }
  
  // Show/hide rows based on filter selection
  const rows = verifierBatchTbody.querySelectorAll('tr');
  rows.forEach(row => {
    const rec = row.dataset.recommendation;
    if (filter === 'all') {
      row.classList.remove('hidden');
    } else if (filter === 'safe') {
      if (rec === 'shipped_parcel' || rec === 'low_risk_shipped') {
        row.classList.remove('hidden');
      } else {
        row.classList.add('hidden');
      }
    } else if (filter === 'high_risk') {
      if (rec === 'do_not_ship') {
        row.classList.remove('hidden');
      } else {
        row.classList.add('hidden');
      }
    }
  });
}

// Add event listeners for filter badges
batchTotalBadge.addEventListener('click', () => applyFilter('all'));
batchPassBadge.addEventListener('click', () => applyFilter('safe'));
batchFailBadge.addEventListener('click', () => applyFilter('high_risk'));


// ── Toast Notifications ─────────────────────────────────────────────────────
function showToast(msg) {
  toastMsg.textContent = msg;
  toast.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add('hidden'), 7000);
}
toastClose.addEventListener('click', () => {
  toast.classList.add('hidden');
  clearTimeout(toastTimer);
});


