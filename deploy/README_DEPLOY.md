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
