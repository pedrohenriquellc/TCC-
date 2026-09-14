# ☁️ Guia de Infraestrutura — Oracle Cloud (Free Tier) + Ubuntu + Nginx + HTTPS/PQC

Guia passo a passo para colocar a aplicação no ar de forma **segura**,
atendendo a **todos os critérios do Eixo 1**. Comandos testados em
**Ubuntu Server** (última versão estável). Onde aparecer `SEU_IP_PUBLICO`,
troque pelo IP público real da sua VM.

> **Por que a versão mais recente do Ubuntu?** O suporte a **PQC**
> (`X25519MLKEM768`) exige **OpenSSL 3.5+** (abril/2025). Use uma versão do
> Ubuntu que já traga o OpenSSL 3.5 (confirme com `openssl version`). Se o seu
> Nginx não estiver ligado ao OpenSSL 3.5, o teste de PQC falha.

---

## 1. Criar a instância na Oracle Cloud

1. Acesse o **console** da Oracle Cloud → **Compute → Instances → Create Instance**.
2. **Image and shape:** escolha **Canonical Ubuntu** (última versão estável) e um
   shape **Always Free** (ex.: `VM.Standard.E2.1.Micro` ou Ampere `A1.Flex`).
3. **Add SSH keys:** selecione **Generate a key pair** e **baixe a chave privada**
   (ou cole a **sua chave pública**, gerada com `ssh-keygen -t ed25519`). Guarde a
   chave privada com segurança — ela **nunca** vai para o Git.
4. **Networking:** crie/escolha uma VCN com sub-rede pública e marque
   **Assign a public IPv4 address**.
5. Crie a instância e anote o **IP público**.

> A criação e configuração da instância fazem parte da avaliação — familiarize-se
> com a console (VCN, Security Lists, Compute).

---

## 2. Primeiro acesso e atualização

```bash
# 'ubuntu' é o usuário padrão da imagem Canonical na Oracle.
chmod 600 minha-chave.key
ssh -i minha-chave.key ubuntu@SEU_IP_PUBLICO

sudo apt update && sudo apt -y upgrade
openssl version   # confirme 3.5 ou superior (necessário p/ PQC)
```

Crie um usuário de deploy sem senha de login (usado pela app e pelo CI/CD):

```bash
sudo adduser --disabled-password --gecos "" deploy
sudo mkdir -p /home/deploy/.ssh && sudo chmod 700 /home/deploy/.ssh
# Autorize sua chave pública para o usuário deploy:
sudo cp ~/.ssh/authorized_keys /home/deploy/.ssh/ 2>/dev/null || true
sudo chown -R deploy:deploy /home/deploy/.ssh
sudo usermod -aG sudo deploy
```

---

## 3. Acesso remoto seguro (somente chave SSH)

Edite a configuração do SSH:

```bash
sudo nano /etc/ssh/sshd_config
```

Garanta estas linhas (desabilita senha — critério obrigatório):

```
PasswordAuthentication no
ChallengeResponseAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
```

```bash
sudo systemctl restart ssh
```

> ⚠️ **Antes de fechar a sessão atual**, abra um novo terminal e confirme que
> consegue entrar com a chave. Assim você não se tranca para fora.

---

## 4. Firewall / Least Privilege (só as portas necessárias)

São **duas camadas** — configure ambas.

### 4.1 Security List da Oracle (nível nuvem)
No console: **Networking → VCN → Security Lists → Ingress Rules**. Deixe apenas:

| Porta | Origem | Uso |
|---|---|---|
| 22  | `0.0.0.0/0` (ou seu IP) | SSH |
| 80  | `0.0.0.0/0` | HTTP (redireciona p/ HTTPS) |
| 443 | `0.0.0.0/0` | HTTPS |

Remova quaisquer outras regras de ingresso.

### 4.2 Firewall no host (UFW)
```bash
sudo apt -y install ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

> A imagem da Oracle às vezes usa `iptables` com regras próprias. Se o tráfego
> HTTP/HTTPS não passar, verifique também:
> `sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT` (e 80).

---

## 5. Fail2Ban na porta 22 (4 tentativas / banimento de 24h)

```bash
sudo apt -y install fail2ban
```

Crie `/etc/fail2ban/jail.local` com o conteúdo de
[`deploy/fail2ban-jail.local`](../deploy/fail2ban-jail.local) (já pronto no repo):

```ini
[DEFAULT]
bantime  = 24h
findtime = 10m
ignoreip = 127.0.0.1/8 ::1

[sshd]
enabled  = true
port     = ssh
maxretry = 4
bantime  = 24h
findtime = 10m
backend  = systemd
```

```bash
sudo systemctl enable --now fail2ban
sudo fail2ban-client status sshd   # deve mostrar a jail 'sshd' ativa
```

---

## 6. Instalar Nginx e a aplicação

```bash
sudo apt -y install nginx python3-venv python3-pip git
sudo systemctl enable --now nginx

# Como usuário deploy, clone o repositório:
sudo su - deploy
git clone https://github.com/SEU_USUARIO/projeto-seguro.git
cd projeto-seguro
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

# Crie o arquivo de segredos (fora do Git):
cp .env.example .env
python3 -c "import secrets; print('SECRET_KEY='+secrets.token_hex(32))" >> .env
nano .env          # ajuste DEMO_USER / DEMO_PASSWORD e a SECRET_KEY
chmod 600 .env
exit               # volta ao usuário sudo
```

Instale o serviço systemd (roda o Gunicorn como usuário `deploy`):

```bash
sudo cp /home/deploy/projeto-seguro/deploy/projeto-seguro.service \
        /etc/systemd/system/projeto-seguro.service
sudo systemctl daemon-reload
sudo systemctl enable --now projeto-seguro
sudo systemctl status projeto-seguro   # deve estar 'active (running)'
```

---

## 7. Configurar o Nginx (proxy + redirecionamento + PQC)

```bash
sudo cp /home/deploy/projeto-seguro/deploy/nginx-projeto-seguro.conf \
        /etc/nginx/sites-available/projeto-seguro
# Substitua SEU_IP_PUBLICO dentro do arquivo:
sudo sed -i "s/SEU_IP_PUBLICO/SEU_IP_REAL/g" /etc/nginx/sites-available/projeto-seguro

sudo ln -s /etc/nginx/sites-available/projeto-seguro /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo mkdir -p /var/www/html
sudo nginx -t
sudo systemctl reload nginx
```

Neste ponto o site já responde em **HTTP** (porta 80) e redireciona para 443 —
que ainda não tem certificado. Vamos emiti-lo.

---

## 8. HTTPS com Certbot para o IP público (Let's Encrypt + PQC)

A Let's Encrypt passou a emitir certificados para **endereços IP** usando o
perfil **`shortlived`** (validade de 6 dias). Requer **Certbot 5.4+**.

### 8.1 Instalar Certbot 5.4+ (via snap — traz a versão mais recente)
```bash
sudo apt -y install snapd
sudo snap install core && sudo snap refresh core
sudo snap install --classic certbot
sudo ln -sf /snap/bin/certbot /usr/bin/certbot
certbot --version    # confirme 5.4 ou superior
```

### 8.2 Emitir o certificado para o IP (teste primeiro com --staging)
```bash
# Teste (não conta no limite de emissão):
sudo certbot certonly --staging \
  --preferred-profile shortlived \
  --webroot --webroot-path /var/www/html \
  --ip-address SEU_IP_PUBLICO

# Deu certo? Emita o certificado real (remova --staging):
sudo certbot certonly \
  --preferred-profile shortlived \
  --webroot --webroot-path /var/www/html \
  --ip-address SEU_IP_PUBLICO
```

O certificado fica em `/etc/letsencrypt/live/SEU_IP_PUBLICO/`. O Nginx já aponta
para lá (`fullchain.pem` / `privkey.pem`). Recarregue:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### 8.3 Autorrenovação automática
Como o certificado de IP dura **6 dias**, a renovação precisa rodar com
frequência. O timer do Certbot já roda 2x/dia; adicione um **deploy-hook** para
recarregar o Nginx a cada renovação:

```bash
echo -e '#!/bin/sh\nsystemctl reload nginx' | \
  sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh

# Testar a renovação a seco:
sudo certbot renew --dry-run
# Verificar o timer:
systemctl list-timers | grep certbot
```

---

## 9. Verificação de conformidade (critério de aprovação)

Acesse `https://SEU_IP_PUBLICO/` no navegador — deve carregar com cadeado e
redirecionar automaticamente de HTTP para HTTPS.

### 9.1 Confirmar PQC no próprio servidor
```bash
openssl s_client -connect SEU_IP_PUBLICO:443 -groups X25519MLKEM768 -tls1_3 \
  2>&1 | grep "Server Temp Key"
# Esperado: Server Temp Key: X25519MLKEM768, 1216 bits
```

### 9.2 Testes online obrigatórios (uso de IP)
1. [**SSL.org — SSL Certificate Checker**](https://www.ssl.org/): informe o IP.
   Deve exibir **Certificate Trusted: YES** e
   **Algorithm / Key Type & Size: Good signature · Acceptable key**.
2. [**DigiCert — TLS quantum readiness check**](https://www.digicert.com/pqc-checker):
   informe o IP. Deve confirmar **PQC ativado**.

> 📸 Tire prints dos dois testes aprovados — servem de evidência na avaliação.

---

## 10. Ligar o CI/CD (GitHub Actions)

No GitHub: **Settings → Secrets and variables → Actions → New repository secret**.
Cadastre:

| Secret | Valor |
|---|---|
| `SSH_HOST` | `SEU_IP_PUBLICO` |
| `SSH_USER` | `deploy` |
| `SSH_PORT` | `22` |
| `SSH_PRIVATE_KEY` | conteúdo da **chave privada** autorizada na VM |

A partir daí, todo `git push origin main` dispara testes + deploy automático na
VM. Confirme na aba **Actions** do repositório.

---

## ✔️ Resumo de conformidade do Eixo 1

- [x] SO Ubuntu Server (última estável, OpenSSL 3.5+)
- [x] Nginx como web server
- [x] Acesso só por chave SSH (senha desabilitada)
- [x] Firewall least privilege (22/80/443) na nuvem e no host
- [x] Fail2Ban na porta 22: 4 tentativas, banimento de 24h
- [x] HTTPS via Certbot 5.4+ (cert de IP, perfil shortlived) com autorrenovação
- [x] Redirecionamento HTTP → HTTPS
- [x] PQC ativado (X25519MLKEM768) e verificado no SSL.org + DigiCert
