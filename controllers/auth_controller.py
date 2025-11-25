# Em controllers/auth_controller.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- 1. NOVAS IMPORTAÇÕES ---
from models.models import Usuario, Familia, Membro, Role # Importe suas classes!
from extensions import db # Importe o 'db'
bp = Blueprint("auth", __name__, url_prefix="/auth")

# ===== LOGIN =====
@bp.get("/login")
def login_page():
    """Tela inicial de login (pais)."""
    return render_template("login.html") 

@bp.get("/login/child")
def login_child_page():
    """Tela de login exclusiva dos filhos."""
    return render_template("child/login_child.html")

@bp.get("/login/parent")
def login_parent_page():
    """Tela de login exclusiva dos pais."""
    return render_template("parent/login_parent.html")

@bp.post("/login")
def login_submit():
    """Processa login de pai ou filho."""
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "PARENT").strip().upper() # PARENT ou CHILD

    # Valida campos
    if not email or password is None:
        flash("Informe e-mail e senha.", "error")
        return redirect(url_for("auth.login_child_page") if role == "CHILD" else url_for("auth.login_parent_page"))

    # 1. Encontre o 'Usuario' pelo email
    usuario = Usuario.query.filter_by(email=email).first()

    # 2. Verifique se o usuário existe E se a senha bate
    if not usuario or not check_password_hash(usuario.senhaHash, password):
        flash("Credenciais inválidas (e-mail ou senha).", "error")
        return redirect(url_for("auth.login_child_page") if role == "CHILD" else url_for("auth.login_parent_page"))

    # 3. Verifique se o usuário tem um 'Membro' com o 'role' que ele está tentando logar
    # (Seu diagrama permite que um usuário seja PAI em uma família e FILHO em outra)
    membro = Membro.query.filter_by(usuario_id=usuario.id, role=role).first()
    
    if not membro:
        flash("Tipo de conta não corresponde ao cadastro desse e-mail.", "error")
        return redirect(url_for("auth.login_child_page") if role == "CHILD" else url_for("auth.login_parent_page"))

    # 4. Login OK! Guarda tudo na sessão
    session["user_id"] = usuario.id
    session["user_email"] = usuario.email
    session["name"] = usuario.nome
    session["role"] = membro.role
    session["membro_id"] = membro.id
    session["familia_id"] = membro.familia_id

    # Envia para a home correta
    if membro.role == "CHILD":
        return redirect(url_for("child.home"))
    else:
        return redirect(url_for("parent.home"))


# ===== LOGOUT =====
@bp.get("/logout")
def logout():
    """Limpa a sessão e volta para login."""
    session.clear()
    return redirect(url_for("auth.login_page"))


# ===== REGISTER =====
@bp.get("/register")
def register_page():
    """Exibe tela de cadastro."""
    return render_template("register.html")


@bp.post("/register")
def register_submit():
    """Processa cadastro de novo usuário."""
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "PARENT").strip().upper()
    parent_email = (request.form.get("parent_email") or "").strip().lower() if role == "CHILD" else ""


    if not name or not email or not password:
        flash("Nome, e-mail e senha são obrigatórios.", "error")
        return redirect(url_for("auth.register_page"))

    # --- 4. LÓGICA DE REGISTRO COM BANCO DE DADOS ---

    # 1. Verifica se o email já existe na tabela 'Usuario'
    usuario_existente = Usuario.query.filter_by(email=email).first()
    if usuario_existente:
        flash("Não foi possível cadastrar (e-mail já existe?).", "error")
        return redirect(url_for("auth.register_page"))

    # 2. Criptografa a senha (NUNCA salve a senha pura)
    senha_hash = generate_password_hash(password)

    # 3. Cria o usuário
    novo_usuario = Usuario(nome=name, email=email, senhaHash=senha_hash)

    try:
        # Se for um PAI, ele cria uma nova Família e um Membro para si
        if role == "PARENT":
            nova_familia = Familia(nome=f"Família de {name}")
            novo_membro = Membro(usuario=novo_usuario, familia=nova_familia, role=Role.PARENT)
            
            # Adiciona os 3 novos registros ao banco
            db.session.add(novo_usuario)
            db.session.add(nova_familia)
            db.session.add(novo_membro)

        # Se for um FILHO, ele precisa se juntar à família do PAI
        elif role == "CHILD":
            if not parent_email:
                flash("Para se cadastrar como FILHO, o e-mail do PAI é obrigatório.", "error")
                return redirect(url_for("auth.register_page"))

            # Encontra o 'Membro' do pai para pegar o ID da família
            parent_user = Usuario.query.filter_by(email=parent_email).first()
            if not parent_user:
                flash("E-mail do PAI não encontrado.", "error")
                return redirect(url_for("auth.register_page"))
            
            # Encontra o registro de 'Membro' onde o pai é PAI
            parent_membro = Membro.query.filter(Membro.usuario_id == parent_user.id, Membro.role == Role.PARENT).first()
            if not parent_membro:
                flash("E-mail do PAI não é uma conta de PAI válida.", "error")
                return redirect(url_for("auth.register_page"))

            # Cria o novo Membro (FILHO) na mesma família
            novo_membro = Membro(usuario=novo_usuario, familia_id=parent_membro.familia_id, role=Role.CHILD)
            
            db.session.add(novo_usuario)
            db.session.add(novo_membro)
        
        else:
            flash("Tipo de conta inválido.", "error")
            return redirect(url_for("auth.register_page"))

        # 4. Salva tudo no banco de dados!
        db.session.commit()

    except Exception as e:
        db.session.rollback() # Desfaz as mudanças se der erro
        flash(f"Erro ao criar conta: {e}", "error")
        return redirect(url_for("auth.register_page"))

    flash("Cadastro realizado! Agora faça login.", "success")
    return redirect(url_for("auth.login_page"))