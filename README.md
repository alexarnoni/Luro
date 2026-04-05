# Luro – Personal Finance App

Aplicativo de finanças pessoais construído como projeto de estudo arquitetural. Está em produção em [luro.alexarnoni.com](https://luro.alexarnoni.com), mas não está em desenvolvimento ativo.

O foco do projeto foi construir uma base técnica sólida — segurança, infra, boas práticas — mais do que escalar um produto.

---

## Stack

- **Backend:** FastAPI (async) + SQLAlchemy 2.0 + Alembic
- **Frontend:** Jinja2 + Vanilla JS + Chart.js
- **Banco:** PostgreSQL (produção) / SQLite (desenvolvimento)
- **Auth:** Magic link via Resend
- **Infra:** Docker Compose + Oracle Cloud VM + Cloudflare
- **IA:** Gemini / OpenAI / Ollama (geração de insights mensais)

---

## Funcionalidades implementadas

- Autenticação por magic link com sessões revogáveis individualmente
- Proteção CSRF dupla (middleware + header `X-CSRF-Token`)
- Rate limiting por IP e por e-mail com persistência em banco
- Captcha via Cloudflare Turnstile
- Content Security Policy dinâmica com nonce por request
- Audit log de todas as mutações de dados
- Cookies `HttpOnly`, `SameSite`, `Secure` com validação de ambiente
- Dashboard com resumo mensal e gráficos por categoria
- Importador CSV/OFX com deduplicação por hash, sugestão de categoria via LLM e sistema de regras
- Gestão de cartão de crédito com parcelamento e controle de faturas
- Metas financeiras com contribuição por conta
- Insights mensais gerados por LLM com cache e rate limiting
- i18n via GNU gettext (pt-BR / en)
- Admin panel com audit log, health check e teste de conectividade do LLM
- Backup automático via `pg_dump` agendável por cron

---

## Segurança

Este foi o principal foco do projeto. Algumas decisões de design:

- Magic link usa `URLSafeTimedSerializer` (itsdangerous) com expiração configurável
- Sessions são armazenadas em banco e podem ser revogadas individualmente — não dependem só do cookie
- O rate limiter de login usa tabela `login_requests` em banco, compatível com múltiplos workers (ao contrário do rate limiter in-memory de outros endpoints, que tem a limitação documentada no código)
- CSP bloqueia scripts inline; nonce é gerado por request via middleware
- `SECRET_KEY` fraca e SQLite em produção causam falha imediata na inicialização
- Senhas de banco hardcoded no `docker-compose.prod.yml` são uma limitação conhecida (docker secrets seria o próximo passo)

---

## Rodando localmente

```bash
git clone https://github.com/alexarnoni/Luro.git
cd Luro
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # ajuste as variáveis
alembic upgrade head
uvicorn main:app --reload --port 8000
```

Acesse `http://localhost:8000` para a UI ou `/docs` para a API.

**Docker (opcional):**
```bash
docker compose up --build
```

---

## Variáveis de ambiente

Todas as variáveis disponíveis estão documentadas em `.env.example`.  
As obrigatórias para rodar em produção:

| Variável | Descrição |
|---|---|
| `SECRET_KEY` | Chave de assinatura (mínimo 32 chars em produção) |
| `DATABASE_URL` | PostgreSQL em produção (`postgresql+asyncpg://...`) |
| `RESEND_API_KEY` | Envio de magic links |
| `ALLOWED_HOSTS` | Hosts permitidos (ex: `luro.seudominio.com`) |

---

## Limitações conhecidas

- Rate limiter de endpoints gerais (`/import`, etc.) é in-memory — não funciona corretamente com múltiplos workers
- Strings de tradução em pt-BR incompletas (arquivos `.mo` não compilados no repositório)
- Algumas funções duplicadas no código de dashboard (`_select_account_id` repetida)

---

## Por que foi congelado

O projeto cumpriu o objetivo de aprender na prática como construir um produto web com segurança séria, autenticação sem senha, integração com LLMs e deploy em produção. A conclusão foi que o problema mais difícil em SaaS não é a engenharia — é distribuição e monetização.

O código fica público como referência de arquitetura e portfólio.

---

## Autor

Alexandre Arnoni — [alexarnoni.com](https://alexarnoni.com) · [LinkedIn](https://linkedin.com/in/alexandrearnoni) · [GitHub](https://github.com/alexarnoni)
