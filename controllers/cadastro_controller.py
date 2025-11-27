from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from extensions import db
from models.models import Usuario, Familia, Membro, Role

cadastro_bp = Blueprint("cadastro", __name__, url_prefix="/cadastro")

# ===== REGISTER =====
# VCP01 - Cadastro de Usuário:
# Valida campos, cria Usuario, cria Família (quando PARENT),
# cria Membro da família, salva no banco.
# VCP03 - Criar Família:
# Já criado no registro do PAI; aqui o parent_controller usa familia_id
# para carregar filhos, tarefas e recompensas.
@cadastro_bp.get("/register")
def register_page():
    """Exibe tela de cadastro."""
    return render_template("register.html")

@cadastro_bp.post("/register")
def register_submit():
    """Processa cadastro de novo usuário (Pai ou Filho)."""
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "PARENT").strip().upper()
    
    parent_email = (request.form.get("parent_email") or "").strip().lower() if role == "CHILD" else ""

    if not name or not email or not password:
        flash("Nome, e-mail e senha são obrigatórios.", "error")
        return redirect(url_for("cadastro.register_page"))

    usuario_existente = Usuario.query.filter_by(email=email).first()
    if usuario_existente:
        flash("Não foi possível cadastrar (e-mail já existe?).", "error")
        return redirect(url_for("cadastro.register_page"))

    senha_hash = generate_password_hash(password)

    novo_usuario = Usuario(nome=name, email=email, senhaHash=senha_hash)

    try:
        # VCP03 - Se for um PAI, cria a FAMÍLIA junto
        if role == "PARENT":
            nova_familia = Familia(nome=f"Família de {name}")
            novo_membro = Membro(usuario=novo_usuario, familia=nova_familia, role=Role.PARENT)
            
            db.session.add(novo_usuario)
            db.session.add(nova_familia)
            db.session.add(novo_membro)

        elif role == "CHILD":
            if not parent_email:
                flash("Para se cadastrar como FILHO, o e-mail do PAI é obrigatório.", "error")
                return redirect(url_for("cadastro.register_page"))

            parent_user = Usuario.query.filter_by(email=parent_email).first()
            if not parent_user:
                flash("E-mail do PAI não encontrado.", "error")
                return redirect(url_for("cadastro.register_page"))
            
            parent_membro = Membro.query.filter(Membro.usuario_id == parent_user.id, Membro.role == Role.PARENT).first()
            if not parent_membro:
                flash("E-mail informado não pertence a uma conta de PAI válida.", "error")
                return redirect(url_for("cadastro.register_page"))

            novo_membro = Membro(usuario=novo_usuario, familia_id=parent_membro.familia_id, role=Role.CHILD)
            
            db.session.add(novo_usuario)
            db.session.add(novo_membro)
        
        else:
            flash("Tipo de conta inválido.", "error")
            return redirect(url_for("cadastro.register_page"))

        db.session.commit()

    except Exception as e:
        db.session.rollback() 
        flash(f"Erro ao criar conta: {e}", "error")
        return redirect(url_for("cadastro.register_page"))

    flash("Cadastro realizado! Agora faça login.", "success")
    
    return redirect(url_for("login.login_page"))