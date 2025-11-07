(function () {
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

    document.addEventListener('click', (event) => {
        const toggleButton = event.target.closest('[data-toggle-target]');
        if (toggleButton) {
            const selector = toggleButton.getAttribute('data-toggle-target');
            const focusSelector = toggleButton.getAttribute('data-toggle-focus');
            if (!selector) {
                return;
            }
            const target = document.querySelector(selector);
            toggleSection(target, selector, undefined, focusSelector);
            return;
        }

        const closeButton = event.target.closest('[data-close-target]');
        if (closeButton) {
            const selector = closeButton.getAttribute('data-close-target');
            if (!selector) {
                return;
            }
            const target = document.querySelector(selector);
            toggleSection(target, selector, false);
        }
    });
})();
