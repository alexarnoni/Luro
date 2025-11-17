(function () {
  const body = document.body;
  if (!body) {
    return;
  }

  const sessionCookieName = body.dataset.sessionCookieName;
  const userAuthenticated = body.dataset.userAuthenticated === 'true';
  const csrfEnabled = body.dataset.enableCsrfJson === 'true';
  const originalFetch = window.fetch.bind(window);

  const state = {
    csrfToken: null,
    refreshPromise: null,
  };

  async function refreshCsrfToken() {
    try {
      const response = await originalFetch('/api/csrf-token', {
        credentials: 'same-origin',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        state.csrfToken = null;
        return null;
      }

      const payload = await response.json();
      state.csrfToken = payload && typeof payload.csrfToken === 'string' ? payload.csrfToken : null;
      return state.csrfToken;
    } catch (error) {
      console.warn('Unable to refresh CSRF token', error);
      state.csrfToken = null;
      return null;
    } finally {
      state.refreshPromise = null;
    }
  }

  async function ensureCsrfToken() {
    if (!csrfEnabled) {
      return null;
    }

    if (state.csrfToken) {
      return state.csrfToken;
    }

    if (!state.refreshPromise) {
      state.refreshPromise = refreshCsrfToken();
    }

    return state.refreshPromise;
  }

  async function fetchWithCsrf(input, init) {
    const options = { ...(init || {}) };
    const method = (options.method || 'GET').toUpperCase();

    if (!options.credentials) {
      options.credentials = 'same-origin';
    }

    if (csrfEnabled && !['GET', 'HEAD', 'OPTIONS'].includes(method)) {
      const token = await ensureCsrfToken();
      if (token) {
        const headers = new Headers(options.headers || {});
        headers.set('X-CSRF-Token', token);
        options.headers = headers;
      }
    }

    return originalFetch(input, options);
  }

  window.luroSecurity = {
    csrfEnabled,
    ensureCsrfToken,
    refreshCsrfToken,
    fetch: fetchWithCsrf,
  };

  if (csrfEnabled) {
    window.fetch = fetchWithCsrf;
    if (hasSession()) {
      ensureCsrfToken().catch((error) => console.warn('Initial CSRF token fetch failed', error));
    }
  }
})();
