# 🔐 Projeto Aplicado: Práticas de Mercado — Protótipo Web Seguro

Relatório técnico da entrega. O projeto simula um ambiente de mercado real
aplicando **Secure by Design** e **Secure by Default** em todo o ciclo de vida
da aplicação, integrando **infraestrutura em nuvem**, **versionamento**,
**desenvolvimento** e um **pipeline de CI/CD**.

| Recurso | Endereço |
|---|---|
| Aplicação (IP público) | **https://144.22.166.21/** |
| Aplicação (hostname p/ teste TLS) | **https://144-22-166-21.sslip.io/** |
| Repositório | https://github.com/pedrohenriquellc/TCC- |

- **Stack:** Python · Flask · Gunicorn · Nginx · Ubuntu Server 26.04 · Oracle Cloud (Free Tier)
- **Credenciais de demonstração:** usuário `admin` / senha definida em `DEMO_PASSWORD` (no `.env` da VM, fora do Git)

> **Codificação assistida por IA:** todo o código, a auditoria de segurança e a
> configuração de infraestrutura foram desenvolvidos com o auxílio de um
> assistente de IA (fluxo equivalente ao proposto pela IDE Antigravity),
> incluindo geração de código seguro, depuração e refatoração.

---

## 🏆 Evidências de TLS/PQC

A entrega é por **IP público**, portanto a validação principal segue o **caminho IP**
da atividade (SSL.org + DigiCert). Como reforço, incluímos também o **caminho Domínio**
(Qualys SSL Labs) via hostname `sslip.io`, que resolve para o mesmo IP.

### ✅ Caminho IP (validação principal — `144.22.166.21`)

**1. SSL.org — SSL Certificate Checker** · https://www.ssl.org/
- **Certificate Trusted: YES**
- **Algorithm / Key Type & Size: Good signature · Good key** (ECDSA P-256 / SHA-384)
- Emissor: **Let's Encrypt** · perfil short-lived (cert de IP) · TLS 1.2 e 1.3

![SSL.org — Certificate Trusted YES no IP](docs/evidencias/ssl-org-ip.png)

**2. DigiCert — TLS Quantum Readiness Check (PQC)** · https://www.digicert.com/pqc-checker
- **PASS** — *TLS 1.3 enabled*
- **PASS** — *Quantum-safe key exchange* (ML-KEM / `X25519MLKEM768`)

![DigiCert PQC — PASS no IP](docs/evidencias/digicert-pqc-ip.png)

### ➕ Caminho Domínio (reforço — Qualys SSL Labs)

Relatório ao vivo: **https://www.ssllabs.com/ssltest/analyze.html?d=144-22-166-21.sslip.io**
- **Overall Rating: A+** · suporte a **PQC** (`X25519MLKEM768`) · TLS 1.3 · HSTS válido

![SSL Labs — nota A+ com suporte a PQC](docs/evidencias/ssllabs.png)

> O teste do SSL Labs não avalia endereços IP diretamente; por isso o caminho Domínio
> usa o hostname `144-22-166-21.sslip.io`, que resolve para o mesmo IP
> (`144.22.166.21`) e usa a mesma configuração TLS. **Nenhum domínio foi registrado.**

> 📸 **Prints:** as imagens acima ficam em [`docs/evidencias/`](docs/evidencias/).
> Como o certificado de IP tem validade curta (renovação automática), recapture os
> prints perto da apresentação — os resultados se mantêm.

---

## 0. Sobre o projeto (conceito)

Este projeto simula o **ciclo de vida completo** de uma aplicação web moderna: escrever
o código, versioná-lo, publicá-lo em nuvem pública e mantê-lo em produção — **com
segurança em cada etapa**, e não como um remendo no fim. Dois princípios guiam tudo:

- **Secure by Design** — a segurança faz parte da arquitetura desde o primeiro commit
  (controle de acesso, hash de senha, proteção CSRF, cabeçalhos de segurança).
- **Secure by Default** — a configuração padrão já é a mais segura: cookie de sessão
  já nasce protegido, o servidor só aceita TLS moderno e só abre as portas necessárias.

**Em uma frase:** o usuário acessa por HTTPS, faz **login** (senha verificada por hash,
com proteção contra força bruta e CSRF), é levado a uma **página interna** que só existe
para quem está autenticado e pode sair pelo **logout**. Por trás, o Nginx faz a
criptografia TLS (com troca de chave pós-quântica) e repassa as requisições ao app
Python rodando sob o Gunicorn.

**Por que Python + Flask:** entrega os controles de segurança exigidos com pouco código
e superfície de ataque pequena — CSRF, sessão, cabeçalhos/HSTS, hash forte e rate
limiting vêm de bibliotecas maduras, tornando a mitigação OWASP direta e fácil de
comprovar. Não exige banco de dados (requisito dispensado).

---

## 📁 Estrutura do repositório

```
projeto-seguro/
├── app.py                     # Aplicação Flask (login, área interna, logout)
├── requirements.txt           # Dependências Python
├── templates/                 # HTML (Jinja2, autoescape ligado)
│   ├── base.html
│   ├── login.html
│   └── dashboard.html
├── static/style.css
├── .env.example               # Modelo de variáveis (o .env real NÃO é versionado)
├── .gitignore                 # Bloqueia segredos, chaves e credenciais
├── .github/workflows/deploy.yml   # Pipeline CI/CD (GitHub Actions)
├── docs/
│   ├── GUIA-INFRAESTRUTURA.md  # Passo a passo da nuvem
│   └── evidencias/             # Prints dos testes TLS/PQC
└── deploy/                    # Configs do servidor
    ├── nginx-projeto-seguro.conf
    ├── projeto-seguro.service
    └── fail2ban-jail.local
```

---

## 💻 Eixo 3 — Desenvolvimento e mitigações OWASP Top 10:2025

O protótipo possui **tela de login**, **página interna protegida** (`/dashboard`)
e **logout funcional**, e mitiga ativamente **3 categorias** do
[OWASP Top 10:2025](https://owasp.org/Top10/2025/).

| Rota | Método | Descrição |
|---|---|---|
| `/login` | GET/POST | Tela de login (formulário com token CSRF) |
| `/dashboard` | GET | Página interna — **só acessível autenticado** |
| `/logout` | POST | Encerra a sessão (POST + CSRF, evita logout forçado) |
| `/healthz` | GET | Checagem de disponibilidade (usada no deploy/CI) |

### ✅ A01:2025 — Broken Access Control
**Onde:** `app.py` → decorator `login_required` + rota `/dashboard`.
**Como:** a página interna só é servida quando existe uma sessão autenticada
(`session["user"]`). Qualquer acesso direto a `/dashboard` sem login é negado e
redirecionado para `/login`. O logout usa **POST + token CSRF**, evitando logout
forçado por terceiros.

### ✅ A05:2025 — Injection (inclui XSS)
**Onde:** `app.py` (validação/allowlist + CSRF) e `templates/*.html`.
**Como:**
- **Validação de entrada por allowlist** no campo usuário
  (`^[A-Za-z0-9_.-]{3,32}$`) — entradas maliciosas são rejeitadas (HTTP 400).
- **Autoescape do Jinja2** mantido ligado: toda saída dinâmica é escapada,
  neutralizando **XSS refletido**.
- **Proteção CSRF** (`Flask-WTF`) obrigatória em todos os POST.

### ✅ A07:2025 — Authentication Failures
**Onde:** `app.py` → função `login()`, dicionário `USERS`, config de sessão.
**Como:**
- Senhas **nunca** em texto puro — armazenadas apenas como **hash scrypt**
  (`werkzeug.security.generate_password_hash`) e verificadas com comparação
  **resistente a timing** (`check_password_hash`).
- **Rate limiting** (`Flask-Limiter`, 5 tentativas/min) freia ataques de
  **força bruta** no login (retorna HTTP 429).
- Defesa contra **user enumeration**: hash "dummy" computado quando o usuário
  não existe, mantendo o tempo de resposta constante.
- **Session fixation** evitada: `session.clear()` regenera a sessão no login.
- Cookies de sessão com `HttpOnly`, `Secure` e `SameSite=Lax`.

> **Bônus — A02:2025 (Security Misconfiguration):** cabeçalhos de segurança
> (`Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`,
> `Strict-Transport-Security`), `DEBUG` desligado por padrão e `SECRET_KEY`
> lido de variável de ambiente (nunca hardcoded).

### 🧪 Evidências dos testes (comportamento)

| Cenário testado | Resultado esperado | Obtido |
|---|---|---|
| Login válido | 302 → `/dashboard` | ✅ 302 |
| Acesso a `/dashboard` sem login | 302 → `/login` | ✅ 302 |
| Logout | 302 → `/login` | ✅ 302 |
| `/dashboard` após logout | 302 → `/login` | ✅ 302 |
| POST login sem token CSRF | 400 | ✅ 400 |
| Entrada fora da allowlist no usuário | 400 | ✅ 400 |
| 6+ logins/minuto | 429 (rate limit) | ✅ 429 |
| `/healthz` | 200 `{"status":"ok"}` | ✅ 200 |

### ▶️ Rodando localmente

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # edite os valores
FLASK_INSECURE=1 python app.py   # http://127.0.0.1:8000
```
Credenciais de demonstração: usuário `admin` / senha definida em `DEMO_PASSWORD`.

---

## ☁️ Eixo 1 — Infraestrutura (Oracle Cloud, Free Tier)

- **Provedor:** Oracle Cloud Infrastructure, Free Tier (região sa-saopaulo-1).
- **Instância:** shape `VM.Standard.E2.1.Micro` (Always Free), 1 OCPU / 1 GB.
- **Sistema operacional:** **Ubuntu Server 26.04 LTS** (OpenSSL 3.5.5).
- **Servidor web:** **Nginx 1.28** como proxy reverso → Gunicorn (127.0.0.1:8000).

Passo a passo detalhado em **[`docs/GUIA-INFRAESTRUTURA.md`](docs/GUIA-INFRAESTRUTURA.md)**.

### Endurecimento e metas de segurança (com evidência)

| Meta obrigatória | Implementação | Como comprovar |
|---|---|---|
| Acesso remoto só por chave SSH | `PasswordAuthentication no`, chave ed25519 | `sudo sshd -T \| grep passwordauthentication` |
| Fail2Ban na porta 22 | jail `sshd`, `maxretry=4`, `bantime=24h` | `sudo fail2ban-client status sshd` |
| Firewall least privilege | Apenas 22, 80, 443 (Security List OCI + UFW/iptables) | `sudo iptables -S INPUT` · `sudo ufw status` |
| HTTPS (Certbot ≥ 5.4) | Certbot **5.8**, cert Let's Encrypt para IP, perfil short-lived, autorrenovação | `sudo certbot certificates` |
| Redirect HTTP → HTTPS | Nginx `return 301 https://...` | `curl -I http://144.22.166.21` → **301** |
| **PQC ativado** | `ssl_ecdh_curve X25519MLKEM768:...` (OpenSSL 3.5) | `openssl s_client -connect 144.22.166.21:443 -groups X25519MLKEM768 -tls1_3` |

> **Certificados:** o app responde por IP e por hostname.
> - `144.22.166.21` — cert Let's Encrypt **short-lived (6 dias)**, modalidade usada
>   para certificados de endereço IP. Validação: SSL.org + DigiCert.
> - `144-22-166-21.sslip.io` — cert Let's Encrypt padrão (90 dias), usado apenas para
>   o teste do SSL Labs (que não avalia IPs). sslip.io resolve para o mesmo IP; nenhum
>   domínio foi registrado. Ambos compartilham a mesma configuração TLS e renovam
>   automaticamente via Certbot.

---

## 📦 Eixo 2 — Repositório e prevenção de vazamento

- Código público no **GitHub**, conta protegida com **2FA** e operações via
  **chave SSH** (ou PAT).
- **`.gitignore`** bloqueia `.env`, chaves privadas (`*.pem`, `id_*`),
  credenciais de nuvem (`.oci/`, `.aws/`), senhas e bancos locais.
- **Nenhuma credencial real** é versionada — segredos ficam em `.env` (local,
  fora do Git) e em **GitHub Secrets** (pipeline).

---

## 🔄 CI/CD — GitHub Actions

Arquivo: **[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)**.
A cada `git push origin main`:

1. **test** — instala dependências, valida a aplicação e roda auditoria de
   dependências (`pip-audit`, mitigando **A03:2025 — Software Supply Chain**).
2. **deploy** — conecta na VM via **SSH** (credenciais em **Secrets**), atualiza
   o código (`git reset --hard origin/main`), reinstala dependências e reinicia
   o serviço (`systemctl restart projeto-seguro`).
3. **health check** — valida `https://144.22.166.21/healthz` após o deploy.

**Secrets configurados no GitHub:** `SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY`,
`SSH_PORT` — nenhuma chave exposta no `.yml`.

---

## ✅ Checklist de entrega

- [x] Aplicação web no ar via IP público (Eixo 1)
- [x] Nginx com HTTPS (Certbot/Let's Encrypt) e redirecionamento HTTP→HTTPS
- [x] Testes TLS/SSL em conformidade + PQC ativado (SSL.org, DigiCert, SSL Labs)
- [x] Acesso por chave SSH + Fail2Ban (4 tentativas / 24h) na porta 22
- [x] Repositório público no GitHub com conta configurada (2FA/SSH)
- [x] `.gitignore` correto, sem segredos expostos
- [x] Login + página interna + logout, desenvolvido com auxílio de IA
- [x] 3 itens do OWASP Top 10:2025 mitigados e documentados (A01, A05, A07)
- [x] CI/CD automatizado com GitHub Actions
