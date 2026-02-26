/* ============================================================
   LessonForge — Frontend Application
   State-driven SPA: Compose view -> Generate view
   ============================================================ */

const API = '/api';

// ---- Descriptions for teaching focuses (not in API response) ----
const FOCUS_DESCRIPTIONS = {
  explicit_instruction: 'Structured, teacher-led instruction with worked examples and guided practice (I Do / We Do / You Do).',
  deep_learning_inquiry: 'Student-centred inquiry with open-ended tasks, rich problems, and deep thinking routines.',
  fluency_practice: 'Scaffolded practice and strategic repetition to build mathematical fluency and automaticity.',
  assessment_feedback: 'Diagnostic assessment, rubrics, success criteria, and targeted feedback strategies.',
  planning: 'Broad curriculum planning, scope and sequence design, and unit overview mapping.',
};

const STEP_META = [
  { key: 'input_analyzer',        label: 'Input Analysis',     short: 'Parse' },
  { key: 'curriculum_matcher',     label: 'Curriculum Match',   short: 'CAG' },
  { key: 'teaching_focus_router',  label: 'Teaching Router',    short: 'Route' },
  { key: 'pedagogy_retriever',     label: 'Pedagogy Retrieval', short: 'RAG' },
  { key: 'template_resolver',      label: 'Template Resolver',  short: 'Tmpl' },
  { key: 'resource_generator',     label: 'Resource Generation',short: 'Gen' },
];

// ---- Application State ----
const S = {
  // Config
  yearLevel:     'Year 5',
  strand:        'Number',
  teachingFocus: 'explicit_instruction',
  resourceType:  'worked_example_study',
  context:       '',
  topic:         '',

  // Reference data from API
  ref: { yearLevels: [], strands: [], focuses: [], resourceTypes: [] },

  // Modal temps (pending selection before Apply)
  pending: {},

  // Generation
  gen: null, // null = not started; object = running/done
};

function freshGen() {
  return {
    id: null,
    status: 'running',
    steps: STEP_META.map(m => ({ ...m, status: 'pending', ms: null, data: null })),
    content: '',
    totalMs: null,
    error: null,
  };
}

// ---- DOM refs ----
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

const dom = {
  composeView:    $('#compose-view'),
  generateView:   $('#generate-view'),
  topicInput:     $('#topic-input'),
  contextInput:   $('#context-input'),
  contextArea:    $('#context-area'),
  generateBtn:    $('#generate-btn'),
  chipCurriculum: $('#chip-curriculum-text'),
  chipFocus:      $('#chip-focus-text'),
  chipResource:   $('#chip-resource-text'),
  chipNotes:      $('#chip-notes'),
  genTopicPill:   $('#gen-topic-pill'),
  stepRail:       $('#step-rail'),
  outputEmpty:    $('#output-empty'),
  markdownBody:   $('#markdown-body'),
  inspectorSteps: $('#inspector-steps'),
  inspectorTime:  $('#inspector-timings'),
  backdrop:       $('#modal-backdrop'),
  clearAllBtn:    $('#clear-all-btn'),
  confirmOverlay: $('#confirm-overlay'),
  confirmCancel:  $('#confirm-cancel'),
  confirmDelete:  $('#confirm-delete'),
};

// ============================================================
// REFERENCE DATA & HISTORY
// ============================================================

async function loadRefData() {
  try {
    const [yl, st, tf, rt] = await Promise.all([
      fetch(`${API}/reference/year-levels`).then(r => r.json()),
      fetch(`${API}/reference/strands`).then(r => r.json()),
      fetch(`${API}/reference/teaching-focuses`).then(r => r.json()),
      fetch(`${API}/reference/resource-types`).then(r => r.json()),
    ]);
    S.ref.yearLevels    = yl;
    S.ref.strands       = st;
    S.ref.focuses       = tf;
    S.ref.resourceTypes = rt;
    updateChips();
  } catch (e) {
    console.warn('Failed to load reference data', e);
  }
}

async function loadHistory() {
  try {
    const items = await fetch(`${API}/generations?limit=6`).then(r => r.json());
    renderHistory(items);
  } catch (e) {
    console.warn('Failed to load history', e);
  }
}

function renderHistory(items) {
  const section = $('#history-section');
  const grid = $('#history-grid');
  if (!items || !items.length) {
    section.classList.add('empty');
    return;
  }
  section.classList.remove('empty');

  grid.innerHTML = items.map(item => {
    const topic = item.topic || 'Untitled';
    const topicShort = topic.length > 65 ? topic.slice(0, 62) + '...' : topic;
    const statusCls = item.status === 'error' ? ' error' : item.status === 'running' ? ' running' : '';
    const focus = formatSlug(item.teaching_focus || '');
    const resource = formatSlug(item.resource_type || '');
    const time = item.created_at ? timeAgo(new Date(item.created_at)) : '';

    return `<div class="history-card" data-gen-id="${esc(item.id)}">
      <span class="history-dot${statusCls}"></span>
      <div class="history-info">
        <div class="history-topic">${esc(topicShort)}</div>
        <div class="history-meta">
          <span>${esc(item.year_level || '')}</span>
          <span>${esc(focus)}</span>
          <span>${esc(resource)}</span>
        </div>
      </div>
      <span class="history-time">${esc(time)}</span>
      <button class="history-delete" data-delete-id="${esc(item.id)}" title="Delete">&times;</button>
      <span class="history-arrow">&rarr;</span>
    </div>`;
  }).join('');
}

function formatSlug(slug) {
  return slug.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function timeAgo(date) {
  const now = new Date();
  const diffMs = now - date;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString();
}

async function viewPastGeneration(generationId) {
  try {
    const data = await fetch(`${API}/debug/${generationId}`).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    });

    // Build a gen state from the stored data
    S.gen = freshGen();
    S.gen.id = data.id;
    S.gen.status = data.status || 'completed';
    S.gen.content = data.generated_resource || '';

    // Populate step timings
    const timings = data.step_timings || {};
    for (const [stepName, ms] of Object.entries(timings)) {
      const idx = STEP_META.findIndex(m => m.key === stepName);
      if (idx >= 0) {
        S.gen.steps[idx].status = 'completed';
        S.gen.steps[idx].ms = ms;
      }
    }

    // Set topic from request payload
    const payload = data.request_payload || {};
    S.topic = payload.topic || 'Past generation';

    showGenerate();

    // Mark all steps as completed (for past generations)
    S.gen.steps.forEach((step, i) => {
      if (step.ms != null) {
        setStepStatus(i, 'completed', step.ms);
      } else {
        // If no timing but generation completed, mark as done
        if (S.gen.status === 'completed') {
          setStepStatus(i, 'completed');
        }
      }
    });

    // Show the content
    dom.outputEmpty.classList.add('hidden');
    dom.markdownBody.classList.add('visible');
    dom.markdownBody.classList.remove('streaming');
    dom.markdownBody.innerHTML = marked.parse(S.gen.content);

    // Show debug data if available
    if (data.matched_descriptors) {
      const matches = Array.isArray(data.matched_descriptors) ? data.matched_descriptors : data.matched_descriptors.matches || [];
      if (matches.length) renderCAGData(matches);
    }
    if (data.routing_decision && typeof data.routing_decision === 'object') {
      renderRoutingData(data.routing_decision);
    }
    if (data.rag_results) {
      const ragData = Array.isArray(data.rag_results)
        ? { num_chunks: data.rag_results.length, results: data.rag_results }
        : data.rag_results;
      renderRAGData(ragData);
    }
    if (data.selected_template) {
      renderTemplateData({ name: data.selected_template, variables_resolved: 0 });
    }

    renderTimings();
  } catch (err) {
    console.error('Failed to load generation', err);
  }
}

async function deleteGeneration(id) {
  try {
    await fetch(`${API}/generations/${id}`, { method: 'DELETE' });
    loadHistory();
  } catch (e) {
    console.error('Failed to delete generation', e);
  }
}

async function deleteAllGenerations() {
  try {
    await fetch(`${API}/generations`, { method: 'DELETE' });
    loadHistory();
  } catch (e) {
    console.error('Failed to delete all generations', e);
  }
}

function showConfirm() {
  dom.confirmOverlay.classList.add('open');
}

function hideConfirm() {
  dom.confirmOverlay.classList.remove('open');
}

// ============================================================
// VIEW MANAGEMENT
// ============================================================

function showCompose() {
  dom.generateView.classList.remove('active');
  dom.composeView.classList.add('active');
  S.gen = null;
  loadHistory(); // Refresh history when returning
}

function showGenerate() {
  dom.composeView.classList.remove('active');
  dom.generateView.classList.add('active');
  // Set topic pill
  const topicText = S.topic.length > 60 ? S.topic.slice(0, 57) + '...' : S.topic;
  dom.genTopicPill.textContent = topicText;
  // Build step rail
  buildStepRail();
  // Build inspector steps
  buildInspectorSteps();
  // Reset output
  dom.outputEmpty.classList.remove('hidden');
  dom.markdownBody.classList.remove('visible', 'streaming');
  dom.markdownBody.innerHTML = '';
  dom.inspectorTime.innerHTML = '';
}

// ============================================================
// CHIPS
// ============================================================

function updateChips() {
  const yl = S.ref.yearLevels.find(y => y.title === S.yearLevel);
  const st = S.ref.strands.find(s => s.title === S.strand);
  dom.chipCurriculum.textContent = `${yl ? yl.title : S.yearLevel} \u00b7 ${st ? st.title : S.strand}`;

  const tf = S.ref.focuses.find(f => f.slug === S.teachingFocus);
  dom.chipFocus.textContent = tf ? tf.name : S.teachingFocus;

  const rt = S.ref.resourceTypes.find(r => r.slug === S.resourceType);
  dom.chipResource.textContent = rt ? rt.name : S.resourceType;
}

function findFocusName(slug) {
  const f = S.ref.focuses.find(x => x.slug === slug);
  return f ? f.name : slug;
}
function findResourceName(slug) {
  const r = S.ref.resourceTypes.find(x => x.slug === slug);
  return r ? r.name : slug;
}

// ============================================================
// MODALS
// ============================================================

function openModal(id) {
  const modal = $(`#${id}`);
  if (!modal) return;
  dom.backdrop.classList.add('open');
  modal.classList.add('open');
  // Render content
  if (id === 'curriculum-modal') renderCurriculumModal();
  if (id === 'focus-modal')      renderFocusModal();
  if (id === 'resource-modal')   renderResourceModal();
}

function closeModal() {
  dom.backdrop.classList.remove('open');
  $$('.modal.open').forEach(m => m.classList.remove('open'));
  S.pending = {};
}

function renderCurriculumModal() {
  S.pending.yearLevel = S.yearLevel;
  S.pending.strand = S.strand;

  const ylList = $('#year-level-list');
  const stList = $('#strand-list');

  // Group year levels by band
  const bands = { early_years: 'Early Years', primary: 'Primary', secondary: 'Secondary' };
  let ylHtml = '';
  for (const [band, label] of Object.entries(bands)) {
    const items = S.ref.yearLevels.filter(y => y.band === band);
    if (!items.length) continue;
    ylHtml += `<div class="option-group-label">${label}</div>`;
    for (const y of items) {
      const sel = y.title === S.pending.yearLevel ? ' selected' : '';
      ylHtml += `<div class="option-item${sel}" data-value="${y.title}" data-group="yl">
        <span class="option-radio"></span><span>${y.title}</span>
      </div>`;
    }
  }
  ylList.innerHTML = ylHtml;

  let stHtml = '';
  for (const s of S.ref.strands) {
    const sel = s.title === S.pending.strand ? ' selected' : '';
    stHtml += `<div class="option-item${sel}" data-value="${s.title}" data-group="st">
      <span class="option-radio"></span><span>${s.title}</span>
    </div>`;
  }
  stList.innerHTML = stHtml;
}

function renderFocusModal() {
  S.pending.teachingFocus = S.teachingFocus;
  const container = $('#focus-cards');
  let html = '';
  for (const f of S.ref.focuses) {
    const sel = f.slug === S.pending.teachingFocus ? ' selected' : '';
    const desc = FOCUS_DESCRIPTIONS[f.slug] || '';
    html += `<div class="card-option${sel}" data-value="${f.slug}" data-group="focus">
      <span class="card-radio"></span>
      <div class="card-info"><div class="card-name">${f.name}</div><div class="card-desc">${desc}</div></div>
    </div>`;
  }
  container.innerHTML = html;
}

function renderResourceModal() {
  S.pending.resourceType = S.resourceType;
  const container = $('#resource-cards');
  const filtered = S.ref.resourceTypes.filter(r => r.teaching_focus_slug === S.teachingFocus);
  const list = filtered.length ? filtered : S.ref.resourceTypes;
  let html = '';
  for (const r of list) {
    const sel = r.slug === S.pending.resourceType ? ' selected' : '';
    const desc = r.description ? r.description.slice(0, 120) + (r.description.length > 120 ? '...' : '') : '';
    html += `<div class="card-option${sel}" data-value="${r.slug}" data-group="resource">
      <span class="card-radio"></span>
      <div class="card-info"><div class="card-name">${r.name}</div><div class="card-desc">${desc}</div></div>
    </div>`;
  }
  container.innerHTML = html;
}

// ============================================================
// STEP RAIL (top bar in generate view)
// ============================================================

function buildStepRail() {
  let html = '';
  STEP_META.forEach((m, i) => {
    if (i > 0) html += `<div class="rail-edge" id="rail-edge-${i}"></div>`;
    html += `<div class="rail-node" id="rail-node-${i}" data-status="pending" title="${m.label}">
      <span class="rail-num">${i + 1}</span>
    </div>`;
  });
  dom.stepRail.innerHTML = html;
}

function updateRailNode(index, status) {
  const node = $(`#rail-node-${index}`);
  if (node) node.setAttribute('data-status', status);
  if (status === 'completed' && index > 0) {
    const edge = $(`#rail-edge-${index}`);
    if (edge) edge.classList.add('done');
  }
}

// ============================================================
// INSPECTOR STEPS (sidebar accordion)
// ============================================================

function buildInspectorSteps() {
  let html = '';
  STEP_META.forEach((m, i) => {
    html += `<div class="istep" id="istep-${i}" data-status="pending">
      <div class="istep-head" data-idx="${i}">
        <span class="istep-dot"><span class="istep-num">${i + 1}</span></span>
        <span class="istep-label">${m.label}</span>
        <span class="istep-time" id="istep-time-${i}"></span>
        <span class="istep-chevron">&#8250;</span>
      </div>
      <div class="istep-body"><div class="istep-data" id="istep-data-${i}"></div></div>
    </div>`;
  });
  dom.inspectorSteps.innerHTML = html;
}

function setStepStatus(index, status, ms) {
  const el = $(`#istep-${index}`);
  if (!el) return;
  el.setAttribute('data-status', status);
  updateRailNode(index, status);

  if (status === 'active') {
    el.classList.add('open');
  }
  if (ms != null) {
    $(`#istep-time-${index}`).textContent = (ms / 1000).toFixed(1) + 's';
  }
  if (status === 'completed') {
    const dot = el.querySelector('.istep-num');
    if (dot) dot.textContent = '\u2713';
  }
}

function setStepData(index, html) {
  const el = $(`#istep-data-${index}`);
  if (el) el.innerHTML = html;
}

function renderTimings() {
  if (!S.gen) return;
  const entries = S.gen.steps.filter(s => s.ms != null);
  if (!entries.length) { dom.inspectorTime.innerHTML = ''; return; }
  const maxMs = Math.max(...entries.map(s => s.ms), 1);
  let html = '<div class="timings-title">Step Timings</div>';
  for (const s of entries) {
    const pct = Math.max((s.ms / maxMs) * 100, 3);
    html += `<div class="timing-row">
      <span class="timing-label">${s.short}</span>
      <div class="timing-track"><div class="timing-fill" style="width:${pct}%"></div></div>
      <span class="timing-val">${(s.ms / 1000).toFixed(1)}s</span>
    </div>`;
  }
  dom.inspectorTime.innerHTML = html;
}

// ============================================================
// GENERATION
// ============================================================

async function startGeneration() {
  S.topic = dom.topicInput.value.trim();
  S.context = dom.contextInput.value.trim();
  if (!S.topic) return;

  S.gen = freshGen();
  showGenerate();

  dom.generateBtn.classList.add('loading');
  dom.generateBtn.disabled = true;

  const fd = new FormData();
  fd.append('topic', S.topic);
  fd.append('year_level', S.yearLevel);
  fd.append('strand', S.strand);
  fd.append('teaching_focus', S.teachingFocus);
  fd.append('resource_type', S.resourceType);
  fd.append('additional_context', S.context);

  try {
    const res = await fetch(`${API}/generate`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop() || '';
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data:')) continue;
        const raw = trimmed.slice(5).trim();
        if (!raw || raw === '[DONE]') continue;
        try { handleEvent(JSON.parse(raw)); } catch (_) {}
      }
    }

    // Final render
    if (S.gen) {
      S.gen.status = 'completed';
      dom.markdownBody.classList.remove('streaming');
      renderTimings();
    }
  } catch (err) {
    if (S.gen) S.gen.error = err.message;
    dom.markdownBody.classList.remove('streaming');
    dom.markdownBody.innerHTML = `<p style="color:var(--error)">Error: ${err.message}</p>`;
    dom.markdownBody.classList.add('visible');
    dom.outputEmpty.classList.add('hidden');
  } finally {
    dom.generateBtn.classList.remove('loading');
    dom.generateBtn.disabled = false;
  }
}

// ============================================================
// SSE EVENT HANDLER
// ============================================================

function handleEvent(ev) {
  if (!S.gen) return;

  switch (ev.type) {
    case 'generation_started':
      S.gen.id = ev.generation_id;
      break;

    case 'step_started': {
      const idx = findStepIndex(ev.step, ev.index);
      if (idx >= 0) {
        S.gen.steps[idx].status = 'active';
        setStepStatus(idx, 'active');
      }
      break;
    }

    case 'step_completed': {
      const idx = findStepIndex(ev.step, ev.index);
      if (idx >= 0) {
        S.gen.steps[idx].status = 'completed';
        S.gen.steps[idx].ms = ev.duration_ms;
        setStepStatus(idx, 'completed', ev.duration_ms);
        if (ev.summary) renderStepSummary(idx, ev.summary);
        renderTimings();
      }
      break;
    }

    case 'cag_matches':
      renderCAGData(ev.matches || []);
      break;

    case 'routing_decision':
      renderRoutingData(ev);
      break;

    case 'rag_results':
      renderRAGData(ev);
      break;

    case 'template_selected':
      renderTemplateData(ev);
      break;

    case 'content_chunk':
      S.gen.content += ev.content;
      dom.outputEmpty.classList.add('hidden');
      dom.markdownBody.classList.add('visible', 'streaming');
      dom.markdownBody.innerHTML = marked.parse(S.gen.content);
      // Auto-scroll to bottom
      dom.markdownBody.scrollTop = dom.markdownBody.scrollHeight;
      break;

    case 'generation_completed':
      S.gen.totalMs = ev.total_duration_ms;
      S.gen.status = 'completed';
      dom.markdownBody.classList.remove('streaming');
      renderTimings();
      break;

    case 'error':
      S.gen.error = ev.message;
      dom.outputEmpty.classList.add('hidden');
      dom.markdownBody.innerHTML = `<p style="color:var(--error)">Error: ${ev.message}</p>`;
      dom.markdownBody.classList.add('visible');
      break;
  }
}

function findStepIndex(name, oneBasedIndex) {
  // Try by name first
  const byName = STEP_META.findIndex(m => m.key === name);
  if (byName >= 0) return byName;
  // Fall back to 1-based index
  if (oneBasedIndex >= 1 && oneBasedIndex <= 6) return oneBasedIndex - 1;
  return -1;
}

// ============================================================
// STEP DATA RENDERERS
// ============================================================

function renderStepSummary(idx, summary) {
  const key = STEP_META[idx]?.key;
  if (key === 'input_analyzer' && summary.topic) {
    setStepData(idx, `
      <div class="kv-row"><span class="kv-key">topic</span><span class="kv-val">${esc(summary.topic)}</span></div>
      <div class="kv-row"><span class="kv-key">intent</span><span class="kv-val">${esc(summary.intent || '')}</span></div>
    `);
  } else if (key === 'curriculum_matcher' && summary.num_matches != null) {
    setStepData(idx, `<div class="kv-row"><span class="kv-key">matches</span><span class="kv-val">${summary.num_matches} content descriptors</span></div>`);
  } else if (key === 'teaching_focus_router') {
    setStepData(idx, `
      <div class="kv-row"><span class="kv-key">path</span><span class="kv-val">${esc(summary.path || '')}</span></div>
      <div class="kv-row"><span class="kv-key">band</span><span class="kv-val">${esc(summary.band || '')}</span></div>
    `);
  } else if (key === 'pedagogy_retriever') {
    setStepData(idx, `<div class="kv-row"><span class="kv-key">chunks</span><span class="kv-val">${summary.num_chunks || 0} retrieved</span></div>`);
  } else if (key === 'template_resolver') {
    setStepData(idx, `<div class="kv-row"><span class="kv-key">template</span><span class="kv-val">${esc(summary.template || '')}</span></div>`);
  }
}

function renderCAGData(matches) {
  if (!matches.length) return;
  const idx = 1; // curriculum_matcher
  let html = '<table><thead><tr><th>Code</th><th>Descriptor</th><th>Conf.</th></tr></thead><tbody>';
  for (const m of matches.slice(0, 5)) {
    const cls = `conf-${m.confidence || 'low'}`;
    const text = m.text && m.text.length > 80 ? m.text.slice(0, 77) + '...' : (m.text || '');
    html += `<tr>
      <td style="white-space:nowrap"><code>${esc(m.code)}</code></td>
      <td>${esc(text)}</td>
      <td><span class="conf-badge ${cls}">${esc(m.confidence || '?')}</span></td>
    </tr>`;
  }
  html += '</tbody></table>';
  setStepData(idx, html);
  const el = $(`#istep-${idx}`);
  if (el) el.classList.add('open');
}

function renderRoutingData(ev) {
  const idx = 2; // teaching_focus_router
  setStepData(idx, `
    <div class="kv-row"><span class="kv-key">path</span><span class="kv-val">${esc(ev.teaching_path || '')}</span></div>
    <div class="kv-row"><span class="kv-key">year band</span><span class="kv-val">${esc(ev.year_band || '')}</span></div>
  `);
}

function renderRAGData(ev) {
  const idx = 3; // pedagogy_retriever
  const results = ev.results || [];
  let html = `<div class="kv-row"><span class="kv-key">chunks</span><span class="kv-val">${ev.num_chunks || 0} retrieved</span></div>`;
  if (results.length) {
    html += '<table><thead><tr><th>Source</th><th>Preview</th></tr></thead><tbody>';
    for (const r of results.slice(0, 4)) {
      const preview = (r.content || '').slice(0, 80) + ((r.content || '').length > 80 ? '...' : '');
      html += `<tr><td>${esc(r.name || 'doc')}</td><td>${esc(preview)}</td></tr>`;
    }
    html += '</tbody></table>';
  }
  setStepData(idx, html);
}

function renderTemplateData(ev) {
  const idx = 4; // template_resolver
  setStepData(idx, `
    <div class="kv-row"><span class="kv-key">name</span><span class="kv-val">${esc(ev.name || '')}</span></div>
    <div class="kv-row"><span class="kv-key">vars</span><span class="kv-val">${ev.variables_resolved || 0} resolved</span></div>
  `);
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// ============================================================
// EVENT LISTENERS
// ============================================================

function init() {
  // Topic input -> enable button
  dom.topicInput.addEventListener('input', () => {
    dom.generateBtn.disabled = !dom.topicInput.value.trim();
  });

  // Generate
  dom.generateBtn.addEventListener('click', (e) => {
    e.preventDefault();
    startGeneration();
  });

  // Also allow Enter (without Shift) to submit
  dom.topicInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (dom.topicInput.value.trim()) startGeneration();
    }
  });

  // Back button
  $('#back-btn').addEventListener('click', showCompose);

  // Notes chip toggle
  dom.chipNotes.addEventListener('click', () => {
    const area = dom.contextArea;
    const isOpen = area.classList.contains('open');
    area.classList.toggle('open');
    dom.chipNotes.classList.toggle('active');
    if (!isOpen) dom.contextInput.focus();
  });

  // Chip -> modal
  $$('.chip[data-modal]').forEach(chip => {
    chip.addEventListener('click', () => openModal(chip.dataset.modal));
  });

  // Modal close buttons
  $$('[data-close]').forEach(btn => {
    btn.addEventListener('click', closeModal);
  });

  // Backdrop click closes modal
  dom.backdrop.addEventListener('click', closeModal);

  // Escape closes modal or confirmation
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { hideConfirm(); closeModal(); }
  });

  // Delegated clicks inside modals for option selection
  document.addEventListener('click', (e) => {
    // Option items (year level, strand)
    const optItem = e.target.closest('.option-item[data-group]');
    if (optItem) {
      const group = optItem.dataset.group;
      const val = optItem.dataset.value;
      // Deselect siblings in same group
      $$(`.option-item[data-group="${group}"]`).forEach(el => el.classList.remove('selected'));
      optItem.classList.add('selected');
      if (group === 'yl') S.pending.yearLevel = val;
      if (group === 'st') S.pending.strand = val;
      return;
    }

    // Card options (teaching focus, resource type)
    const cardItem = e.target.closest('.card-option[data-group]');
    if (cardItem) {
      const group = cardItem.dataset.group;
      const val = cardItem.dataset.value;
      $$('.card-option[data-group="' + group + '"]').forEach(el => el.classList.remove('selected'));
      cardItem.classList.add('selected');
      if (group === 'focus') S.pending.teachingFocus = val;
      if (group === 'resource') S.pending.resourceType = val;
      return;
    }

    // History delete button (check before card click since it's inside the card)
    const deleteBtn = e.target.closest('.history-delete[data-delete-id]');
    if (deleteBtn) {
      e.stopPropagation();
      deleteGeneration(deleteBtn.dataset.deleteId);
      return;
    }

    // History card click
    const historyCard = e.target.closest('.history-card[data-gen-id]');
    if (historyCard) {
      viewPastGeneration(historyCard.dataset.genId);
      return;
    }

    // Inspector step accordion toggle
    const stepHead = e.target.closest('.istep-head');
    if (stepHead) {
      const istep = stepHead.closest('.istep');
      if (istep) istep.classList.toggle('open');
    }
  });

  // Apply buttons
  $('#curriculum-apply').addEventListener('click', () => {
    if (S.pending.yearLevel) S.yearLevel = S.pending.yearLevel;
    if (S.pending.strand) S.strand = S.pending.strand;
    updateChips();
    closeModal();
  });

  $('#focus-apply').addEventListener('click', () => {
    if (S.pending.teachingFocus) {
      S.teachingFocus = S.pending.teachingFocus;
      // Auto-update resource type if current one doesn't match new focus
      const filtered = S.ref.resourceTypes.filter(r => r.teaching_focus_slug === S.teachingFocus);
      if (filtered.length && !filtered.find(r => r.slug === S.resourceType)) {
        S.resourceType = filtered[0].slug;
      }
    }
    updateChips();
    closeModal();
  });

  $('#resource-apply').addEventListener('click', () => {
    if (S.pending.resourceType) S.resourceType = S.pending.resourceType;
    updateChips();
    closeModal();
  });

  // Clear All button -> show confirmation
  dom.clearAllBtn.addEventListener('click', showConfirm);

  // Confirmation dialog
  dom.confirmCancel.addEventListener('click', hideConfirm);
  dom.confirmDelete.addEventListener('click', () => {
    hideConfirm();
    deleteAllGenerations();
  });
  dom.confirmOverlay.addEventListener('click', (e) => {
    if (e.target === dom.confirmOverlay) hideConfirm();
  });

  // Load reference data and history
  loadRefData();
  loadHistory();
}

init();
