from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from extensions import db
from models.models import Usuario, Familia, Membro, Role

# Definindo o Blueprint para Cadastro
# As rotas ficarão acessíveis em /cadastro/...
cadastro_bp = Blueprint("cadastro", __name__, url_prefix="/cadastro")

# VCP01 - Cadastro de Usuário
# VCP03 - Criar Família (Implícito no cadastro do Pai)
@cadastro_bp.get("/register")
def register_page():
    """Exibe tela de cadastro."""
    # Nota: Lembre-se de atualizar o action do seu form HTML para 
    # {{ url_for('cadastro.register_submit') }}
    return render_template("register.html")

@cadastro_bp.post("/register")
def register_submit():
    """Processa cadastro de novo usuário (Pai ou Filho)."""
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "PARENT").strip().upper()
    
    # Campo específico para cadastro de filho (email do pai para vincular)
    parent_email = (request.form.get("parent_email") or "").strip().lower() if role == "CHILD" else ""

    if not name or not email or not password:
        flash("Nome, e-mail e senha são obrigatórios.", "error")
        return redirect(url_for("cadastro.register_page"))

    # LÓGICA DE REGISTRO COM BANCO DE DADOS
    # Verifica se o email já existe na tabela 'Usuario'
    usuario_existente = Usuario.query.filter_by(email=email).first()
    if usuario_existente:
        flash("Não foi possível cadastrar (e-mail já existe?).", "error")
        return redirect(url_for("cadastro.register_page"))

    # Criptografa a senha (NUNCA salve a senha pura)
    senha_hash = generate_password_hash(password)

    # Cria o usuário base
    novo_usuario = Usuario(nome=name, email=email, senhaHash=senha_hash)

    try:
        # VCP03 - Se for um PAI, cria a FAMÍLIA junto
        if role == "PARENT":
            nova_familia = Familia(nome=f"Família de {name}")
            novo_membro = Membro(usuario=novo_usuario, familia=nova_familia, role=Role.PARENT)
            
            # Adiciona os 3 novos registros ao banco
            db.session.add(novo_usuario)
            db.session.add(nova_familia)
            db.session.add(novo_membro)

        # Se for um FILHO, ele precisa se juntar à família do PAI existente
        elif role == "CHILD":
            if not parent_email:
                flash("Para se cadastrar como FILHO, o e-mail do PAI é obrigatório.", "error")
                return redirect(url_for("cadastro.register_page"))

            # Encontra o 'Membro' do pai para pegar o ID da família
            parent_user = Usuario.query.filter_by(email=parent_email).first()
            if not parent_user:
                flash("E-mail do PAI não encontrado.", "error")
                return redirect(url_for("cadastro.register_page"))
            
            # Encontra o registro de 'Membro' onde o pai é PAI
            parent_membro = Membro.query.filter(Membro.usuario_id == parent_user.id, Membro.role == Role.PARENT).first()
            if not parent_membro:
                flash("E-mail informado não pertence a uma conta de PAI válida.", "error")
                return redirect(url_for("cadastro.register_page"))

            # Cria o novo Membro (FILHO) na mesma família
            novo_membro = Membro(usuario=novo_usuario, familia_id=parent_membro.familia_id, role=Role.CHILD)
            
            db.session.add(novo_usuario)
            db.session.add(novo_membro)
        
        else:
            flash("Tipo de conta inválido.", "error")
            return redirect(url_for("cadastro.register_page"))

        # Salva tudo no banco de dados
        db.session.commit()

    except Exception as e:
        db.session.rollback() # Desfaz as mudanças se der erro
        flash(f"Erro ao criar conta: {e}", "error")
        return redirect(url_for("cadastro.register_page"))

    flash("Cadastro realizado! Agora faça login.", "success")
    
    # ATENÇÃO: Aqui estou redirecionando para 'login.login_page'.
    # Isso assumirá que o próximo arquivo que criaremos terá o blueprint chamado 'login'.
    return redirect(url_for("login.login_page"))