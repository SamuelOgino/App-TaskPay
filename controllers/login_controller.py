from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from models.models import Usuario, Membro

login_bp = Blueprint("login", __name__, url_prefix="/login")


# ===== LOGIN =====
# VCP02 - Login:
# Verifica email/senha, identifica se é PARENT ou CHILD,
# cria sessão e redireciona para home correspondente.
@login_bp.get("/")
def login_page():
    """Tela inicial de escolha ou login principal."""
    return render_template("login.html") 

@login_bp.get("/child")
def login_child_page():
    """Tela de login exclusiva dos filhos."""
    return render_template("child/login_child.html")

@login_bp.get("/parent")
def login_parent_page():
    """Tela de login exclusiva dos pais."""
    return render_template("parent/login_parent.html")

@login_bp.post("/submit")
def login_submit():
    """Processa login de pai ou filho."""
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "PARENT").strip().upper() # PARENT ou CHILD

    if not email or not password:
        flash("Informe e-mail e senha.", "error")
        return redirect(url_for("login.login_child_page") if role == "CHILD" else url_for("login.login_parent_page"))

    usuario = Usuario.query.filter_by(email=email).first()

    if not usuario or not check_password_hash(usuario.senhaHash, password):
        flash("Credenciais inválidas (e-mail ou senha).", "error")
        return redirect(url_for("login.login_child_page") if role == "CHILD" else url_for("login.login_parent_page"))

    membro = Membro.query.filter_by(usuario_id=usuario.id, role=role).first()
    
    if not membro:
        flash("Tipo de conta não corresponde ao cadastro desse e-mail.", "error")
        return redirect(url_for("login.login_child_page") if role == "CHILD" else url_for("login.login_parent_page"))

    session["user_id"] = usuario.id
    session["user_email"] = usuario.email
    session["name"] = usuario.nome
    session["role"] = membro.role
    session["membro_id"] = membro.id
    session["familia_id"] = membro.familia_id
    
    if membro.role == "CHILD":
        return redirect(url_for("notificacoes.home_child")) 
    else:
        return redirect(url_for("notificacoes.home_parent")) 

@login_bp.get("/logout")
def logout():
    """Limpa a sessão e volta para login."""
    session.clear()
    return redirect(url_for("login.login_page"))