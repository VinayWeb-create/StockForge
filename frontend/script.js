/**
 * StockForge — Dashboard Script
 * Handles all frontend logic: API calls, chart rendering, state management
 */

// ── Config ──────────────────────────────────────────────────────────────────
// Use current origin for API calls to avoid hardcoded localhost in production
const API = window.location.origin;

// ── State ────────────────────────────────────────────────────────────────────
let state = {
  rawData: null,   // raw dataset from upload/fetch
  cleanedData: null,   // cleaned dataset
  outlierData: null,   // outlier-annotated dataset
  normalizedData: null,   // normalized dataset
  symbol: null,   // current stock symbol
  outlierMethod: 'iqr',
  normMethod: 'minmax',
  edu: {
    ma: {
      title: 'Moving Averages (Price Path)',
      desc: 'It\'s like looking at a blurry photo of a running cat. You can\'t see every whisker, but you can see exactly which way the cat is running! MA7 is the last 7 days, MA50 is the last 50.'
    },
    outliers: {
      title: 'Outlier Detection (Weird Numbers)',
      desc: 'Outliers are "weird" prices that are accidentally too high or too low (like a typo). Finding them is like picking out the one blue grape in a bowl of green ones so they don\'t mess up the flavor.'
    },
    normalize: {
      title: 'Normalization (Fair Share)',
      desc: 'If we want to compare an ant to an elephant fairly, we shrink them both so they are the same size. Now we can see who is faster for their size! It makes comparing different stocks easy.'
    },
    prediction: {
      title: 'AI Prediction Confidence',
      desc: 'This is the robot\'s "Pinky Promise." A score of 1.0 means "I promise this is right!" and 0.0 means "I\'m just guessing, sorry!"'
    }
  },
  onboarding: [
    { step: '1. Give the Robot Data', desc: 'Go to "Upload" or "Fetch" to give the robot some stock numbers to read. It\'s like giving it homework!' },
    { step: '2. Wash the Data', desc: 'Go to "Clean Data." This removes any messy or empty spots so the robot doesn\'t get confused.' },
    { step: '3. Find the Weirdos', desc: 'Use "Outlier Detection" to find numbers that are accidentally too big or too small.' },
    { step: '4. The Big Guess', desc: 'Go to "AI Prediction" and ask the robot to guess if the price will go up or down tomorrow!' }
  ]
};

// Persistent Chart instances (destroy before re-create to avoid conflicts)
const charts = {};
let socket = null;

// ── DOM Ready ────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Guard: redirect to login if no user session
  const user = JSON.parse(localStorage.getItem('sf_user') || 'null');
  if (!user) { window.location.href = 'main.html'; return; }

  // Populate user chip
  document.getElementById('user-name').textContent = user.name || user.email;
  document.getElementById('user-avatar').textContent = (user.name || user.email || 'U')[0].toUpperCase();

  // Load history on launch
  loadHistory();

  // Apply saved theme
  const saved = localStorage.getItem('sf_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  updateThemeIcon();

  // Init SocketIO
  initSocket();

  // Init Education tooltips
  initEducation();

  // Auto-show Learning Center for new users
  if (!localStorage.getItem('sf_help_seen')) {
    openHelpModal();
    localStorage.setItem('sf_help_seen', 'true');
  }
});

function initEducation() {
  const tooltip = document.getElementById('edu-tooltip');
  document.querySelectorAll('.info-icon').forEach(icon => {
    icon.addEventListener('mouseenter', (e) => {
      const id = e.target.dataset.edu;
      const content = state.edu[id];
      if (!content) return;
      tooltip.innerHTML = `<strong>${content.title}</strong><br>${content.desc}`;
      tooltip.classList.add('show');

      const rect = e.target.getBoundingClientRect();
      tooltip.style.top = `${rect.top - tooltip.offsetHeight - 10}px`;
      tooltip.style.left = `${rect.left - tooltip.offsetWidth / 2 + 8}px`;
    });
    icon.addEventListener('mouseleave', () => {
      tooltip.classList.remove('show');
    });
  });
}

function openHelpModal() {
  const modal = document.getElementById('help-modal');
  const list = document.getElementById('help-content-list');

  let html = `
    <h3 class="font-syne mb-2" style="color:var(--accent2)">🚀 First Steps (How to Use)</h3>
    <div style="margin-bottom: 24px;">
      ${state.onboarding.map(o => `
        <div class="edu-card" style="border-left: 4px solid var(--accent2)">
          <h4 style="color:var(--accent2)">${o.step}</h4>
          <p>${o.desc}</p>
        </div>
      `).join('')}
    </div>
    
    <h3 class="font-syne mb-2">📖 Word Meanings (Glossary)</h3>
    <div>
      ${Object.values(state.edu).map(e => `
        <div class="edu-card">
          <h4>${e.title}</h4>
          <p>${e.desc}</p>
        </div>
      `).join('')}
    </div>
  `;

  list.innerHTML = html;
  modal.classList.add('show');
}

function closeHelpModal() {
  document.getElementById('help-modal').classList.remove('show');
}

function initSocket() {
  if (typeof io === 'undefined') return;
  // Connect to the same origin as the frontend
  socket = io(window.location.origin);

  socket.on('connect', () => {
    console.log('[Socket] Connected');
    toast('Live updates active', 'success');
    document.getElementById('data-status').textContent = 'Live • ' + (document.getElementById('data-status').textContent.split(' • ')[1] || 'No Data');
  });

  socket.on('stock_update', (data) => {
    console.log('[Socket] Update:', data);
    updateLivePrice(data);
  });
}

function updateLivePrice(data) {
  // Update UI with live price if symbol matches
  const currentSymbol = document.getElementById('fetch-symbol-badge')?.textContent;
  if (data.symbol === currentSymbol) {
    toast(`${data.symbol}: $${data.price.toFixed(2)}`, 'info');
  }
}

// ── Routing ──────────────────────────────────────────────────────────────────
function showPage(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  const target = document.getElementById(`page-${page}`);
  if (target) target.classList.add('active');

  // Highlight nav item
  document.querySelectorAll('.nav-item').forEach(n => {
    if (n.getAttribute('onclick')?.includes(page)) n.classList.add('active');
  });

  // Page titles
  const titles = {
    overview: 'Overview', upload: 'Upload Dataset', fetch: 'Fetch Live Stock',
    clean: 'Data Cleaning', outliers: 'Outlier Detection', normalize: 'Normalization',
    charts: 'Analytics Charts', predict: 'AI Prediction', compare: 'Multi-Stock Compare',
    history: 'Analysis History'
  };
  document.getElementById('page-title').textContent = titles[page] || page;

  // Refresh charts page if data loaded
  if (page === 'charts' && state.rawData) renderChartsPage();
  if (page === 'overview' && state.rawData) refreshOverview();
  if (page === 'history') loadHistory();

  // Close sidebar on mobile
  document.getElementById('sidebar').classList.remove('open');
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}

// ── Theme ─────────────────────────────────────────────────────────────────────
function toggleTheme() {
  const curr = document.documentElement.getAttribute('data-theme');
  const next = curr === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('sf_theme', next);
  updateThemeIcon();
  // Re-render charts with new theme if data loaded
  if (state.rawData) {
    refreshOverview();
    if (document.getElementById('page-charts').classList.contains('active')) renderChartsPage();
  }
}
function updateThemeIcon() {
  const btn = document.querySelector('.theme-toggle');
  btn.textContent = document.documentElement.getAttribute('data-theme') === 'dark' ? '🌙' : '☀️';
}

// ── Auth ──────────────────────────────────────────────────────────────────────
function logout() {
  localStorage.removeItem('sf_user');
  fetch(`${API}/logout`, { method: 'POST', credentials: 'include' }).finally(() => {
    window.location.href = 'main.html';
  });
}

// ── Toast Notifications ───────────────────────────────────────────────────────
function toast(msg, type = 'info') {
  const container = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

// ── Loading ───────────────────────────────────────────────────────────────────
function showLoading(msg = 'Processing...') {
  document.getElementById('loading-msg').textContent = msg;
  document.getElementById('loading-overlay').classList.remove('hidden');
}
function hideLoading() {
  document.getElementById('loading-overlay').classList.add('hidden');
}

// ── API Helper ────────────────────────────────────────────────────────────────
async function api(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    credentials: 'include',
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'API Error');
  return data;
}

// ── Data Status Badge ─────────────────────────────────────────────────────────
function updateDataStatus() {
  const badge = document.getElementById('data-status');
  if (state.rawData) {
    badge.textContent = `${state.symbol || 'Dataset'} · ${state.rawData.length} rows`;
    badge.className = 'badge badge-accent';
  } else {
    badge.textContent = 'No Data Loaded';
    badge.className = 'badge badge-success';
  }
}

// ── Table Rendering ───────────────────────────────────────────────────────────
/**
 * Render data array into an HTML table inside a container element.
 * @param {string} containerId - ID of the container div
 * @param {Array}  rows        - Array of objects
 * @param {Array}  outlierIndices - (optional) row indices to highlight red
 */
function renderTable(containerId, rows, outlierIndices = []) {
  if (!rows || rows.length === 0) {
    document.getElementById(containerId).innerHTML = '<p class="text-muted text-sm" style="padding:20px">No data to display.</p>';
    return;
  }
  const cols = Object.keys(rows[0]);
  const thead = `<thead><tr>${cols.map(c => `<th>${c}</th>`).join('')}</tr></thead>`;
  const tbody = rows.map((row, i) => {
    const cls = outlierIndices.includes(i) ? ' class="outlier"' : '';
    const cells = cols.map(c => {
      const v = row[c];
      const formatted = typeof v === 'number' ? v.toFixed(4) : (v ?? '—');
      return `<td>${formatted}</td>`;
    }).join('');
    return `<tr${cls}>${cells}</tr>`;
  }).join('');
  document.getElementById(containerId).innerHTML = `<table class="data-table">${thead}<tbody>${tbody}</tbody></table>`;
}

// ── Chart Helper ──────────────────────────────────────────────────────────────
function getChartColors() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  return {
    grid: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.08)',
    text: isDark ? '#5a6075' : '#8a92a8',
    accent: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#00e5ff',
  };
}

function destroyChart(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

function makeChart(canvasId, config) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId)?.getContext('2d');
  if (!ctx) return;
  charts[canvasId] = new Chart(ctx, config);
}

// ── UPLOAD ────────────────────────────────────────────────────────────────────
function handleDragOver(e) { e.preventDefault(); document.getElementById('drop-zone').classList.add('drag-over'); }
function handleDragLeave() { document.getElementById('drop-zone').classList.remove('drag-over'); }

function handleDrop(e) {
  e.preventDefault();
  document.getElementById('drop-zone').classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
}

function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) uploadFile(file);
}

async function uploadFile(file) {
  if (!file.name.endsWith('.csv')) return toast('Please upload a CSV file', 'error');
  if (file.size > 10 * 1024 * 1024) return toast('File too large (max 10MB)', 'error');

  showLoading('Uploading and parsing CSV...');
  const form = new FormData();
  form.append('file', file);

  try {
    const res = await fetch(`${API}/upload`, { method: 'POST', body: form, credentials: 'include' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);

    state.rawData = data.data;
    state.symbol = file.name.replace('.csv', '');
    state.cleanedData = null; state.outlierData = null; state.normalizedData = null;

    // Show preview
    document.getElementById('upload-filename').textContent = file.name;
    document.getElementById('upload-rows').textContent = `${data.data.length} rows`;
    document.getElementById('upload-preview').classList.remove('hidden');
    renderTable('upload-table-wrap', data.data.slice(0, 100));

    updateDataStatus();
    refreshOverview();
    toast(`Uploaded ${data.data.length} rows successfully`, 'success');
  } catch (e) {
    toast(e.message, 'error');
  }
  hideLoading();
}

function clearUpload() {
  state.rawData = null; state.symbol = null;
  document.getElementById('upload-preview').classList.add('hidden');
  document.getElementById('file-input').value = '';
  updateDataStatus();
}

// ── FETCH LIVE STOCK ──────────────────────────────────────────────────────────
async function fetchStock() {
  const symbol = document.getElementById('fetch-symbol').value.trim().toUpperCase();
  const period = document.getElementById('fetch-period').value;
  const interval = document.getElementById('fetch-interval').value;

  if (!symbol) return toast('Enter a stock symbol', 'error');

  showLoading(`Fetching ${symbol} from Yahoo Finance...`);
  try {
    const data = await api('/fetch-stock', {
      method: 'POST',
      body: JSON.stringify({ symbol, period, interval })
    });

    state.rawData = data.data;
    state.symbol = symbol;
    state.cleanedData = null; state.outlierData = null; state.normalizedData = null;

    document.getElementById('fetch-symbol-badge').textContent = symbol;
    document.getElementById('fetch-rows-badge').textContent = `${data.data.length} rows`;
    document.getElementById('fetch-result').classList.remove('hidden');
    renderTable('fetch-table-wrap', data.data.slice(0, 100));

    updateDataStatus();
    refreshOverview();
    toast(`Fetched ${data.data.length} rows for ${symbol}`, 'success');
  } catch (e) {
    toast(e.message, 'error');
  }
  hideLoading();
}

// ── CLEAN DATA ────────────────────────────────────────────────────────────────
async function cleanData() {
  if (!state.rawData) return toast('Load data first', 'error');

  showLoading('Cleaning dataset...');
  try {
    const data = await api('/clean-data', { method: 'POST' });

    state.cleanedData = data.cleaned;

    // Show stats
    document.getElementById('clean-removed').textContent = data.stats.rows_removed;
    document.getElementById('clean-remaining').textContent = data.stats.rows_remaining;
    document.getElementById('clean-nulls').textContent = data.stats.nulls_removed;
    document.getElementById('clean-dupes').textContent = data.stats.duplicates_removed;

    document.getElementById('clean-results').classList.remove('hidden');
    document.getElementById('clean-empty').classList.add('hidden');

    renderTable('before-table', state.rawData.slice(0, 60));
    renderTable('after-table', data.cleaned.slice(0, 60));

    // Update raw data reference to cleaned (keep original for diff display)
    toast(`Cleaning complete. ${data.stats.rows_removed} rows removed.`, 'success');
  } catch (e) {
    toast(e.message, 'error');
  }
  hideLoading();
}

// ── OUTLIER DETECTION ─────────────────────────────────────────────────────────
function selectMethod(method, el) {
  state.outlierMethod = method;
  document.querySelectorAll('#page-outliers .method-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
}

async function detectOutliers() {
  if (!state.rawData) return toast('Load data first', 'error');

  showLoading(`Running ${state.outlierMethod} outlier detection...`);
  try {
    const data = await api('/detect-outliers', {
      method: 'POST',
      body: JSON.stringify({ method: state.outlierMethod })
    });

    state.outlierData = data.data;
    const outlierIdxs = data.data
      .map((r, i) => r.__outlier ? i : null)
      .filter(i => i !== null);

    document.getElementById('out-count').textContent = data.stats.outlier_count;
    document.getElementById('out-total').textContent = data.stats.total_rows;
    document.getElementById('out-pct').textContent = data.stats.outlier_pct + '%';

    document.getElementById('outlier-results').classList.remove('hidden');
    document.getElementById('outlier-empty').classList.add('hidden');
    document.getElementById('remove-outliers-btn').style.display = 'inline-flex';

    // Strip __outlier field before table display
    const displayData = data.data.map(r => { const { __outlier, ...rest } = r; return rest; });
    renderTable('outlier-table', displayData, outlierIdxs);

    toast(`Found ${data.stats.outlier_count} outliers (${data.stats.outlier_pct}%)`, 'info');
  } catch (e) {
    toast(e.message, 'error');
  }
  hideLoading();
}

async function removeOutliers() {
  showLoading('Removing outliers...');
  try {
    const data = await api('/remove-outliers', { method: 'POST' });
    state.rawData = data.data;
    state.cleanedData = data.data;
    state.outlierData = null;

    document.getElementById('outlier-results').classList.add('hidden');
    document.getElementById('outlier-empty').classList.remove('hidden');
    document.getElementById('remove-outliers-btn').style.display = 'none';

    updateDataStatus();
    toast(`Removed outliers. ${data.data.length} rows remaining.`, 'success');
  } catch (e) {
    toast(e.message, 'error');
  }
  hideLoading();
}

// ── NORMALIZE ─────────────────────────────────────────────────────────────────
function selectNormMethod(method, el) {
  state.normMethod = method;
  document.querySelectorAll('#page-normalize .method-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
}

async function normalizeData() {
  if (!state.rawData) return toast('Load data first', 'error');

  showLoading('Normalizing data...');
  try {
    const data = await api('/normalize', {
      method: 'POST',
      body: JSON.stringify({ method: state.normMethod })
    });

    state.normalizedData = data.normalized;

    document.getElementById('norm-results').classList.remove('hidden');
    document.getElementById('norm-empty').classList.add('hidden');

    renderTable('before-norm-table', state.rawData.slice(0, 60));
    renderTable('after-norm-table', data.normalized.slice(0, 60));

    toast('Normalization complete', 'success');
  } catch (e) {
    toast(e.message, 'error');
  }
  hideLoading();
}

// ── DOWNLOAD ──────────────────────────────────────────────────────────────────
async function downloadData(type) {
  try {
    showLoading('Preparing download...');
    const res = await fetch(`${API}/download/${type}`, { credentials: 'include' });
    if (!res.ok) { const d = await res.json(); throw new Error(d.error); }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `${state.symbol || 'stock'}_${type}.csv`;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
    toast('Download started', 'success');
  } catch (e) {
    toast(e.message || 'Download failed', 'error');
  }
  hideLoading();
}

// ── OVERVIEW CHARTS ───────────────────────────────────────────────────────────
function refreshOverview() {
  const data = state.rawData;
  if (!data || data.length === 0) return;

  const cols = getChartColors();
  const labels = data.map(r => r.Date || r.date || '');
  const closes = data.map(r => parseFloat(r.Close || r.close || 0));
  const volumes = data.map(r => parseFloat(r.Volume || r.volume || 0));

  // Stat cards
  const validCloses = closes.filter(v => !isNaN(v) && v > 0);
  document.getElementById('ov-rows').textContent = data.length;
  document.getElementById('ov-high').textContent = validCloses.length ? '$' + Math.max(...validCloses).toFixed(2) : '—';
  document.getElementById('ov-low').textContent = validCloses.length ? '$' + Math.min(...validCloses).toFixed(2) : '—';
  document.getElementById('ov-avg').textContent = validCloses.length ? '$' + (validCloses.reduce((a, b) => a + b, 0) / validCloses.length).toFixed(2) : '—';

  document.getElementById('ov-empty').classList.add('hidden');

  // Moving averages helper
  function ma(arr, n) {
    return arr.map((_, i) => {
      if (i < n - 1) return null;
      const slice = arr.slice(i - n + 1, i + 1);
      return slice.reduce((a, b) => a + b, 0) / n;
    });
  }

  const sample = (arr, max) => {
    if (arr.length <= max) return arr;
    const step = Math.floor(arr.length / max);
    return arr.filter((_, i) => i % step === 0).slice(0, max);
  };

  const N = 120;
  const sl = labels.slice(-N), sc = closes.slice(-N), sv = volumes.slice(-N);

  // Close price chart
  makeChart('chart-close', {
    type: 'line',
    data: {
      labels: sample(sl, 40),
      datasets: [{
        label: 'Close', data: sample(sc, 40),
        borderColor: '#00e5ff', borderWidth: 2,
        pointRadius: 0, fill: true,
        backgroundColor: 'rgba(0,229,255,0.07)',
        tension: 0.4
      }]
    },
    options: chartOptions(cols, '$')
  });

  // Volume chart
  makeChart('chart-volume', {
    type: 'bar',
    data: {
      labels: sample(sl, 40),
      datasets: [{
        label: 'Volume', data: sample(sv, 40),
        backgroundColor: 'rgba(124,92,252,0.5)',
        borderColor: 'rgba(124,92,252,0.8)',
        borderWidth: 1,
      }]
    },
    options: chartOptions(cols, '')
  });

  // MA chart
  const ma7 = ma(sc, 7);
  const ma20 = ma(sc, 20);
  const ma50 = ma(sc, 50);
  makeChart('chart-ma', {
    type: 'line',
    data: {
      labels: sample(sl, 60),
      datasets: [
        { label: 'Close', data: sample(sc, 60), borderColor: '#00e5ff', borderWidth: 1.5, pointRadius: 0, tension: 0.3 },
        { label: 'MA7', data: sample(ma7, 60), borderColor: '#00ff88', borderWidth: 1.5, pointRadius: 0, tension: 0.3, borderDash: [4, 2] },
        { label: 'MA20', data: sample(ma20, 60), borderColor: '#ffa640', borderWidth: 1.5, pointRadius: 0, tension: 0.3, borderDash: [6, 3] },
        { label: 'MA50', data: sample(ma50, 60), borderColor: '#7c5cfc', borderWidth: 1.5, pointRadius: 0, tension: 0.3, borderDash: [8, 4] },
      ]
    },
    options: chartOptions(cols, '$')
  });
}

function chartOptions(cols, prefix = '') {
  return {
    responsive: true, maintainAspectRatio: false,
    interaction: { intersect: false, mode: 'index' },
    plugins: {
      legend: { display: true, labels: { color: cols.text, font: { family: 'Space Mono', size: 11 }, boxWidth: 12 } },
      tooltip: {
        backgroundColor: '#111318', borderColor: '#242830', borderWidth: 1,
        titleColor: '#e8eaf0', bodyColor: '#5a6075',
        callbacks: { label: ctx => `  ${ctx.dataset.label}: ${prefix}${ctx.parsed.y !== null ? ctx.parsed.y.toFixed(2) : '—'}` }
      }
    },
    scales: {
      x: { grid: { color: cols.grid }, ticks: { color: cols.text, font: { size: 10, family: 'Space Mono' }, maxTicksLimit: 8 } },
      y: { grid: { color: cols.grid }, ticks: { color: cols.text, font: { size: 10, family: 'Space Mono' }, callback: v => prefix + v.toFixed(0) } }
    }
  };
}

// ── CHARTS PAGE ───────────────────────────────────────────────────────────────
function renderChartsPage() {
  const data = state.rawData;
  if (!data || !data.length) return;

  document.getElementById('charts-empty').classList.add('hidden');
  const cols = getChartColors();
  const labels = data.map(r => r.Date || r.date || '');
  const opens = data.map(r => parseFloat(r.Open || r.open || 0));
  const highs = data.map(r => parseFloat(r.High || r.high || 0));
  const lows = data.map(r => parseFloat(r.Low || r.low || 0));
  const closes = data.map(r => parseFloat(r.Close || r.close || 0));
  const vols = data.map(r => parseFloat(r.Volume || r.volume || 0));

  const sample = (arr, max) => {
    if (arr.length <= max) return arr;
    const step = Math.floor(arr.length / max);
    return arr.filter((_, i) => i % step === 0).slice(0, max);
  };
  const N = 80;
  const sl = labels.slice(-N);

  // OHLC-style multi-line
  makeChart('chart-ohlc', {
    type: 'line',
    data: {
      labels: sample(sl, 50),
      datasets: [
        { label: 'Open', data: sample(opens.slice(-N), 50), borderColor: '#ffa640', borderWidth: 1.5, pointRadius: 0, tension: 0.3 },
        { label: 'High', data: sample(highs.slice(-N), 50), borderColor: '#00ff88', borderWidth: 1.5, pointRadius: 0, tension: 0.3 },
        { label: 'Low', data: sample(lows.slice(-N), 50), borderColor: '#ff4d4d', borderWidth: 1.5, pointRadius: 0, tension: 0.3 },
        { label: 'Close', data: sample(closes.slice(-N), 50), borderColor: '#00e5ff', borderWidth: 2, pointRadius: 0, tension: 0.3 },
      ]
    },
    options: chartOptions(cols, '$')
  });

  makeChart('chart-vol2', {
    type: 'bar',
    data: {
      labels: sample(sl, 50),
      datasets: [{ label: 'Volume', data: sample(vols.slice(-N), 50), backgroundColor: 'rgba(124,92,252,0.55)', borderRadius: 3 }]
    },
    options: chartOptions(cols, '')
  });

  function ma(arr, n) { return arr.map((_, i) => i < n - 1 ? null : arr.slice(i - n + 1, i + 1).reduce((a, b) => a + b, 0) / n); }
  const ma7 = ma(closes, 7);
  const ma20 = ma(closes, 20);
  const ma50 = ma(closes, 50);

  makeChart('chart-ma2', {
    type: 'line',
    data: {
      labels: sample(sl, 60),
      datasets: [
        { label: 'Close', data: sample(closes.slice(-N), 60), borderColor: '#00e5ff', borderWidth: 1.5, pointRadius: 0, tension: 0.3, fill: true, backgroundColor: 'rgba(0,229,255,0.04)' },
        { label: 'MA7', data: sample(ma7.slice(-N), 60), borderColor: '#00ff88', borderWidth: 1.5, pointRadius: 0, tension: 0.3, borderDash: [4, 2] },
        { label: 'MA20', data: sample(ma20.slice(-N), 60), borderColor: '#ffa640', borderWidth: 1.5, pointRadius: 0, tension: 0.3, borderDash: [6, 3] },
        { label: 'MA50', data: sample(ma50.slice(-N), 60), borderColor: '#7c5cfc', borderWidth: 1.5, pointRadius: 0, tension: 0.3, borderDash: [8, 4] },
      ]
    },
    options: chartOptions(cols, '$')
  });
}
// ── AI PREDICTION ─────────────────────────────────────────────────────────────
async function runPrediction() {
  if (!state.rawData) return toast('Load data first', 'error');

  const days = document.getElementById('forecast-days').value || 30;
  const method = document.querySelector('.predict-method.active')?.dataset.method || 'linear';

  showLoading(`Running ${method} prediction...`);
  try {
    const endpoint = method === 'arima' ? '/predict-arima' : '/predict';
    const res = await api(endpoint, {
      method: 'POST',
      body: JSON.stringify({ forecast_days: days })
    });

    document.getElementById('predict-results').classList.remove('hidden');
    document.getElementById('predict-empty').classList.add('hidden');
    document.getElementById('pred-r2').textContent = res.r2.toFixed(4);
    document.getElementById('pred-mae').textContent = '$' + res.mae.toFixed(2);
    document.getElementById('pred-next').textContent = '$' + res.next_day.toFixed(2);

    const cols = getChartColors();
    makeChart('chart-predict', {
      type: 'line',
      data: {
        labels: [...res.actual_dates, ...res.forecast_dates],
        datasets: [
          {
            label: 'Actual', data: [...res.actual_prices, ...Array(res.forecast_dates.length).fill(null)],
            borderColor: '#00e5ff', borderWidth: 2, pointRadius: 0, tension: 0.3
          },
          {
            label: 'Predicted', data: [...Array(res.actual_dates.length).fill(null), ...res.forecast_prices],
            borderColor: '#7c5cfc', borderWidth: 2, pointRadius: 0, tension: 0.3, borderDash: [6, 4]
          }
        ]
      },
      options: chartOptions(cols, '$')
    });

    toast(`R² Score: ${res.r2.toFixed(4)} | Next day: $${res.next_day.toFixed(2)}`, 'success');
  } catch (e) {
    toast(e.message, 'error');
  }
  hideLoading();
}

// ── MULTI-STOCK COMPARE ────────────────────────────────────────────────────────
async function compareStocks() {
  const symbols = [
    document.getElementById('cmp-s1').value.trim().toUpperCase(),
    document.getElementById('cmp-s2').value.trim().toUpperCase(),
    document.getElementById('cmp-s3').value.trim().toUpperCase(),
  ].filter(Boolean);

  if (symbols.length < 2) return toast('Enter at least 2 symbols', 'error');

  const period = document.getElementById('cmp-period').value;
  showLoading('Fetching comparison data...');

  try {
    const data = await api('/compare-stocks', {
      method: 'POST',
      body: JSON.stringify({ symbols, period })
    });

    document.getElementById('compare-chart-wrap').classList.remove('hidden');
    const cols = getChartColors();
    const COLORS = ['#00e5ff', '#7c5cfc', '#ffa640', '#00ff88', '#ff4d4d'];

    makeChart('chart-compare', {
      type: 'line',
      data: {
        labels: data.dates,
        datasets: data.series.map((s, i) => ({
          label: s.symbol, data: s.prices,
          borderColor: COLORS[i], borderWidth: 2, pointRadius: 0, tension: 0.3
        }))
      },
      options: chartOptions(cols, '$')
    });
    toast('Comparison loaded', 'success');
  } catch (e) {
    toast(e.message, 'error');
  }
  hideLoading();
}

// ── HISTORY ───────────────────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const data = await api('/history');
    const wrap = document.getElementById('history-table-wrap');

    if (!data.history || data.history.length === 0) {
      wrap.innerHTML = '<div class="empty-state"><div class="icon">🕒</div><p>No sessions yet. Load some stock data to get started.</p></div>';
      return;
    }

    const rows = data.history.map(h => `
      <tr class="history-row">
        <td>${h.symbol || 'Upload'}</td>
        <td>${h.source}</td>
        <td>${h.rows}</td>
        <td>${new Date(h.timestamp).toLocaleString()}</td>
        <td><span class="badge badge-${h.cleaned ? 'success' : 'warn'}">${h.cleaned ? 'Cleaned' : 'Raw'}</span></td>
      </tr>`).join('');

    wrap.innerHTML = `
      <div class="data-table-wrap">
        <table class="data-table">
          <thead><tr><th>Symbol</th><th>Source</th><th>Rows</th><th>Time</th><th>Status</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  } catch (e) {
    document.getElementById('history-table-wrap').innerHTML = '<p class="text-muted text-sm">Could not load history.</p>';
  }
}
