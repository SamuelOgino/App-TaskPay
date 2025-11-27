from flask import Blueprint, request, redirect, url_for, session, flash, current_app, render_template
from datetime import datetime
from werkzeug.utils import secure_filename
import os
from extensions import db
from models.models import (
    Membro, Role, Tarefa, TaskStatus, Submissao, SubmissionStatus, 
    Notificacao, Carteira, Transacao, TransactionType, Progresso
)
taskssubmission_bp = Blueprint("taskssubmission", __name__, url_prefix="/submission")
# --- Função Auxiliar de Segurança ---
def _get_current_member():
    uid = session.get("user_id")
    role = session.get("role")
    if not uid or not role: return None
    return Membro.query.filter_by(usuario_id=uid, role=role).first()
# ==========================================================
# ÁREA DO PAI - VCP 08 (Validar/Rejeitar)
# ==========================================================
# VCP08 - Validar/Rejeitar Submissão:
# Pai aprova (gera XP, adiciona saldo, registra transação)
# ou rejeita (marca tarefa como INATIVA e notifica).

@taskssubmission_bp.get("/approve/<submissao_id>")
def approve_submission(submissao_id):
    parent_member = _get_current_member()
    if not parent_member or parent_member.role != Role.PARENT:
        return redirect(url_for("login.login_page"))
        
    submissao = db.session.get(Submissao, submissao_id)
    if not submissao: 
        return redirect(url_for("notificacoes.home_parent"))
        
    tarefa = submissao.tarefa
    membro_filho = tarefa.executor
    
    if membro_filho.familia_id != parent_member.familia_id:
        flash("Permissão negada.", "error")
        return redirect(url_for("notificacoes.home_parent"))
        
    if submissao.status == SubmissionStatus.APPROVED:
        flash("Esta tarefa já foi aprovada.", "warning")
        return redirect(url_for("notificacoes.home_parent"))
        
    try:
        submissao.status = SubmissionStatus.APPROVED
        submissao.aprovadaEm = datetime.utcnow()
        submissao.valorAprovado = tarefa.valorBase
        
        if not membro_filho.carteira: 
            membro_filho.carteira = Carteira(membro_id=membro_filho.id, saldo=0)
            db.session.add(membro_filho.carteira)
            
        membro_filho.carteira.saldo = (membro_filho.carteira.saldo or 0) + tarefa.valorBase
        
        transacao = Transacao(
            tipo=TransactionType.CREDIT_TASK,
            valor=tarefa.valorBase,
            descricao=f"Pagamento da tarefa: {tarefa.titulo}",
            carteira_id=membro_filho.carteira.id
        )
        db.session.add(transacao)

        xp_ganho = 100 
        membro_filho.saldoXP = (membro_filho.saldoXP or 0) + xp_ganho
        
        if not membro_filho.progresso: 
            membro_filho.progresso = Progresso(membro_id=membro_filho.id)
            db.session.add(membro_filho.progresso)
            
        progresso = membro_filho.progresso
        progresso.xp_total = (progresso.xp_total or 0) + xp_ganho
        progresso.xp = (progresso.xp or 0) + xp_ganho
        progresso.ultimaTarefaEm = datetime.utcnow()

        max_xp_nivel_atual = 1000 
        while progresso.xp >= max_xp_nivel_atual:
            progresso.nivel += 1
            progresso.xp -= max_xp_nivel_atual 
            
        notif = Notificacao(
            tipo="TAREFA_APROVADA",
            mensagem=f"Tarefa '{tarefa.titulo}' aprovada! +R${tarefa.valorBase} e +{xp_ganho} XP",
            usuario_id=membro_filho.usuario_id
        )
        db.session.add(notif)
        db.session.commit()
        
        flash(f"Tarefa aprovada com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao aprovar: {e}", "error")
    
    return redirect(url_for("taskssubmission.tasks_page"))


# VCP08 - Validar/Rejeitar Submissão:
# Pai aprova (gera XP, adiciona saldo, registra transação)
# ou rejeita (marca tarefa como INATIVA e notifica).
@taskssubmission_bp.get("/reject/<submissao_id>")
def reject_submission(submissao_id):
    """
    Ação de Rejeitar:
    Marca como rejeitada e notifica o filho.
    """
    parent_member = _get_current_member()
    if not parent_member or parent_member.role != Role.PARENT:
        return redirect(url_for("login.login_page"))
        
    submissao = db.session.get(Submissao, submissao_id)
    if not submissao: 
        return redirect(url_for("notificacoes.home_parent"))
        
    tarefa = submissao.tarefa
    if tarefa.executor.familia_id != parent_member.familia_id:
        return redirect(url_for("notificacoes.home_parent"))

    try:
        submissao.status = SubmissionStatus.REJECTED
        tarefa.status = TaskStatus.INATIVA 
        
        notif = Notificacao(
            tipo="TAREFA_REJEITADA",
            mensagem=f"Sua submissão de '{tarefa.titulo}' foi rejeitada pelo responsável.",
            usuario_id=tarefa.executor.usuario_id
        )
        db.session.add(notif)
        db.session.commit()
        
        flash(f"Tarefa rejeitada.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro: {e}", "error")
        
    return redirect(url_for("taskssubmission.tasks_page"))

@taskssubmission_bp.get("/parent/tasks")
def tasks_page():
    parent_member = _get_current_member()
    if not parent_member or parent_member.role != Role.PARENT:
        flash("Acesso negado.", "error")
        return redirect(url_for("login.login_page"))

    filhos = Membro.query.filter_by(familia_id=parent_member.familia_id, role=Role.CHILD).all()
    filhos_ids = [f.id for f in filhos]
    
    tarefas_pendentes = []
    if filhos_ids:
        tarefas_pendentes = Tarefa.query.filter(
            Tarefa.executor_id.in_(filhos_ids),
            Tarefa.status == TaskStatus.ATIVA
        ).order_by(Tarefa.prazo.asc()).all()

    tarefas_para_avaliar = []
    if filhos_ids:
        tarefas_para_avaliar = Submissao.query.join(Tarefa).filter(
            Tarefa.executor_id.in_(filhos_ids),
            Submissao.status == SubmissionStatus.PENDING
        ).order_by(Submissao.enviadaEm.asc()).all()

    return render_template(
        "parent/tasks.html", 
        tarefas_pendentes=tarefas_pendentes,
        tarefas_para_avaliar=tarefas_para_avaliar
    )

# ==========================================================
# ÁREA DO FILHO - VCP07 (Registrar Tarefa)
# ==========================================================
# Filho envia submissão de tarefa (com ou sem foto),
# tarefa vira INATIVA e pai recebe notificação.

@taskssubmission_bp.post("/child/submit/<tarefa_id>")
def submit_task_simple(tarefa_id):
    """Filho envia tarefa que NÃO exige foto."""
    membro = _get_current_member()
    if not membro or membro.role != Role.CHILD:
        return redirect(url_for("login.login_page"))
    
    tarefa = db.session.get(Tarefa, tarefa_id)
    
    if not tarefa or tarefa.executor_id != membro.id:
        flash("Tarefa inválida.", "error")
        return redirect(url_for("taskspending.tasks_page"))
    
    if tarefa.exigeFoto:
        flash("Esta tarefa exige foto.", "error")
        return redirect(url_for("taskspending.tasks_page"))

    try:
        tarefa.status = TaskStatus.INATIVA
        
        submissao = Submissao.query.filter_by(tarefa_id=tarefa.id).first()
        if submissao:
            submissao.status = SubmissionStatus.PENDING
            submissao.nota = "Reenvio."
            submissao.enviadaEm = datetime.utcnow()
            submissao.fotoUrl = None
        else:
            submissao = Submissao(
                tarefa_id=tarefa.id,
                status=SubmissionStatus.PENDING,
                nota="Concluída."
            )
            db.session.add(submissao)

        pais = Membro.query.filter_by(familia_id=membro.familia_id, role=Role.PARENT).all()
        for pai in pais:
            notif = Notificacao(
                tipo="TAREFA_PENDENTE", 
                mensagem=f"{membro.usuario.nome} marcou '{tarefa.titulo}' como feita.", 
                usuario_id=pai.usuario_id
            )
            db.session.add(notif)
            
        db.session.commit()
        flash("Tarefa enviada para aprovação!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao enviar: {e}", "error")

    return redirect(url_for("taskspending.tasks_page"))

@taskssubmission_bp.post("/child/submit_photo/<tarefa_id>")
def submit_task_photo(tarefa_id):
    """Filho envia tarefa COM foto."""
    membro = _get_current_member()
    if not membro or membro.role != Role.CHILD:
        return redirect(url_for("login.login_page"))

    tarefa = db.session.get(Tarefa, tarefa_id)
    if not tarefa or tarefa.executor_id != membro.id:
        return redirect(url_for("taskspending.tasks_page"))
    if not tarefa.exigeFoto:
        flash("Esta tarefa não exige foto.", "warning")

    foto = request.files.get('foto_tarefa')
    if not foto or foto.filename == '':
        flash("Selecione uma foto.", "error")
        return redirect(url_for("taskspending.tasks_page"))

    try:
        nome_seguro = secure_filename(foto.filename)
        nome_final = f"sub_{tarefa.id}_{membro.usuario_id}_{nome_seguro}"
        
        caminho_dir = os.path.join(current_app.static_folder, 'uploads', 'submissions')
        os.makedirs(caminho_dir, exist_ok=True)
        foto.save(os.path.join(caminho_dir, nome_final))
        
        db_path = os.path.join('uploads', 'submissions', nome_final).replace("\\", "/")

        tarefa.status = TaskStatus.INATIVA
        
        submissao = Submissao.query.filter_by(tarefa_id=tarefa.id).first()
        if submissao:
            submissao.status = SubmissionStatus.PENDING
            submissao.fotoUrl = db_path
            submissao.enviadaEm = datetime.utcnow()
        else:
            submissao = Submissao(
                tarefa_id=tarefa.id, 
                status=SubmissionStatus.PENDING, 
                fotoUrl=db_path
            )
            db.session.add(submissao)

        pais = Membro.query.filter_by(familia_id=membro.familia_id, role=Role.PARENT).all()
        for pai in pais:
            notif = Notificacao(
                tipo="TAREFA_PENDENTE", 
                mensagem=f"{membro.usuario.nome} enviou uma foto para '{tarefa.titulo}'.", 
                usuario_id=pai.usuario_id
            )
            db.session.add(notif)
            
        db.session.commit()
        flash("Foto enviada com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao salvar foto: {e}", "error")

    return redirect(url_for("taskspending.tasks_page"))