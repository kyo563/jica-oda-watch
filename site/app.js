const listEl = document.getElementById('list');
const qEl = document.getElementById('q');
let projects = [];

function render(items) {
  listEl.innerHTML = '';
  items.forEach((p) => {
    const li = document.createElement('li');
    li.className = `card ${p.change_flag || 'no_change'}`;

    const title = document.createElement('h2');
    title.textContent = p.project_name || '';
    li.appendChild(title);

    const meta = document.createElement('p');
    meta.textContent = `${p.country || ''} / ${p.scheme || ''}`;
    li.appendChild(meta);

    const status = document.createElement('p');
    status.textContent = `状態: ${p.status_auto || '要確認'} (${p.change_flag || 'no_change'})`;
    li.appendChild(status);

    if (isValidHttpUrl(p.source_url)) {
      const link = document.createElement('a');
      link.href = p.source_url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = '原文リンク';
      li.appendChild(link);
    }

    listEl.appendChild(li);
  });
}

function isValidHttpUrl(value) {
  if (!value) return false;
  try {
    const u = new URL(value);
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch {
    return false;
  }
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
    listEl.innerHTML = '';
    const li = document.createElement('li');
    li.textContent = 'データ読込に失敗しました';
    listEl.appendChild(li);
  });
