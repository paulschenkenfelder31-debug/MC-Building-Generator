import './style.css';
import { Preview } from './preview.js';

const cube = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9zM4 7.5l8 4.5 8-4.5M12 12v9"/></svg>';
const arrow = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 4v12m-5-5 5 5 5-5M5 17v4h14v-4"/></svg>';
const sparkle = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="m12 3 2.7 6.3L21 12l-6.3 2.7L12 21l-2.7-6.3L3 12l6.3-2.7z"/></svg>';
const examples = {
  manor: 'A 29×25 medieval manor with 2 floors, a tall corner tower, timber framing, a steep dark roof and a tree-lined approach.',
  villa: 'A modern 33×25 villa with 2 floors, white concrete, broad windows and a roof terrace. No tower.',
  temple: 'A Japanese 27×23 temple with 2 floors, dark timber beams, white walls and sweeping layered eaves.',
};

document.querySelector('#app').innerHTML = `
  <header class="topbar">
    <a class="brand" href="/" aria-label="Blockwright home"><span class="brand-icon">${cube}</span>blockwright<span class="beta">LAB</span></a>
    <span class="header-caption">A little imagination. A lot of blocks.</span>
    <span class="version"><i></i> JAVA EDITION · 1.20.1+</span>
  </header>
  <main class="workspace">
    <aside class="sidebar">
      <div class="section-tag">YOUR NEXT GREAT BUILD</div>
      <h1>Dream it.<br><span>Build it in blocks.</span></h1>
      <p class="intro">Turn a building idea into a Minecraft blueprint you can actually use.</p>
      <form id="build-form">
        <label class="field-label" for="prompt">The idea <span>01</span></label>
        <div class="prompt-wrap"><textarea id="prompt" maxlength="2000" required spellcheck="false" aria-describedby="prompt-help">${examples.manor}</textarea><span class="prompt-mark">${sparkle}</span></div>
        <div class="examples"><button type="button" data-example="manor">Manor</button><button type="button" data-example="villa">Modern villa</button><button type="button" data-example="temple">Temple</button></div>
        <div id="prompt-help" class="help">Try dimensions like 29×25 and “2 floors”.</div>
        <label class="field-label" for="style">Architectural style <span>02</span></label>
        <select id="style"><option value="">From my description</option><option value="medieval">Medieval · timber & stone</option><option value="modern">Modern · concrete & glass</option><option value="japanese">Japanese-inspired · dark timber</option></select>
        <div class="two-fields"><div><label class="small-label" for="seed">Variation seed</label><input id="seed" type="number" min="0" max="2147483647" value="42" required /></div><div><label class="small-label" for="mode">Design planner</label><select id="mode"><option value="offline">Offline · no API</option><option value="ai">AI · API required</option></select></div></div>
        <label class="toggle-row"><span>Include landscape <small>Ground, approach & trees</small></span><input id="terrain" type="checkbox" role="switch" checked /><span class="switch" aria-hidden="true"></span></label>
        <button class="generate" id="generate" type="submit">${sparkle}<span>Generate building</span><span class="key-hint">↵</span></button>
      </form>
      <div class="offline-note"><span class="note-dot"></span><p id="planner-note">Runs locally. No account or API key needed.<br>Curated geometry, with an optional AI planner.</p></div>
      <details class="assistant-connect" id="assistant-connect"><summary>Build with ChatGPT or Codex <span>No API key</span></summary><p>Describe your building in an assistant that supports custom MCP servers. It can send the design here and give you a preview link.</p><label for="mcp-url">MCP server address</label><div class="mcp-address"><input id="mcp-url" readonly aria-label="MCP server address" /><button id="copy-mcp" type="button">Copy</button></div><span id="mcp-copy-status" role="status"></span><p>Your assistant does the planning in chat. This website does not call your subscription or an AI model through MCP.</p></details>
      <div class="sidebar-foot"><span>IDEA → DESIGN → BLOCKS → MINECRAFT</span><span>↗</span></div>
    </aside>
    <section class="studio" aria-label="Building workbench">
      <div class="studio-bar"><div class="project-label"><span class="status-dot"></span><span id="project-title">Untitled building</span></div><div class="studio-tools"><span class="local-badge" id="mode-badge">PROCEDURAL</span><button type="button" id="snapshot" class="icon-button" title="Save preview image" aria-label="Save preview image">▣</button></div></div>
      <div class="viewport" id="viewport">
        <div class="viewport-label"><span class="eyebrow">LIVE VOXEL PREVIEW</span><span id="dimensions">Preparing your workspace…</span></div>
        <div class="view-controls" aria-label="Camera views"><button class="active" data-view="iso" type="button">Perspective</button><button data-view="front" type="button">Front</button><button data-view="top" type="button">Floor plan</button></div>
        <div class="view-help">Drag to orbit <b>·</b> Scroll to zoom <b>·</b> Right-drag to pan</div>
        <div class="compass" aria-hidden="true"><span>N</span><div>↑</div></div>
        <div class="loading hidden" id="loading" role="status"><div class="loader-cube">${cube}</div><strong>Finding the shape of your idea…</strong><span>Planning · building · checking block states</span></div>
        <div class="error hidden" id="error" role="alert"></div>
      </div>
      <div class="cutaway"><div><span class="cutaway-icon">▱</span><label for="layer">Look inside</label><span class="cutaway-copy">Slice through the building</span></div><input id="layer" type="range" min="0" max="40" value="40" aria-label="Highest visible block layer" /><output id="layer-value" for="layer">All layers</output></div>
      <div class="details-grid">
        <section class="details-card"><div class="card-heading"><h2>The blueprint</h2><span class="tag" id="validation-badge">WAITING</span></div><div class="stats"><div><strong id="block-count">—</strong><span>placed blocks</span></div><div><strong id="material-count">—</strong><span>materials</span></div><div><strong id="floor-count">—</strong><span>floors</span></div></div><div class="design-notes" id="design-notes">Your design details will appear here.</div></section>
        <section class="details-card materials-card"><div class="card-heading"><h2>Material palette</h2><span class="muted">BLOCKS</span></div><div id="materials" class="materials"><span class="muted">Generate a building to see its materials.</span></div></section>
        <section class="details-card export-card"><div class="card-heading"><h2>Take it to your world</h2>${cube}</div><p>Real blocks. Ready for your next world.</p><div class="export-buttons"><a id="schem" class="download disabled" aria-disabled="true">${arrow}.schem</a><a id="litematic" class="download secondary disabled" aria-disabled="true">${arrow}.litematic</a></div><div class="export-foot"><span>WorldEdit / FAWE · Litematica</span><a id="json" class="disabled" aria-disabled="true">Design JSON ↗</a></div><small>Imports include air. Paste into a backup or an empty area.</small></section>
      </div>
      <footer class="studio-footer"><span>Built one block at a time.</span><span>Prototype · template-based geometry · no visual AI review yet</span></footer>
    </section>
  </main>`;

const $ = (id) => document.getElementById(id);
let preview;
const previewUnavailable = '3D preview could not start. Enable WebGL in your browser. Generation and exports are still available.';
try { preview = new Preview($('viewport')); }
catch { showError(previewUnavailable); }
let current;
let pending = false;

function showError(message) { $('error').textContent = message; $('error').classList.remove('hidden'); }
function colorFor(name) { return preview?.colorFor(name) || '#729375'; }

function displayBuild(data, syncForm = false) {
  current = data;
  $('project-title').textContent = data.spec.title;
  $('dimensions').textContent = `${data.dimensions[0]} × ${data.dimensions[2]} × ${data.dimensions[1]} blocks · including site`;
  $('mode-badge').textContent = data.planning.mode === 'assistant' ? 'ASSISTANT DESIGN' : data.planning.mode === 'ai' ? 'AI PLANNED' : 'PROCEDURAL';
  $('block-count').textContent = data.block_count.toLocaleString();
  $('material-count').textContent = data.materials.length;
  $('floor-count').textContent = `${data.spec.floors}${data.spec.tower ? ' + tower' : ''}`;
  $('validation-badge').textContent = data.validation.passed ? 'STATES CHECKED' : 'CHECK FAILED';
  $('design-notes').textContent = `${data.spec.width} × ${data.spec.depth} building footprint · Seed ${data.spec.seed}. ${data.planning.description}`;
  $('materials').replaceChildren(...data.materials.map(({ block, count }) => {
    const row = document.createElement('div'); row.className = 'material';
    const chip = document.createElement('i'); chip.style.background = colorFor(block);
    const name = document.createElement('span'); name.textContent = block.replace('minecraft:', '').replaceAll('_', ' ');
    const amount = document.createElement('b'); amount.textContent = count.toLocaleString();
    row.append(chip, name, amount); return row;
  }));
  for (const format of ['schem', 'litematic', 'json']) {
    $(format).href = `/api/builds/${data.id}/${format}`;
    $(format).classList.remove('disabled'); $(format).removeAttribute('aria-disabled');
    $(format).setAttribute('download', `building-${data.spec.seed}.${format}`);
  }
  $('layer').max = data.dimensions[1] - 1; $('layer').value = $('layer').max;
  $('layer-value').textContent = 'All layers';
  if (syncForm) {
    $('style').value = data.spec.style; $('seed').value = data.spec.seed; $('terrain').checked = data.spec.terrain;
    $('prompt').value = `A ${data.spec.width}×${data.spec.depth} ${data.spec.style} building with ${data.spec.floors} floors. ${data.spec.tower ? 'Include a corner tower.' : 'No tower.'}`;
  }
  if (preview) { preview.load(data); setView('iso'); }
  else showError(previewUnavailable);
}

async function generate(event) {
  event?.preventDefault();
  if (pending || !$('build-form').reportValidity()) return;
  pending = true;
  $('generate').disabled = true;
  $('loading').classList.remove('hidden');
  $('error').classList.add('hidden');
  $('viewport').setAttribute('aria-busy', 'true');
  try {
    const overrides = { seed: Number($('seed').value), terrain: $('terrain').checked };
    if ($('style').value) overrides.style = $('style').value;
    const response = await fetch('/api/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt: $('prompt').value, mode: $('mode').value, overrides }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Generation failed. Please try again.');
    displayBuild(data);
  } catch (error) { showError(error.message || 'Could not reach the building server.'); }
  finally {
    pending = false; $('generate').disabled = false; $('loading').classList.add('hidden');
    $('viewport').setAttribute('aria-busy', 'false');
  }
}

async function loadBuild(buildId) {
  pending = true; $('generate').disabled = true;
  $('loading').classList.remove('hidden'); $('viewport').setAttribute('aria-busy', 'true');
  try {
    const response = await fetch(`/api/builds/${encodeURIComponent(buildId)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'This build could not be loaded.');
    displayBuild(data, true);
  } catch (error) { showError(error.message || 'Could not load this build. You can generate a new one.'); }
  finally {
    pending = false; $('generate').disabled = false;
    $('loading').classList.add('hidden'); $('viewport').setAttribute('aria-busy', 'false');
  }
}

function setView(view) {
  preview?.setView(view);
  document.querySelectorAll('[data-view]').forEach(button => { const active = button.dataset.view === view; button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active)); });
}
$('build-form').addEventListener('submit', generate);
document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click', () => { $('prompt').value = examples[button.dataset.example]; $('style').value = ''; }));
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
$('layer').addEventListener('input', () => {
  $('layer-value').textContent = $('layer').value === $('layer').max ? 'All layers' : `Layer ${$('layer').value}`;
  if (current) preview?.setLayer(Number($('layer').value));
});
$('snapshot').addEventListener('click', () => {
  if (!preview || !current) return;
  const link = document.createElement('a'); link.download = 'blockwright-preview.png'; link.href = preview.snapshot(); link.click();
});
$('mode').addEventListener('change', () => {
  $('planner-note').textContent = $('mode').value === 'ai' ? 'AI planning sends your description to OpenAI. Uses a server-side API key and may incur API charges.' : 'Runs locally. No account or API key needed. Curated geometry, with an optional AI planner.';
});
$('mcp-url').value = `${window.location.origin}/mcp`;
$('copy-mcp').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText($('mcp-url').value);
    $('mcp-copy-status').textContent = 'Address copied. Add it to your assistant’s MCP server settings.';
  } catch {
    $('mcp-url').focus(); $('mcp-url').select();
    $('mcp-copy-status').textContent = 'Select and copy the address above.';
  }
});
const requestedBuild = new URLSearchParams(window.location.search).get('build');
if (requestedBuild) loadBuild(requestedBuild);
else generate();
