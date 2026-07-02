const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  tg.setHeaderColor('#f2f2f7');
  tg.setBackgroundColor('#f2f2f7');
}

const API = '';
let initData = tg?.initData || '';
let amount = '0';
let txType = 'expense';
let selectedCategory = '';
let categories = [];

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-Init-Data': initData,
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2000);
}

function formatAmount(n) {
  return Math.round(n).toLocaleString('uk-UA') + ' ₴';
}

function updateDisplay() {
  const n = parseInt(amount, 10) || 0;
  $('#amountDisplay').textContent = formatAmount(n);
}

function buildKeypad() {
  const keys = ['1','2','3','4','5','6','7','8','9','00','0','⌫'];
  const grid = $('#keypad');
  grid.innerHTML = '';
  keys.forEach((k, i) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'key' + (k === '00' ? ' wide' : '');
    btn.textContent = k;
    btn.addEventListener('click', () => {
      if (k === '⌫') {
        amount = amount.length <= 1 ? '0' : amount.slice(0, -1);
      } else if (k === '00') {
        if (amount === '0') return;
        amount += '00';
      } else {
        amount = amount === '0' ? k : amount + k;
      }
      if (amount.length > 8) amount = amount.slice(0, 8);
      updateDisplay();
    });
    grid.appendChild(btn);
  });
}

function renderCategories() {
  const grid = $('#categoryGrid');
  grid.innerHTML = '';
  categories.forEach((c) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'cat-btn' + (selectedCategory === c.name ? ' selected' : '');
    btn.innerHTML = `<span class="cat-icon">${c.icon}</span><span class="cat-name">${c.name}</span>`;
    btn.addEventListener('click', () => {
      selectedCategory = c.name;
      renderCategories();
    });
    grid.appendChild(btn);
  });
}

async function loadSummary() {
  const data = await api('/api/summary');
  $('#monthTitle').textContent = data.month;
  $('#balanceVal').textContent = data.formatted.balance;
  $('#incomeVal').textContent = data.formatted.income;
  $('#expenseVal').textContent = data.formatted.expense;
  $('#dailyVal').textContent = data.formatted.daily;
}

async function loadEvents() {
  const { events } = await api('/api/events');
  const list = $('#eventsList');
  if (!events.length) {
    list.innerHTML = '<div class="empty">Немає операцій цього місяця</div>';
    return;
  }
  const icons = { income: '💚', expense: '📦', 'Транспорт': '🚌', 'Їжа': '🍔' };
  list.innerHTML = events.slice(0, 30).map((e) => {
    const icon = e.type === 'income' ? '💚' : (icons[e.category] || '📦');
    const sign = e.type === 'income' ? '+' : '−';
    return `<div class="event-item">
      <div class="event-icon ${e.type}">${icon}</div>
      <div class="event-info">
        <div class="event-title">${e.description || e.category || 'Операція'}${e.auto ? ' 🤖' : ''}</div>
        <div class="event-date">${e.formatted_date}</div>
      </div>
      <div class="event-amount ${e.type}">${sign}${e.formatted_amount.replace(' ₴','')}</div>
    </div>`;
  }).join('');
}

async function loadSettings() {
  const data = await api('/api/settings');
  categories = data.categories;
  const s = data.settings;
  $('#settingsList').innerHTML = `
    <div class="setting-item"><span class="setting-label">Аванс</span><span class="setting-value">${formatAmount(s.advance_amount)} · ${s.advance_day}-е</span></div>
    <div class="setting-item"><span class="setting-label">Зарплата</span><span class="setting-value">${formatAmount(s.salary_amount)} · ${s.salary_day}-е</span></div>
    <div class="setting-item"><span class="setting-label">Дорога (1 бік)</span><span class="setting-value">${formatAmount(s.transport_one_way)}</span></div>
    <div class="setting-item"><span class="setting-label">Поїздок/день</span><span class="setting-value">${s.transport_trips_per_day}</span></div>
    <div class="setting-item"><span class="setting-label">Автотранспорт</span><span class="setting-value">${s.transport_auto_enabled ? 'Увімкнено' : 'Вимкнено'}</span></div>
  `;
  renderCategories();
}

async function saveTransaction() {
  const val = parseInt(amount, 10) || 0;
  if (val <= 0) return toast('Введи суму');
  if (txType === 'expense' && !selectedCategory) return toast('Обери категорію');

  try {
    if (txType === 'expense') {
      await api('/api/expense', {
        method: 'POST',
        body: JSON.stringify({
          amount: val,
          category: selectedCategory,
          recurring: $('#recurringCheck').checked,
        }),
      });
      toast(`−${formatAmount(val)}`);
    } else {
      await api('/api/income', {
        method: 'POST',
        body: JSON.stringify({ amount: val }),
      });
      toast(`+${formatAmount(val)}`);
    }
    amount = '0';
    updateDisplay();
    if (tg) tg.HapticFeedback?.notificationOccurred('success');
    showTab('home');
    await refresh();
  } catch {
    toast('Помилка збереження');
  }
}

async function refresh() {
  await Promise.all([loadSummary(), loadEvents()]);
}

function showTab(tab) {
  $$('.screen').forEach((s) => s.classList.remove('active'));
  $$('.tab').forEach((t) => t.classList.remove('active'));
  $(`#screen-${tab}`).classList.add('active');
  document.querySelector(`[data-tab="${tab}"]`)?.classList.add('active');
  if (tab === 'settings') loadSettings();
}

$$('.tab').forEach((tab) => {
  tab.addEventListener('click', () => showTab(tab.dataset.tab));
});

$$('.seg').forEach((seg) => {
  seg.addEventListener('click', () => {
    $$('.seg').forEach((s) => s.classList.remove('active'));
    seg.classList.add('active');
    txType = seg.dataset.type;
    $('#recurringRow').style.display = txType === 'expense' ? 'flex' : 'none';
    $('#categoryGrid').parentElement.style.display = txType === 'expense' ? 'block' : 'none';
  });
});

$('#saveBtn').addEventListener('click', saveTransaction);

$('#monthPrev').addEventListener('click', async () => {
  await api('/api/month', { method: 'POST', body: JSON.stringify({ delta: -1 }) });
  await refresh();
  const s = await api('/api/summary');
  $('#monthTitle').textContent = s.month;
});

$('#monthNext').addEventListener('click', async () => {
  await api('/api/month', { method: 'POST', body: JSON.stringify({ delta: 1 }) });
  await refresh();
  const s = await api('/api/summary');
  $('#monthTitle').textContent = s.month;
});

buildKeypad();
updateDisplay();
loadSettings().then(refresh);
