'use strict';

// ═══════════════════════════════════════
//  CONSTANTS
// ═══════════════════════════════════════

const API_URL = 'https://api.anthropic.com/v1/messages';
const MODEL   = 'claude-opus-4-8';
const TOP_N   = 14; // max categories per chart

const FIELDS = {
  type:            { label: 'סוג תקלה',       pat: ['סוג','קטגוריה','type','category','סוג בעיה','סוג תקלה','classification'], req: true  },
  discovery_phase: { label: 'שלב גילוי',      pat: ['שלב גילוי','שלב','phase','detection','גילוי','נמצא'], req: true  },
  root_cause:      { label: 'גורם שורש',      pat: ['גורם שורש','סיבת שורש','שורש','root cause','root_cause','גורם','סיבה'], req: false },
  severity:        { label: 'חומרה',           pat: ['חומרה','severity','דחיפות','priority','רמת חומרה','חומרת'], req: false },
  status:          { label: 'סטטוס',           pat: ['סטטוס','status','מצב','state'], req: false },
  date:            { label: 'תאריך',           pat: ['תאריך','date','created','נפתח','תאריך פתיחה','opened','open date'], req: false },
  team:            { label: 'צוות / אחראי',   pat: ['צוות','team','אחראי','responsible','assigned','developer','owner','responsible team'], req: false },
  product:         { label: 'מוצר / רכיב',    pat: ['מוצר','product','מערכת','system','component','רכיב','module','subsystem'], req: false },
  id:              { label: 'מזהה תקלה',      pat: ['מזהה','מספר','id','#','bug id','defect id','issue id'], req: false },
};

const PALETTE = [
  '#5b5ef4','#06b6d4','#10b981','#f59e0b','#ef4444',
  '#8b5cf6','#ec4899','#14b8a6','#f97316','#6366f1',
  '#0ea5e9','#84cc16','#a855f7','#22d3ee','#fb923c',
];

const SEV_COLORS = {
  'קריטי':'#ef4444','critical':'#ef4444','blocker':'#ef4444',
  'גבוה':'#f97316','high':'#f97316',
  'בינוני':'#f59e0b','medium':'#f59e0b','normal':'#f59e0b',
  'נמוך':'#22c55e','low':'#22c55e','minor':'#22c55e','trivial':'#22c55e',
};

const OPEN_TERMS   = ['פתוח','open','active','new','in progress','בעבודה','ממתין','חדש','ממתין','reopen'];
const CLOSED_TERMS = ['סגור','closed','done','fixed','resolved','נסגר','תוקן','completed','verified'];

// ═══════════════════════════════════════
//  STATE
// ═══════════════════════════════════════

const S = {
  apiKey: '',
  headers: [],
  rows: [],
  mapping: {},
  stats: {},
  charts: [],
  aiBuffer: '',
};

// ═══════════════════════════════════════
//  INIT
// ═══════════════════════════════════════

function init() {
  S.apiKey = localStorage.getItem('dfa_key') || '';
  if (S.apiKey) document.getElementById('api-key').value = S.apiKey;
  setupDrop();
  document.getElementById('file-input').addEventListener('change', e => {
    if (e.target.files[0]) handleFile(e.target.files[0]);
  });
}

// ═══════════════════════════════════════
//  API KEY
// ═══════════════════════════════════════

function saveApiKey() {
  const k = document.getElementById('api-key').value.trim();
  if (!k.startsWith('sk-')) { toast('מפתח API לא תקין', 'err'); return; }
  S.apiKey = k;
  localStorage.setItem('dfa_key', k);
  toast('מפתח API נשמר', 'ok');
}

// ═══════════════════════════════════════
//  FILE HANDLING
// ═══════════════════════════════════════

function setupDrop() {
  const zone = document.getElementById('drop-zone');
  zone.addEventListener('click', () => document.getElementById('file-input').click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });
}

function handleFile(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  const reader = new FileReader();
  reader.onload = e => {
    try {
      if (ext === 'csv') parseCSV(e.target.result);
      else parseExcel(e.target.result);
      showFileBanner(file.name);
    } catch(err) {
      toast('שגיאה בקריאת הקובץ: ' + err.message, 'err');
    }
  };
  if (ext === 'csv') reader.readAsText(file, 'UTF-8');
  else reader.readAsArrayBuffer(file);
}

function parseExcel(buf) {
  const wb = XLSX.read(buf, { type: 'array', cellDates: true });
  const ws = wb.Sheets[wb.SheetNames[0]];
  processGrid(XLSX.utils.sheet_to_json(ws, { header: 1, raw: false, dateNF: 'YYYY-MM-DD' }));
}

function parseCSV(text) {
  const wb = XLSX.read(text, { type: 'string' });
  const ws = wb.Sheets[wb.SheetNames[0]];
  processGrid(XLSX.utils.sheet_to_json(ws, { header: 1, raw: false }));
}

function processGrid(grid) {
  if (!grid || grid.length < 2) throw new Error('הקובץ ריק או חסר שורות נתונים');
  S.headers = (grid[0] || []).map(h => String(h ?? '').trim()).filter(Boolean);
  if (!S.headers.length) throw new Error('לא נמצאו כותרות עמודות');
  S.rows = grid.slice(1)
    .filter(r => r.some(c => c !== '' && c != null))
    .map(r => {
      const obj = {};
      S.headers.forEach((h, i) => { obj[h] = String(r[i] ?? '').trim(); });
      return obj;
    });
  if (!S.rows.length) throw new Error('לא נמצאו שורות נתונים');
  autoDetect();
}

function showFileBanner(name) {
  document.getElementById('file-name').textContent = name;
  document.getElementById('file-rows').textContent = S.rows.length.toLocaleString() + ' שורות';
  document.getElementById('file-banner').classList.remove('hidden');
}

// ═══════════════════════════════════════
//  AUTO-DETECT COLUMN MAPPING
// ═══════════════════════════════════════

function autoDetect() {
  S.mapping = {};
  Object.entries(FIELDS).forEach(([field, def]) => {
    const hit = S.headers.find(h =>
      def.pat.some(p => h.toLowerCase().replace(/[\s_\-]/g, '').includes(p.toLowerCase().replace(/[\s_\-]/g, '')))
    );
    if (hit) S.mapping[field] = hit;
  });
}

// ═══════════════════════════════════════
//  MAPPING UI
// ═══════════════════════════════════════

function proceedToMapping() {
  renderMapGrid();
  renderPreview();
  showSection('mapping');
}

function renderMapGrid() {
  document.getElementById('map-grid').innerHTML = Object.entries(FIELDS).map(([f, def]) => {
    const cur = S.mapping[f] || '';
    const opts = ['<option value="">— לא מופה —</option>',
      ...S.headers.map(h => `<option value="${x(h)}"${h === cur ? ' selected' : ''}>${x(h)}</option>`)
    ].join('');
    const dot = def.req ? '<span class="dot-req" title="שדה חשוב"></span>' : '<span class="dot-opt"></span>';
    return `<div class="map-field">
      <div class="map-field-name">${dot}${def.label}</div>
      <select onchange="setMap('${f}',this.value)">${opts}</select>
    </div>`;
  }).join('');
}

function setMap(field, val) {
  if (val) S.mapping[field] = val; else delete S.mapping[field];
}

function renderPreview() {
  const rows = S.rows.slice(0, 5);
  document.getElementById('preview-tbl').innerHTML =
    `<table><thead><tr>${S.headers.map(h => `<th>${x(h)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(r =>
      `<tr>${S.headers.map(h => `<td class="cell-trunc">${x(r[h] ?? '')}</td>`).join('')}</tr>`
    ).join('')}</tbody></table>`;
}

// ═══════════════════════════════════════
//  ANALYSIS ENTRY
// ═══════════════════════════════════════

function proceedToAnalysis() {
  if (!Object.keys(S.mapping).filter(f => f !== 'id').length) {
    toast('יש למפות לפחות עמודה אחת', 'err'); return;
  }
  S.stats = computeStats();
  showSection('dashboard');
  document.getElementById('hdr-actions').classList.remove('hidden');
  renderKPI();
  renderCharts();
  runAI();
}

// ═══════════════════════════════════════
//  STATISTICS
// ═══════════════════════════════════════

function computeStats() {
  const st = { total: S.rows.length, byField: {} };

  // Count by each categorical field
  Object.entries(S.mapping).forEach(([field, col]) => {
    if (field === 'id' || field === 'date') return;
    const counts = {};
    S.rows.forEach(r => {
      const v = (r[col] || 'לא ידוע').trim() || 'לא ידוע';
      counts[v] = (counts[v] || 0) + 1;
    });
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    if (!sorted.length) return;
    // Group tail into "אחר"
    if (sorted.length > TOP_N) {
      const top = sorted.slice(0, TOP_N - 1);
      const other = sorted.slice(TOP_N - 1).reduce((s, [, v]) => s + v, 0);
      top.push(['אחר', other]);
      st.byField[field] = Object.fromEntries(top);
    } else {
      st.byField[field] = Object.fromEntries(sorted);
    }
  });

  // Open / closed split
  if (S.mapping.status) {
    let open = 0, closed = 0, other = 0;
    S.rows.forEach(r => {
      const v = (r[S.mapping.status] || '').toLowerCase();
      if (OPEN_TERMS.some(t => v.includes(t))) open++;
      else if (CLOSED_TERMS.some(t => v.includes(t))) closed++;
      else other++;
    });
    st.openClosed = { open, closed, other };
  }

  // Monthly trend
  if (S.mapping.date) {
    const monthly = {};
    S.rows.forEach(r => {
      const d = parseDate(r[S.mapping.date]);
      if (!d) return;
      const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      monthly[k] = (monthly[k] || 0) + 1;
    });
    const sorted = Object.entries(monthly).sort((a, b) => a[0].localeCompare(b[0]));
    if (sorted.length > 1) st.trend = sorted;
  }

  // Critical count
  if (S.mapping.severity && st.byField.severity) {
    st.criticalCount = Object.entries(st.byField.severity)
      .filter(([k]) => /קריטי|critical|blocker/i.test(k))
      .reduce((s, [, v]) => s + v, 0);
  }

  return st;
}

function parseDate(str) {
  if (!str) return null;
  let d = new Date(str);
  if (!isNaN(d)) return d;
  const m = str.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})$/);
  if (m) {
    const yr = m[3].length === 2 ? '20' + m[3] : m[3];
    return new Date(`${yr}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`);
  }
  return null;
}

// ═══════════════════════════════════════
//  KPI CARDS
// ═══════════════════════════════════════

function renderKPI() {
  const st = S.stats;
  const cards = [
    { lbl: 'סה"כ תקלות', val: st.total.toLocaleString(), cls: 'accent' },
  ];

  if (st.openClosed) {
    const pct = n => Math.round(n / st.total * 100) + '%';
    cards.push({ lbl: 'תקלות פתוחות', val: st.openClosed.open.toLocaleString(), sub: pct(st.openClosed.open), cls: 'warn' });
    cards.push({ lbl: 'תקלות סגורות', val: st.openClosed.closed.toLocaleString(), sub: pct(st.openClosed.closed), cls: 'ok' });
  }
  if (st.criticalCount) {
    cards.push({ lbl: 'תקלות קריטיות', val: st.criticalCount.toLocaleString(), sub: Math.round(st.criticalCount / st.total * 100) + '%', cls: 'danger' });
  }
  if (st.byField.type) {
    const [nm, cnt] = Object.entries(st.byField.type)[0];
    cards.push({ lbl: 'סוג תקלה שכיח', val: nm, sub: cnt + ' תקלות', cls: 'text' });
  }
  if (st.byField.root_cause) {
    const [nm, cnt] = Object.entries(st.byField.root_cause)[0];
    cards.push({ lbl: 'גורם שורש עיקרי', val: nm, sub: cnt + ' תקלות', cls: 'text' });
  }

  document.getElementById('kpi-row').innerHTML = cards.map(c =>
    `<div class="kpi ${c.cls}">
      <div class="kpi-lbl">${x(c.lbl)}</div>
      <div class="kpi-val">${x(String(c.val))}</div>
      ${c.sub ? `<div class="kpi-sub">${x(c.sub)}</div>` : ''}
    </div>`
  ).join('');
}

// ═══════════════════════════════════════
//  CHARTS
// ═══════════════════════════════════════

function renderCharts() {
  S.charts.forEach(c => c.destroy());
  S.charts = [];
  const area = document.getElementById('charts-area');
  area.innerHTML = '';

  const defs = [
    { field: 'type',            label: 'חלוקה לפי סוג תקלה',   kind: 'barH' },
    { field: 'discovery_phase', label: 'שלב גילוי',              kind: 'doughnut' },
    { field: 'root_cause',      label: 'גורמי שורש',             kind: 'barH' },
    { field: 'severity',        label: 'חלוקה לפי חומרה',        kind: 'bar' },
    { field: 'status',          label: 'סטטוס תקלות',            kind: 'doughnut' },
    { field: 'team',            label: 'חלוקה לפי צוות',         kind: 'barH' },
    { field: 'product',         label: 'חלוקה לפי מוצר / רכיב', kind: 'barH' },
    { field: 'trend',           label: 'מגמה חודשית',            kind: 'line' },
  ];

  defs.forEach(({ field, label, kind }) => {
    const data = field === 'trend' ? S.stats.trend : S.stats.byField[field];
    if (!data) return;

    const id = `canvas-${field}`;
    const tall = kind === 'barH' && Object.keys(data).length > 6;
    const card = document.createElement('div');
    card.className = 'chart-card';
    card.innerHTML = `<h4>${x(label)}</h4><div class="chart-wrap${tall ? ' tall' : ''}"><canvas id="${id}"></canvas></div>`;
    area.appendChild(card);

    S.charts.push(buildChart(id, kind, field, data));
  });
}

function buildChart(id, kind, field, data) {
  const canvas = document.getElementById(id);
  const labels = kind === 'trend' ? data.map(([k]) => k) : Object.keys(data);
  const values = kind === 'trend' ? data.map(([, v]) => v) : Object.values(data);
  const trunc  = labels.map(l => l.length > 28 ? l.slice(0, 26) + '…' : l);

  let type, datasets, extra = {};

  if (kind === 'doughnut') {
    type = 'doughnut';
    datasets = [{ data: values, backgroundColor: labels.map((_, i) => PALETTE[i % PALETTE.length]), borderWidth: 2, borderColor: '#13151f' }];
  } else if (kind === 'barH') {
    type = 'bar';
    extra = { indexAxis: 'y' };
    datasets = [{ data: values, backgroundColor: PALETTE.map(c => c + 'cc'), borderColor: PALETTE, borderWidth: 1 }];
  } else if (kind === 'bar') {
    type = 'bar';
    const colors = field === 'severity'
      ? labels.map(l => (SEV_COLORS[l.toLowerCase()] || PALETTE[0]) + 'cc')
      : PALETTE.map(c => c + 'cc');
    const borders = field === 'severity'
      ? labels.map(l => SEV_COLORS[l.toLowerCase()] || PALETTE[0])
      : PALETTE;
    datasets = [{ data: values, backgroundColor: colors, borderColor: borders, borderWidth: 1 }];
  } else { // line
    type = 'line';
    datasets = [{ label: 'תקלות', data: values, borderColor: PALETTE[0], backgroundColor: PALETTE[0] + '33', fill: true, tension: 0.4, pointRadius: 3 }];
  }

  const isDoughnut = type === 'doughnut';
  const isHoriz    = kind === 'barH';

  return new Chart(canvas, {
    type,
    data: { labels: trunc, datasets },
    options: {
      ...extra,
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: isDoughnut,
          position: 'bottom',
          labels: { color: '#8b8fa8', font: { size: 11 }, padding: 14, boxWidth: 12 },
        },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.raw} תקלות`,
          },
        },
      },
      scales: isDoughnut ? {} : {
        x: {
          ticks: { color: '#8b8fa8', font: { size: 11 }, maxRotation: isHoriz ? 0 : 30 },
          grid: { color: '#252838' },
        },
        y: {
          ticks: { color: '#8b8fa8', font: { size: 11 } },
          grid: { color: isHoriz ? 'transparent' : '#252838' },
          beginAtZero: true,
        },
      },
    },
  });
}

// ═══════════════════════════════════════
//  AI ANALYSIS
// ═══════════════════════════════════════

async function runAI() {
  const out   = document.getElementById('ai-out');
  const badge = document.getElementById('ai-badge');
  S.aiBuffer = '';
  out.innerHTML = '';

  if (!S.apiKey) {
    out.innerHTML = '<p>הזן מפתח API של Anthropic בשלב הראשון כדי לקבל תובנות AI.</p>';
    badge.className = 'badge'; badge.textContent = 'ממתין למפתח';
    return;
  }

  try {
    const res = await fetch(API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': S.apiKey,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true',
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 2048,
        stream: true,
        system: 'אתה מומחה לניתוח תקלות ואיכות תוכנה/מוצרים. ענה תמיד בעברית, בפורמט מובנה עם כותרות ברורות. השתמש בנתונים הספציפיים שקיבלת.',
        messages: [{ role: 'user', content: buildPrompt() }],
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      if (res.status === 401) throw new Error('מפתח API לא תקין');
      if (res.status === 429) throw new Error('חרגת ממגבלת הקריאות — נסה שוב עוד כמה שניות');
      throw new Error(err.error?.message || `שגיאת API (${res.status})`);
    }

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const raw = line.slice(6).trim();
        if (raw === '[DONE]') continue;
        try {
          const ev = JSON.parse(raw);
          if (ev.type === 'content_block_delta' && ev.delta?.type === 'text_delta') {
            S.aiBuffer += ev.delta.text;
            out.innerHTML = renderMd(S.aiBuffer) + '<span class="cursor-blink"></span>';
          }
        } catch { /* skip malformed SSE */ }
      }
    }

    out.innerHTML = renderMd(S.aiBuffer);
    badge.className = 'badge badge-done'; badge.textContent = 'הושלם ✓';

  } catch (err) {
    out.innerHTML = `<p style="color:var(--danger)">שגיאה: ${x(err.message)}</p>`;
    badge.className = 'badge badge-err'; badge.textContent = 'שגיאה';
  }
}

function buildPrompt() {
  const st  = S.stats;
  const pct = n => Math.round(n / st.total * 100) + '%';
  let p = `## נתוני ניתוח תקלות\n\n**סה"כ תקלות: ${st.total.toLocaleString()}**\n`;

  if (st.openClosed) {
    const { open, closed } = st.openClosed;
    p += `\n**סטטוס כללי:** ${open} פתוחות (${pct(open)}) · ${closed} סגורות (${pct(closed)})\n`;
  }

  Object.entries(st.byField).forEach(([field, counts]) => {
    p += `\n**${FIELDS[field]?.label || field}:**\n`;
    Object.entries(counts).slice(0, 12).forEach(([k, v]) => {
      p += `• ${k}: ${v} (${pct(v)})\n`;
    });
  });

  if (st.trend) {
    p += `\n**מגמה חודשית (6 חודשים אחרונים):**\n`;
    st.trend.slice(-6).forEach(([m, v]) => { p += `• ${m}: ${v}\n`; });
  }

  p += `
---
נא לכתוב דוח ניתוח מקצועי הכולל:

## 1. ממצאים עיקריים
(3–5 ממצאים בולטים עם מספרים קונקרטיים מהנתונים)

## 2. ניתוח גורמי שורש
(מהם הגורמים העיקריים, כיצד הם קשורים זה לזה)

## 3. דפוסים ומגמות
(תבניות חוזרות, קורלציות, מגמות לאורך זמן אם יש)

## 4. נקודות כשל עיקריות
(היכן מרוכזת הבעיה ביותר — שלבים/רכיבים/צוותים)

## 5. המלצות לשיפור
(3–5 המלצות ספציפיות, מדידות ובנות-יישום)

## 6. סיכום מנהלים
(3–4 משפטים לקברניט)`;

  return p;
}

// ═══════════════════════════════════════
//  SIMPLE MARKDOWN RENDERER
// ═══════════════════════════════════════

function renderMd(text) {
  const lines = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .split('\n');

  let html = '';
  let inPara = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    if (!trimmed) {
      if (inPara) { html += '</p>'; inPara = false; }
      continue;
    }
    if (trimmed.startsWith('## ')) {
      if (inPara) { html += '</p>'; inPara = false; }
      html += `<h4>${trimmed.slice(3)}</h4>`;
    } else if (trimmed.startsWith('### ')) {
      if (inPara) { html += '</p>'; inPara = false; }
      html += `<h5>${trimmed.slice(4)}</h5>`;
    } else if (trimmed.startsWith('• ') || trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (inPara) { html += '</p>'; inPara = false; }
      html += `<span class="md-li">${trimmed.slice(2)}</span>`;
    } else {
      if (!inPara) { html += '<p>'; inPara = true; }
      else html += ' ';
      html += trimmed;
    }
  }
  if (inPara) html += '</p>';
  return html;
}

// ═══════════════════════════════════════
//  NAVIGATION
// ═══════════════════════════════════════

function showSection(name) {
  ['upload', 'mapping', 'dashboard'].forEach(s => {
    document.getElementById(`sec-${s}`).classList.toggle('hidden', s !== name);
  });
}

function resetApp() {
  S.rows = []; S.headers = []; S.mapping = {}; S.stats = {};
  S.charts.forEach(c => c.destroy()); S.charts = [];
  document.getElementById('file-banner').classList.add('hidden');
  document.getElementById('file-input').value = '';
  document.getElementById('hdr-actions').classList.add('hidden');
  showSection('upload');
}

// ═══════════════════════════════════════
//  UTILITIES
// ═══════════════════════════════════════

function x(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

let _toastTimer;
function toast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast${type ? ' ' + type : ''}`;
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.add('hidden'), 3500);
}

// ─── start ───
init();
