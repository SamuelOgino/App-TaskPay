from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from models.models import Usuario, Membro

# Define o Blueprint 'login'
login_bp = Blueprint("login", __name__, url_prefix="/login")


# ===== LOGIN =====
# VCP02 - Login:
# Verifica email/senha, identifica se é PARENT ou CHILD,
# cria sessão e redireciona para home correspondente.
@login_bp.get("/")
def login_page():
    """Tela inicial de escolha ou login principal."""
    # Nota: Verifique se o seu template se chama 'login.html' mesmo
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

    # Valida campos
    if not email or not password:
        flash("Informe e-mail e senha.", "error")
        # Redireciona de volta para a tela específica
        return redirect(url_for("login.login_child_page") if role == "CHILD" else url_for("login.login_parent_page"))

    # Encontre o 'Usuario' pelo email
    usuario = Usuario.query.filter_by(email=email).first()

    # Verifique se o usuário existe E se a senha bate
    if not usuario or not check_password_hash(usuario.senhaHash, password):
        flash("Credenciais inválidas (e-mail ou senha).", "error")
        return redirect(url_for("login.login_child_page") if role == "CHILD" else url_for("login.login_parent_page"))

    # Verifique se o usuário tem um 'Membro' com o 'role' que ele está tentando logar
    membro = Membro.query.filter_by(usuario_id=usuario.id, role=role).first()
    
    if not membro:
        flash("Tipo de conta não corresponde ao cadastro desse e-mail.", "error")
        return redirect(url_for("login.login_child_page") if role == "CHILD" else url_for("login.login_parent_page"))

    # Login OK! Guarda tudo na sessão
    session["user_id"] = usuario.id
    session["user_email"] = usuario.email
    session["name"] = usuario.nome
    session["role"] = membro.role
    session["membro_id"] = membro.id
    session["familia_id"] = membro.familia_id

    # Envia para a home correta
    # ATENÇÃO: Aqui estamos assumindo que ainda vamos criar os controllers
    # 'notificacoes_controller' (para home do pai/filho) ou manteremos nomes temporários.
    # Baseado na sua lista, não existe um 'HOME_CONTROLLER', então assumirei
    # que a home do pai está no controller de Notificações ou Carteira? 
    # NA VERDADE: Geralmente a Home fica num 'dashboard' ou no próprio controller principal do ator.
    # Como você não listou um 'HOME_CONTROLLER', vou apontar para onde estavam:
    
    if membro.role == "CHILD":
        # Vamos ter que definir onde fica a 'home' do filho.
        # No seu código antigo era child.home. 
        # Vou apontar para 'notificacoes.home_child' ou similar futuramente.
        # Por enquanto, vou manter o padrão antigo para não quebrar a lógica mental,
        # mas teremos que decidir em qual arquivo a HOME vai ficar.
        # Sugestão: A Home do filho tem muitas notificações, talvez 'notificacoes_controller'?
        return redirect(url_for("notificacoes.home_child")) 
    else:
        return redirect(url_for("notificacoes.home_parent")) 

# ===== LOGOUT =====
@login_bp.get("/logout")
def logout():
    """Limpa a sessão e volta para login."""
    session.clear()
    return redirect(url_for("login.login_page"))