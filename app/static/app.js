'use strict';

(() => {
  const $ = id => document.getElementById(id);
  const names = {email: 'Email address', phone: 'Phone number', token: 'Credential pattern', custom: 'Custom keyword'};
  const state = {job: null, samples: [], decisions: new Map(), selected: null, masks: [], drawing: false, draft: null, pointer: null, poll: null, generation: 0, compare: false, dirty: false, initialized: false, busy: false, connectionWarning: false, authenticated: false};
  const svgNS = 'http://www.w3.org/2000/svg';

  function show(id, visible) { $(id).hidden = !visible; }
  function notice(message) { $('notice').textContent = message || ''; show('notice', Boolean(message)); }
  function time(value, detailed = true) {
    const ticks = Math.round(Math.max(0, Number(value) || 0) * 100);
    const minutes = Math.floor(ticks / 6000).toString().padStart(2, '0');
    const remainder = detailed ? ((ticks % 6000) / 100).toFixed(2).padStart(5, '0') : Math.floor((ticks % 6000) / 100).toString().padStart(2, '0');
    return `${minutes}:${remainder}`;
  }
  function currentTime() { return state.job?.media_type === 'video' ? $('original-video').currentTime || 0 : 0; }
  function duration() { return Math.max(Number(state.job?.duration) || 1, 0.01); }
  function keywords() { return $('keywords').value.split(/\r?\n/).map(value => value.trim()).filter(Boolean); }
  function isBusy() { return state.busy || Boolean(state.job?.worker_active) || ['queued', 'analyzing', 'exporting'].includes(state.job?.status); }
  async function request(url, options = {}) {
    let response;
    try { response = await fetch(url, {credentials: 'same-origin', ...options}); }
    catch { throw new Error('The local service could not be reached. Check that DemoSafe is running, then try again.'); }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail || data.error;
      const error = new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(item => item.msg || 'Invalid input').join('; ') : `The request failed (${response.status}). Please try again.`);
      error.status = response.status;
      throw error;
    }
    return data;
  }
  function post(url, body) { return request(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}); }
  function setSteps(stage) {
    ['import', 'review', 'export'].forEach((name, index) => {
      const element = $(`step-${name}`);
      element.classList.toggle('active', stage === index);
      element.classList.toggle('complete', stage > index);
      if (stage === index) element.setAttribute('aria-current', 'step'); else element.removeAttribute('aria-current');
    });
  }
  function setSubmissionBusy(value) {
    state.busy = value;
    $('load-sample').disabled = value || !state.authenticated || !state.samples.length;
    $('sample-select').disabled = value || !state.authenticated || !state.samples.length;
    $('file-input').disabled = value || !state.authenticated;
    $('keywords').disabled = value || !state.authenticated;
    $('load-sample').textContent = value ? 'Starting…' : 'Load sample';
  }
  async function startJob(create) {
    if (isBusy() || !state.authenticated) return;
    notice('');
    setSubmissionBusy(true);
    try {
      const result = await create();
      if (!result.id) throw new Error('The service returned an invalid job. Please try again.');
      clearTimeout(state.poll);
      state.generation += 1;
      state.job = {id: result.id, status: 'queued', progress: 0};
      state.initialized = false;
      state.decisions.clear();
      state.selected = null;
      state.masks = [];
      state.compare = false;
      state.dirty = false;
      show('intake', false);
      show('review', false);
      show('finished-message', false);
      show('new-review', false);
      show('delete-job', false);
      show('verification', false);
      show('download-actions', false);
      renderProcessing();
      pollJob(state.generation);
    } catch (error) { notice(error.message); }
    finally { setSubmissionBusy(false); }
  }
  async function upload(file) {
    if (!file) return;
    if (!/\.(png|jpe?g|mp4|webm|mov)$/i.test(file.name)) {
      notice('Choose a PNG, JPG, MP4, WebM, or MOV file.');
      return;
    }
    if (file.size > 100 * 1024 * 1024) { notice('Choose a file smaller than 100 MB.'); return; }
    await startJob(() => {
      const body = new FormData();
      body.append('file', file);
      body.append('keywords', keywords().join('\n'));
      return request('/api/jobs', {method: 'POST', body});
    });
  }
  function renderProcessing() {
    const job = state.job;
    const exporting = job?.status === 'exporting';
    const active = ['queued', 'analyzing', 'exporting'].includes(job?.status);
    show('processing', active);
    if (!active) return;
    const fraction = Math.max(0, Math.min(1, Number(job.progress) || 0));
    $('progress-bar').style.width = `${fraction * 100}%`;
    $('progress-percent').textContent = `${Math.round(fraction * 100)}%`;
    $('processing-kicker').textContent = exporting ? 'Local export & rescan' : 'Local analysis';
    $('processing-title').textContent = exporting ? 'Masking your selection, then checking the copy…' : job.status === 'queued' ? 'Preparing your file…' : 'Analyzing visible text…';
    $('progress-message').textContent = exporting ? 'Video audio is removed. The original stays unchanged.' : 'Your file remains on this computer.';
    $('cancel-job').disabled = false;
    $('cancel-job').textContent = 'Cancel';
    setSteps(exporting ? 2 : 0);
  }
  async function pollJob(generation) {
    if (generation !== state.generation || !state.job) return;
    try {
      const job = await request(`/api/jobs/${encodeURIComponent(state.job.id)}`);
      if (generation !== state.generation) return;
      if (state.connectionWarning) { notice(''); state.connectionWarning = false; }
      state.job = job;
      renderJob();
      if (job.worker_active || ['queued', 'analyzing', 'exporting'].includes(job.status)) state.poll = setTimeout(() => pollJob(generation), 850);
    } catch (error) {
      if (generation !== state.generation) return;
      if (error.status === 401) {
        state.authenticated = false; setSubmissionBusy(false);
        notice('This local session has expired. Open DemoSafe using the start script again.');
        return;
      }
      state.connectionWarning = true;
      notice(`${error.message} Retrying in a moment…`);
      state.poll = setTimeout(() => pollJob(generation), 2200);
    }
  }
  function renderJob() {
    const job = state.job;
    renderProcessing();
    show('delete-job', Boolean(job));
    $('delete-job').disabled = isBusy();
    $('delete-job').title = job.worker_active ? 'Wait for the background worker to finish before deleting.' : 'Delete this review and its local files';
    $('workspace-title').textContent = job.filename || 'Preparing review';
    $('workspace-subtitle').textContent = job.status === 'done' ? 'Redacted copy created. Review the export and its verification report.' : 'Inspect every finding before you share the result.';
    if (job.backend) $('backend-label').textContent = `${job.backend} · local engine`;
    if (['cancelled', 'error'].includes(job.status)) {
      show('review', false);
      show('finished-message', true);
      $('finished-title').textContent = job.status === 'cancelled' ? (job.worker_active ? 'Stopping the background task…' : 'Review cancelled.') : 'This file could not be processed.';
      $('finished-restart').disabled = isBusy();
      $('finished-description').textContent = job.status === 'cancelled' ? 'No new export was completed. Your original file has not been changed.' : job.error || 'Please check the file format and limits, then start a new review.';
      return;
    }
    if (['ready', 'done', 'exporting'].includes(job.status)) {
      show('review', true);
      if (!state.initialized) initializeReview();
      const working = job.status === 'exporting' || Boolean(job.worker_active);
      $('export-job').disabled = working;
      $('draw-mask').disabled = working;
      $('select-all').disabled = working;
      $('filter-type').disabled = working;
      $('finding-list').querySelectorAll('input').forEach(input => input.disabled = working);
      $('manual-list').querySelectorAll('button').forEach(button => button.disabled = working);
      show('new-review', !working);
      if (!working) setSteps(job.status === 'done' ? 2 : 1);
      if (job.status === 'done') initializeExport();
      renderSelection();
    }
  }
  function initializeReview() {
    const job = state.job;
    state.initialized = true;
    (job.events || []).forEach(event => state.decisions.set(String(event.id), event.redact !== false));
    const base = `/api/jobs/${encodeURIComponent(job.id)}/media/`;
    const video = job.media_type === 'video';
    show('original-video', video);
    show('original-image', !video);
    show('result-video', video);
    show('result-image', !video);
    const source = video ? $('original-video') : $('original-image');
    source.src = `${base}original`;
    if (video) { $('original-video').load(); $('original-video').muted = true; }
    const width = Number(job.width) || 1920;
    const height = Number(job.height) || 1080;
    $('original-frame').style.aspectRatio = `${width} / ${height}`;
    $('result-frame').style.aspectRatio = `${width} / ${height}`;
    $('original-frame').style.setProperty('--media-ratio', String(width / height));
    $('result-frame').style.setProperty('--media-ratio', String(width / height));
    $('overlay').setAttribute('viewBox', `0 0 ${width} ${height}`);
    $('overlay').setAttribute('preserveAspectRatio', 'none');
    $('media-details').textContent = `${width} × ${height}${video ? ` · ${Number(job.duration || 0).toFixed(1)}s${job.fps ? ` · ${Number(job.fps).toFixed(0)} fps` : ''}` : ' · image'}`;
    $('time-display').textContent = video ? time(0, true) : 'STILL IMAGE';
    $('view-compare').disabled = true;
    setPreview(false);
    renderFindings();
    renderMasks();
    renderOverlay();
  }
  function renderFindings() {
    const job = state.job;
    const events = job?.events || [];
    const filter = $('filter-type').value;
    const visible = events.filter(event => filter === 'all' || event.type === filter);
    const list = $('finding-list');
    list.replaceChildren();
    $('finding-count').textContent = String(events.length);
    show('no-findings', events.length === 0);
    if (events.length && !visible.length) {
      const message = document.createElement('p');
      message.className = 'filtered-empty';
      message.textContent = 'No findings of this type. Choose another filter to see the rest.';
      list.append(message);
    }
    visible.forEach(event => {
      const id = String(event.id);
      const item = document.createElement('div');
      item.className = `finding-item${state.selected === id ? ' selected' : ''}`;
      item.setAttribute('role', 'listitem');
      item.dataset.eventId = id;
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.className = 'finding-checkbox';
      checkbox.checked = state.decisions.get(id) !== false;
      checkbox.disabled = isBusy();
      checkbox.setAttribute('aria-label', `Mask ${names[event.type] || 'finding'} at ${time(event.start)}`);
      checkbox.addEventListener('change', () => { state.decisions.set(id, checkbox.checked); markDirty(); renderSelection(); renderOverlay(); });
      const inspect = document.createElement('button');
      inspect.className = 'finding-inspect';
      inspect.setAttribute('aria-label', `Inspect ${names[event.type] || 'finding'} at ${time(event.start)}`);
      inspect.setAttribute('aria-pressed', String(state.selected === id));
      const top = document.createElement('span');
      top.className = 'finding-top';
      const type = document.createElement('span');
      type.className = 'finding-type';
      type.textContent = names[event.type] || 'Sensitive text';
      const timestamp = document.createElement('span');
      timestamp.className = 'finding-time';
      timestamp.textContent = job.media_type === 'video' ? `${time(event.start)}–${time(event.end)}` : 'IMAGE';
      top.append(type, timestamp);
      const text = document.createElement('span');
      text.className = 'finding-text';
      text.textContent = event.display || '•••• (sensitive text)';
      const meta = document.createElement('span');
      meta.className = 'finding-meta';
      const confidence = Number(event.confidence);
      const exposure = job.media_type === 'video' ? `${Math.max(0, Number(event.end) - Number(event.start)).toFixed(2)} s exposure · ` : '';
      meta.textContent = exposure + (Number.isFinite(confidence) ? `OCR confidence ${Math.round(Math.max(0, Math.min(1, confidence)) * 100)}%` : 'Click to inspect the original');
      inspect.append(top, text, meta);
      inspect.addEventListener('click', () => selectEvent(event));
      item.append(checkbox, inspect);
      list.append(item);
    });
    renderSelection();
  }
  function selectEvent(event) {
    state.selected = String(event.id);
    if (state.job.media_type === 'video') {
      $('original-video').pause();
      $('original-video').currentTime = Math.min(Number(event.start) || 0, Math.max(0, duration() - 0.001));
      if (state.compare) $('result-video').currentTime = $('original-video').currentTime;
    }
    $('finding-list').querySelectorAll('.finding-item').forEach(item => {
      const selected = item.dataset.eventId === state.selected;
      item.classList.toggle('selected', selected);
      item.querySelector('.finding-inspect').setAttribute('aria-pressed', String(selected));
    });
    renderOverlay();
  }
  function renderSelection() {
    const events = state.job?.events || [];
    const checked = events.filter(event => state.decisions.get(String(event.id)) !== false).length;
    $('selection-count').textContent = `${checked} selected`;
    $('select-all').textContent = checked === events.length && events.length > 0 ? 'Deselect all' : 'Select all';
    $('select-all').disabled = isBusy() || !events.length;
    $('summary-detected').textContent = String(events.length);
    $('summary-selected').textContent = String(checked);
    $('summary-manual').textContent = String(state.masks.length);
    $('summary-kept').textContent = String(events.length - checked);
    $('export-summary').textContent = state.dirty ? 'Selection changed. Export again to apply it.' : events.length > checked ? `${events.length - checked} finding(s) will remain visible. Review before exporting.` : 'All findings selected. Review the original before exporting.';
    $('export-job').firstChild.textContent = state.job?.status === 'done' ? 'Export updated copy' : 'Export redacted copy';
  }
  function activeAt(start, end, timestamp) {
    return state.job?.media_type !== 'video' || timestamp >= (Number(start) || 0) - 0.002 && timestamp < Number(end);
  }
  function rectangle(box, className) {
    if (!Array.isArray(box) || box.length !== 4 || box.some(value => !Number.isFinite(Number(value)))) return null;
    const rect = document.createElementNS(svgNS, 'rect');
    rect.setAttribute('x', String(box[0])); rect.setAttribute('y', String(box[1]));
    rect.setAttribute('width', String(Math.max(0, box[2] - box[0]))); rect.setAttribute('height', String(Math.max(0, box[3] - box[1])));
    rect.setAttribute('rx', '2');
    if (className) rect.setAttribute('class', className);
    return rect;
  }
  function renderOverlay() {
    if (!state.job) return;
    const overlay = $('overlay');
    overlay.replaceChildren();
    const timestamp = currentTime();
    (state.job.events || []).forEach(event => {
      if (!activeAt(event.start, event.end, timestamp)) return;
      const selected = String(event.id) === state.selected;
      if (state.decisions.get(String(event.id)) === false && !selected) return;
      const rect = rectangle(event.box, selected ? 'selected' : '');
      if (rect) overlay.append(rect);
    });
    state.masks.forEach(mask => {
      if (activeAt(mask.start, mask.end, timestamp)) { const rect = rectangle(mask.box, 'manual'); if (rect) overlay.append(rect); }
    });
    if (state.draft) { const rect = rectangle(state.draft, 'draft'); if (rect) overlay.append(rect); }
    $('time-display').textContent = state.job.media_type === 'video' ? time(timestamp, true) : 'STILL IMAGE';
  }
  function markDirty() {
    if (state.job?.status === 'done') {
      state.dirty = true;
      $('verification-title').textContent = 'Review changed since this export';
      $('verification-message').textContent = 'The displayed export and report reflect your previous selection. Export again to apply your latest changes.';
      $('verification').classList.add('warning');
    }
  }
  function beginMask() {
    if (isBusy()) return;
    state.drawing = true;
    state.draft = null;
    $('original-video').pause();
    setPreview(false);
    const start = currentTime();
    $('mask-start').value = start.toFixed(2);
    $('mask-end').value = state.job.media_type === 'video' ? Math.min(duration(), start + 2).toFixed(2) : '1';
    $('mask-start').disabled = state.job.media_type !== 'video';
    $('mask-end').disabled = state.job.media_type !== 'video';
    $('mask-start').max = String(duration());
    $('mask-end').max = String(duration());
    ['box-left', 'box-right'].forEach(id => $(id).max = String(state.job.width));
    ['box-top', 'box-bottom'].forEach(id => $(id).max = String(state.job.height));
    $('save-mask').disabled = true;
    show('manual-editor', true);
    show('draw-instruction', true);
    $('overlay').classList.add('drawing');
    $('draw-mask').textContent = 'Drawing mask…';
    $('mask-status').textContent = state.job.media_type === 'video' ? 'Draw a rectangle in the original preview, then set its time range.' : 'Draw a rectangle in the original preview. It will cover the whole image.';
  }
  function endMask() {
    state.drawing = false; state.draft = null; state.pointer = null;
    show('manual-editor', false); show('draw-instruction', false);
    $('overlay').classList.remove('drawing');
    $('draw-mask').innerHTML = '<svg class="icon"><use href="#i-box"/></svg>Draw mask';
    renderOverlay();
  }
  function pointerPoint(event) {
    const bounds = $('overlay').getBoundingClientRect();
    return [Math.round(Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)) * state.job.width), Math.round(Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)) * state.job.height)];
  }
  function saveMask() {
    if (!state.draft || isBusy()) return;
    const start = Number($('mask-start').value), end = Number($('mask-end').value);
    if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start || end > duration() + 0.01) {
      $('mask-status').textContent = `Use a start before the end, within 0–${duration().toFixed(2)} seconds.`;
      return;
    }
    state.masks.push({start, end: Math.min(end, duration()), box: [...state.draft]});
    markDirty(); endMask(); renderMasks(); renderSelection();
  }
  function renderMasks() {
    $('manual-list').replaceChildren();
    state.masks.forEach((mask, index) => {
      const item = document.createElement('li');
      const description = document.createElement('span');
      description.textContent = `Manual mask ${index + 1} · ${state.job.media_type === 'video' ? `${time(mask.start, true)}–${time(mask.end, true)}` : 'Whole image'} · ${mask.box[2] - mask.box[0]} × ${mask.box[3] - mask.box[1]} px`;
      const remove = document.createElement('button');
      remove.setAttribute('aria-label', `Remove manual mask ${index + 1}`);
      remove.innerHTML = '<svg class="icon"><use href="#i-close"/></svg>';
      remove.addEventListener('click', () => { if (isBusy()) return; state.masks.splice(index, 1); markDirty(); renderMasks(); renderOverlay(); renderSelection(); });
      item.append(description, remove); $('manual-list').append(item);
    });
  }
  function setPreview(compare) {
    state.compare = compare && state.job?.status === 'done';
    $('preview-grid').classList.toggle('compare', state.compare);
    show('result-pane', state.compare);
    $('view-original').classList.toggle('selected', !state.compare);
    $('view-compare').classList.toggle('selected', state.compare);
    $('view-original').setAttribute('aria-pressed', String(!state.compare));
    $('view-compare').setAttribute('aria-pressed', String(state.compare));
    if (state.compare && state.job.media_type === 'video') $('result-video').currentTime = currentTime();
    if (!state.compare) $('result-video').pause();
  }
  function initializeExport() {
    const job = state.job;
    const source = job.export_url || `/api/jobs/${encodeURIComponent(job.id)}/media/redacted`;
    const media = job.media_type === 'video' ? $('result-video') : $('result-image');
    // Each completed export gets a fresh URL to avoid displaying a previous copy.
    if (media.dataset.exportSource !== source || media.dataset.needsRefresh === 'true') {
      media.src = `${source}${source.includes('?') ? '&' : '?'}v=${Date.now()}`;
      media.dataset.exportSource = source;
      media.dataset.needsRefresh = 'false';
      if (job.media_type === 'video') media.load();
    }
    $('view-compare').disabled = false;
    $('download-media').href = source;
    $('download-report').href = job.report_url || `/api/jobs/${encodeURIComponent(job.id)}/report`;
    show('download-actions', true);
    show('verification', true);
    if (!state.dirty) {
      const result = job.metrics?.rescan || job.rescan;
      const status = result?.status;
      $('verification').classList.toggle('warning', status !== 'passed');
      $('verification-title').textContent = status === 'passed' ? 'Rescan complete · no supported patterns found' : status === 'findings' ? 'Rescan flagged text for another look' : status === 'error' ? 'Export created · rescan could not finish' : 'Export created · rescan not verified';
      $('verification-message').textContent = result?.message || (status === 'passed' ? 'The exported copy was checked again. Watch or inspect it before sharing.' : status === 'findings' ? `${Number(result.findings_count) || 0} finding(s) remain in the exported copy. Review the output and add masks if needed.` : 'Review the exported copy manually. No completed rescan result is available.');
    }
  }
  async function exportJob() {
    if (!state.job || isBusy()) return;
    notice(''); endMask();
    $('original-video').pause(); $('result-video').pause();
    setSubmissionBusy(true);
    $('export-job').disabled = true;
    try {
      const result = await post(`/api/jobs/${encodeURIComponent(state.job.id)}/export`, {decisions: (state.job.events || []).map(event => ({event_id: event.id, redact: state.decisions.get(String(event.id)) !== false})), manual_masks: state.masks});
      state.job = {...state.job, ...result, status: result.status || 'exporting'};
      state.dirty = false;
      $('result-video').dataset.needsRefresh = 'true';
      $('result-image').dataset.needsRefresh = 'true';
      show('download-actions', false); show('verification', false);
      renderJob();
      clearTimeout(state.poll);
      pollJob(state.generation);
    } catch (error) { notice(error.message); $('export-job').disabled = false; }
    finally { setSubmissionBusy(false); }
  }
  function reset() {
    if (isBusy()) return;
    clearTimeout(state.poll); state.generation += 1;
    $('original-video').pause(); $('result-video').pause();
    for (const id of ['original-video', 'original-image', 'result-video', 'result-image']) { $(id).removeAttribute('src'); delete $(id).dataset.exportSource; }
    state.job = null; state.initialized = false; state.selected = null; state.decisions.clear(); state.masks = []; state.dirty = false;
    endMask(); notice(''); setSubmissionBusy(false); setSteps(0);
    $('file-input').value = '';
    $('filter-type').value = 'all';
    $('workspace-title').textContent = 'Source file';
    $('workspace-subtitle').textContent = 'Screenshot or screen recording';
    show('intake', true); show('processing', false); show('review', false); show('finished-message', false); show('new-review', false); show('delete-job', false);
    $('file-input').focus();
  }

  $('file-input').addEventListener('change', event => upload(event.target.files[0]));
  $('dropzone').addEventListener('dragover', event => { event.preventDefault(); if (!isBusy()) $('dropzone').classList.add('drag-over'); });
  $('dropzone').addEventListener('dragleave', event => { if (!$('dropzone').contains(event.relatedTarget)) $('dropzone').classList.remove('drag-over'); });
  $('dropzone').addEventListener('drop', event => { event.preventDefault(); $('dropzone').classList.remove('drag-over'); if (!isBusy()) upload(event.dataTransfer.files[0]); });
  $('load-sample').addEventListener('click', () => {
    const sample = state.samples.find(item => String(item.id) === $('sample-select').value);
    if (!sample) return;
    startJob(() => post('/api/jobs/sample', {sample_id: sample.id, keywords: keywords()}));
  });
  $('sample-select').addEventListener('change', () => {
    const sample = state.samples.find(item => String(item.id) === $('sample-select').value);
    $('sample-description').textContent = sample?.description || 'Generated fictional data for demonstration.';
  });
  $('cancel-job').addEventListener('click', async () => {
    if (!state.job) return;
    $('cancel-job').disabled = true; $('cancel-job').textContent = 'Cancelling…';
    try { await post(`/api/jobs/${encodeURIComponent(state.job.id)}/cancel`, {}); }
    catch (error) { notice(error.message); $('cancel-job').disabled = false; }
  });
  $('filter-type').addEventListener('change', renderFindings);
  $('select-all').addEventListener('click', () => {
    if (isBusy()) return;
    const events = state.job?.events || [];
    const allSelected = events.every(event => state.decisions.get(String(event.id)) !== false);
    events.forEach(event => state.decisions.set(String(event.id), !allSelected));
    markDirty(); renderFindings(); renderOverlay();
  });
  $('draw-mask').addEventListener('click', beginMask);
  $('cancel-mask').addEventListener('click', endMask);
  $('save-mask').addEventListener('click', saveMask);
  $('set-mask-box').addEventListener('click', () => {
    if (!state.drawing || isBusy()) return;
    const box = ['box-left', 'box-top', 'box-right', 'box-bottom'].map(id => Math.round(Number($(id).value)));
    if (box.some(value => !Number.isFinite(value)) || box[0] < 0 || box[1] < 0 || box[2] > state.job.width || box[3] > state.job.height || box[2] - box[0] < 4 || box[3] - box[1] < 4) {
      $('mask-status').textContent = `Choose a rectangle at least 4 × 4 pixels, within ${state.job.width} × ${state.job.height}.`;
      return;
    }
    state.draft = box; $('save-mask').disabled = false;
    $('mask-status').textContent = 'Rectangle selected. Confirm the time range, then add the mask.';
    renderOverlay();
  });
  $('overlay').addEventListener('pointerdown', event => {
    if (!state.drawing || event.button !== 0) return;
    state.pointer = pointerPoint(event); state.draft = [...state.pointer, ...state.pointer];
    $('overlay').setPointerCapture(event.pointerId); event.preventDefault(); renderOverlay();
  });
  $('overlay').addEventListener('pointermove', event => {
    if (!state.drawing || !state.pointer) return;
    const point = pointerPoint(event);
    state.draft = [Math.min(state.pointer[0], point[0]), Math.min(state.pointer[1], point[1]), Math.max(state.pointer[0], point[0]), Math.max(state.pointer[1], point[1])];
    renderOverlay();
  });
  $('overlay').addEventListener('pointerup', event => {
    if (!state.pointer) return;
    state.pointer = null;
    if ($('overlay').hasPointerCapture(event.pointerId)) $('overlay').releasePointerCapture(event.pointerId);
    const usable = state.draft && state.draft[2] - state.draft[0] >= 4 && state.draft[3] - state.draft[1] >= 4;
    $('save-mask').disabled = !usable;
    if (usable) ['box-left', 'box-top', 'box-right', 'box-bottom'].forEach((id, index) => $(id).value = String(state.draft[index]));
    $('mask-status').textContent = usable ? 'Rectangle selected. Confirm the time range, then add the mask.' : 'That area is too small. Draw a larger rectangle.';
  });
  $('overlay').addEventListener('pointercancel', () => { state.pointer = null; state.draft = null; $('save-mask').disabled = true; renderOverlay(); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && state.drawing) endMask(); });
  $('view-original').addEventListener('click', () => setPreview(false));
  $('view-compare').addEventListener('click', () => setPreview(true));
  $('export-job').addEventListener('click', exportJob);
  $('new-review').addEventListener('click', reset);
  $('finished-restart').addEventListener('click', reset);
  $('delete-job').addEventListener('click', () => {
    if (!state.job || isBusy()) return;
    $('delete-confirm').disabled = false;
    $('delete-dialog').showModal();
    $('delete-cancel').focus();
  });
  $('delete-cancel').addEventListener('click', () => $('delete-dialog').close());
  $('delete-confirm').addEventListener('click', async () => {
    if (!state.job || isBusy()) return;
    $('delete-confirm').disabled = true;
    state.busy = true;
    try {
      await request(`/api/jobs/${encodeURIComponent(state.job.id)}`, {method: 'DELETE'});
      state.busy = false;
      $('delete-dialog').close();
      reset();
      notice('Review deleted. Its original, preview, export and report were removed from this workspace.');
    } catch (error) {
      state.busy = false;
      $('delete-dialog').close();
      notice(error.message);
      pollJob(state.generation);
    }
  });
  $('original-video').addEventListener('timeupdate', () => {
    renderOverlay();
    if (state.compare && Math.abs($('result-video').currentTime - currentTime()) > 0.15) $('result-video').currentTime = currentTime();
  });
  $('original-video').addEventListener('play', () => { if (state.compare) $('result-video').play().catch(() => {}); });
  $('original-video').addEventListener('pause', () => { if (state.compare) $('result-video').pause(); });
  $('original-video').addEventListener('seeked', () => { renderOverlay(); if (state.compare) $('result-video').currentTime = currentTime(); });
  ['original-video', 'original-image', 'result-video', 'result-image'].forEach(id => $(id).addEventListener('error', () => {
    if ($(id).getAttribute('src')) notice('The browser could not display this media. Your file may use an unsupported codec. The report and download remain available when export succeeds.');
  }));

  async function initialize() {
    setSubmissionBusy(false);
    let credential = new URLSearchParams(window.location.hash.slice(1)).get('bootstrap');
    if (window.location.hash) window.history.replaceState(null, '', window.location.pathname + window.location.search);
    try {
      if (credential) await post('/api/session', {credential});
      else await request('/api/session');
      credential = null;
      state.authenticated = true;
      setSubmissionBusy(false);
    } catch (error) {
      credential = null;
      $('backend-label').textContent = 'Local session required';
      $('sample-select').options[0].textContent = 'Open from the start script';
      $('sample-description').textContent = 'The start script opens an authorized local session automatically.';
      notice('Open DemoSafe using scripts/start.ps1 to create a private local session. No account or password is needed.');
      return;
    }
    const results = await Promise.allSettled([request('/api/health'), request('/api/samples')]);
    const [health, catalog] = results;
    if (health.status === 'fulfilled') {
      const data = health.value;
      $('backend-label').textContent = `${data.backend || 'CPU'} · local engine`;
      $('backend-label').title = data.model || '';
      $('hardware-status').textContent = data.hardware_verified ? `${data.backend} · hardware verified` : 'CPU baseline · UGen300 not connected';
    } else { $('backend-label').textContent = 'Local engine unavailable'; notice(health.reason.message); }
    if (catalog.status === 'fulfilled') {
      const all = catalog.value.samples || [];
      const demos = all.filter(sample => /^demo[_-]/.test(String(sample.id)));
      state.samples = demos.length ? demos : all.filter(sample => !/heldout|benchmark|^dev[_-]/i.test(String(sample.id)));
      $('sample-select').replaceChildren();
      state.samples.forEach(sample => {
        const option = document.createElement('option'); option.value = sample.id; option.textContent = sample.name; $('sample-select').append(option);
      });
      if (state.samples.length) {
        $('sample-select').disabled = false; $('load-sample').disabled = false;
        $('sample-description').textContent = state.samples[0].description || 'Generated fictional data for demonstration.';
      } else {
        const option = document.createElement('option'); option.textContent = 'No samples available'; $('sample-select').append(option);
        $('sample-description').textContent = 'Choose a file from your computer to get started.';
      }
    } else {
      $('sample-select').options[0].textContent = 'Samples unavailable';
      $('sample-description').textContent = 'You can still choose a file from your computer.';
    }
  }
  initialize();
})();
