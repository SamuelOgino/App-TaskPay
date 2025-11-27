from flask import Blueprint, render_template, redirect, url_for, session, flash
from extensions import db
from models.models import Membro, Role

melhorarplano_bp = Blueprint("melhorarplano", __name__, url_prefix="/plans")

def _get_parent_member():
    """Garante que quem está acessando é um PAI."""
    uid = session.get("user_id")
    role = session.get("role")
    if not uid or role != Role.PARENT: return None
    return Membro.query.filter_by(usuario_id=uid, role=Role.PARENT).first()

# ==========================================================
# VCP12 - MELHORAR PLANO (Upgrade para PRO)
# ==========================================================

@melhorarplano_bp.get("/")
def plans_page():
    """
    Exibe a tela de comparação de planos (Free vs Pro).
    Mostra o plano atual da família.
    """
    parent_member = _get_parent_member()
    if not parent_member:
        flash("Acesso negado.", "error")
        return redirect(url_for("login.login_page"))
    
    plano_atual = parent_member.familia.plano
    
    return render_template("parent/plans.html", plano_atual=plano_atual)

@melhorarplano_bp.post("/subscribe")
def subscribe_pro():
    parent_member = _get_parent_member()
    if not parent_member:
        return redirect(url_for("login.login_page"))
    
    familia = parent_member.familia
    
    try:
        familia.plano = "PRO"
        db.session.commit()
        
        flash("Pagamento confirmado! Bem-vindo ao TaskPay PRO!", "success")
        
        return redirect(url_for("notificacoes.home_parent"))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao assinar: {e}", "error")
        
    return redirect(url_for("melhorarplano.plans_page"))