(function () {
    const totalsContainer = document.getElementById('totals-cards');
    const categoriasContainer = document.querySelector('[data-chart-target="categorias"]');
    const evolucaoContainer = document.querySelector('[data-chart-target="evolucao"]');
    const contasContainer = document.getElementById('contas-list');
    const monthInput = document.getElementById('filtro-mes');
    const toastContainer = document.getElementById('toast-container');

    const DEFAULT_CATEGORY_COLOR = '#9ca3af';
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

    function showToast(message, variant = 'error') {
        if (!toastContainer) {
            window.alert(message); // fallback when container is missing
            return;
        }
        const toast = document.createElement('div');
        toast.className = `toast toast-${variant}`;
        toast.textContent = message;
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
        renderCardsSkeleton();
        renderChartSkeleton(categoriasContainer);
        renderChartSkeleton(evolucaoContainer);
        renderContasSkeleton();
    }

    function renderCardsTotais(data) {
        if (!totalsContainer) return;
        const totais = data?.totais ?? {};
        const receitas = Number(totais.receitas ?? 0);
        const despesas = Number(totais.despesas ?? 0);
        const saldo = Number(totais.saldo ?? receitas - despesas);

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
            categoriasContainer.innerHTML = '<p class="empty-state">Nenhuma despesa encontrada para este mês.</p>';
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
                        borderColor: '#ffffff'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
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
            evolucaoContainer.innerHTML = '<p class="empty-state">Não há movimentações para exibir.</p>';
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
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.15)',
                        tension: 0.35,
                        fill: true,
                        pointRadius: 4
                    },
                    {
                        label: 'Receitas',
                        data: receitas,
                        borderColor: '#22c55e',
                        backgroundColor: 'rgba(34, 197, 94, 0.15)',
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
                    y: {
                        ticks: {
                            callback(value) {
                                return formatCurrency(value);
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
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
            contasContainer.innerHTML = '<p class="empty-state">Não encontramos movimentações para suas contas neste período.</p>';
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
            totalsContainer.innerHTML = '<p class="empty-state">Não foi possível carregar os totais.</p>';
        }
        if (categoriasContainer) {
            categoriasContainer.innerHTML = '<p class="empty-state">Erro ao carregar categorias.</p>';
        }
        if (evolucaoContainer) {
            evolucaoContainer.innerHTML = '<p class="empty-state">Erro ao carregar evolução mensal.</p>';
        }
        if (contasContainer) {
            contasContainer.innerHTML = '<p class="empty-state">Erro ao carregar as contas.</p>';
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
                return; // Uma requisição mais recente já está em andamento
            }
            renderCardsTotais(payload);
            renderPizzaCategorias(payload);
            renderEvolucaoMensal(payload);
            renderContas(payload);
        } catch (error) {
            console.error(error);
            renderErrorStates();
            showToast('Não foi possível carregar o resumo financeiro.', 'error');
        }
    }

    function setupFilters() {
        if (!monthInput) return;
        const now = new Date();
        const defaultMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
        if (!monthInput.value) {
            monthInput.value = defaultMonth;
        }
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
            carregarResumo(month, year);
        });
    }

    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible' && monthInput && monthInput.value) {
            const [year, month] = monthInput.value.split('-');
            carregarResumo(month, year);
        }
    });

    document.addEventListener('DOMContentLoaded', () => {
        showLoadingState();
        setupFilters();
    });
})();
