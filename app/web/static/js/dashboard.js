(function () {
    const root = document.documentElement;
    const totalsContainer = document.getElementById('totals-cards');
    const categoriasContainer = document.querySelector('[data-chart-target="categorias"]');
    const evolucaoContainer = document.querySelector('[data-chart-target="evolucao"]');
    const contasContainer = document.getElementById('contas-list');
    const dashboardRoot = document.querySelector('[data-dashboard]');
    const monthInput = document.getElementById('filtro-mes');
    const toastContainer = document.getElementById('toast-container');
    const insightCard = document.querySelector('[data-insight-card]');
    const insightMessage = insightCard ? insightCard.querySelector('[data-insight-text]') : null;
    const insightButton = document.querySelector('[data-insight-action]');

    const DEFAULT_CATEGORY_COLOR = '#9ca3af';
    const EMPTY_ICONS = {
        categorias: 'M4 4h16a2 2 0 0 1 2 2v4.5l-3 2.25V19a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-6.25L2 10.5V6a2 2 0 0 1 2-2Zm0 2v3.382l2 1.5V17h12v-6.118l2-1.5V6H4Zm4 3h8a1 1 0 0 1 0 2H8a1 1 0 1 1 0-2Z',
        evolucao: 'M3 18a1 1 0 0 1 0-2h1.586l4.707-4.707a1 1 0 0 1 1.414 0L13 13.586l6.293-6.293a1 1 0 0 1 1.414 1.414l-7 7a1 1 0 0 1-1.414 0L10 12.586l-4 4V17a1 1 0 0 1-1 1H3Zm0-12a1 1 0 1 1 0-2h4a1 1 0 0 1 0 2H3Z',
        contas: 'M4 5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H4Zm0 2h16v2H4V7Zm0 4h16v6H4v-6Zm7 1v2h2v2h-2v2h-2v-2H7v-2h2v-2h2Z',
        erro: 'M11 3a1 1 0 0 1 2 0v8a1 1 0 1 1-2 0V3Zm1 18a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3Z'
    };

    const currencyFormatter = new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    });
    const monthLabelFormatter = new Intl.DateTimeFormat('pt-BR', {
        month: 'short',
        year: 'numeric'
    });

    const charts = {
        categorias: null,
        evolucao: null
    };

    let requestId = 0;
    let palette = null;
    let insightButtonDefaultLabel = insightButton ? insightButton.textContent.trim() : null;

    function getPalette() {
        const styles = window.getComputedStyle(root);
        return {
            text: styles.getPropertyValue('--color-text').trim() || '#1f2937',
            textMuted: styles.getPropertyValue('--color-text-muted').trim() || '#4b5563',
            surface: styles.getPropertyValue('--color-surface').trim() || '#ffffff',
            border: styles.getPropertyValue('--color-border').trim() || 'rgba(148, 163, 184, 0.4)',
            incomeLine: styles.getPropertyValue('--color-income').trim() || '#22c55e',
            incomeFill: styles.getPropertyValue('--color-chart-area-income').trim() || 'rgba(34, 197, 94, 0.15)',
            expenseLine: styles.getPropertyValue('--color-expense').trim() || '#ef4444',
            expenseFill: styles.getPropertyValue('--color-chart-area-expense').trim() || 'rgba(239, 68, 68, 0.15)',
            tooltipBg: styles.getPropertyValue('--color-chart-tooltip').trim() || 'rgba(17, 24, 39, 0.92)',
            tooltipText: styles.getPropertyValue('--color-chart-tooltip-text').trim() || '#f8fafc',
            grid: styles.getPropertyValue('--color-chart-grid').trim() || 'rgba(148, 163, 184, 0.25)'
        };
    }

    function applyChartDefaults() {
        if (typeof Chart === 'undefined') {
            return;
        }
        Chart.defaults.color = palette.text;
        Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
        Chart.defaults.plugins.legend.labels.color = palette.text;
        Chart.defaults.plugins.tooltip.backgroundColor = palette.tooltipBg;
        Chart.defaults.plugins.tooltip.titleColor = palette.tooltipText;
        Chart.defaults.plugins.tooltip.bodyColor = palette.tooltipText;
    }

    function updateChartsTheme() {
        Object.values(charts).forEach((chart) => {
            if (!chart) return;
            if (chart.config.type === 'doughnut') {
                chart.data.datasets.forEach((dataset) => {
                    dataset.borderColor = palette.surface;
                });
                if (chart.options?.plugins?.legend?.labels) {
                    chart.options.plugins.legend.labels.color = palette.text;
                }
            } else if (chart.config.type === 'line') {
                const [despesas, receitas] = chart.data.datasets;
                if (despesas) {
                    despesas.borderColor = palette.expenseLine;
                    despesas.backgroundColor = palette.expenseFill;
                }
                if (receitas) {
                    receitas.borderColor = palette.incomeLine;
                    receitas.backgroundColor = palette.incomeFill;
                }
                if (chart.options?.scales) {
                    const { x, y } = chart.options.scales;
                    if (x) {
                        x.ticks = x.ticks || {};
                        x.ticks.color = palette.textMuted;
                        x.grid = x.grid || {};
                        x.grid.color = palette.grid;
                        x.grid.drawBorder = false;
                    }
                    if (y) {
                        y.ticks = y.ticks || {};
                        y.ticks.color = palette.textMuted;
                        y.grid = y.grid || {};
                        y.grid.color = palette.grid;
                        y.grid.drawBorder = false;
                    }
                }
                if (chart.options?.plugins?.legend?.labels) {
                    chart.options.plugins.legend.labels.color = palette.text;
                }
            }
            chart.options.plugins = chart.options.plugins || {};
            chart.options.plugins.tooltip = chart.options.plugins.tooltip || {};
            chart.options.plugins.tooltip.backgroundColor = palette.tooltipBg;
            chart.options.plugins.tooltip.titleColor = palette.tooltipText;
            chart.options.plugins.tooltip.bodyColor = palette.tooltipText;
            chart.update();
        });
    }

    function showToast(message, variant = 'error') {
        if (!toastContainer) {
            window.alert(message);
            return;
        }
        const toast = document.createElement('div');
        toast.className = `toast toast-${variant}`;
        toast.textContent = message;
        toast.setAttribute('role', 'status');
        toastContainer.appendChild(toast);
        setTimeout(() => {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 4000);
    }

    function formatCurrency(value) {
        const numeric = Number.isFinite(value) ? value : 0;
        return currencyFormatter.format(numeric);
    }

    function formatMonthLabel(value) {
        if (!value) return '';
        const parts = value.split('-');
        if (parts.length !== 2) return value;
        const [year, month] = parts.map(Number);
        const date = new Date(Date.UTC(year, month - 1, 1));
        return monthLabelFormatter.format(date);
    }

    function setInsightMessage(message, state = 'idle') {
        if (insightCard) {
            insightCard.dataset.state = state;
        }
        if (insightMessage) {
            insightMessage.textContent = message || '';
        }
    }

    function updateInsightButtonLabel(monthValue) {
        if (!insightButton) return;
        const label = formatMonthLabel(monthValue);
        if (label) {
            insightButton.setAttribute('aria-label', `Gerar ou atualizar insight para ${label}`);
        } else {
            insightButton.removeAttribute('aria-label');
        }
    }

    function resetInsightMessage(monthValue) {
        if (!insightCard || !insightMessage) return;
        const label = formatMonthLabel(monthValue);
        const suffix = label ? ` para ${label}` : '';
        setInsightMessage(
            `Nenhum insight gerado${suffix}. Clique em "Gerar/Atualizar" para obter uma análise personalizada.`,
            'empty'
        );
        updateInsightButtonLabel(monthValue);
        insightCard.setAttribute('aria-busy', 'false');
        if (insightButton) {
            insightButton.disabled = false;
            insightButton.setAttribute('aria-busy', 'false');
            if (!insightButtonDefaultLabel) {
                insightButtonDefaultLabel = insightButton.textContent.trim();
            } else {
                insightButton.textContent = insightButtonDefaultLabel;
            }
        }
    }

    function setInsightLoading(isLoading) {
        if (!insightCard) return;
        insightCard.setAttribute('aria-busy', isLoading ? 'true' : 'false');
        if (insightButton) {
            if (!insightButtonDefaultLabel) {
                insightButtonDefaultLabel = insightButton.textContent.trim();
            }
            insightButton.disabled = isLoading;
            insightButton.setAttribute('aria-busy', isLoading ? 'true' : 'false');
            insightButton.textContent = isLoading ? 'Gerando...' : insightButtonDefaultLabel;
        }
        if (isLoading) {
            setInsightMessage('Gerando insight do mês, isso pode levar alguns segundos...', 'loading');
        }
    }

    async function gerarInsightDoMes() {
        if (!monthInput || !monthInput.value) {
            showToast('Selecione um mês válido.', 'error');
            return;
        }

        const monthValue = monthInput.value;
        setInsightLoading(true);

        try {
            const response = await fetch(`/api/insights/generate?month=${encodeURIComponent(monthValue)}`, {
                method: 'POST',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json'
                }
            });

            let data = null;
            try {
                data = await response.json();
            } catch (error) {
                data = null;
            }

            if (!response.ok) {
                const detail = (data && (data.detail || data.message)) || 'Não foi possível gerar um insight no momento.';
                const state = response.status === 404 ? 'empty' : 'error';
                setInsightMessage(detail, state);
                showToast(detail, response.status === 404 ? 'info' : 'error');
                return;
            }

            const insightText = typeof data?.insight === 'string' ? data.insight.trim() : '';
            if (insightText) {
                setInsightMessage(insightText, 'success');
                showToast('Insight atualizado com sucesso!', 'success');
            } else {
                const fallbackMessage = 'Nenhum insight foi retornado. Tente novamente em instantes.';
                setInsightMessage(fallbackMessage, 'error');
                showToast(fallbackMessage, 'error');
            }
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Não foi possível gerar um insight no momento.';
            setInsightMessage(message, 'error');
            showToast(message, 'error');
        } finally {
            setInsightLoading(false);
        }
    }

    function initializeInsightCard() {
        if (!insightButton) return;
        insightButton.addEventListener('click', (event) => {
            event.preventDefault();
            gerarInsightDoMes();
        });
    }

    function setBusyState(isBusy) {
        const value = isBusy ? 'true' : 'false';
        [dashboardRoot, totalsContainer, categoriasContainer, evolucaoContainer, contasContainer]
            .filter(Boolean)
            .forEach((element) => element.setAttribute('aria-busy', value));
    }

    function renderCardsSkeleton() {
        if (!totalsContainer) return;
        totalsContainer.innerHTML = Array.from({ length: 3 })
            .map(() => `
                <div class="stat-card skeleton-card">
                    <div class="skeleton skeleton-line" style="width: 55%; height: 14px;"></div>
                    <div class="skeleton skeleton-line" style="width: 80%; height: 32px;"></div>
                </div>
            `)
            .join('');
    }

    function renderChartSkeleton(container) {
        if (!container) return;
        container.innerHTML = '<div class="skeleton skeleton-chart skeleton-block"></div>';
    }

    function renderContasSkeleton() {
        if (!contasContainer) return;
        contasContainer.innerHTML = Array.from({ length: 3 })
            .map(() => `
                <div class="account-item">
                    <div class="account-info" style="flex:1;">
                        <div class="skeleton skeleton-line" style="width:60%;"></div>
                        <div class="skeleton skeleton-line" style="width:40%; height:12px;"></div>
                    </div>
                    <div class="skeleton skeleton-line" style="width:80px; height:20px; margin-bottom:0;"></div>
                </div>
            `)
            .join('');
    }

    function showLoadingState() {
        setBusyState(true);
        renderCardsSkeleton();
        renderChartSkeleton(categoriasContainer);
        renderChartSkeleton(evolucaoContainer);
        renderContasSkeleton();
    }

    function renderEmptyState(container, { iconKey, title, description, actions = [] }) {
        if (!container) return;
        const iconPath = EMPTY_ICONS[iconKey] || EMPTY_ICONS.erro;
        const actionsMarkup = actions
            .map((action) => {
                if (action.type === 'link') {
                    const attrs = [`class="btn ${action.variant === 'ghost' ? 'btn-ghost' : 'btn-primary'}"`, `href="${action.href}"`];
                    if (action.ariaLabel) {
                        attrs.push(`aria-label="${action.ariaLabel}"`);
                    }
                    return `<a ${attrs.join(' ')}>${action.label}</a>`;
                }
                if (action.type === 'button') {
                    const attrs = [`type="button"`, `class="btn ${action.variant === 'ghost' ? 'btn-ghost' : 'btn-primary'}"`];
                    if (action.dataToggle) {
                        attrs.push(`data-toggle-target="${action.dataToggle}"`);
                    }
                    if (action.dataFocus) {
                        attrs.push(`data-toggle-focus="${action.dataFocus}"`);
                    }
                    if (action.ariaControls) {
                        attrs.push(`aria-controls="${action.ariaControls}"`);
                        attrs.push(`aria-expanded="false"`);
                    }
                    return `<button ${attrs.join(' ')}>${action.label}</button>`;
                }
                return '';
            })
            .join('');

        container.innerHTML = `
            <div class="empty-state" role="status" aria-live="polite">
                <span class="empty-state__icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" focusable="false" role="presentation"><path d="${iconPath}" /></svg>
                </span>
                <h3 class="empty-state__title">${title}</h3>
                <p class="empty-state__description">${description}</p>
                ${actionsMarkup ? `<div class="empty-state__actions">${actionsMarkup}</div>` : ''}
            </div>
        `;
    }

    function renderCardsTotais(data) {
        if (!totalsContainer) return;
        const totais = data?.totais ?? {};
        const receitas = Number(totais.receitas ?? 0);
        const despesas = Number(totais.despesas ?? 0);
        const saldo = Number.isFinite(totais.saldo) ? Number(totais.saldo) : receitas - despesas;

        totalsContainer.innerHTML = `
            <div class="stat-card total-income">
                <h3>Receitas</h3>
                <p class="stat-value">${formatCurrency(receitas)}</p>
            </div>
            <div class="stat-card total-expense">
                <h3>Despesas</h3>
                <p class="stat-value">${formatCurrency(despesas)}</p>
            </div>
            <div class="stat-card total-balance">
                <h3>Saldo</h3>
                <p class="stat-value">${formatCurrency(saldo)}</p>
            </div>
        `;
    }

    function renderPizzaCategorias(data) {
        if (!categoriasContainer) return;
        categoriasContainer.innerHTML = '';
        if (charts.categorias) {
            charts.categorias.destroy();
            charts.categorias = null;
        }
        const items = Array.isArray(data?.porCategoria) ? data.porCategoria : [];
        if (items.length === 0) {
            renderEmptyState(categoriasContainer, {
                iconKey: 'categorias',
                title: 'Nenhuma categoria encontrada',
                description: 'Cadastre categorias ou importe um extrato para visualizar a distribuição de despesas.',
                actions: [
                    { type: 'link', label: 'Criar categoria', href: '/transactions' },
                    { type: 'link', label: 'Importar CSV/OFX', href: '/transactions', variant: 'ghost' }
                ]
            });
            return;
        }
        const canvas = document.createElement('canvas');
        categoriasContainer.appendChild(canvas);
        const ctx = canvas.getContext('2d');
        const labels = items.map((item) => item?.name ?? 'Categoria');
        const values = items.map((item) => Number(item?.total ?? 0));
        const colors = items.map((item) => item?.color || DEFAULT_CATEGORY_COLOR);

        charts.categorias = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [
                    {
                        data: values,
                        backgroundColor: colors,
                        borderWidth: 2,
                        borderColor: palette.surface
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: palette.text }
                    },
                    tooltip: {
                        backgroundColor: palette.tooltipBg,
                        titleColor: palette.tooltipText,
                        bodyColor: palette.tooltipText,
                        callbacks: {
                            label(context) {
                                const label = context.label || '';
                                const value = context.parsed || 0;
                                return `${label}: ${formatCurrency(value)}`;
                            }
                        }
                    }
                }
            }
        });
    }

    function renderEvolucaoMensal(data) {
        if (!evolucaoContainer) return;
        evolucaoContainer.innerHTML = '';
        if (charts.evolucao) {
            charts.evolucao.destroy();
            charts.evolucao = null;
        }
        const series = Array.isArray(data?.porMes) ? data.porMes : [];
        if (series.length === 0) {
            renderEmptyState(evolucaoContainer, {
                iconKey: 'evolucao',
                title: 'Não há movimentações ainda',
                description: 'Lance suas receitas e despesas para acompanhar a evolução mensal.',
                actions: [
                    { type: 'link', label: 'Adicionar transação', href: '/transactions' },
                    { type: 'link', label: 'Importar extrato', href: '/transactions', variant: 'ghost' }
                ]
            });
            return;
        }
        const canvas = document.createElement('canvas');
        evolucaoContainer.appendChild(canvas);
        const ctx = canvas.getContext('2d');
        const labels = series.map((item) => formatMonthLabel(item?.mes));
        const despesas = series.map((item) => Number(item?.despesas ?? 0));
        const receitas = series.map((item) => Number(item?.receitas ?? 0));

        charts.evolucao = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Despesas',
                        data: despesas,
                        borderColor: palette.expenseLine,
                        backgroundColor: palette.expenseFill,
                        tension: 0.35,
                        fill: true,
                        pointRadius: 4
                    },
                    {
                        label: 'Receitas',
                        data: receitas,
                        borderColor: palette.incomeLine,
                        backgroundColor: palette.incomeFill,
                        tension: 0.35,
                        fill: true,
                        pointRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    x: {
                        ticks: { color: palette.textMuted },
                        grid: { color: palette.grid, drawBorder: false }
                    },
                    y: {
                        ticks: {
                            color: palette.textMuted,
                            callback(value) {
                                return formatCurrency(value);
                            }
                        },
                        grid: { color: palette.grid, drawBorder: false }
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: palette.text }
                    },
                    tooltip: {
                        backgroundColor: palette.tooltipBg,
                        titleColor: palette.tooltipText,
                        bodyColor: palette.tooltipText,
                        callbacks: {
                            label(context) {
                                const label = context.dataset.label || '';
                                const value = context.parsed.y || 0;
                                return `${label}: ${formatCurrency(value)}`;
                            }
                        }
                    }
                }
            }
        });
    }

    function renderContas(data) {
        if (!contasContainer) return;
        const contas = Array.isArray(data?.contas) ? data.contas : [];
        if (contas.length === 0) {
            renderEmptyState(contasContainer, {
                iconKey: 'contas',
                title: 'Cadastre contas para acompanhar saldos',
                description: 'Consolide suas contas bancárias e carteiras para visualizar o saldo total.',
                actions: [
                    { type: 'link', label: 'Adicionar conta', href: '/accounts' },
                    { type: 'link', label: 'Importar CSV/OFX', href: '/transactions', variant: 'ghost' }
                ]
            });
            return;
        }
        contasContainer.innerHTML = '';
        contas.forEach((conta) => {
            const item = document.createElement('div');
            item.className = 'account-item';

            const info = document.createElement('div');
            info.className = 'account-info';
            const title = document.createElement('h4');
            title.textContent = conta?.name ?? 'Conta';
            const meta = document.createElement('span');
            meta.className = 'account-meta';
            meta.textContent = `ID ${conta?.id ?? '-'}`;
            info.appendChild(title);
            info.appendChild(meta);

            const balance = document.createElement('span');
            balance.className = 'account-balance';
            const saldo = Number(conta?.saldo ?? 0);
            balance.textContent = formatCurrency(saldo);
            if (saldo >= 0) {
                balance.classList.add('positive');
            } else {
                balance.classList.add('negative');
            }

            item.appendChild(info);
            item.appendChild(balance);
            contasContainer.appendChild(item);
        });
    }

    function renderErrorStates() {
        if (totalsContainer) {
            renderEmptyState(totalsContainer, {
                iconKey: 'erro',
                title: 'Não foi possível carregar os totais',
                description: 'Tente novamente em instantes ou atualize a página.'
            });
        }
        if (categoriasContainer) {
            renderEmptyState(categoriasContainer, {
                iconKey: 'erro',
                title: 'Erro ao carregar categorias',
                description: 'Recarregue a página ou tente novamente mais tarde.'
            });
        }
        if (evolucaoContainer) {
            renderEmptyState(evolucaoContainer, {
                iconKey: 'erro',
                title: 'Erro ao carregar evolução mensal',
                description: 'Recarregue a página ou tente novamente mais tarde.'
            });
        }
        if (contasContainer) {
            renderEmptyState(contasContainer, {
                iconKey: 'erro',
                title: 'Erro ao carregar as contas',
                description: 'Recarregue a página ou tente novamente mais tarde.'
            });
        }
        if (insightCard) {
            setInsightMessage(
                'Não foi possível carregar os dados financeiros. Gere o insight novamente após recarregar a página.',
                'error'
            );
            insightCard.setAttribute('aria-busy', 'false');
        }
    }

    async function carregarResumo(mes, ano) {
        if (!mes || !ano) {
            showToast('Selecione um mês e ano válidos.');
            return;
        }
        const current = ++requestId;
        showLoadingState();
        const params = new URLSearchParams({
            mes: String(mes).padStart(2, '0'),
            ano: String(ano)
        });
        try {
            const response = await fetch(`/api/resumo?${params.toString()}`, {
                headers: {
                    Accept: 'application/json'
                }
            });
            if (!response.ok) {
                throw new Error('Falha ao carregar o resumo.');
            }
            const payload = await response.json();
            if (current !== requestId) {
                return;
            }
            renderCardsTotais(payload);
            renderPizzaCategorias(payload);
            renderEvolucaoMensal(payload);
            renderContas(payload);
        } catch (error) {
            console.error(error);
            renderErrorStates();
            showToast('Não foi possível carregar o resumo financeiro.', 'error');
        } finally {
            setBusyState(false);
        }
    }

    function setupFilters() {
        if (!monthInput) return;
        const now = new Date();
        const defaultMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
        if (!monthInput.value) {
            monthInput.value = defaultMonth;
        }
        resetInsightMessage(monthInput.value);
        const [yearStr, monthStr] = monthInput.value.split('-');
        carregarResumo(monthStr, yearStr);

        monthInput.addEventListener('change', () => {
            const value = monthInput.value;
            if (!value) {
                showToast('Selecione um mês válido.');
                return;
            }
            const [year, month] = value.split('-');
            if (!year || !month) {
                showToast('Selecione um mês válido.');
                return;
            }
            resetInsightMessage(value);
            carregarResumo(month, year);
        });
    }

    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible' && monthInput && monthInput.value) {
            const [year, month] = monthInput.value.split('-');
            carregarResumo(month, year);
        }
    });

    document.addEventListener('luro:themechange', () => {
        palette = getPalette();
        applyChartDefaults();
        updateChartsTheme();
    });

    document.addEventListener('DOMContentLoaded', () => {
        palette = getPalette();
        applyChartDefaults();
        showLoadingState();
        setupFilters();
        initializeInsightCard();
    });
})();
