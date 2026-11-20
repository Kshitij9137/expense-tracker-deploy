/* End-to-end check of the dashboard: loads the real page from a running server in jsdom and
 * drives it like a user. Usage:  BASE=http://127.0.0.1:8003 KEY=<api key> node ui_check.js
 * (install once with: cd tools/ui && npm install) */
const { JSDOM } = require('jsdom');
const BASE = process.env.BASE || 'http://127.0.0.1:8003';
const KEY = process.env.KEY;
if (!KEY) { console.error('Set KEY to the API key'); process.exit(2); }

let passed = 0, failed = 0;
function check(name, ok, detail) {
  if (ok) { passed++; console.log('[PASS] ' + name); }
  else { failed++; console.log('[FAIL] ' + name + (detail ? '  -> ' + detail : '')); }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitFor(fn, what, ms = 4000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { try { if (fn()) return true; } catch (e) { /* retry */ } await sleep(25); }
  return false;
}
async function seed(body) {
  const r = await fetch(BASE + '/api/expenses', { method: 'POST', headers: { 'X-API-Key': KEY, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (r.status !== 201) { throw new Error('seed failed ' + r.status + ' ' + (await r.text())); }
}

(async () => {
  // ---- seed data: 13 expenses incl. hostile text ----
  for (let i = 1; i <= 10; i++) { await seed({ amount: String(i * 10), category: 'food', date: '2026-10-' + String(i).padStart(2, '0'), note: 'meal ' + i }); }
  await seed({ amount: '500', category: 'rent', date: '2026-10-01', note: 'monthly rent' });
  await seed({ amount: '40', category: 'food', date: '2026-09-15', note: 'last month' });
  await seed({ amount: '7.77', category: '<b>evil</b>', date: '2026-10-20', note: '<img src=x onerror="window.__pwned=1">' });

  const dom = await JSDOM.fromURL(BASE + '/', {
    runScripts: 'dangerously', resources: 'usable', pretendToBeVisual: true,
    beforeParse(window) {
      window.fetch = (u, o) => fetch(new URL(u, BASE), o);
      window.confirm = () => true;
      window.URL.createObjectURL = () => 'blob:fake';
      window.URL.revokeObjectURL = () => {};
      window.HTMLAnchorElement.prototype.click = function () { window.__downloaded = this.download; };
    }
  });
  const w = dom.window, d = w.document, $ = (id) => d.getElementById(id);
  await waitFor(() => $('signin') && w.document.readyState === 'complete', 'load');
  const click = (id) => $(id).dispatchEvent(new w.Event('click', { bubbles: true }));
  const status = () => $('status').textContent;

  // ---- login ----
  check('login screen shown first, app hidden', !$('login').hidden && $('app').hidden);
  $('apikey').value = 'definitely-wrong-key'; click('signin');
  check('wrong key is rejected with a message', await waitFor(() => /not valid/i.test(status())) && !$('login').hidden, status());
  $('apikey').value = KEY; click('signin');
  check('correct key opens the app', await waitFor(() => !$('app').hidden && $('login').hidden));
  check('API key is cleared from the input field', $('apikey').value === '');
  check('key stored in sessionStorage only', w.sessionStorage.getItem('et_api_key') === KEY && !w.localStorage.getItem('et_api_key'));

  // ---- dashboard ----
  // change month immediately after sign-in while the first dashboard request is still in flight (race check)
  $('month').value = '2026-10'; $('month').dispatchEvent(new w.Event('change', { bubbles: true }));
  await sleep(300);
  check('dashboard shows 5 insight cards', await waitFor(() => d.querySelectorAll('#insight-cards .stat').length === 5));
  const cards = $('insight-cards').textContent;
  check('top category is rent', /Top category/.test(cards) && /rent/.test(cards), cards);
  check('chart has 12 bars and highlights October', d.querySelectorAll('#monthly-chart rect').length === 12 && d.querySelectorAll('#monthly-chart rect.selected').length === 1);
  check('category meters rendered for the month', d.querySelectorAll('#category-list meter').length >= 3);

  // ---- expenses list, pagination, XSS ----
  d.querySelector('[data-tab="expenses"]').dispatchEvent(new w.Event('click', { bubbles: true }));
  check('expenses tab shows 10 rows (page size)', await waitFor(() => d.querySelectorAll('#expense-rows tr').length === 10), String(d.querySelectorAll('#expense-rows tr').length));
  check('page info reports the total', /of 13$/.test($('page-info').textContent), $('page-info').textContent);
  check('Previous disabled on first page, Next enabled', $('prev').disabled && !$('next').disabled);
  const tableHtml = $('expense-rows').innerHTML;
  check('XSS: hostile note is shown as text, not parsed as an element', d.querySelectorAll('#expense-rows img, #expense-rows b').length === 0 && /<img src=x/.test($('expense-rows').textContent), tableHtml.slice(0, 120));
  check('XSS: injected onerror handler never ran', w.__pwned === undefined);
  click('next');
  check('page 2 shows the remaining 3 rows', await waitFor(() => d.querySelectorAll('#expense-rows tr').length === 3 && /11.13 of 13/.test($('page-info').textContent.replace('\u2013', '.'))));
  check('Next disabled on last page', $('next').disabled);
  // ---- filter ----
  click('prev'); await waitFor(() => d.querySelectorAll('#expense-rows tr').length === 10);
  $('q-category').value = 'rent'; click('apply-filters');
  check('category filter returns only rent', await waitFor(() => d.querySelectorAll('#expense-rows tr').length === 1 && /rent/.test($('expense-rows').textContent)));
  click('clear-filters'); await waitFor(() => d.querySelectorAll('#expense-rows tr').length === 10);

  // ---- add ----
  $('f-amount').value = '12.34'; $('f-category').value = 'Coffee'; $('f-date').value = '2026-10-25'; $('f-note').value = 'ui test'; click('save');
  check('adding an expense confirms and refreshes', await waitFor(() => /added/i.test(status())) && /of 14$/.test($('page-info').textContent), $('page-info').textContent);
  check('new expense appears first (newest date)', /coffee/.test($('expense-rows').firstChild.textContent));

  // ---- validation error shown ----
  $('f-amount').value = 'abc'; $('f-category').value = 'x'; click('save');
  check('invalid amount shows the server message', await waitFor(() => /Invalid amount/.test(status())) && $('status').classList.contains('error'), status());
  click('cancel-edit'); $('f-amount').value = ''; $('f-category').value = '';

  // ---- edit ----
  const editBtn = Array.from($('expense-rows').firstChild.querySelectorAll('button')).find((b) => b.textContent === 'Edit');
  editBtn.dispatchEvent(new w.Event('click', { bubbles: true }));
  check('edit mode fills the form', /Edit expense #/.test($('form-title').textContent) && $('f-amount').value === '12.34' && !$('cancel-edit').hidden);
  $('f-amount').value = '15.00'; click('save');
  check('saving an edit updates the row', await waitFor(() => /updated/i.test(status()) && /15\.00/.test($('expense-rows').firstChild.textContent)));
  check('form returns to add mode', $('form-title').textContent === 'Add expense' && $('cancel-edit').hidden);

  // ---- delete ----
  const delBtn = Array.from($('expense-rows').firstChild.querySelectorAll('button')).find((b) => b.textContent === 'Delete');
  delBtn.dispatchEvent(new w.Event('click', { bubbles: true }));
  check('deleting removes the expense', await waitFor(() => /deleted/i.test(status()) && /of 13$/.test($('page-info').textContent)));

  // ---- budgets ----
  d.querySelector('[data-tab="budgets"]').dispatchEvent(new w.Event('click', { bubbles: true }));
  $('b-category').value = 'food'; $('b-limit').value = '100'; click('save-budget');
  check('budget saved and listed with OVER BUDGET flag', await waitFor(() => /Budget saved/.test(status()) && d.querySelectorAll('#budget-list .budget.over').length === 1 && /OVER BUDGET/.test($('budget-list').textContent)), $('budget-list').textContent);
  $('b-category').value = 'rent'; $('b-limit').value = '900'; click('save-budget');
  check('second budget is within limit (no flag)', await waitFor(() => d.querySelectorAll('#budget-list .budget').length === 2 && d.querySelectorAll('#budget-list .budget.over').length === 1));
  Array.from(d.querySelectorAll('#budget-list button')).find((b) => /rent/.test(b.getAttribute('aria-label'))).dispatchEvent(new w.Event('click', { bubbles: true }));
  check('budget can be removed', await waitFor(() => d.querySelectorAll('#budget-list .budget').length === 1));

  // ---- export ----
  click('export');
  check('CSV export triggers a download named expenses.csv', await waitFor(() => w.__downloaded === 'expenses.csv'));

  // ---- logout ----
  click('logout');
  check('sign out returns to login, clears key and data', await waitFor(() => !$('login').hidden && $('app').hidden) && w.sessionStorage.getItem('et_api_key') === null && $('expense-rows').children.length === 0);

  console.log(`\nUI RESULT: ${passed} passed, ${failed} failed`);
  w.close();
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error('UI check crashed:', e); process.exit(2); });
