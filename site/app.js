const listEl = document.getElementById('list');
const qEl = document.getElementById('q');
let projects = [];

function render(items) {
  listEl.innerHTML = items.map(p => `
    <li class="card ${p.change_flag || 'no_change'}">
      <h2>${p.project_name}</h2>
      <p>${p.country} / ${p.scheme || ''}</p>
      <p>状態: ${p.status_auto || '要確認'} (${p.change_flag || 'no_change'})</p>
      <a href="${p.source_url || '#'}" target="_blank" rel="noopener">原文リンク</a>
    </li>
  `).join('');
}

function filter() {
  const q = qEl.value.trim().toLowerCase();
  render(projects.filter(p => `${p.project_name} ${p.country}`.toLowerCase().includes(q)));
}

qEl.addEventListener('input', filter);

fetch('data/projects.json')
  .then(r => r.json())
  .then(d => {
    projects = d.projects || [];
    render(projects);
  })
  .catch(() => {
    listEl.innerHTML = '<li>データ読込に失敗しました</li>';
  });
