# 🔐 Projeto Aplicado: Práticas de Mercado — Protótipo Web Seguro

Relatório técnico da entrega. O projeto simula um ambiente de mercado real
aplicando **Secure by Design** e **Secure by Default** em todo o ciclo de vida
da aplicação, integrando **infraestrutura em nuvem**, **versionamento**,
**desenvolvimento** e um **pipeline de CI/CD**.

- **Aplicação no ar:** `https://SEU_IP_PUBLICO/`  *(substitua pelo IP da sua VM)*
- **Stack:** Python 3.12 · Flask · Gunicorn · Nginx · Ubuntu Server · Oracle Cloud (Free Tier)

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
└── deploy/                    # Configs do servidor
    ├── nginx-projeto-seguro.conf
    ├── projeto-seguro.service
    └── fail2ban-jail.local
```

---

## 💻 Eixo 3 — Desenvolvimento e mitigações OWASP Top 10:2025

O protótipo possui **tela de login**, **página interna protegida** (`/dashboard`)
e **logout funcional**, e mitiga ativamente **3 categorias** do
[OWASP Top 10:2025](https://top10.owasp.org/2025/). O código foi escrito e
auditado com assistência de IA (fluxo de desenvolvimento moderno).

### ✅ A01:2025 — Broken Access Control
**Onde:** `app.py` → decorator `login_required` + rota `/dashboard`.
**Como:** a página interna só é servida quando existe uma sessão autenticada
(`session["user"]`). Qualquer acesso direto a `/dashboard` sem login é negado e
redirecionado para `/login`. O logout usa **POST + token CSRF**, evitando logout
forçado por terceiros.

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

### ✅ A05:2025 — Injection (inclui XSS)
**Onde:** `app.py` (validação/allowlist + CSRF) e `templates/*.html`.
**Como:**
- **Validação de entrada por allowlist** no campo usuário
  (`^[A-Za-z0-9_.-]{3,32}$`) — entradas maliciosas são rejeitadas (HTTP 400).
- **Autoescape do Jinja2** mantido ligado: toda saída dinâmica é escapada,
  neutralizando **XSS refletido**.
- **Proteção CSRF** (`Flask-WTF`) obrigatória em todos os POST.

> **Bônus — A02:2025 (Security Misconfiguration):** cabeçalhos de segurança
> (`Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`,
> `Strict-Transport-Security`), `DEBUG` desligado por padrão e `SECRET_KEY`
> lido de variável de ambiente (nunca hardcoded).

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

Passo a passo detalhado em **[`docs/GUIA-INFRAESTRUTURA.md`](docs/GUIA-INFRAESTRUTURA.md)**.
Resumo dos controles de segurança implementados:

| Requisito | Implementação |
|---|---|
| SO | Ubuntu Server (última versão estável, com OpenSSL 3.5+ para PQC) |
| Servidor web | Nginx como proxy reverso para o Gunicorn |
| Acesso remoto | **Somente chave SSH** — `PasswordAuthentication no` |
| Firewall (least privilege) | Só as portas 80, 443 e 22 abertas (Security List + UFW) |
| Fail2Ban | Porta 22 protegida: **4 tentativas / banimento de 24h** (`deploy/fail2ban-jail.local`) |
| HTTPS | **Certbot 5.4+** com certificado de **IP** da Let's Encrypt (perfil `shortlived`), **autorrenovação** ativa |
| Redirecionamento | Todo tráfego **HTTP → HTTPS** (bloco 80 do Nginx) |
| PQC | `ssl_ecdh_curve X25519MLKEM768:...` (ML-KEM híbrido, OpenSSL 3.5) |

### 🧪 Verificação de conformidade TLS/SSL (uso de IP)
- [SSL.org — SSL Certificate Checker](https://www.ssl.org/): deve exibir
  **Certificate Trusted: YES** e **Algorithm / Key Type & Size: Good signature ·
  Acceptable key**.
- [DigiCert — TLS quantum readiness check](https://www.digicert.com/pqc-checker):
  deve confirmar **suporte a PQC ativado**.

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

Arquivo: **`.github/workflows/deploy.yml`**. A cada `git push origin main`:

1. **test** — instala dependências, valida a aplicação e roda auditoria de
   dependências (`pip-audit`, mitigando **A03:2025 — Software Supply Chain**).
2. **deploy** — conecta na VM via **SSH** (credenciais em **Secrets**), atualiza
   o código (`git reset --hard origin/main`), reinstala dependências e reinicia
   o serviço (`systemctl restart projeto-seguro`).
3. **health check** — valida `https://SEU_IP_PUBLICO/healthz` após o deploy.

**Secrets configurados no GitHub:** `SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY`,
`SSH_PORT` — nenhuma chave exposta no `.yml`.

---

## ✅ Checklist de entrega

- [x] Aplicação web no ar via IP público (Eixo 1)
- [x] Nginx com HTTPS (Certbot/Let's Encrypt) e redirecionamento HTTP→HTTPS
- [x] Testes TLS/SSL em conformidade + PQC ativado
- [x] Acesso por chave SSH + Fail2Ban (4 tentativas / 24h) na porta 22
- [x] Repositório público no GitHub com conta configurada (2FA/SSH)
- [x] `.gitignore` correto, sem segredos expostos
- [x] Login + página interna + logout, desenvolvido com auxílio de IA
- [x] 3 itens do OWASP Top 10:2025 mitigados e documentados (A01, A07, A05)
- [x] CI/CD automatizado com GitHub Actions
