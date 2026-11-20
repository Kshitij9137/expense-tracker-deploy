/* Expense Tracker dashboard.
 * Security notes: all data is inserted with textContent / createTextNode (never parsed as HTML),
 * so stored text cannot run as markup. The API key lives in sessionStorage (cleared when the
 * tab closes) and is sent only in the X-API-Key header to the same origin. */
(function () {
  'use strict';

  var PAGE_SIZE = 10;
  var KEY_NAME = 'et_api_key';
  var state = { key: '', tab: 'dashboard', offset: 0, total: 0, editId: null };
  /* Request counters: a response is drawn only if no newer request for the same view was started,
   * so a slow, older response can never overwrite a newer one (and nothing is drawn after sign-out). */
  var seq = { dashboard: 0, expenses: 0, budgets: 0 };

  function $(id) { return document.getElementById(id); }

  /* ---------- small DOM helpers (text only, no HTML parsing) ---------- */
  function el(tag, props) {
    var node = document.createElement(tag);
    props = props || {};
    Object.keys(props).forEach(function (k) { node[k] = props[k]; });
    for (var i = 2; i < arguments.length; i++) {
      var child = arguments[i];
      if (child === null || child === undefined) { continue; }
      node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
    }
    return node;
  }
  function clear(node) { while (node.firstChild) { node.removeChild(node.firstChild); } }
  function svg(tag, attrs) {
    var node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.keys(attrs || {}).forEach(function (k) { node.setAttribute(k, String(attrs[k])); });
    return node;
  }
  function money(text) {
    var n = Number(text);
    return isFinite(n) ? n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : String(text);
  }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function today() { var d = new Date(); return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function selectedMonth() { return $('month').value || today().slice(0, 7); }
  function monthRange(ym) {
    var parts = ym.split('-'), y = Number(parts[0]), m = Number(parts[1]);
    return { start: ym + '-01', end: ym + '-' + pad(new Date(y, m, 0).getDate()) };
  }

  var statusTimer = null;
  function say(message, isError) {
    var box = $('status');
    box.textContent = message;
    box.className = 'status' + (isError ? ' error' : '');
    clearTimeout(statusTimer);
    if (message) { statusTimer = setTimeout(function () { box.textContent = ''; box.className = 'status'; }, isError ? 8000 : 3500); }
  }

  /* ---------- API ---------- */
  function api(path, options) {
    options = options || {};
    var headers = { 'X-API-Key': state.key };
    if (options.body !== undefined) { headers['Content-Type'] = 'application/json'; }
    return fetch(path, { method: options.method || 'GET', headers: headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body) })
      .then(function (res) {
        if (res.status === 204) { return null; }
        var type = res.headers.get('Content-Type') || '';
        var read = type.indexOf('json') !== -1 ? res.json() : res.text();
        return read.then(function (data) {
          if (res.ok) { return data; }
          if (res.status === 401 && state.key) { logout('Your API key was rejected. Please sign in again.'); }
          var err = new Error((data && data.error) || 'Request failed (' + res.status + ')');
          err.status = res.status;
          throw err;
        });
      });
  }
  function fail(err) { if (err.status !== 401) { say(err.message, true); } }
  function query(params) {
    var parts = [];
    Object.keys(params).forEach(function (k) {
      if (params[k] !== '' && params[k] !== null && params[k] !== undefined) {
        parts.push(encodeURIComponent(k) + '=' + encodeURIComponent(params[k]));
      }
    });
    return parts.length ? '?' + parts.join('&') : '';
  }

  /* ---------- session ---------- */
  function showApp(on) {
    $('login').hidden = on; $('app').hidden = !on; $('session-actions').hidden = !on;
  }
  function login() {
    var key = $('apikey').value.trim();
    if (!key) { say('Enter your API key.', true); return; }
    state.key = key;
    api('/api/summary').then(function () {
      try { sessionStorage.setItem(KEY_NAME, key); } catch (e) { /* storage may be blocked */ }
      $('apikey').value = '';
      showApp(true); say('Signed in.'); refresh();
    }).catch(function (err) {
      state.key = '';
      say(err.status === 401 ? 'That API key is not valid.' : err.message, true);
    });
  }
  function logout(message) {
    state.key = '';
    seq.dashboard++; seq.expenses++; seq.budgets++;
    try { sessionStorage.removeItem(KEY_NAME); } catch (e) { /* ignore */ }
    showApp(false);
    clear($('expense-rows')); clear($('insight-cards')); clear($('budget-list'));
    say(typeof message === 'string' ? message : 'Signed out.', typeof message === 'string');
  }

  /* ---------- tabs ---------- */
  function setTab(name) {
    state.tab = name;
    ['dashboard', 'expenses', 'budgets'].forEach(function (t) { $('tab-' + t).hidden = t !== name; });
    Array.prototype.forEach.call(document.querySelectorAll('.tab'), function (b) {
      var active = b.getAttribute('data-tab') === name;
      b.classList.toggle('active', active);
      if (active) { b.setAttribute('aria-current', 'page'); } else { b.removeAttribute('aria-current'); }
    });
    refresh();
  }
  function refresh() {
    if (state.tab === 'dashboard') { loadDashboard(); }
    else if (state.tab === 'expenses') { loadExpenses(); }
    else { loadBudgets(); }
  }

  /* ---------- dashboard ---------- */
  function stat(label, value, sub, cls) {
    return el('div', { className: 'stat' }, el('div', { className: 'label' }, label),
      el('div', { className: 'value ' + (cls || '') }, value), el('div', { className: 'sub' }, sub || '\u00a0'));
  }
  function loadDashboard() {
    var ym = selectedMonth(), range = monthRange(ym), year = ym.slice(0, 4), n = ++seq.dashboard;
    Promise.all([
      api('/api/insights' + query({ month: ym })),
      api('/api/monthly' + query({ year: year })),
      api('/api/summary' + query(range))
    ]).then(function (r) {
      if (n !== seq.dashboard) { return; }
      renderInsights(r[0]); renderChart(r[1], ym); renderCategories(r[2]);
    }).catch(function (err) { if (n === seq.dashboard) { fail(err); } });
  }
  function renderInsights(i) {
    var box = $('insight-cards'); clear(box);
    var change = i.change_percent, sub = 'vs ' + money(i.previous_total) + ' last month', cls = '', label = 'No earlier data';
    if (change !== null) { label = (change > 0 ? '+' : '') + change + '% ' + sub; cls = change > 0 ? 'up' : (change < 0 ? 'down' : ''); }
    box.appendChild(stat('Spent in ' + i.month, money(i.total), i.expense_count + (i.expense_count === 1 ? ' expense' : ' expenses')));
    box.appendChild(el('div', { className: 'stat' }, el('div', { className: 'label' }, 'Change'),
      el('div', { className: 'value ' + cls }, change === null ? '\u2013' : (change > 0 ? '+' : '') + change + '%'),
      el('div', { className: 'sub' }, change === null ? label : sub)));
    box.appendChild(stat('Top category', i.top_category ? i.top_category.category : '\u2013',
      i.top_category ? money(i.top_category.total) : 'No spending yet'));
    box.appendChild(stat('Daily average', money(i.daily_average), 'over the whole month'));
    box.appendChild(stat('Largest expense', i.largest_expense ? money(i.largest_expense.amount) : '\u2013',
      i.largest_expense ? i.largest_expense.category + ' \u00b7 ' + i.largest_expense.date : 'None'));
  }
  function renderChart(data, ym) {
    $('chart-year').textContent = data.year + ' \u00b7 total ' + money(data.total);
    var box = $('monthly-chart'); clear(box);
    var W = 560, H = 200, left = 6, base = H - 24, innerH = base - 18, slot = (W - left * 2) / 12;
    var values = data.months.map(function (m) { return Number(m.total); });
    var max = Math.max.apply(null, values.concat([1]));
    var chart = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', width: '100%',
      'aria-label': 'Bar chart of spending per month in ' + data.year });
    var letters = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    data.months.forEach(function (m, idx) {
      var h = Math.round(values[idx] / max * innerH), x = left + idx * slot + 4;
      var bar = svg('rect', { x: x, y: base - h, width: slot - 8, height: h, rx: 3,
        'class': 'bar' + (m.month === ym ? ' selected' : '') });
      bar.appendChild(svg('title')).textContent = letters[idx] + ': ' + money(m.total);
      chart.appendChild(bar);
      var t = svg('text', { x: x + (slot - 8) / 2, y: H - 8, 'text-anchor': 'middle' });
      t.textContent = letters[idx]; chart.appendChild(t);
    });
    box.appendChild(chart);
  }
  function renderCategories(s) {
    var box = $('category-list'); clear(box);
    var names = Object.keys(s.categories);
    if (!names.length) { box.appendChild(el('div', { className: 'empty' }, 'No spending in this month.')); return; }
    var max = Math.max.apply(null, names.map(function (n) { return Number(s.categories[n]); }));
    names.forEach(function (name) {
      var meter = el('meter', { min: 0, max: max, value: Number(s.categories[name]) });
      meter.setAttribute('aria-label', name + ' ' + money(s.categories[name]));
      box.appendChild(el('div', { className: 'bar-row' }, el('span', { className: 'name', title: name }, name), meter,
        el('span', { className: 'amount' }, money(s.categories[name]))));
    });
  }

  /* ---------- expenses ---------- */
  function filters() { return { category: $('q-category').value.trim(), start: $('q-start').value, end: $('q-end').value }; }
  function loadExpenses() {
    var q = filters(), n = ++seq.expenses; q.limit = PAGE_SIZE; q.offset = state.offset;
    api('/api/expenses' + query(q)).then(function (data) {
      if (n !== seq.expenses) { return; }
      state.total = data.total; renderExpenses(data);
    }).catch(function (err) { if (n === seq.expenses) { fail(err); } });
  }
  function renderExpenses(data) {
    var body = $('expense-rows'); clear(body);
    if (!data.expenses.length) {
      body.appendChild(el('tr', {}, el('td', { colSpan: 5, className: 'empty' }, 'No expenses found.')));
    }
    data.expenses.forEach(function (e) {
      var edit = el('button', { type: 'button', className: 'secondary', textContent: 'Edit' });
      edit.setAttribute('aria-label', 'Edit expense ' + e.id);
      edit.addEventListener('click', function () { startEdit(e); });
      var del = el('button', { type: 'button', className: 'danger', textContent: 'Delete' });
      del.setAttribute('aria-label', 'Delete expense ' + e.id);
      del.addEventListener('click', function () { removeExpense(e); });
      body.appendChild(el('tr', {}, el('td', {}, e.date), el('td', {}, e.category),
        el('td', { className: 'num' }, money(e.amount)), el('td', {}, e.description),
        el('td', {}, el('div', { className: 'row' }, edit, del))));
    });
    var first = data.total === 0 ? 0 : data.offset + 1, last = data.offset + data.count;
    $('page-info').textContent = 'Showing ' + first + '\u2013' + last + ' of ' + data.total;
    $('prev').disabled = data.offset === 0; $('next').disabled = last >= data.total;
  }
  function resetForm() {
    state.editId = null;
    $('f-amount').value = ''; $('f-category').value = ''; $('f-note').value = ''; $('f-date').value = today();
    $('form-title').textContent = 'Add expense'; $('save').textContent = 'Add expense'; $('cancel-edit').hidden = true;
  }
  function startEdit(e) {
    state.editId = e.id;
    $('f-amount').value = e.amount; $('f-category').value = e.category; $('f-date').value = e.date; $('f-note').value = e.description;
    $('form-title').textContent = 'Edit expense #' + e.id; $('save').textContent = 'Save changes'; $('cancel-edit').hidden = false;
    $('f-amount').focus();
  }
  function saveExpense() {
    var body = { amount: $('f-amount').value.trim(), category: $('f-category').value.trim(),
      date: $('f-date').value, note: $('f-note').value };
    var editing = state.editId !== null;
    api(editing ? '/api/expenses/' + state.editId : '/api/expenses', { method: editing ? 'PUT' : 'POST', body: body })
      .then(function () { say(editing ? 'Expense updated.' : 'Expense added.'); resetForm(); state.offset = 0; loadExpenses(); })
      .catch(fail);
  }
  function removeExpense(e) {
    if (!window.confirm('Delete the ' + e.category + ' expense of ' + money(e.amount) + ' on ' + e.date + '?')) { return; }
    api('/api/expenses/' + e.id, { method: 'DELETE' }).then(function () {
      say('Expense deleted.');
      if (state.offset > 0 && state.offset >= state.total - 1) { state.offset = Math.max(0, state.offset - PAGE_SIZE); }
      loadExpenses();
    }).catch(fail);
  }

  /* ---------- budgets ---------- */
  function loadBudgets() {
    var ym = selectedMonth(), n = ++seq.budgets;
    $('budget-month').textContent = ym;
    api('/api/budgets' + query({ month: ym })).then(function (data) {
      if (n !== seq.budgets) { return; }
      var box = $('budget-list'); clear(box);
      if (!data.budgets.length) { box.appendChild(el('div', { className: 'empty' }, 'No budgets yet. Set one above.')); return; }
      data.budgets.forEach(function (b) {
        var meter = el('meter', { min: 0, max: Math.max(Number(b.limit), Number(b.spent)), value: Number(b.spent) });
        meter.setAttribute('aria-label', b.category + ' budget used ' + b.percent + ' percent');
        var del = el('button', { type: 'button', className: 'danger', textContent: 'Remove' });
        del.setAttribute('aria-label', 'Remove budget ' + b.category);
        del.addEventListener('click', function () { removeBudget(b.category); });
        box.appendChild(el('div', { className: 'budget' + (b.over ? ' over' : '') },
          el('header', {}, el('strong', {}, b.category),
            el('span', {}, money(b.spent) + ' of ' + money(b.limit) + ' (' + b.percent + '%) ',
              b.over ? el('span', { className: 'badge' }, 'OVER BUDGET') : null)),
          meter, el('div', { className: 'row' }, del)));
      });
    }).catch(function (err) { if (n === seq.budgets) { fail(err); } });
  }
  function saveBudget() {
    var cat = $('b-category').value.trim();
    if (!cat) { say('Enter a category.', true); return; }
    api('/api/budgets/' + encodeURIComponent(cat), { method: 'PUT', body: { limit: $('b-limit').value.trim() } })
      .then(function () { say('Budget saved.'); $('b-category').value = ''; $('b-limit').value = ''; loadBudgets(); }).catch(fail);
  }
  function removeBudget(category) {
    if (!window.confirm('Remove the budget for ' + category + '?')) { return; }
    api('/api/budgets/' + encodeURIComponent(category), { method: 'DELETE' })
      .then(function () { say('Budget removed.'); loadBudgets(); }).catch(fail);
  }

  /* ---------- export ---------- */
  function exportCsv() {
    api('/api/export.csv').then(function (text) {
      var url = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
      var link = el('a', { href: url, download: 'expenses.csv' });
      document.body.appendChild(link); link.click(); document.body.removeChild(link);
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      say('CSV downloaded.');
    }).catch(fail);
  }

  /* ---------- start-up ---------- */
  function init() {
    $('month').value = today().slice(0, 7); $('f-date').value = today();
    $('signin').addEventListener('click', login);
    $('apikey').addEventListener('keydown', function (e) { if (e.key === 'Enter') { login(); } });
    $('logout').addEventListener('click', function () { logout(); });
    $('export').addEventListener('click', exportCsv);
    $('month').addEventListener('change', refresh);
    Array.prototype.forEach.call(document.querySelectorAll('.tab'), function (b) {
      b.addEventListener('click', function () { setTab(b.getAttribute('data-tab')); });
    });
    $('save').addEventListener('click', saveExpense);
    $('cancel-edit').addEventListener('click', resetForm);
    $('apply-filters').addEventListener('click', function () { state.offset = 0; loadExpenses(); });
    $('clear-filters').addEventListener('click', function () {
      $('q-category').value = ''; $('q-start').value = ''; $('q-end').value = ''; state.offset = 0; loadExpenses();
    });
    $('prev').addEventListener('click', function () { state.offset = Math.max(0, state.offset - PAGE_SIZE); loadExpenses(); });
    $('next').addEventListener('click', function () { state.offset += PAGE_SIZE; loadExpenses(); });
    $('save-budget').addEventListener('click', saveBudget);
    var saved = '';
    try { saved = sessionStorage.getItem(KEY_NAME) || ''; } catch (e) { saved = ''; }
    if (saved) { state.key = saved; showApp(true); refresh(); } else { showApp(false); }
  }
  init();
}());
