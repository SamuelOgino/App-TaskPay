from flask import Blueprint, render_template, redirect, url_for, session, flash
from sqlalchemy.sql import or_, and_
from datetime import datetime, timedelta
from extensions import db
from models.models import (
    Membro, Role, Recompensa, ResgateRecompensa, ResgateStatus, Notificacao
)

# Blueprint para Resgate e Gerenciamento de Recompensas
resgatar_bp = Blueprint("resgatar", __name__, url_prefix="/rewards")

# --- Auxiliar ---
def _get_current_member():
    uid = session.get("user_id")
    role = session.get("role")
    if not uid or not role: return None
    return Membro.query.filter_by(usuario_id=uid, role=role).first()

# ==========================================================
# ÁREA DO FILHO (Loja e Resgate)
# ==========================================================

@resgatar_bp.get("/shop")
def shop_page():
    """
    Exibe a Loja de Recompensas para o Filho.
    Mostra itens disponíveis e o histórico recente.
    """
    membro = _get_current_member()
    if not membro or membro.role != Role.CHILD:
        return redirect(url_for("login.login_page"))
    
    # 1. Busca Histórico (Regra das 36h)
    limite_tempo = datetime.utcnow() - timedelta(hours=36)
    historico_resgates = db.session.query(ResgateRecompensa).filter(
        ResgateRecompensa.membro_id == membro.id,
        or_(
            ResgateRecompensa.status == ResgateStatus.PENDING,
            and_(
                ResgateRecompensa.status.in_([ResgateStatus.DELIVERED, ResgateStatus.REJECTED]),
                ResgateRecompensa.criadoEm >= limite_tempo
            )
        )
    ).order_by(ResgateRecompensa.criadoEm.desc()).all()
    
    # 2. Filtra a Loja (Esconde o que já foi pedido pela família toda e ainda está ativo)
    resgates_familia = db.session.query(ResgateRecompensa.recompensa_id)\
        .join(Membro, ResgateRecompensa.membro_id == Membro.id)\
        .filter(Membro.familia_id == membro.familia_id)\
        .all()
    ids_esconder = [r.recompensa_id for r in resgates_familia]
    
    query_loja = Recompensa.query.filter_by(familia_id=membro.familia_id, ativa=True)
    if ids_esconder:
        query_loja = query_loja.filter(Recompensa.id.notin_(ids_esconder))
        
    recompensas_disponiveis = query_loja.order_by(Recompensa.custoXP.asc()).all()
    
    return render_template(
        "child/rewards.html",
        membro=membro,
        saldo_atual=membro.carteira.saldo if membro.carteira else 0,
        xp_atual=membro.saldoXP,
        historico_resgates=historico_resgates, 
        recompensas=recompensas_disponiveis,
        now=datetime.utcnow(),
        plano_atual=membro.familia.plano
    )

@resgatar_bp.post("/redeem/<recompensa_id>")
def redeem_reward(recompensa_id):
    """
    Ação do Filho: Gastar XP para pedir uma recompensa.
    """
    membro = _get_current_member()
    if not membro or membro.role != Role.CHILD:
        return redirect(url_for("login.login_page"))
    
    recompensa = db.session.get(Recompensa, recompensa_id)
    
    # Validações
    if not recompensa or recompensa.familia_id != membro.familia_id:
        flash("Recompensa inválida.", "error")
        return redirect(url_for("resgatar.shop_page"))
        
    if (membro.saldoXP or 0) < recompensa.custoXP:
        flash(f"XP insuficiente. Você precisa de {recompensa.custoXP} XP.", "error")
        return redirect(url_for("resgatar.shop_page"))
        
    try:
        # 1. Deduz o XP (Pagamento antecipado)
        membro.saldoXP -= recompensa.custoXP
        
        # 2. Cria o registro de resgate
        resgate = ResgateRecompensa(
            recompensa_id=recompensa.id,
            membro_id=membro.id,
            xpPago=recompensa.custoXP,
            status=ResgateStatus.PENDING
        )
        db.session.add(resgate)
        
        # 3. Notifica os pais
        pais = Membro.query.filter_by(familia_id=membro.familia_id, role=Role.PARENT).all()
        for pai in pais:
            notif = Notificacao(
                tipo="NOVO_RESGATE",
                mensagem=f"{membro.usuario.nome} resgatou '{recompensa.titulo}'!",
                usuario_id=pai.usuario_id
            )
            db.session.add(notif)
            
        db.session.commit()
        flash(f"Pedido de '{recompensa.titulo}' enviado!", "success")
        
    except Exception as e:
        db.session.rollback()
        flash("Erro ao processar resgate.", "error")
        
    return redirect(url_for("resgatar.shop_page"))


# ==========================================================
# ÁREA DO PAI (Gerenciamento e Entrega)
# ==========================================================

@resgatar_bp.get("/manage")
def manage_page():
    """
    Exibe a lista de pedidos de recompensa para o Pai (Pendentes e Histórico).
    """
    membro = _get_current_member()
    if not membro or membro.role != Role.PARENT:
        return redirect(url_for("login.login_page"))
    
    filhos = Membro.query.filter_by(familia_id=membro.familia_id, role=Role.CHILD).all()
    
    # 1. Resumo de XP para o cabeçalho
    xp_por_filho = [{
        "id": f.id, "nome": f.usuario.nome, 
        "xp": (f.saldoXP or 0), "avatar": f.usuario.avatarUrl
    } for f in filhos]
    
    # 2. Recompensas Ativas (Disponíveis para compra) - Apenas visualização
    # (Similar à lógica do filho, esconde as que já foram resgatadas)
    resgates_familia = db.session.query(ResgateRecompensa.recompensa_id)\
        .join(Membro, ResgateRecompensa.membro_id == Membro.id)\
        .filter(Membro.familia_id == membro.familia_id).all()
    ids_ja_resgatados = [r.recompensa_id for r in resgates_familia]
    
    query_ativas = Recompensa.query.filter_by(familia_id=membro.familia_id, ativa=True)
    if ids_ja_resgatados:
        query_ativas = query_ativas.filter(Recompensa.id.notin_(ids_ja_resgatados))
    ativas = query_ativas.order_by(Recompensa.criadoEm.desc()).all()
    
    # 3. Histórico de Pedidos (Onde o pai clica para entregar)
    limite_tempo = datetime.utcnow() - timedelta(hours=36)
    historico = (ResgateRecompensa.query
        .join(Membro).join(Recompensa)
        .filter(Membro.familia_id == membro.familia_id)
        .filter(or_(
            ResgateRecompensa.status == ResgateStatus.PENDING,
            ResgateRecompensa.criadoEm >= limite_tempo
        ))
        .order_by(ResgateRecompensa.criadoEm.desc()).all()
    )

    return render_template(
        "parent/rewards.html",
        filhos=filhos,
        xp_por_filho=xp_por_filho,
        ativas=ativas,
        historico=historico,
        plano_atual=membro.familia.plano
    )

@resgatar_bp.get("/deliver/<resgate_id>")
def deliver_reward(resgate_id):
    """
    Ação do Pai: Marcar como ENTREGUE.
    Confirma que o filho recebeu o prêmio. O XP já foi gasto.
    """
    parent = _get_current_member()
    if not parent or parent.role != Role.PARENT: return redirect(url_for("login.login_page"))
    
    resgate = db.session.get(ResgateRecompensa, resgate_id)
    if not resgate or resgate.membro.familia_id != parent.familia_id:
        return redirect(url_for("resgatar.manage_page"))

    try:
        resgate.status = ResgateStatus.DELIVERED
        
        notif = Notificacao(
            tipo="RECOMPENSA_ENTREGUE",
            mensagem=f"Sua recompensa '{resgate.recompensa.titulo}' foi entregue!",
            usuario_id=resgate.membro.usuario_id
        )
        db.session.add(notif)
        db.session.commit()
        flash("Recompensa entregue!", "success")
    except Exception:
        db.session.rollback()
        
    return redirect(url_for("resgatar.manage_page"))

@resgatar_bp.get("/reject/<resgate_id>")
def reject_reward(resgate_id):
    """
    Ação do Pai: REJEITAR pedido.
    IMPORTANTE: Devolve o XP gasto para a conta do filho.
    """
    parent = _get_current_member()
    if not parent or parent.role != Role.PARENT: return redirect(url_for("login.login_page"))
    
    resgate = db.session.get(ResgateRecompensa, resgate_id)
    if not resgate or resgate.membro.familia_id != parent.familia_id:
        return redirect(url_for("resgatar.manage_page"))
        
    if resgate.status != ResgateStatus.PENDING:
        flash("Já processado.", "warning")
        return redirect(url_for("resgatar.manage_page"))

    try:
        # 1. Marca rejeitado
        resgate.status = ResgateStatus.REJECTED
        
        # 2. REEMBOLSO DE XP
        filho = resgate.membro
        filho.saldoXP = (filho.saldoXP or 0) + resgate.xpPago
        
        # 3. Notifica
        notif = Notificacao(
            tipo="RECOMPENSA_REJEITADA",
            mensagem=f"Pedido de '{resgate.recompensa.titulo}' cancelado. {resgate.xpPago} XP devolvidos.",
            usuario_id=filho.usuario_id
        )
        db.session.add(notif)
        db.session.commit()
        flash(f"Rejeitado. XP devolvido para {filho.usuario.nome}.", "success")
    except Exception:
        db.session.rollback()
        
    return redirect(url_for("resgatar.manage_page"))