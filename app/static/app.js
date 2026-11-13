const $ = (s, el=document) => el.querySelector(s);
const $$ = (s, el=document) => [...el.querySelectorAll(s)];

function previewSrc(asset) {
  if (!asset) return '';
  const p = asset.preview_path || '';
  if (!p) return '';
  const name = p.split('/').pop();
  return '/previews/' + encodeURIComponent(name);
}
function chip(status) {
  const s = (status || '').toLowerCase();
  const cls = /block|fail|reject/.test(s) ? 'block' : /warn/.test(s) ? 'warn' : /pass|approved|appeal/.test(s) ? 'pass' : 'info';
  return `<span class="chip ${cls}">${status || '-'}</span>`;
}
function fmtMs(ms) { return ms == null ? '-' : Number(ms).toFixed(1) + ' ms'; }
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

$$('.nav-btn').forEach(b => b.addEventListener('click', () => {
  $$('.nav-btn').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  const page = b.dataset.page;
  $$('main > section').forEach(s => s.classList.add('hidden'));
  $('#page-' + page).classList.remove('hidden');
  if (page === 'queue') loadQueue();
  if (page === 'templates') loadTemplates();
  if (page === 'cost') loadCost();
  if (page === 'eval') loadEval();
}));

function filters() {
  return {
    project_id: $('#s-project').value,
    asset_type: $('#s-type').value || null,
    format: $('#s-format').value || null,
    triangle_min: $('#s-tmin').value ? Number($('#s-tmin').value) : null,
    triangle_max: $('#s-tmax').value ? Number($('#s-tmax').value) : null,
    cross_project: $('#s-cross').value === '1',
  };
}

async function doSearch() {
  const q = $('#q').value.trim();
  if (!q) return;
  $('#s-warn').innerHTML = '';
  $('#s-grid').innerHTML = '检索中…';
  $('#s-detail').innerHTML = '';
  const f = filters();
  const params = new URLSearchParams({ q, project_id: f.project_id, top_k: 10, cross_project: f.cross_project });
  if (f.asset_type) params.set('asset_type', f.asset_type);
  if (f.format) params.set('format', f.format);
  if (f.triangle_min != null) params.set('triangle_min', f.triangle_min);
  if (f.triangle_max != null) params.set('triangle_max', f.triangle_max);
  const res = await fetch('/api/search?' + params).then(r => r.json());
  renderSearch(res);
}
$('#btn-search').addEventListener('click', doSearch);
$('#q').addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

$('#q-img').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const f = filters();
  const fd = new FormData();
  fd.append('file', file);
  fd.append('project_id', f.project_id);
  fd.append('cross_project', f.cross_project ? 'true' : 'false');
  if (f.asset_type) fd.append('asset_type', f.asset_type);
  if (f.format) fd.append('format', f.format);
  $('#s-grid').innerHTML = '以图搜图中…';
  const res = await fetch('/api/search/image', { method: 'POST', body: fd }).then(r => r.json());
  renderSearch(res);
});

function renderSearch(res) {
  const warns = (res.warnings || []);
  $('#s-warn').innerHTML = warns.map(w => `<div class="banner">${esc(w)}</div>`).join('');
  $('#s-meta').textContent = `模式 ${res.mode || ''} · 耗时 ${fmtMs(res.duration_ms)} · 语义${res.semantic_available ? '可用' : '不可用'} · ${ (res.results||[]).length } 条`;
  const grid = $('#s-grid');
  const items = res.results || [];
  if (!items.length) { grid.innerHTML = '<div class="sub">没有结果。</div>'; return; }
  grid.innerHTML = items.map((a, i) => `
    <div class="card" data-i="${i}">
      <img src="${previewSrc(a)}" alt="" onerror="this.style.opacity=.2" />
      <div class="body">
        <div class="name" title="${esc(a.canonical_name||a.original_filename)}">${esc(a.canonical_name || a.original_filename || a.asset_id)}</div>
        <div class="meta">
          <span>${esc(a.asset_type || '')} · ${esc(a.format || '')}</span>
          <span>${a.score != null ? Number(a.score).toFixed(3) : ''}</span>
        </div>
      </div>
    </div>`).join('');
  $$('.card', grid).forEach(c => c.addEventListener('click', () => showAsset(items[Number(c.dataset.i)])));
}

async function showAsset(a) {
  let full = a;
  if (a.id || a.asset_id) {
    try { full = await fetch('/api/assets/' + encodeURIComponent(a.id || a.asset_id)).then(r => r.json()); }
    catch (e) {}
  }
  const report = full.latest_report && (full.latest_report.report || full.latest_report);
  const items = (report && report.items) || [];
  $('#s-detail').innerHTML = `
    <div class="detail">
      <div>
        <img class="big" src="${previewSrc(full)}" onerror="this.style.opacity=.2" />
      </div>
      <div>
        <h3>${esc(full.canonical_name || '')}</h3>
        <div class="kv">
          <span>ID</span><b class="mono">${esc(full.id || full.asset_id)}</b>
          <span>项目</span><b>${esc(full.project_id)}</b>
          <span>类型</span><b>${esc(full.asset_type)}</b>
          <span>原文件名</span><b class="mono">${esc(full.original_filename)}</b>
          <span>面数</span><b>${full.triangles ?? '-'}</b>
          <span>许可</span><b>${esc(full.license)}</b>
          <span>来源</span><b>${esc(full.source)} ${esc(full.source_pack||'')}</b>
          <span>状态</span><b>${chip(full.status)}</b>
        </div>
        ${items.length ? renderReport(report) : '<p class="sub">无预检报告（可能为种子库较早记录）。</p>'}
      </div>
    </div>`;
}

function renderReport(report) {
  if (!report) return '';
  const items = report.items || [];
  const rows = items.map(it => `
    <div class="report-item">
      <div class="t">
        <strong>${esc(it.title)}</strong>
        <span>${chip(it.severity)} ${chip(it.status)}</span>
      </div>
      <div class="sub" style="margin:4px 0 0">
        ${esc(it.message || '')}
        ${it.measured != null ? ` · 实测 <span class="mono">${esc(typeof it.measured==='object'?JSON.stringify(it.measured):it.measured)}</span>` : ''}
        ${it.threshold != null ? ` · 阈值 <span class="mono">${esc(typeof it.threshold==='object'?JSON.stringify(it.threshold):it.threshold)}</span>` : ''}
        ${it.source ? ` · 来源 ${esc(it.source)}` : ''}
      </div>
    </div>`).join('');
  return `<p style="margin:14px 0 6px">预检总体 ${chip(report.overall)} · ${fmtMs(report.duration_ms)}</p>${rows}`;
}

$('#btn-ingest').addEventListener('click', async () => {
  const file = $('#i-file').files[0];
  if (!file) { $('#i-out').innerHTML = '<div class="banner err">请选择文件</div>'; return; }
  const fd = new FormData();
  fd.append('file', file);
  fd.append('project_id', $('#i-project').value);
  fd.append('asset_type', $('#i-type').value);
  const vlm = $('#i-vlm').value;
  if (vlm) fd.append('vlm_backend', vlm);
  if (vlm === 'disabled') fd.append('skip_vlm', 'true');
  $('#i-out').innerHTML = '<div class="banner">预检中，规则层不走模型…</div>';
  const res = await fetch('/api/ingest', { method: 'POST', body: fd }).then(r => r.json());
  const report = res.report || {};
  $('#i-out').innerHTML = `
    <div class="banner ok">已提交。状态 ${chip(res.status)}，总体 ${chip(report.overall)}。默认进入人工队列，不会自动入库。</div>
    <div class="detail">
      <div><img class="big" src="${previewSrc(res.asset||{})}" onerror="this.style.opacity=.2"/></div>
      <div>
        <div class="kv">
          <span>canonical</span><b class="mono">${esc(res.canonical_name)}</b>
          <span>asset_id</span><b class="mono">${esc(res.asset_id)}</b>
        </div>
        ${renderReport(report)}
      </div>
    </div>`;
});

async function loadQueue() {
  const pid = $('#q-project').value;
  const url = '/api/queue' + (pid ? ('?project_id=' + encodeURIComponent(pid)) : '');
  const res = await fetch(url).then(r => r.json());
  const items = res.items || [];
  if (!items.length) { $('#q-list').innerHTML = '<div class="sub">队列为空。从「入库预检」提交，或查看种子库是否已全部确认。</div>'; return; }
  $('#q-list').innerHTML = items.map(a => {
    const report = a.latest_report && (a.latest_report.report || a.latest_report);
    return `<div class="qitem" data-id="${esc(a.id)}">
      <img src="${previewSrc(a)}" onerror="this.style.opacity=.2"/>
      <div>
        <div><strong>${esc(a.canonical_name)}</strong> ${chip(report && report.overall || a.status)} ${chip(a.project_id)}</div>
        <div class="sub">${esc(a.original_filename)} · ${esc(a.asset_type)} · 面数 ${a.triangles ?? '-'}</div>
        ${report ? renderReport(report) : ''}
      </div>
      <div>
        <label>原因（必填）<textarea class="reason" placeholder="通过 / 退回 / 申诉的原因"></textarea></label>
        <div class="actions" style="margin-top:8px">
          <button class="btn pass" data-act="pass">通过</button>
          <button class="btn danger" data-act="reject">退回</button>
          <button class="btn warn" data-act="appeal_pass">申诉通过</button>
        </div>
        <div class="rev-msg sub"></div>
      </div>
    </div>`;
  }).join('');
  $$('.qitem').forEach(el => {
    $$('[data-act]', el).forEach(btn => btn.addEventListener('click', async () => {
      const reason = $('.reason', el).value;
      const msg = $('.rev-msg', el);
      if (!reason.trim()) { msg.textContent = '原因必填。'; return; }
      const r = await fetch('/api/queue/' + encodeURIComponent(el.dataset.id) + '/review', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ action: btn.dataset.act, reason, reviewer: 'TA' })
      });
      const data = await r.json();
      if (!r.ok) { msg.textContent = data.detail || JSON.stringify(data); return; }
      msg.textContent = '已记录：' + data.new_status;
      setTimeout(loadQueue, 400);
    }));
  });
}
$('#btn-refresh-q').addEventListener('click', loadQueue);
$('#q-project').addEventListener('change', loadQueue);

async function loadTemplates() {
  const res = await fetch('/api/templates').then(r => r.json());
  $('#tmpl-box').innerHTML = (res.projects || []).map(t => `
    <div class="box">
      <h3>${esc(t.name)} <small class="chip">${esc(t.project_id)}</small></h3>
      <p class="sub">${esc(t.description || '')}</p>
      <div class="kv">
        <span>风格</span><b>${esc(t.style)}</b>
        <span>命名示例</span><b class="mono">${esc(t.naming && t.naming.example)}</b>
        <span>允许格式</span><b>${esc((t.allowed_formats||[]).join(', '))}</b>
        <span>体积上限</span><b>${t.max_file_size_mb} MB</b>
        <span>贴图最长边</span><b>${t.texture && t.texture.max_side}</b>
        <span>必选通道</span><b>${esc((t.texture && (t.texture.required_channels||[]).join(', ')) || '（无）')}</b>
        <span>面数预算 LOD0</span><b class="mono">${esc(JSON.stringify((t.poly_budget)||{}))}</b>
      </div>
      <h4 style="margin:14px 0 6px">检查项级别</h4>
      <table><thead><tr><th>检查</th><th>级别</th></tr></thead>
      <tbody>${Object.entries(t.checks||{}).map(([k,v])=>`<tr><td class="mono">${esc(k)}</td><td>${chip(v)}</td></tr>`).join('')}</tbody></table>
    </div>`).join('');
}

async function loadCost() {
  const res = await fetch('/api/cost').then(r => r.json());
  const rows = res.by_kind || [];
  $('#cost-out').innerHTML = `
    <div class="banner">${esc(res.note || '')}</div>
    <table>
      <thead><tr><th>类型</th><th>次数</th><th>成功</th><th>总耗时</th><th>平均耗时</th><th>估计费用（元，假设）</th></tr></thead>
      <tbody>${rows.length ? rows.map(r => `<tr>
        <td class="mono">${esc(r.kind)}</td><td>${r.n}</td><td>${r.n_ok}</td>
        <td>${fmtMs(r.total_ms)}</td><td>${fmtMs(r.avg_ms)}</td>
        <td>${r.total_cny != null ? Number(r.total_cny).toFixed(4) : '0'}</td>
      </tr>`).join('') : '<tr><td colspan="6">暂无记录。先构建库或跑一次检索。</td></tr>'}</tbody>
    </table>`;
}

async function loadEval() {
  const res = await fetch('/api/eval').then(r => r.json());
  $('#eval-out').textContent = res.text || '无';
}
