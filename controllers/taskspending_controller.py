from flask import Blueprint, render_template, redirect, url_for, session, flash
from extensions import db
from models.models import Membro, Role, Tarefa, TaskStatus

# Blueprint para Visualização de Tarefas Pendentes (Visão do Filho)
taskspending_bp = Blueprint("taskspending", __name__, url_prefix="/child/tasks")

# Função auxiliar de segurança
def _require_child():
    if session.get("role") != Role.CHILD:
        flash("Acesso negado. Apenas filhos podem acessar esta área.", "error")
        return redirect(url_for("login.login_page"))
    return None

# ==========================================================
# VCP06 - Visualizar Tarefas Pendentes
# ==========================================================

@taskspending_bp.get("/")
def tasks_page():
    """Exibe a lista de tarefas ativas para o filho logado."""
    # 1. Verifica permissão
    guard = _require_child()
    if guard: return guard
    
    membro_id = session.get('membro_id')
    if not membro_id:
        flash("Sessão inválida.", "error")
        return redirect(url_for("login.login_page"))

    # 2. Busca apenas tarefas ATIVAS (Pendentes) do próprio filho
    # Ordenadas por prazo (as mais urgentes primeiro)
    tarefas_pendentes = Tarefa.query.filter(
        Tarefa.executor_id == membro_id,
        Tarefa.status == TaskStatus.ATIVA
    ).order_by(Tarefa.prazo.asc()).all()
    
    # 3. Renderiza o HTML específico do filho
    return render_template(
        "child/tasks.html",
        tarefas_pendentes=tarefas_pendentes
    )