from flask import Blueprint, render_template, redirect, url_for, session, flash
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from extensions import db
from models.models import (
    Membro, Role, Notificacao, Tarefa, TaskStatus, 
    Submissao, SubmissionStatus, Progresso, Carteira, 
    Transacao, TransactionType,
    ResgateRecompensa, ResgateStatus
)

notificacoes_bp = Blueprint("notificacoes", __name__, url_prefix="/home")

def _get_member(role_required):
    """Retorna o membro logado se corresponder ao papel exigido (PARENT ou CHILD)."""
    uid = session.get("user_id")
    if not uid: return None
    membro = Membro.query.filter_by(usuario_id=uid, role=role_required).first()
    return membro

# ==========================================================
# HOME DO PAI (Dashboard + Aprovações + Notificações)
# ==========================================================
@notificacoes_bp.get("/parent")
def home_parent():
    """
    Exibe o Dashboard do Pai.
    Responsabilidades:
    1. Resumo Financeiro (Total Prometido vs Pago).
    2. Lista de Aprovação (Tarefas que os filhos enviaram).
    3. Feed de Notificações.
    """
    parent_member = _get_member(Role.PARENT)
    if not parent_member:
        return redirect(url_for("login.login_page"))

    filhos = Membro.query.filter_by(familia_id=parent_member.familia_id, role=Role.CHILD).all()
    filhos_ids = [f.id for f in filhos]
    
    total_prometido = 0.0
    total_pago = 0.0
    
    if filhos_ids:
        total_prometido = db.session.query(func.sum(Transacao.valor)).join(Carteira).filter(
            Carteira.membro_id.in_(filhos_ids),
            Transacao.tipo.in_([TransactionType.CREDIT_TASK, TransactionType.CREDIT_ALLOWANCE])
        ).scalar() or 0.0

        total_pago = db.session.query(func.sum(Transacao.valor)).join(Carteira).filter(
            Carteira.membro_id.in_(filhos_ids),
            Transacao.tipo == 'DEBIT_PAYMENT'
        ).scalar() or 0.0

    tarefas_para_avaliar = []
    if filhos_ids:
        tarefas_para_avaliar = Submissao.query.join(Tarefa).filter(
            Tarefa.executor_id.in_(filhos_ids),
            Submissao.status == SubmissionStatus.PENDING
        ).order_by(Submissao.enviadaEm.asc()).all()

    tarefas_pendentes = []
    if filhos_ids:
        tarefas_pendentes = Tarefa.query.filter(
            Tarefa.executor_id.in_(filhos_ids),
            Tarefa.status == TaskStatus.ATIVA
        ).order_by(Tarefa.prazo.asc()).all()

    notificacoes = Notificacao.query.filter_by(
        usuario_id=parent_member.usuario_id, 
        lidaEm=None
    ).order_by(Notificacao.enviadaEm.desc()).all()

    return render_template(
        "parent/home.html", 
        parent_member=parent_member,
        total_prometido=total_prometido,
        total_pago=total_pago,
        tarefas_pendentes=tarefas_pendentes,
        tarefas_para_avaliar=tarefas_para_avaliar, 
        notificacoes=notificacoes
    )

# ==========================================================
# HOME DO FILHO (Dashboard + Foguinho + Notificações)
# ==========================================================
@notificacoes_bp.get("/child")
def home_child():
    """
    Exibe o Dashboard do Filho.
    Responsabilidades:
    1. Status do Jogador (XP, Nível, Streak).
    2. Resumo da Carteira (Ganhos, Perdas, XP Gasto).
    3. Notificações (Lê automaticamente ao abrir).
    """
    child_member = _get_member(Role.CHILD)
    if not child_member:
        return redirect(url_for("login.login_page"))

    if not child_member.progresso:
        db.session.add(Progresso(membro_id=child_member.id))
    if not child_member.carteira:
        db.session.add(Carteira(membro_id=child_member.id, saldo=0))
    db.session.commit()

    progresso = child_member.progresso
    carteira = child_member.carteira

    # 1. Lógica de Notificações (VCP 11)
    notificacoes_db = Notificacao.query.filter_by(
        usuario_id=child_member.usuario_id, 
        lidaEm=None
    ).order_by(Notificacao.enviadaEm.desc()).all()

    unread_count = len(notificacoes_db)
    notificacoes_novas = list(notificacoes_db)

    if notificacoes_db:
        for n in notificacoes_db:
            n.lidaEm = datetime.utcnow()
        db.session.commit()

    current_xp = progresso.xp
    max_xp = 1000
    xp_percent = (current_xp / max_xp) * 100 if max_xp > 0 else 0

    is_streak_active = False
    if progresso.ultimaTarefaEm:
        agora = datetime.utcnow()
        limite_streak = progresso.ultimaTarefaEm + timedelta(hours=24)
        if agora < limite_streak:
            is_streak_active = True

    saldo_atual = carteira.saldo
    
    soma_tarefas = db.session.query(func.sum(Transacao.valor)).filter(
        Transacao.carteira_id == carteira.id,
        Transacao.tipo == TransactionType.CREDIT_TASK
    ).scalar() or 0.0

    
    soma_rejeitadas = db.session.query(func.sum(Tarefa.valorBase)).join(Submissao).filter(
        Tarefa.executor_id == child_member.id,
        Submissao.status == SubmissionStatus.REJECTED
    ).scalar() or 0.0

    soma_xp_gasto = db.session.query(func.sum(ResgateRecompensa.xpPago)).filter(
        ResgateRecompensa.membro_id == child_member.id,
        ResgateRecompensa.status != ResgateStatus.REJECTED
    ).scalar() or 0

    # -----------------------------------------------------------

    tarefas_pendentes = Tarefa.query.filter(
        Tarefa.executor_id == child_member.id,
        Tarefa.status == TaskStatus.ATIVA
    ).order_by(Tarefa.prazo.asc()).all()
    
    tarefas_enviadas = Submissao.query.join(Tarefa).filter(
        Tarefa.executor_id == child_member.id
    ).order_by(Submissao.enviadaEm.desc()).limit(10).all()

    return render_template(
        "child/home.html",
        current_xp=current_xp,
        max_xp=max_xp,
        xp_percent=xp_percent,
        is_streak_active=is_streak_active,
        saldo_atual=saldo_atual,
        soma_tarefas=soma_tarefas,
        
        soma_rejeitadas=soma_rejeitadas, 
        soma_xp_gasto=soma_xp_gasto,
        
        tarefas_pendentes=tarefas_pendentes,
        tarefas_enviadas=tarefas_enviadas,
        notificacoes_novas=notificacoes_novas,
        unread_count=unread_count
    )

# ==========================================================
# GERENCIAMENTO DE NOTIFICAÇÕES (Ações)
# ==========================================================
# VCP11 - Notificações:
@notificacoes_bp.get("/read/<notif_id>")
def mark_read(notif_id):
    """Marca uma notificação específica como lida manualmente."""
    uid = session.get("user_id")
    if not uid: return redirect(url_for("login.login_page"))
    
    n = Notificacao.query.get(notif_id)
    if n and n.usuario_id == uid:
        n.lidaEm = datetime.utcnow()
        db.session.commit()
        
    if session.get("role") == Role.CHILD:
        return redirect(url_for("notificacoes.home_child"))
    return redirect(url_for("notificacoes.home_parent"))

@notificacoes_bp.get("/read_all")
def mark_all_read():
    """Marca todas as notificações do usuário como lidas."""
    uid = session.get("user_id")
    if uid:
        (Notificacao.query
         .filter_by(usuario_id=uid)
         .filter(Notificacao.lidaEm.is_(None))
         .update({Notificacao.lidaEm: datetime.utcnow()}))
        db.session.commit()
        
    if session.get("role") == Role.CHILD:
        return redirect(url_for("notificacoes.home_child"))
    return redirect(url_for("notificacoes.home_parent"))