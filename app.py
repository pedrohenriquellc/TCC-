"""
Projeto Aplicado: Práticas de Mercado — Protótipo Web Seguro (Eixo 3)
=====================================================================

Aplicação Flask mínima (Login -> Página interna -> Logout) construída sob
os princípios de Secure by Design e Secure by Default.

Mitigações OWASP Top 10:2025 documentadas e implementadas neste arquivo:

  * A01:2025 - Broken Access Control
      -> Decorator @login_required protege a rota interna (/dashboard).
         Sem sessão autenticada o acesso é negado e redirecionado ao login.

  * A07:2025 - Authentication Failures
      -> Senha NUNCA fica em texto puro: guardamos apenas o hash
         (Werkzeug, algoritmo scrypt por padrão). Comparação resistente a timing.
      -> Rate limiting (Flask-Limiter) freia ataques de força bruta
         na rota de login. Cookies de sessão com HttpOnly, Secure e SameSite.

  * A05:2025 - Injection (inclui XSS)
      -> Autoescape do Jinja2 mantido ligado (saída sempre escapada).
      -> Validação/allowlist de entrada no formulário de login.
      -> Proteção CSRF (Flask-WTF) em todas as requisições POST.

  Bônus — A02:2025 - Security Misconfiguration
      -> Cabeçalhos de segurança (CSP, X-Frame-Options, HSTS, etc.),
         DEBUG desligado por padrão e SECRET_KEY vindo de variável de
         ambiente (nunca hardcoded no repositório).
"""

import os
import re
import secrets

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort,
)
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env em desenvolvimento (o .env NÃO vai para o Git).
load_dotenv()

app = Flask(__name__)

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO SEGURA (Secure by Default)
# ---------------------------------------------------------------------------
# SECRET_KEY vem do ambiente. Se estiver ausente (ex.: dev local), geramos uma
# aleatória — mas em produção ela DEVE ser fixada via variável de ambiente,
# senão as sessões expiram a cada restart.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# Cookies de sessão endurecidos (A07 / A02):
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,   # JS não lê o cookie -> reduz roubo por XSS
    SESSION_COOKIE_SAMESITE="Lax",  # mitiga CSRF em navegação cross-site
    # Secure=True exige HTTPS. Em produção o Nginx serve via HTTPS, então
    # ativamos por padrão; permite desligar em dev local via FLASK_INSECURE=1.
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_INSECURE") != "1",
)

# Proteção CSRF global para formulários (A05 / A08).
csrf = CSRFProtect(app)

# Rate limiting: por padrão limita, e a rota de login recebe limite estrito.
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "60 per hour"],
    storage_uri="memory://",
)

# ---------------------------------------------------------------------------
# "BANCO" DE USUÁRIOS EM MEMÓRIA
# ---------------------------------------------------------------------------
# O briefing NÃO exige banco de dados. Guardamos um usuário demo com a senha
# ARMAZENADA COMO HASH (nunca em texto puro). A senha inicial pode ser definida
# por variável de ambiente DEMO_PASSWORD; caso ausente, usa um padrão de
# demonstração (troque em produção!).
_DEMO_USER = os.environ.get("DEMO_USER", "admin")
_DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "SenhaForte#2026")

USERS = {
    _DEMO_USER: generate_password_hash(_DEMO_PASSWORD),
}

# Allowlist de caracteres para o campo usuário (A05 - validação de entrada).
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


# ---------------------------------------------------------------------------
# CONTROLE DE ACESSO (A01:2025 - Broken Access Control)
# ---------------------------------------------------------------------------
def login_required(view):
    """Nega acesso a rotas internas quando não há sessão autenticada."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            flash("Faça login para acessar essa página.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


# ---------------------------------------------------------------------------
# CABEÇALHOS DE SEGURANÇA (A02:2025 - Security Misconfiguration)
# ---------------------------------------------------------------------------
@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; "
        "img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'"
    )
    # HSTS: força HTTPS por 1 ano (o Nginx também redireciona 80 -> 443).
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    return response


# ---------------------------------------------------------------------------
# ROTAS
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if session.get("user"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])  # A07: freia brute force
def login():
    if session.get("user"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        # A05: valida a entrada antes de qualquer processamento.
        if not USERNAME_RE.match(username):
            flash("Usuário ou senha inválidos.", "danger")
            return render_template("login.html"), 400

        stored_hash = USERS.get(username)
        # check_password_hash faz comparação resistente a timing (A07).
        # Mesmo quando o usuário não existe, computamos um hash falso para
        # não vazar por diferença de tempo se o usuário existe ou não.
        if stored_hash is None:
            check_password_hash(
                generate_password_hash("dummy"), password
            )
            flash("Usuário ou senha inválidos.", "danger")
            return render_template("login.html"), 401

        if check_password_hash(stored_hash, password):
            # Regenera a sessão para evitar session fixation (A07).
            session.clear()
            session["user"] = username
            session.permanent = False
            flash("Login realizado com sucesso.", "success")
            return redirect(url_for("dashboard"))

        flash("Usuário ou senha inválidos.", "danger")
        return render_template("login.html"), 401

    return render_template("login.html")


@app.route("/dashboard")
@login_required  # A01: rota interna protegida
def dashboard():
    return render_template("dashboard.html", user=session.get("user"))


@app.route("/logout", methods=["POST"])  # POST + CSRF token => evita CSRF logout
@login_required
def logout():
    session.clear()
    flash("Você saiu com segurança.", "success")
    return redirect(url_for("login"))


@app.route("/healthz")
def healthz():
    """Endpoint simples para checagem de saúde (usado no CI/CD)."""
    return {"status": "ok"}, 200


# ---------------------------------------------------------------------------
# TRATAMENTO DE ERROS (A10:2025 - Mishandling of Exceptional Conditions)
# ---------------------------------------------------------------------------
@app.errorhandler(429)
def ratelimit_handler(e):
    return render_template("login.html", rate_limited=True), 429


@app.errorhandler(404)
def not_found(e):
    return redirect(url_for("login"))


if __name__ == "__main__":
    # DEBUG desligado por padrão (A02). Escuta só localhost: em produção o
    # Nginx faz proxy reverso para 127.0.0.1:8000, então nada é exposto direto.
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(host="127.0.0.1", port=8000, debug=debug)
