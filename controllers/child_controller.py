# controllers/child_controller.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from extensions import db
from models.models import (
    Progresso, Carteira, Transacao, TransactionType, Role, Tarefa, TaskStatus, 
    Membro, Submissao, SubmissionStatus, Notificacao, ResgateRecompensa
)
from sqlalchemy.sql import func, or_ # Para fazer cálculos (soma)
from datetime import datetime, timedelta # Para o foguinho

# --- MUDANÇA 1: Novas importações para upload de ficheiros ---
from werkzeug.utils import secure_filename
import os

# 1. Cria o "departamento" (Blueprint) do filho
bp = Blueprint("child", __name__, url_prefix="/child")

# 2. (BOA PRÁTICA) Criar uma função de "guarda" para rotas do filho
def _require_child():
    """Função de guarda: garante que o usuário logado é um FILHO."""
    if session.get("role") != Role.CHILD:
        flash("Acesso negado.", "error")
        return redirect(url_for("auth.login_page"))
    return None

def _get_parent_members(familia_id):
    """Busca todos os membros PAIS de uma família."""
    if not familia_id: return []
    return Membro.query.filter_by(familia_id=familia_id, role=Role.PARENT).all()

# 3. Rota "home" do filho
@bp.get("/home")
def home():
    """Exibe a página inicial do FILHO com XP, Saldo e Foguinho."""
    guard = _require_child()
    if guard: return guard
    
    membro_id = session.get('membro_id')
    if not membro_id:
        flash("Erro de sessão. Por favor, faça login novamente.", "error")
        return redirect(url_for("auth.login_page"))

    # --- LÓGICA DO BANCO DE DADOS ---
    progresso = Progresso.query.filter_by(membro_id=membro_id).first()
    if not progresso:
        progresso = Progresso(membro_id=membro_id)
        db.session.add(progresso)
    carteira = Carteira.query.filter_by(membro_id=membro_id).first()
    if not carteira:
        carteira = Carteira(membro_id=membro_id, saldo=0)
        db.session.add(carteira)
    db.session.commit()

    # Lógica do XP
    current_xp = progresso.xp
    max_xp = 1000
    xp_percent = (current_xp / max_xp) * 100 if max_xp > 0 else 0
    
    # Lógica do Foguinho
    is_streak_active = False
    if progresso.ultimaTarefaEm:
        agora = datetime.utcnow()
        limite_streak = progresso.ultimaTarefaEm + timedelta(hours=24)
        if agora < limite_streak:
            is_streak_active = True
    
    # Lógica do Saldo e Transações
    saldo_atual = carteira.saldo
    soma_tarefas = db.session.query(func.sum(Transacao.valor)).filter(
        Transacao.carteira_id == carteira.id,
        Transacao.tipo == TransactionType.CREDIT_TASK
    ).scalar() or 0.0
    soma_rejeitadas = db.session.query(func.sum(Tarefa.valorBase)).join(Submissao).filter(
        Tarefa.executor_id == membro_id,
        Submissao.status == SubmissionStatus.REJECTED
    ).scalar() or 0.0
    soma_xp_gasto = db.session.query(func.sum(ResgateRecompensa.xpPago)).filter(
        ResgateRecompensa.membro_id == membro_id,
        ResgateRecompensa.status == 'APPROVED' # (Ou o status que você usa para 'gasto')
    ).scalar() or 0
    
    # Buscar as Tarefas Pendentes
    tarefas_pendentes = Tarefa.query.filter(
        Tarefa.executor_id == membro_id,
        Tarefa.status == TaskStatus.ATIVA
    ).order_by(Tarefa.prazo.asc()).all()
    
    # Busca as 10 submissões mais recentes deste filho
    time_limit = datetime.utcnow() - timedelta(hours=8) 
    
    # Busca tarefas enviadas que:
    # 1. NÃO estão aprovadas (ex: PENDING, REJECTED)
    # OU
    # 2. Foram APROVADAS HÁ MENOS DE 1 MINUTO
    tarefas_enviadas = Submissao.query.join(Tarefa).filter(
        Tarefa.executor_id == membro_id,
        or_(
            Submissao.status != SubmissionStatus.APPROVED,
            Submissao.aprovadaEm >= time_limit
        )
    ).order_by(Submissao.enviadaEm.desc()).limit(10).all()
    
    # Envia tudo para o HTML
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
        tarefas_enviadas=tarefas_enviadas
    )

# ---
# --- 4. A ROTA DE PERFIL ---
# ---
@bp.get("/profile")  # A URL
def profile_page():    # O nome da função (endpoint)
    """Exibe a página de Perfil do FILHO."""
    guard = _require_child()
    if guard: return guard
    
    membro_id = session.get('membro_id')
    if not membro_id:
        flash("Erro de sessão. Por favor, faça login novamente.", "error")
        return redirect(url_for("auth.login_page"))

    # 1. Busca todos os objetos principais
    membro = Membro.query.get(membro_id)
    progresso = membro.progresso
    carteira = membro.carteira
    
    # 2. Garante que eles existem
    if not progresso:
        progresso = Progresso(membro_id=membro_id)
        db.session.add(progresso)
    if not carteira:
        carteira = Carteira(membro_id=membro_id, saldo=0)
        db.session.add(carteira)
    db.session.commit()

    # 3. Lógica do Foguinho (Streak)
    is_streak_active = False
    if progresso.ultimaTarefaEm:
        agora = datetime.utcnow()
        limite_streak = progresso.ultimaTarefaEm + timedelta(hours=24)
        if agora < limite_streak:
            is_streak_active = True
    
    # 4. Lógica do Nível e XP
    # 4. Lógica do Nível e XP

    # MUDANÇA: 'current_xp' agora é o XP do nível atual (o que reseta)
    current_xp = progresso.xp 

    nivel = progresso.nivel
    max_xp = 1000 # <-- MUDANÇA: Fixo em 1000 (como definimos)
    xp_percent = (current_xp / max_xp) * 100 if max_xp > 0 else 0

    # MUDANÇA: Precisamos do XP TOTAL acumulado para o card
    xp_total_acumulado = progresso.xp_total

    # 5. Lógica do Saldo
    saldo_atual = carteira.saldo

    # 6. Lógica das Tarefas Concluídas (Contagem)
    tarefas_concluidas_count = Submissao.query.join(Tarefa).filter(
        Tarefa.executor_id == membro_id,
        Submissao.status == SubmissionStatus.APPROVED
    ).count()

    # 7. Envia tudo para o novo HTML
    return render_template(
        "child/profile.html", # <-- O nome do seu novo ficheiro HTML
        membro=membro,
        progresso=progresso,
        current_xp=current_xp,
        max_xp=max_xp,
        xp_percent=xp_percent,
        nivel=nivel,
        saldo_atual=saldo_atual,
        is_streak_active=is_streak_active,
        xp_total_acumulado=xp_total_acumulado,
        tarefas_concluidas_count=tarefas_concluidas_count
    )

# ---
# --- MUDANÇA 2: ADICIONAR AS NOVAS ROTAS DE "EDITAR PERFIL" ---
# ---

@bp.get("/profile/edit")
def edit_profile_page():
    """Mostra a página para editar o perfil."""
    guard = _require_child()
    if guard: return guard
    
    membro_id = session.get('membro_id')
    membro = Membro.query.get(membro_id)
    
    # Envia o 'membro' para o template, para que possamos mostrar o nome atual no formulário
    return render_template("child/edit_profile.html", membro=membro)

@bp.post("/profile/edit")
def edit_profile_submit():
    """Processa a submissão do formulário de edição de perfil."""
    guard = _require_child()
    if guard: return guard
    
    membro_id = session.get('membro_id')
    membro = Membro.query.get(membro_id)
    usuario = membro.usuario # O objeto 'Usuario' que tem o nome e a foto

    # 1. Processa a atualização do NOME
    novo_nome = request.form.get("nome")
    if novo_nome and novo_nome.strip() != usuario.nome:
        usuario.nome = novo_nome.strip()
        flash("Nome atualizado com sucesso!", "success")

    # 2. Processa o UPLOAD DA FOTO
    foto = request.files.get('foto_perfil')
    
    # Verifica se um ficheiro foi realmente enviado e se tem um nome
    if foto and foto.filename != '':
        try:
            # Garante que o nome do ficheiro é seguro
            nome_seguro_ficheiro = secure_filename(foto.filename)
            
            # Cria um nome de ficheiro final único
            nome_final_ficheiro = f"avatar_{usuario.id}_{nome_seguro_ficheiro}"
            
            # Define o caminho completo onde a foto será guardada
            caminho_salvar = os.path.join(
                current_app.static_folder, 'uploads', nome_final_ficheiro
            )
            
            # (Opcional: Apaga a foto antiga antes de salvar a nova)
            if usuario.avatarUrl:
                caminho_antigo = os.path.join(current_app.static_folder, 'uploads', usuario.avatarUrl)
                if os.path.exists(caminho_antigo):
                    os.remove(caminho_antigo)

            # Salva a nova foto na pasta static/uploads
            foto.save(caminho_salvar)
            
            # 3. Salva o NOME DO FICHEIRO no banco de dados
            usuario.avatarUrl = nome_final_ficheiro # (Este é o 'avatarUrl' do seu models.py)
            flash("Foto de perfil atualizada!", "success")

        except Exception as e:
            flash(f"Erro ao salvar a foto: {e}", "error")

    # 4. Salva todas as alterações (nome e/ou foto) no banco
    db.session.commit()
    
    # 5. Redireciona de volta para a página de perfil
    return redirect(url_for("child.profile_page"))

@bp.get("/tasks")  # A nova URL (ex: /child/tasks)
def tasks_page():
    """Exibe a página dedicada de 'Tarefas Pendentes'."""
    guard = _require_child()
    if guard: return guard
    
    membro_id = session.get('membro_id')
    if not membro_id:
        flash("Erro de sessão. Por favor, faça login novamente.", "error")
        return redirect(url_for("auth.login_page"))

    # Esta é a MESMA lógica de busca que você já usa no seu @bp.get("/home")
    # Buscar as Tarefas Pendentes
    tarefas_pendentes = Tarefa.query.filter(
        Tarefa.executor_id == membro_id,
        Tarefa.status == TaskStatus.ATIVA
    ).order_by(Tarefa.prazo.asc()).all()
    
    return render_template(
        "child/tasks.html",
        tarefas_pendentes=tarefas_pendentes
    )
@bp.post("/tasks/submit/<tarefa_id>")
def submit_task_simple(tarefa_id):
    """Processa a submissão de uma tarefa que NÃO exige foto."""
    guard = _require_child()
    if guard: return guard
    
    membro_id = session.get('membro_id')
    tarefa = db.session.get(Tarefa, tarefa_id)
    membro = Membro.query.get(membro_id)

    # --- Validações de Segurança (sem mudanças) ---
    if not tarefa:
        flash("Tarefa não encontrada.", "error")
        return redirect(url_for("child.tasks_page"))
    if tarefa.executor_id != membro_id:
        flash("Você não tem permissão para esta tarefa.", "error")
        return redirect(url_for("child.tasks_page"))
    if tarefa.status != TaskStatus.ATIVA:
        flash("Esta tarefa não está mais ativa.", "warning")
        return redirect(url_for("child.tasks_page"))
    if tarefa.exigeFoto:
        flash("Esta tarefa exige uma foto e não pode ser marcada como feita.", "error")
        return redirect(url_for("child.tasks_page"))

    try:
        # 1. Mude o status da tarefa
        tarefa.status = TaskStatus.INATIVA
        
        # --- INÍCIO DA CORREÇÃO ---
        # 2. Verifica se já existe uma submissão (rejeitada) para esta tarefa
        submissao = Submissao.query.filter_by(tarefa_id=tarefa.id).first()
        
        if submissao:
            # Se já existe (foi rejeitada), ATUALIZA ela
            submissao.status = SubmissionStatus.PENDING
            submissao.nota = "Tarefa reenviada (sem foto)."
            submissao.enviadaEm = datetime.utcnow()
            submissao.fotoUrl = None # Garante que a foto antiga (se houver) seja limpa
        else:
            # Se não existe, CRIA uma nova
            submissao = Submissao(
                tarefa_id=tarefa.id,
                status=SubmissionStatus.PENDING,
                nota="Tarefa marcada como concluída."
            )
            db.session.add(submissao)
        # --- FIM DA CORREÇÃO ---

        # 3. Notifique os pais
        parents = _get_parent_members(membro.familia_id)
        for parent in parents:
            notif = Notificacao(
                tipo="TAREFA_PENDENTE",
                mensagem=f"{membro.usuario.nome} marcou a tarefa '{tarefa.titulo}' como concluída.",
                usuario_id=parent.usuario_id
            )
            db.session.add(notif)
            
        db.session.commit()
        flash("Tarefa enviada para aprovação!", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao enviar tarefa: {e}", "error")

    return redirect(url_for("child.tasks_page"))


@bp.post("/tasks/submit_photo/<tarefa_id>")
def submit_task_photo(tarefa_id):
    """Processa a submissão de uma tarefa que EXIGE foto."""
    guard = _require_child()
    if guard: return guard
    
    membro_id = session.get('membro_id')
    tarefa = db.session.get(Tarefa, tarefa_id)
    membro = Membro.query.get(membro_id)

    # --- Validações de Segurança (sem mudanças) ---
    if not tarefa:
        flash("Tarefa não encontrada.", "error")
        return redirect(url_for("child.tasks_page"))
    if tarefa.executor_id != membro_id:
        flash("Você não tem permissão para esta tarefa.", "error")
        return redirect(url_for("child.tasks_page"))
    if tarefa.status != TaskStatus.ATIVA:
        flash("Esta tarefa não está mais ativa.", "warning")
        return redirect(url_for("child.tasks_page"))
    if not tarefa.exigeFoto:
        flash("Esta tarefa não exige foto.", "error")
        return redirect(url_for("child.tasks_page"))

    # --- Lógica de Upload (sem mudanças) ---
    foto = request.files.get('foto_tarefa')
    
    if not foto or foto.filename == '':
        flash("Você precisa selecionar um arquivo de foto.", "error")
        return redirect(url_for("child.tasks_page"))

    try:
        # 1. Salvar a foto (sem mudanças)
        nome_seguro = secure_filename(foto.filename)
        nome_final = f"submissao_{tarefa.id}_{membro.usuario_id}_{nome_seguro}"
        caminho_dir = os.path.join(current_app.static_folder, 'uploads', 'submissions')
        os.makedirs(caminho_dir, exist_ok=True)
        caminho_salvar = os.path.join(caminho_dir, nome_final)
        foto.save(caminho_salvar)
        db_path = os.path.join('uploads', 'submissions', nome_final).replace("\\", "/")

        # 2. Mude o status da tarefa
        tarefa.status = TaskStatus.INATIVA
        
        # --- INÍCIO DA CORREÇÃO ---
        # 3. Verifica se já existe uma submissão (rejeitada)
        submissao = Submissao.query.filter_by(tarefa_id=tarefa.id).first()
        
        if submissao:
            # Se já existe, ATUALIZA ela com a nova foto e status
            submissao.status = SubmissionStatus.PENDING
            submissao.nota = "Foto reenviada para aprovação."
            submissao.enviadaEm = datetime.utcnow()
            submissao.fotoUrl = db_path # Atualiza o caminho da foto
        else:
            # Se não existe, CRIA uma nova
            submissao = Submissao(
                tarefa_id=tarefa.id,
                status=SubmissionStatus.PENDING,
                nota="Foto enviada para aprovação.",
                fotoUrl=db_path
            )
            db.session.add(submissao)
        # --- FIM DA CORREÇÃO ---
        
        # 4. Notifique os pais
        parents = _get_parent_members(membro.familia_id)
        for parent in parents:
            notif = Notificacao(
                tipo="TAREFA_PENDENTE",
                mensagem=f"{membro.usuario.nome} enviou uma foto para a tarefa '{tarefa.titulo}'.",
                usuario_id=parent.usuario_id
            )
            db.session.add(notif)
            
        db.session.commit()
        flash("Foto enviada para aprovação!", "success")
        
    except Exception as e:
        db.session.rollback()
        # Captura o erro específico de constraint
        if "UNIQUE constraint failed" in str(e):
             flash("Erro: Esta tarefa já tem uma submissão pendente.", "error")
        else:
             flash(f"Erro ao enviar a foto: {e}", "error")

    return redirect(url_for("child.tasks_page"))