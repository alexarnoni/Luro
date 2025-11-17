# Luro – Personal Finance Manager

Luro é um gerenciador financeiro pessoal com foco em segurança, autenticação sem senha e visualizações ricas construídas com FastAPI, Jinja e Chart.js. O projeto oferece dashboard interativo, gestão de contas, transações, metas e importação de extratos para agilizar o onboarding financeiro.

## Visão geral da arquitetura

- **Backend**: FastAPI (async) com SQLAlchemy e Alembic.
- **Templates**: Jinja2 com componentes reutilizáveis.
- **Frontend**: CSS modular versionado no repositório e scripts vanilla (sem bundler).
- **Gráficos**: Chart.js via CDN UMD (`cdn.jsdelivr.net`).
- **Autenticação**: Login por magic link usando Resend.
- **Infra**: Docker/Docker Compose para desenvolvimento opcional.

## Pré-requisitos

- Python 3.11+
- SQLite (padrão) ou qualquer banco suportado pelo SQLAlchemy async
- Node não é necessário (CSS já versionado)

## Variáveis de ambiente essenciais

Configure um arquivo `.env` na raiz com os valores abaixo (todos disponíveis em `app/core/config.py`):

| Variável | Descrição |
| --- | --- |
| `DATABASE_URL` | URL de conexão do banco (padrão: `sqlite+aiosqlite:///./luro.db`). |
| `RESEND_API_KEY` | Chave da API Resend para envio de magic links. |
| `ENV` | `development` ou `production`; controla cookies e headers seguros. |
| `ENABLE_CSRF_JSON` | Habilita validação de CSRF para requisições JSON mutáveis. |
| `ENABLE_SECURITY_HARDENING` | Ativa captcha + rate limit persistente no login por magic link. |
| `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY` | Chaves do Cloudflare Turnstile para o captcha da tela de login. |
| `RATE_LIMIT_MAX` | Número máximo de requisições em janela para proteção de força bruta. |
| `RATE_LIMIT_WINDOW_SECONDS` | Janela (em segundos) usada pelo rate limiter. |
| `LOGIN_RATE_LIMIT_IP_MAX` / `LOGIN_RATE_LIMIT_IP_WINDOW_SECONDS` | Limite por IP para envio de magic link (usado quando o hardening está ativo). |
| `LOGIN_RATE_LIMIT_EMAIL_MAX` / `LOGIN_RATE_LIMIT_EMAIL_WINDOW_SECONDS` | Limite por e-mail para envio de magic link (usado quando o hardening está ativo). |
| `RESEND_FROM_EMAIL` | Remetente usado nos e-mails de autenticação. |

Outras chaves relevantes: `SECRET_KEY`, `IMPORT_MAX_FILE_MB` e `DEBUG`.

## Executando localmente (runbook)

1. **Clonar e preparar ambiente**
   ```bash
   git clone https://github.com/alexarnoni/Luro.git
   cd Luro
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env  # ajuste conforme necessário
   ```

2. **Inicializar banco e executar migrations**
   ```bash
   alembic upgrade head
   ```

3. **Iniciar a aplicação**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
   Acesse `http://localhost:8000` para a UI ou `http://localhost:8000/docs` para a documentação OpenAPI.

4. **(Opcional) Docker Compose**
   ```bash
   docker-compose up --build
   ```

## Considerações de segurança

- **Cookies de sessão**: enviados com `HttpOnly`, `SameSite=Lax` e `Secure` automático em produção.
- **CSRF**: middleware `CSRFMiddleware` + `security.js` adicionam/verificam token em requisições JSON mutáveis quando `ENABLE_CSRF_JSON` está ativo.
- **Rate limiting**: `RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW_SECONDS` protegem rotas sensíveis (login/import).
- **Hardening de login**: quando `ENABLE_SECURITY_HARDENING=true`, o login exige validação Turnstile (`TURNSTILE_SITE_KEY`/`TURNSTILE_SECRET_KEY`) e rate limit persistente (por IP/e-mail via tabela `login_requests`).
- **CSP**: `SecurityHeadersMiddleware` aplica `Content-Security-Policy` que permite scripts apenas do próprio host e `cdn.jsdelivr.net` (Chart.js), evitando inline scripts.
- **SQLite**: `journal_mode=WAL`, `foreign_keys=ON` e `busy_timeout` configurados automaticamente para resiliência.

## Importador de transações

Endpoint `POST /api/import` suporta CSV/OFX até `IMPORT_MAX_FILE_MB` (padrão 5 MB) com dois modos:

- `preview`: retorna colunas normalizadas, totais, duplicatas detectadas e sugestões de categoria.
- `apply`: persiste transações válidas, ignora duplicatas já existentes e pode criar/atualizar regras (`save_rules=true`) para categorização automática futura.

A deduplicação usa `source_hash`, regras existentes são aplicadas automaticamente e overrides podem forçar categorias específicas. Mapeamentos de colunas customizados são aceitos (`mapping`).

## Migrations e boas práticas

- Sempre execute `alembic revision --autogenerate -m "sua mensagem"` após alterar modelos.
- Revise o diff gerado e ajuste tipos/nulos manualmente antes de aplicar.
- Rode `alembic upgrade head` localmente e em ambientes de CI/CD.
- Sincronize o modelo Python e a migration para evitar divergências.

## Estilos e build de assets

O CSS principal (`app/web/static/css/style.css`) é versionado diretamente. Não há pipeline de build; alterações devem ser feitas no arquivo e revisadas com atenção ao modo escuro (`html.dark`). Chart.js é carregado via CDN UMD e scripts customizados ficam em `app/web/static/js`.

## Roadmap curto

- Criar UI dedicada para gerenciamento de categorias.
- Expor interface para importação (atualmente apenas API).
- Cobertura de testes E2E para fluxos críticos (login, importação, dashboard).

## Backups

- Script manual: `bash scripts/backup_db.sh` (usa `docker exec luro-db-1 pg_dump` e salva em `/opt/luro_backups` por padrão).
- Agendamento sugerido na VM: `0 3 * * * /bin/bash /opt/luro/scripts/backup_db.sh >> /var/log/luro_backup.log 2>&1`

## Privacidade e Termos de Uso

- Política de Privacidade: [`docs/PRIVACIDADE.md`](docs/PRIVACIDADE.md)
- Termos de Uso: [`docs/TERMOS_DE_USO.md`](docs/TERMOS_DE_USO.md)
- Links também disponíveis no rodapé da aplicação (`/privacidade` e `/termos`).

## Checklist de testes manuais

Antes de abrir PRs, execute manualmente:

- [ ] Dashboard: carregamento do resumo mensal (`/dashboard` → cards, gráficos e skeletons).
- [ ] Chart de categorias: validar exibição de dados e estado vazio com CTA.
- [ ] Importador: requisitar `POST /api/import` em modo `preview` e `apply` com arquivos CSV/OFX pequenos.

Marcar os itens no PR ajuda a garantir uma experiência consistente para novas contribuições.
