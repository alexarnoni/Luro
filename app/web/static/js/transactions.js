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
    const txnId = form.dataset.txnId;
    const submit = form.querySelector('button[type="submit"]');
    if (submit) submit.disabled = true;
    try {
      // client-side validation for amount
      const amountInput = form.querySelector('input[name="amount"]');
      if (amountInput) {
        const parsed = parseMoney(amountInput.value);
        if (parsed === null) {
          const msg = (window.LURO_I18N && window.LURO_I18N.invalid_amount) || 'Invalid amount format';
          window.luroToast.show(msg, 'error');
          if (submit) submit.disabled = false;
          return;
        }
        amountInput.value = String(parsed.toFixed(2));
      }

      const res = await fetch(form.action, { method: 'POST', body: new FormData(form), credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || 'Save failed');
      }
      const json = await res.json();
      const row = document.querySelector(`[data-txn-row="${json.id}"]`);
      if (row) {
        const desc = row.querySelector('.txn-desc');
        const amt = row.querySelector('.txn-amount');
        if (desc) desc.textContent = json.description || '-';
        if (amt) amt.textContent = (json.transaction_type === 'income' ? '+' : '-') + '$' + Number(json.amount).toFixed(2);
      }
      // hide edit row
      const editRow = document.getElementById('txn-edit-' + json.id);
      if (editRow) editRow.hidden = true;
      window.luroToast.show((window.LURO_I18N && window.LURO_I18N.transaction_updated) || 'Transaction updated', 'success');
    } catch (err) {
      console.error('Transaction save failed', err);
      const prefix = (window.LURO_I18N && window.LURO_I18N.unable_save_transaction_prefix) || 'Unable to save transaction: ';
      window.luroToast.show(prefix + (err.message || err), 'error');
    } finally {
      if (submit) submit.disabled = false;
    }
  }

  function bindTransactionCreate() {
    const form = document.getElementById('transaction-create-form');
    if (!form || form.dataset.bound) return;
    const paymentSelect = form.querySelector('#payment_method');
    const bankSelect = form.querySelector('#bank_account_id');
    const cardSelect = form.querySelector('#card_account_id');
    const accountHidden = form.querySelector('#account_id');
    const instTotal = form.querySelector('#installments_total');
    const instAmount = form.querySelector('#amount_per_installment');
    const amountInput = form.querySelector('#amount');
    const cardBlocks = form.querySelectorAll('[data-card-only]');
    const accountBlocks = form.querySelectorAll('[data-account-only]');
    const categorySelect = form.querySelector('#category_id');
    const newCategoryInput = form.querySelector('#new_category');

    const syncVisibility = () => {
      const mode = paymentSelect ? paymentSelect.value : 'account';
      const isCard = mode === 'card';
      cardBlocks.forEach((el) => { el.hidden = !isCard; });
      accountBlocks.forEach((el) => { el.hidden = isCard; });
      if (accountHidden) {
        if (isCard) {
          accountHidden.value = cardSelect ? cardSelect.value : '';
        } else {
          accountHidden.value = bankSelect ? bankSelect.value : '';
        }
      }
    };

    const syncInstallmentAmount = () => {
      if (!instTotal || !amountInput || !instAmount) return;
      const totalVal = parseMoney(amountInput.value);
      const totalInst = Number(instTotal.value || '1');
      if (totalVal !== null && totalInst > 0) {
        const per = totalVal / totalInst;
        instAmount.value = per.toFixed(2);
      }
    };

    const syncCategoryInput = () => {
      if (!categorySelect || !newCategoryInput) return;
      const isNew = categorySelect.value === '__new__' || categorySelect.options.length <= 2;
      if (isNew && categorySelect.value !== '__new__') {
        categorySelect.value = '__new__';
      }
      newCategoryInput.hidden = !isNew;
      if (!isNew) {
        newCategoryInput.value = '';
      }
    };

    paymentSelect && paymentSelect.addEventListener('change', syncVisibility);
    bankSelect && bankSelect.addEventListener('change', () => {
      if (accountHidden) accountHidden.value = bankSelect.value;
    });
    cardSelect && cardSelect.addEventListener('change', () => {
      if (accountHidden) accountHidden.value = cardSelect.value;
    });
    instTotal && instTotal.addEventListener('change', syncInstallmentAmount);
    amountInput && amountInput.addEventListener('blur', syncInstallmentAmount);
    categorySelect && categorySelect.addEventListener('change', syncCategoryInput);

    form.addEventListener('submit', (ev) => {
      // ensure hidden account id is set
      syncVisibility();
      syncCategoryInput();
      // if card and user filled parcel value, adjust amount = parcel * total
      const mode = paymentSelect ? paymentSelect.value : 'account';
      if (mode === 'card' && instTotal && instAmount && amountInput) {
        const per = parseMoney(instAmount.value);
        const totalInst = Number(instTotal.value || '1');
        if (per !== null && totalInst > 0) {
          amountInput.value = String((per * totalInst).toFixed(2));
        }
      }
      // if creating new category, ensure select value won't submit "__new__"
      if (categorySelect && categorySelect.value === '__new__') {
        categorySelect.name = 'category_id';
      }
    });

    syncVisibility();
    syncCategoryInput();
    form.dataset.bound = '1';
  }

  function init() {
    bindTransactionCreate();
    document.querySelectorAll('form.txn-edit-form-ajax').forEach((f) => {
      if (f.dataset.luroBound) return;
      f.addEventListener('submit', handleSubmit);
      f.dataset.luroBound = '1';
    });
    // bind delete buttons
    document.querySelectorAll('button[data-delete-txn]').forEach((btn) => {
      if (btn.dataset.luroDeleteBound) return;
      btn.addEventListener('click', async function () {
        const id = btn.getAttribute('data-delete-txn');
        if (!id) return;
        if (!confirm((window.LURO_I18N && window.LURO_I18N.confirm_delete_transaction) || 'Delete this transaction?')) return;
        try {
          const res = await fetch('/transactions/' + id + '/delete', { method: 'POST', credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
          if (!res.ok) throw new Error(await res.text());
          const json = await res.json();
          const row = document.querySelector(`[data-txn-row="${json.id}"]`);
          if (row) row.remove();
          // optionally update account balance display if present
          if (json.account_balance !== undefined) {
            // try to find account row and update balance text
            const accountEls = document.querySelectorAll(`[data-account-row]`);
            accountEls.forEach((el) => {
              const balEl = el.querySelector('.account-balance');
              if (balEl && balEl.dataset.accountId == json.account_id) {
                balEl.textContent = '$' + Number(json.account_balance).toFixed(2);
              }
            });
          }
          window.luroToast.show((window.LURO_I18N && window.LURO_I18N.transaction_deleted) || 'Transaction deleted', 'success');
        } catch (err) {
          console.error('Delete transaction failed', err);
          window.luroToast.show((window.LURO_I18N && window.LURO_I18N.unable_delete_transaction_prefix ? (window.LURO_I18N.unable_delete_transaction_prefix + (err.message || err)) : ('Unable to delete transaction: ' + (err.message || err))), 'error');
        }
      });
      btn.dataset.luroDeleteBound = '1';
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
