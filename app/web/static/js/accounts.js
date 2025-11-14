(function () {
  function parseMoney(value) {
    if (value === null || value === undefined) return null;
    let s = String(value).trim();
    if (!s) return null;
    s = s.replace(/[R$€£¥\s]/g, '');
    let negative = false;
    if (s.startsWith('(') && s.endsWith(')')) { negative = true; s = s.slice(1, -1); }
    if (s.startsWith('-')) { negative = true; s = s.slice(1); }
    const commaCount = (s.match(/,/g) || []).length;
    const dotCount = (s.match(/\./g) || []).length;
    if (commaCount && dotCount) {
      if (s.lastIndexOf(',') > s.lastIndexOf('.')) { s = s.replace(/\./g, ''); s = s.replace(/,/g, '.'); }
      else { s = s.replace(/,/g, ''); }
    } else if (commaCount === 1 && dotCount === 0) { s = s.replace(/,/g, '.'); }
    else { s = s.replace(/,/g, ''); }
    s = s.replace(/[^0-9.]/g, '');
    if (!s) return null;
    const n = Number(s);
    if (Number.isNaN(n)) return null;
    return negative ? -n : n;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const form = e.currentTarget;
    const accountId = form.dataset.accountId;
    const submit = form.querySelector('button[type="submit"]');
    if (submit) { submit.disabled = true; }
    try {
      // client-side validation for balance
      const balanceInput = form.querySelector('input[name="balance"]');
      if (balanceInput) {
        const parsed = parseMoney(balanceInput.value);
        if (parsed === null) {
          const msg = (window.LURO_I18N && window.LURO_I18N.invalid_balance) || 'Invalid balance format';
          window.luroToast.show(msg, 'error');
          if (submit) submit.disabled = false;
          return;
        }
        // replace the form value with normalized number
        balanceInput.value = String(parsed.toFixed(2));
      }

      const res = await fetch(form.action, { method: 'POST', body: new FormData(form), credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || 'Save failed');
      }
      const json = await res.json();
      const row = document.querySelector(`[data-account-row="${json.id}"]`);
      if (row) {
        const nameEl = row.querySelector('.account-name');
        const balanceEl = row.querySelector('.account-balance');
        if (nameEl) nameEl.textContent = json.name;
        if (balanceEl) balanceEl.textContent = '$' + Number(json.balance).toFixed(2);
      }
      // close form
      const section = form.closest('section');
      if (section) { section.hidden = true; }
      window.luroToast.show((window.LURO_I18N && window.LURO_I18N.account_updated) || 'Account updated', 'success');
    } catch (err) {
      console.error('Account save failed', err);
      const prefix = (window.LURO_I18N && window.LURO_I18N.unable_save_account_prefix) || 'Unable to save account: ';
      window.luroToast.show(prefix + (err.message || err), 'error');
    } finally {
      if (submit) { submit.disabled = false; }
    }
  }

  function init() {
    document.querySelectorAll('form.account-edit-form-ajax').forEach((f) => {
      if (f.dataset.luroBound) return;
      f.addEventListener('submit', handleSubmit);
      f.dataset.luroBound = '1';
    });
    // bind delete buttons
    document.querySelectorAll('button[data-delete-account]').forEach((btn) => {
      if (btn.dataset.luroDeleteBound) return;
      btn.addEventListener('click', async function () {
        const id = btn.getAttribute('data-delete-account');
        if (!id) return;
        if (!confirm((window.LURO_I18N && window.LURO_I18N.confirm_delete_account) || 'Delete this account?')) return;
        try {
          const res = await fetch('/accounts/' + id + '/delete', { method: 'POST', credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
          if (!res.ok) throw new Error(await res.text());
          const json = await res.json();
          const row = document.querySelector(`[data-account-row="${json.id}"]`);
          if (row) row.remove();
          window.luroToast.show((window.LURO_I18N && window.LURO_I18N.account_deleted) || 'Account deleted', 'success');
        } catch (err) {
          console.error('Delete account failed', err);
          window.luroToast.show((window.LURO_I18N && window.LURO_I18N.unable_delete_account_prefix ? (window.LURO_I18N.unable_delete_account_prefix + (err.message || err)) : ('Unable to delete account: ' + (err.message || err))), 'error');
        }
      });
      btn.dataset.luroDeleteBound = '1';
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
