const result = document.querySelector('#result');
const busy = document.querySelector('#busy');
const status = document.querySelector('#status');

function show(data) {
  result.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
}

function setBusy(value) {
  busy.hidden = !value;
  document.querySelectorAll('.primary').forEach((button) => { button.disabled = value; });
}

async function api(path, options = {}) {
  setBusy(true);
  try {
    const response = await fetch(path, options);
    if (response.status === 204) return null;
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
    return payload;
  } finally {
    setBusy(false);
  }
}

document.querySelectorAll('.tab').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.tab, .panel').forEach((node) => node.classList.remove('active'));
    button.classList.add('active');
    document.querySelector(`#${button.dataset.panel}`).classList.add('active');
    if (button.dataset.panel === 'history-panel') loadHistory();
  });
});

document.querySelector('#text-submit').addEventListener('click', async () => {
  try {
    show(await api('/analyze_text', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: document.querySelector('#text-input').value, company_name: document.querySelector('#text-company').value || null})
    }));
  } catch (error) { show(`Ошибка: ${error.message}`); }
});

document.querySelector('#image-submit').addEventListener('click', async () => {
  const file = document.querySelector('#image-input').files[0];
  if (!file) return show('Выберите изображение.');
  const form = new FormData();
  form.append('file', file);
  form.append('company_name', document.querySelector('#image-company').value);
  try { show(await api('/analyze_image', {method: 'POST', body: form})); }
  catch (error) { show(`Ошибка: ${error.message}`); }
});

document.querySelector('#parse-submit').addEventListener('click', async () => {
  try {
    show(await api('/parse_demo', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({competitor: document.querySelector('#competitor-select').value})
    }));
  } catch (error) { show(`Ошибка: ${error.message}`); }
});

async function loadHistory() {
  const container = document.querySelector('#history-list');
  try {
    const data = await api('/history');
    container.replaceChildren(...data.items.slice().reverse().map((item) => {
      const card = document.createElement('div');
      card.className = 'history-item';
      const title = document.createElement('strong');
      title.textContent = `${item.request_type}: ${item.request_summary}`;
      const time = document.createElement('small');
      time.textContent = new Date(item.timestamp).toLocaleString('ru-RU');
      card.append(title, document.createElement('br'), time);
      card.addEventListener('click', () => show(item.response));
      return card;
    }));
    if (!data.items.length) container.textContent = 'История пуста.';
  } catch (error) { container.textContent = `Ошибка: ${error.message}`; }
}

document.querySelector('#history-clear').addEventListener('click', async () => {
  if (!window.confirm('Очистить историю?')) return;
  try { await api('/history', {method: 'DELETE'}); await loadHistory(); }
  catch (error) { show(`Ошибка: ${error.message}`); }
});

api('/health').then((data) => {
  status.textContent = data.api_configured ? 'API готов' : 'Нужен ключ в .env';
  status.className = `status ${data.api_configured ? 'ok' : 'warn'}`;
}).catch(() => { status.textContent = 'Backend недоступен'; });

