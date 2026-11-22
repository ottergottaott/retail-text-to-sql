/* Same-origin library. WebUI owns the session; retail credentials stay server-side. */
(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  const state = {reports: [], selected: null, html: null, loading: false, request: null, reportUrl: null};
  const frame = byId('report-frame');
  const status = message => { byId('status').textContent = message; };
  async function api(path, signal) {
    const token = localStorage.getItem('token');
    if (!token) throw new Error('Sign in to Open WebUI, then return to Reports.');
    const response = await fetch('/api/retail-reports' + path, {
      headers: {Authorization: 'Bearer ' + token}, cache: 'no-store', signal
    });
    if (!response.ok) {
      if (response.status === 401) throw new Error('Your session expired. Sign in to Open WebUI again.');
      if ([403,404].includes(response.status)) throw new Error('This report is no longer accessible to your account.');
      throw new Error('The report service is unavailable. Please try Refresh.');
    }
    return response;
  }
  function clearViewer(message = 'Select a report') {
    state.html = null;
    frame.hidden = true; frame.removeAttribute('src');
    if (state.reportUrl) URL.revokeObjectURL(state.reportUrl);
    state.reportUrl = null;
    byId('viewer-title').textContent = message;
    byId('viewer-empty').hidden = false;
    byId('download').disabled = byId('open-tab').disabled = true;
  }
  function render() {
    const term = byId('search').value.trim().toLocaleLowerCase();
    const found = state.reports.filter(r => (r.title + ' ' + r.id).toLocaleLowerCase().includes(term));
    byId('count').textContent = term ? found.length + ' of ' + state.reports.length + ' reports' : state.reports.length + ' saved reports';
    byId('reports').replaceChildren();
    for (const report of found) {
      const button = document.createElement('button');
      button.className = 'report' + (state.selected === report.id ? ' selected' : '');
      button.setAttribute('aria-pressed', String(state.selected === report.id));
      const title = document.createElement('span'); title.className = 'report-title'; title.textContent = report.title;
      const date = document.createElement('span'); date.className = 'report-date';
      date.textContent = typeof report.created === 'number' ? new Date(report.created * 1000).toLocaleString(undefined, {dateStyle:'medium',timeStyle:'short'}) : 'Date unavailable';
      const id = document.createElement('span'); id.className = 'report-id'; id.textContent = report.id;
      button.append(title, date, id); button.addEventListener('click', () => open(report.id));
      byId('reports').append(button);
    }
    if (!state.loading) status(!state.reports.length ? 'No saved reports yet. Create an analysis and ask to save it.' : !found.length ? 'No matching reports.' : '');
  }
  async function open(id) {
    if (!/^rep_[A-Za-z0-9]+$/.test(id)) return;
    state.request?.abort();
    const controller = new AbortController(); state.request = controller;
    const report = state.reports.find(r => r.id === id);
    state.selected = id; clearViewer('Loading report…'); render();
    try {
      const response = await api('/' + encodeURIComponent(id) + '/html', controller.signal);
      const html = await response.text();
      if (controller.signal.aborted) return;
      // srcdoc inherits the library's base URL: #evidence would load the
      // library inside this sandbox. A Blob gives the report its own URL.
      state.html = html;
      state.reportUrl = URL.createObjectURL(new Blob([html], {type:'text/html'}));
      frame.src = state.reportUrl; frame.hidden = false;
      byId('viewer-empty').hidden = true;
      byId('viewer-title').textContent = report?.title || 'Saved report';
      byId('download').disabled = byId('open-tab').disabled = false;
      history.replaceState(null, '', '#' + id);
    } catch (error) {
      if (error.name === 'AbortError') return;
      clearViewer('Report unavailable'); status(error.message);
    }
  }
  async function refresh() {
    state.request?.abort(); state.request = null;
    clearViewer();
    state.loading = true; byId('refresh').disabled = true; status('Loading your reports…');
    try {
      const response = await api(''); const reports = await response.json();
      if (!Array.isArray(reports) || !reports.every(r => typeof r.id === 'string' && /^rep_[A-Za-z0-9]+$/.test(r.id) && typeof r.title === 'string')) throw new Error('Invalid report list. Please try Refresh.');
      state.reports = reports.sort((a,b) => (b.created || 0) - (a.created || 0));
      state.loading = false; render();
      byId('updated').textContent = 'Updated ' + new Date().toLocaleTimeString() + ' · Access checked on every open';
      const selected = state.selected || location.hash.slice(1);
      if (selected && state.reports.some(r => r.id === selected)) await open(selected);
      else { state.selected = null; history.replaceState(null, '', location.pathname); }
    } catch (error) {
      state.reports = []; byId('reports').replaceChildren(); byId('count').textContent = 'Unavailable';
      status(error.message || 'Unable to load reports.');
    } finally { state.loading = false; byId('refresh').disabled = false; }
  }
  byId('search').addEventListener('input', render);
  window.addEventListener('pagehide', () => {
    if (state.reportUrl) URL.revokeObjectURL(state.reportUrl);
  });
  byId('refresh').addEventListener('click', refresh);
  byId('download').addEventListener('click', () => {
    if (!state.html) return;
    const url = URL.createObjectURL(new Blob([state.html], {type:'text/html'}));
    const a = document.createElement('a'); a.href = url; a.download = state.selected + '.html'; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  });
  byId('open-tab').addEventListener('click', () => {
    if (state.selected) window.open('/static/retail-reports.html#' + state.selected, '_blank', 'noopener');
  });
  refresh();
})();
