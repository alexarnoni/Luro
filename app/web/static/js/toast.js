(function () {
  function ensureContainer() {
    let c = document.getElementById('luro-toast-container');
    if (!c) {
      c = document.createElement('div');
      c.id = 'luro-toast-container';
      c.style.position = 'fixed';
      c.style.right = '16px';
      c.style.top = '16px';
      c.style.zIndex = '9999';
      document.body.appendChild(c);
    }
    return c;
  }

  function show(message, type = 'info', timeout = 5000) {
    try {
      const container = ensureContainer();
      const el = document.createElement('div');
      el.className = 'luro-toast luro-toast-' + type;
      el.style.marginTop = '8px';
      el.style.padding = '10px 14px';
      el.style.borderRadius = '6px';
      el.style.boxShadow = '0 2px 6px rgba(0,0,0,0.12)';
      el.style.color = '#fff';
      el.style.fontSize = '14px';
      if (type === 'error') el.style.background = '#d9534f';
      else if (type === 'success') el.style.background = '#5cb85c';
      else el.style.background = '#333';
      el.textContent = message;
      container.appendChild(el);
      setTimeout(() => {
        try { el.remove(); } catch (e) {}
      }, timeout);
    } catch (e) {
      // fallback to alert if toast fails
      try { alert(message); } catch (e) {}
    }
  }

  window.luroToast = { show };
})();
