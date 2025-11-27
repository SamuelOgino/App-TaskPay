from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from decimal import Decimal
from datetime import datetime
from extensions import db
from models.models import Membro, Role, Tarefa, TaskStatus, Notificacao

newtask_bp = Blueprint("newtask", __name__, url_prefix="/tasks")

def _get_parent_member():
    uid = session.get("user_id")
    if not uid: return None
    if session.get("role") != Role.PARENT: return None
    return Membro.query.filter_by(usuario_id=uid, role=Role.PARENT).first()

# ==========================================================
# VCP04 - Criar Tarefa
# VCP05 - Designar Tarefa ao Filho (Via seleção no formulário)
# ==========================================================
# VCP04 - Criar Tarefa: 
# Recebe dados do formulário, valida, cria Tarefa e envia notificação ao filho.
@newtask_bp.get("/new")
def new_task_page():
    """Exibe o formulário de criação de tarefa."""
    parent_member = _get_parent_member()
    if not parent_member:
        flash("Sessão inválida ou acesso negado.", "error")
        return redirect(url_for("login.login_page"))

    # Busca os filhos para preencher o <select> (VCP 05)
    filhos = Membro.query.filter_by(familia_id=parent_member.familia_id, role=Role.CHILD).all()
    
    return render_template("parent/new_task.html", filhos=filhos)

@newtask_bp.post("/new")
def create_task():
    """Processa o formulário de criação."""
    parent_member = _get_parent_member()
    if not parent_member:
        flash("Sessão inválida.", "error")
        return redirect(url_for("login.login_page"))
    
    titulo = (request.form.get("titulo") or "").strip()
    descricao = (request.form.get("descricao") or "").strip()
    valor = request.form.get("valor") or "0"
    exige_foto = True if request.form.get("exige_foto") == "on" else False
    prazo_str = (request.form.get("prazo") or "").strip()
    prioridade = request.form.get("prioridade") or None
    icone = request.form.get("icone") or None
    
    # VCP05 - O ID do executor define para quem a tarefa vai
    executor_id = request.form.get("executor_id") or None 

    has_error = False
    if not titulo:
        flash("Informe o nome da tarefa.", "error")
        has_error = True
    
    if not executor_id:
        flash("Selecione um filho para a tarefa.", "error")
        has_error = True

    if not prioridade:
        flash("Selecione uma prioridade.", "error")
        has_error = True
        
    if not icone:
        flash("Selecione um ícone.", "error")
        has_error = True

    if has_error:
        return redirect(url_for("newtask.new_task_page"))

    try:
        valor_base = Decimal(valor.replace(",", "."))
    except:
        valor_base = Decimal("0.00")
    
    prazo_dt = None
    if prazo_str:
        try:
            prazo_dt = datetime.fromisoformat(prazo_str)
        except:
            prazo_dt = None
            
    tarefa = Tarefa(
        titulo=titulo,
        descricao=descricao,
        valorBase=valor_base,
        status=TaskStatus.ATIVA,
        exigeFoto=exige_foto,
        prazo=prazo_dt,
        prioridade=prioridade,
        icone=icone,
        criador_id=parent_member.id,
        executor_id=executor_id # VCP05
    )
    db.session.add(tarefa)
    db.session.commit()
    
    if executor_id:
        filho = Membro.query.get(executor_id)
        if filho:
            notif = Notificacao(
                tipo="NOVA_TAREFA",
                mensagem=f"Nova tarefa: {tarefa.titulo}",
                usuario_id=filho.usuario_id
            )
            db.session.add(notif)
            db.session.commit()
            
    flash("Tarefa criada com sucesso!", "success")
    
    return redirect(url_for("notificacoes.home_parent"))