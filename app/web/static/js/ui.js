(function () {
    // Lightweight UI helper used across pages (toggle sections / close buttons).
    // Add defensive logging and error handling so failures don't break other scripts.
    function logDebug(...args) {
        try {
            if (window && window.console && typeof window.console.log === 'function') {
                window.console.log('[luro-ui]', ...args);
            }
        } catch (e) {
            /* ignore */
        }
    }

    function logError(...args) {
        try {
            if (window && window.console && typeof window.console.error === 'function') {
                window.console.error('[luro-ui]', ...args);
            }
        } catch (e) {
            /* ignore */
        }
    }

    let __luro_ui_initialized = false;

    // Mark on the document that the ui.js script executed so we can detect
    // whether the script ran even if the console is filtered.
    try {
        if (document && document.documentElement) {
            document.documentElement.dataset.luroUiScript = 'loaded';
        }
    } catch (e) {
        /* ignore */
    }

    function updateToggleButtons(selector, expanded) {
        if (!selector) {
            return;
        }
        document.querySelectorAll(`[data-toggle-target="${selector}"]`).forEach((button) => {
            button.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        });
    }

    function toggleSection(target, selector, show, focusSelector) {
        if (!target) {
            return;
        }
        const shouldShow = typeof show === 'boolean' ? show : target.hasAttribute('hidden');
        if (shouldShow) {
            target.removeAttribute('hidden');
            target.setAttribute('aria-hidden', 'false');
        } else {
            target.setAttribute('hidden', '');
            target.setAttribute('aria-hidden', 'true');
        }
        updateToggleButtons(selector, shouldShow);
        if (shouldShow && focusSelector) {
            const focusTarget = typeof focusSelector === 'string'
                ? target.querySelector(focusSelector) || document.querySelector(focusSelector)
                : null;
            if (focusTarget && typeof focusTarget.focus === 'function') {
                window.requestAnimationFrame(() => focusTarget.focus());
            }
        }
    }

    function registerUiHandlers() {
        if (typeof window !== 'undefined' && window.__luro_ui_handlers_registered) {
            logDebug('UI handlers already registered (global)');
            return;
        }
        if (__luro_ui_initialized) return;
        __luro_ui_initialized = true;
        logDebug('Initializing UI handlers');

            try {
                // mark global so subsequent script executions don't re-register
                try { if (typeof window !== 'undefined') window.__luro_ui_handlers_registered = true; } catch (e) {}
                document.addEventListener('click', (event) => {
                    // mark last interaction on the document for debugging without console
                    try {
                        if (document && document.documentElement) {
                            document.documentElement.dataset.luroUiLastInteraction = String(Date.now());
                        }
                    } catch (e) {}
                try {
                    const toggleButton = event.target.closest('[data-toggle-target]');
                        if (toggleButton) {
                        logDebug('toggle-button clicked', toggleButton.getAttribute('data-toggle-target'));
                        try {
                            if (document && document.documentElement) {
                                document.documentElement.dataset.luroUiLastToggle = toggleButton.getAttribute('data-toggle-target') || '';
                            }
                        } catch (e) {}
                        const selector = toggleButton.getAttribute('data-toggle-target');
                        const focusSelector = toggleButton.getAttribute('data-toggle-focus');
                        if (!selector) {
                            logDebug('toggle-button had no selector');
                            return;
                        }
                        // Helpful debug for common actions
                        if (selector === '#account-form') {
                            logDebug('Add account clicked');
                        } else if (selector === '#transaction-form') {
                            logDebug('Add transaction clicked');
                        } else if (selector && selector.indexOf('#goal-form') === 0) {
                            logDebug('Edit goal clicked', selector);
                        }
                        const target = document.querySelector(selector);
                        toggleSection(target, selector, undefined, focusSelector);
                        return;
                    }

                    const closeButton = event.target.closest('[data-close-target]');
                    if (closeButton) {
                        logDebug('close-button clicked', closeButton.getAttribute('data-close-target'));
                        const selector = closeButton.getAttribute('data-close-target');
                        if (!selector) {
                            logDebug('close-button had no selector');
                            return;
                        }
                        const target = document.querySelector(selector);
                        toggleSection(target, selector, false);
                    }
                } catch (err) {
                    logError('Error in delegated click handler', err);
                    try { alert('UI error: ' + (err && err.message ? err.message : String(err))); } catch (e) {}
                }
            });
            logDebug('UI click delegation registered');
        } catch (err) {
            logError('Failed to register UI handlers', err);
        }
    }

    // Register immediately and also on DOMContentLoaded to be robust in all load orders
    try {
        registerUiHandlers();
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', registerUiHandlers);
        }
    } catch (err) {
        logError('Failed to initialize UI handlers at load', err);
    }
})();
