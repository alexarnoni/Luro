(function () {
  function formatCurrency(num) {
    return '$' + Number(num).toFixed(2);
  }

  function findGoalCard(el) {
    let node = el;
    while (node && !node.classList.contains('goal-card')) {
      node = node.parentElement;
    }
    return node;
  }

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

  async function handleSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const submitBtn = form.querySelector('button[type="submit"]');
    if (!form) return;
    const goalId = form.dataset.goalId;
    const formData = new FormData(form);

    // disable button to prevent double submits
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.dataset.origText = submitBtn.textContent;
      submitBtn.textContent = (window.LURO_I18N && window.LURO_I18N.processing_text) || 'Processing...';
    }

    // client-side validation for amount
    const amountInput = form.querySelector('input[name="amount"]');
    if (amountInput) {
      const parsed = parseMoney(amountInput.value);
      if (parsed === null || parsed <= 0) {
        const msg = (window.LURO_I18N && window.LURO_I18N.invalid_amount) || 'Invalid amount';
        window.luroToast.show(msg, 'error');
        return;
      }
      amountInput.value = String(parsed.toFixed(2));
    }

    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: formData,
        credentials: 'same-origin',
        headers: {
          'Accept': 'application/json'
        }
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || 'Request failed');
      }

      const payload = await response.json();

      // Update the UI
      const goalForm = form;
      const card = findGoalCard(goalForm);
      if (card) {
        const fill = card.querySelector('.progress-fill');
        const details = card.querySelector('.progress-details');
        const badge = card.querySelector('.badge');

        if (details) {
          const spans = details.querySelectorAll('span');
          if (spans.length >= 2) {
            spans[0].textContent = formatCurrency(payload.current_amount);
            spans[1].textContent = formatCurrency(payload.target_amount);
          }
        }

        if (fill && payload.target_amount && payload.target_amount > 0) {
          const pct = Math.min(100, Math.round((payload.current_amount / payload.target_amount) * 100));
          fill.style.width = pct + '%';
        }

        if (badge) {
          if (payload.is_completed) {
            badge.classList.remove('badge-info');
            badge.classList.add('badge-success');
            badge.textContent = (window.LURO_I18N && window.LURO_I18N.completed_text) || '✓ Completed';
          } else {
            badge.classList.remove('badge-success');
            badge.classList.add('badge-info');
            badge.textContent = (window.LURO_I18N && window.LURO_I18N.in_progress_text) || 'In Progress';
          }
        }
      }

    } catch (err) {
      console.error('Contribution failed', err);
      try {
        const prefix = (window.LURO_I18N && window.LURO_I18N.unable_contribute_prefix) || 'Unable to contribute to goal: ';
        window.luroToast.show(prefix + (err.message || err), 'error');
      } catch (e) {
        // ignore
      }
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = submitBtn.dataset.origText || ((window.LURO_I18N && window.LURO_I18N.contribute_fallback_text) || 'Contribute');
      }
    }
  }

  function init() {
    // Toggle add-goal form (uses data attribute instead of inline JS)
    const toggleBtn = document.querySelector('[data-goal-toggle]');
    if (toggleBtn && !toggleBtn.dataset.luroBoundToggle) {
      const form = document.getElementById('goal-form');
      toggleBtn.addEventListener('click', () => {
        if (!form) return;
        const isHidden = form.hasAttribute('hidden');
        if (isHidden) form.removeAttribute('hidden');
        else form.setAttribute('hidden', 'true');
      });
      toggleBtn.dataset.luroBoundToggle = '1';
    }

    const forms = document.querySelectorAll('form.goal-contribute-form');
    forms.forEach((f) => {
      // guard idempotent registration
      if (f.dataset.luroBound) return;
      f.addEventListener('submit', handleSubmit);
      f.dataset.luroBound = '1';
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
