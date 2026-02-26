// LessonForge Frontend - SSE consumption + markdown rendering + debug panel

const API_BASE = '/api';

// State
let currentGenerationId = null;
let eventLog = [];
let stepTimings = {};

// DOM elements
const form = document.getElementById('generate-form');
const generateBtn = document.getElementById('generate-btn');
const resourceOutput = document.getElementById('resource-output');
const eventsLog = document.getElementById('events-log');
const cagTable = document.getElementById('cag-table');
const ragTable = document.getElementById('rag-table');
const templateInfo = document.getElementById('template-info');
const timingsChart = document.getElementById('timings-chart');

// ===== Initialise dropdowns from reference API =====

async function loadDropdowns() {
  try {
    const [yearLevels, strands, focuses, resourceTypes] = await Promise.all([
      fetch(`${API_BASE}/reference/year-levels`).then(r => r.json()),
      fetch(`${API_BASE}/reference/strands`).then(r => r.json()),
      fetch(`${API_BASE}/reference/teaching-focuses`).then(r => r.json()),
      fetch(`${API_BASE}/reference/resource-types`).then(r => r.json()),
    ]);

    populateSelect('year_level', yearLevels.map(y => ({ value: y.title, label: y.title })), 'Year 5');
    populateSelect('strand', strands.map(s => ({ value: s.title, label: s.title })), 'Number');
    populateSelect('teaching_focus', focuses.map(f => ({ value: f.slug, label: f.name })), 'explicit_instruction');

    window._allResourceTypes = resourceTypes;
    filterResourceTypes();
  } catch (e) {
    console.warn('Could not load reference data:', e);
  }
}

function populateSelect(id, options, defaultValue) {
  const select = document.getElementById(id);
  select.innerHTML = '';
  for (const opt of options) {
    const el = document.createElement('option');
    el.value = opt.value;
    el.textContent = opt.label;
    if (opt.value === defaultValue) el.selected = true;
    select.appendChild(el);
  }
}

function filterResourceTypes() {
  const focus = document.getElementById('teaching_focus').value;
  const types = (window._allResourceTypes || []).filter(
    rt => !focus || rt.teaching_focus_slug === focus
  );
  if (types.length === 0 && window._allResourceTypes) {
    // Show all if no match
    populateSelect('resource_type',
      window._allResourceTypes.map(rt => ({ value: rt.slug, label: rt.name })),
      'worked_example_study');
    return;
  }
  populateSelect('resource_type',
    types.map(rt => ({ value: rt.slug, label: rt.name })),
    types[0]?.slug || '');
}

document.getElementById('teaching_focus').addEventListener('change', filterResourceTypes);

// ===== Form submission =====

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  startGeneration();
});

async function startGeneration() {
  // Reset UI
  resetUI();
  generateBtn.disabled = true;
  generateBtn.textContent = 'Generating...';

  const formData = new FormData(form);

  try {
    const response = await fetch(`${API_BASE}/generate`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let markdownContent = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data:')) continue;
        const dataStr = trimmed.slice(5).trim();
        if (!dataStr || dataStr === '[DONE]') continue;

        try {
          const event = JSON.parse(dataStr);
          handleSSEEvent(event);

          if (event.type === 'content_chunk') {
            markdownContent += event.content;
            renderMarkdown(markdownContent);
          }
        } catch (parseErr) {
          // Not valid JSON, skip
        }
      }
    }
  } catch (err) {
    resourceOutput.innerHTML = `<div class="placeholder"><p style="color:var(--danger)">Error: ${err.message}</p></div>`;
  } finally {
    generateBtn.disabled = false;
    generateBtn.textContent = 'Generate Resource';
  }
}

// ===== SSE Event Handler =====

function handleSSEEvent(event) {
  logEvent(event);

  switch (event.type) {
    case 'generation_started':
      currentGenerationId = event.generation_id;
      resourceOutput.innerHTML = '<div class="placeholder"><p>Generating resource...</p></div>';
      break;

    case 'step_started':
      setStepActive(event.index);
      break;

    case 'step_completed':
      setStepCompleted(event.index, event.duration_ms);
      stepTimings[event.step] = event.duration_ms;
      renderTimings();
      break;

    case 'cag_matches':
      renderCAGMatches(event.matches);
      break;

    case 'routing_decision':
      logEvent({ type: 'info', message: `Routed: ${event.teaching_path} (${event.year_band})` });
      break;

    case 'rag_results':
      renderRAGResults(event.results || [], event.num_chunks);
      break;

    case 'template_selected':
      templateInfo.textContent = JSON.stringify(event, null, 2);
      break;

    case 'content_chunk':
      // Handled in startGeneration
      break;

    case 'generation_completed':
      logEvent({ type: 'info', message: `Completed in ${event.total_duration_ms}ms` });
      break;

    case 'error':
      resourceOutput.innerHTML = `<div class="placeholder"><p style="color:var(--danger)">Error: ${event.message}</p></div>`;
      break;
  }
}

// ===== Rendering functions =====

function renderMarkdown(md) {
  resourceOutput.innerHTML = marked.parse(md);
}

function setStepActive(index) {
  document.querySelectorAll('.step').forEach(el => {
    const step = parseInt(el.dataset.step);
    if (step === index) el.classList.add('active');
  });
}

function setStepCompleted(index, durationMs) {
  document.querySelectorAll('.step').forEach(el => {
    const step = parseInt(el.dataset.step);
    if (step === index) {
      el.classList.remove('active');
      el.classList.add('completed');
      // Add timing
      let timeEl = el.querySelector('.step-time');
      if (!timeEl) {
        timeEl = document.createElement('span');
        timeEl.className = 'step-time';
        el.appendChild(timeEl);
      }
      timeEl.textContent = `${(durationMs / 1000).toFixed(1)}s`;
    }
  });
}

function renderCAGMatches(matches) {
  if (!matches || matches.length === 0) {
    cagTable.innerHTML = '<p>No matches found.</p>';
    return;
  }
  let html = '<table><thead><tr><th>Code</th><th>Descriptor</th><th>Year/Strand</th><th>Confidence</th></tr></thead><tbody>';
  for (const m of matches) {
    const confClass = `confidence-${m.confidence || 'low'}`;
    html += `<tr>
      <td><code>${m.code}</code></td>
      <td>${m.text || ''}</td>
      <td>${m.year_level || ''} / ${m.strand || ''}</td>
      <td class="${confClass}">${m.confidence || 'N/A'}</td>
    </tr>`;
  }
  html += '</tbody></table>';
  cagTable.innerHTML = html;
}

function renderRAGResults(results, numChunks) {
  if (!results || results.length === 0) {
    ragTable.innerHTML = `<p>${numChunks || 0} chunks retrieved (no details available).</p>`;
    return;
  }
  let html = `<p><strong>${numChunks}</strong> chunks retrieved</p>`;
  html += '<table><thead><tr><th>Source</th><th>Content Preview</th></tr></thead><tbody>';
  for (const r of results) {
    html += `<tr><td>${r.name || 'unknown'}</td><td>${r.content || ''}</td></tr>`;
  }
  html += '</tbody></table>';
  ragTable.innerHTML = html;
}

function renderTimings() {
  const entries = Object.entries(stepTimings);
  if (entries.length === 0) return;

  const maxMs = Math.max(...entries.map(([, ms]) => ms));
  let html = '';
  for (const [name, ms] of entries) {
    const pct = maxMs > 0 ? (ms / maxMs) * 100 : 0;
    html += `<div class="timing-row">
      <span class="timing-label">${formatStepName(name)}</span>
      <div style="flex:1"><div class="timing-bar" style="width:${pct}%"></div></div>
      <span class="timing-value">${(ms / 1000).toFixed(1)}s</span>
    </div>`;
  }
  timingsChart.innerHTML = html;
}

function formatStepName(name) {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function logEvent(event) {
  eventLog.push(event);
  const timestamp = new Date().toLocaleTimeString();
  const line = `[${timestamp}] ${event.type}: ${JSON.stringify(event)}\n`;
  eventsLog.textContent += line;
  eventsLog.scrollTop = eventsLog.scrollHeight;
}

function resetUI() {
  // Reset steps
  document.querySelectorAll('.step').forEach(el => {
    el.classList.remove('active', 'completed');
    const timeEl = el.querySelector('.step-time');
    if (timeEl) timeEl.remove();
  });

  // Reset output
  resourceOutput.innerHTML = '<div class="placeholder"><p>Starting generation...</p></div>';

  // Reset debug
  eventLog = [];
  stepTimings = {};
  eventsLog.textContent = '';
  cagTable.innerHTML = '';
  ragTable.innerHTML = '';
  templateInfo.textContent = '';
  timingsChart.innerHTML = '';
  currentGenerationId = null;
}

// ===== Debug panel toggle =====

document.getElementById('debug-toggle').addEventListener('click', () => {
  const content = document.getElementById('debug-content');
  const isHidden = content.style.display === 'none';
  content.style.display = isHidden ? 'block' : 'none';
  document.getElementById('debug-toggle').textContent = isHidden ? 'Debug View (Hide)' : 'Debug View';
});

// Debug tab switching
document.querySelectorAll('.debug-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.debug-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');

    const tabName = tab.dataset.tab;
    document.querySelectorAll('.debug-tab-content').forEach(c => c.style.display = 'none');
    document.getElementById(`debug-${tabName}`).style.display = 'block';
  });
});

// ===== Load on init =====
loadDropdowns();
