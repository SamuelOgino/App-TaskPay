from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from uuid import uuid4
from extensions import db
from models.models import Membro, Role, Recompensa, Notificacao

# Blueprint para Criação de Recompensas
criarrecompensa_bp = Blueprint("criarrecompensa", __name__, url_prefix="/rewards")

# --- Auxiliar de Segurança ---
def _get_parent_member():
    uid = session.get("user_id")
    role = session.get("role")
    if not uid or role != Role.PARENT: return None
    return Membro.query.filter_by(usuario_id=uid, role=Role.PARENT).first()

# ==========================================================
# VCP 13 - CRIAR RECOMPENSA (Ação exclusiva do Pai)
# ==========================================================

@criarrecompensa_bp.get("/new")
def new_reward_page():
    """Exibe o formulário para cadastrar uma nova recompensa."""
    parent_member = _get_parent_member()
    if not parent_member:
        flash("Acesso negado.", "error")
        return redirect(url_for("login.login_page"))
        
    return render_template("parent/new_reward.html")

@criarrecompensa_bp.post("/new")
def create_reward():
    """Processa a criação da recompensa e notifica os filhos."""
    parent_member = _get_parent_member()
    if not parent_member:
        return redirect(url_for("login.login_page"))
    
    # 1. Captura dados do formulário
    titulo = (request.form.get("titulo") or "").strip()
    descricao = (request.form.get("descricao") or "").strip()
    custoXP_str = request.form.get("custoXP") or "0"
    
    # 2. Validações
    if not titulo:
        flash("Informe o título da recompensa.", "error")
        return redirect(url_for("criarrecompensa.new_reward_page"))
    
    try:
        custoXP = int(custoXP_str)
    except:
        custoXP = 0
        
    try:
        # 3. Cria a Recompensa
        recompensa = Recompensa(
            id=str(uuid4()), # Gera ID único
            titulo=titulo,
            descricao=descricao,
            custoXP=custoXP,
            ativa=True,
            familia_id=parent_member.familia_id,
            criador_id=parent_member.id
        )
        db.session.add(recompensa)
        
        # 4. Notifica todos os filhos da família
        filhos = Membro.query.filter_by(familia_id=parent_member.familia_id, role=Role.CHILD).all()
        for f in filhos:
            notif = Notificacao(
                tipo="NOVA_RECOMPENSA",
                mensagem=f"Nova recompensa disponível: {recompensa.titulo} ({recompensa.custoXP} XP)",
                usuario_id=f.usuario_id
            )
            db.session.add(notif)
            
        db.session.commit()
        flash("Recompensa criada com sucesso!", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao criar recompensa: {e}", "error")
        return redirect(url_for("criarrecompensa.new_reward_page"))

    # Redireciona para o gerenciador de recompensas (arquivo resgatarrecompensa_controller)
    return redirect(url_for("resgatar.manage_page"))