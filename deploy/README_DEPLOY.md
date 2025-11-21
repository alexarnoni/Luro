# Guia de Deploy do Luro

Este documento descreve os passos recomendados para implantar o Luro em um servidor Linux.

1. **Copiar o projeto para `/opt/luro`**
   ```bash
   sudo mkdir -p /opt/luro
   sudo chown -R $(whoami):$(whoami) /opt/luro
   rsync -av --delete ./ /opt/luro/
   ```

2. **Criar o ambiente virtual e instalar dependências**
   ```bash
   cd /opt/luro
   python3 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Aplicar as migrações do banco de dados**
   ```bash
   alembic upgrade head
   ```

4. **Configurar e iniciar o serviço systemd**
   ```bash
   sudo cp deploy/luro.service /etc/systemd/system/luro.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now luro
   ```

5. **Instalar e configurar o Nginx**
   ```bash
   sudo apt-get update && sudo apt-get install -y nginx
   sudo cp deploy/luro.nginx.conf /etc/nginx/sites-available/luro.conf
   sudo ln -s /etc/nginx/sites-available/luro.conf /etc/nginx/sites-enabled/luro.conf
   sudo nginx -t
   sudo systemctl reload nginx
   ```

6. **Configurar TLS (Cloudflare ou Let's Encrypt)**
   - Configure o proxy e os certificados TLS usando Cloudflare **ou**
     gere certificados com Let's Encrypt (Certbot) apontando para `luro.seu-dominio.com`.
   - Atualize a configuração do Nginx para escutar em `443` e usar os certificados emitidos.

7. **Validar o deploy**
   - Garanta que o arquivo `.env` em `/opt/luro/.env` contenha todas as variáveis obrigatórias.
   - Execute `scripts/check_deploy.py` para validar o ambiente.

> Observação: adapte os caminhos e usuários conforme a política da sua infraestrutura.

   ## Deploy com Docker Compose (recomendado para a VM)

   Se preferir construir e rodar a aplicação via Docker Compose na VM (opção escolhida), siga estes passos na VM:

   1. Instale o Docker e o Docker Compose (ex.: `docker-ce` e `docker-compose-plugin`).

   2. Copie o projeto para a VM e crie o arquivo `.env` a partir de `.env.example`:
   ```bash
   cp .env.example .env
   # editar .env e preencher SECRET_KEY, POSTGRES_PASSWORD, RESEND_API_KEY, etc.
   ```

   3. Opções:
   - Usar `docker-compose.prod.yml` presente na raiz: ele cria a imagem localmente e levanta um serviço `db` (Postgres).

   4. Build & start:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

   5. Executar migrações (uma vez):
   ```bash
   docker compose -f docker-compose.prod.yml run --rm web alembic upgrade head
   ```

   6. Verificar logs e status:
   ```bash
   docker compose -f docker-compose.prod.yml ps
   docker compose -f docker-compose.prod.yml logs -f web
   ```

   7. Configurar Nginx (opcional) para servir `static/` e proxy_pass para `http://127.0.0.1:8000` (ex.: `deploy/luro.nginx.conf`).

   Para SSL, use Certbot ou sua solução de certificados (Cloudflare, etc.).
