(function () {
    const storageKey = 'luro-theme';
    const darkClass = 'dark';
    const root = document.documentElement;
    const toggleSelector = '[data-theme-toggle]';
    const toggleTextSelector = '[data-theme-toggle-text]';
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    function getStoredTheme() {
        try {
            return localStorage.getItem(storageKey);
        } catch (error) {
            console.warn('Unable to read theme preference', error);
            return null;
        }
    }

    function storeTheme(value) {
        try {
            localStorage.setItem(storageKey, value);
        } catch (error) {
            console.warn('Unable to persist theme preference', error);
        }
    }

    function getPreferredTheme() {
        const stored = getStoredTheme();
        if (stored === 'light' || stored === 'dark') {
            return stored;
        }
        return mediaQuery.matches ? 'dark' : 'light';
    }

    function updateRootTheme(theme) {
        const isDark = theme === 'dark';
        root.classList.toggle(darkClass, isDark);
        root.dataset.theme = theme;
        root.style.colorScheme = theme;
    }

    function updateToggle(theme) {
        const toggle = document.querySelector(toggleSelector);
        if (!toggle) {
            return;
        }
        const isDark = theme === 'dark';
        toggle.setAttribute('aria-pressed', isDark ? 'true' : 'false');
        toggle.setAttribute(
            'aria-label',
            isDark ? 'Alternar para tema claro' : 'Alternar para tema escuro'
        );
        const label = toggle.querySelector(toggleTextSelector);
        if (label) {
            label.textContent = isDark ? 'Modo escuro' : 'Modo claro';
        }
    }

    function dispatchThemeChange(theme) {
        document.dispatchEvent(
            new CustomEvent('luro:themechange', {
                detail: { theme },
            })
        );
    }

    function applyTheme(theme, { persist = true } = {}) {
        updateRootTheme(theme);
        updateToggle(theme);
        if (persist) {
            storeTheme(theme);
        }
        dispatchThemeChange(theme);
    }

    function toggleTheme() {
        const nextTheme = root.classList.contains(darkClass) ? 'light' : 'dark';
        applyTheme(nextTheme);
    }

    document.addEventListener('DOMContentLoaded', () => {
        const initialTheme = getPreferredTheme();
        applyTheme(initialTheme, { persist: false });

        const toggle = document.querySelector(toggleSelector);
        if (toggle) {
            toggle.addEventListener('click', toggleTheme);
        }
    });

    mediaQuery.addEventListener('change', (event) => {
        const stored = getStoredTheme();
        if (stored === 'light' || stored === 'dark') {
            return;
        }
        const theme = event.matches ? 'dark' : 'light';
        applyTheme(theme, { persist: false });
    });

    window.addEventListener('storage', (event) => {
        if (event.key !== storageKey) {
            return;
        }
        const value = event.newValue === 'dark' ? 'dark' : 'light';
        applyTheme(value, { persist: false });
    });
})();
