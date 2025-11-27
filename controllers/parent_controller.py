from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from decimal import Decimal
from datetime import datetime, timedelta
from extensions import db
from uuid import uuid4
import os
from werkzeug.utils import secure_filename
from sqlalchemy.sql import func, or_
from models.models import Membro, Role, Tarefa, Notificacao, TaskStatus, Recompensa, ResgateRecompensa, Submissao, SubmissionStatus, Progresso, Carteira, Usuario, Transacao, TransactionType, ResgateStatus

bp = Blueprint("parent", __name__, url_prefix="/parent")

def _require_parent(): #essa função verifica se o usuário em questão é da categoria pais
    if session.get("role") != Role.PARENT:
        return redirect(url_for("auth.login_page"))
    return None

def _current_parent_member():
    uid = session.get("user_id")
    if not uid: return None
    return Membro.query.filter_by(usuario_id=uid, role=Role.PARENT).first()

@bp.get("/home")
def home():
    # ... (Verificações iniciais de login continuam iguais) ...
    guard = _require_parent()
    if guard: return guard

    parent_member = Membro.query.filter_by(usuario_id=session.get("user_id"), role=Role.PARENT).first()
    if not parent_member:
        flash("Sessão de PAI inválida.", "error")
        return redirect(url_for("auth.login_page"))

    filhos = Membro.query.filter_by(familia_id=parent_member.familia_id, role=Role.CHILD).all()
    filhos_ids = [filho.id for filho in filhos]
    
    # --- CÁLCULOS FINANCEIROS ATUALIZADOS ---

    # 1. Total Prometido (HISTÓRICO TOTAL DE GANHOS)
    # Soma todas as transações de entrada (Tarefas e Mesadas) desde o início.
    # NÃO subtrai o que já foi pago.
    total_prometido = 0.0
    if filhos_ids:
        total_prometido = db.session.query(func.sum(Transacao.valor)).join(Carteira).filter(
            Carteira.membro_id.in_(filhos_ids),
            # Filtra apenas tipos de entrada de dinheiro
            Transacao.tipo.in_([TransactionType.CREDIT_TASK, TransactionType.CREDIT_ALLOWANCE])
        ).scalar() or 0.0

    # 2. Total Pago (HISTÓRICO TOTAL DE PAGAMENTOS)
    # Soma tudo que o pai já registrou como pago/sacado.
    total_pago = 0.0
    if filhos_ids:
        total_pago = db.session.query(func.sum(Transacao.valor)).join(Carteira).filter(
            Carteira.membro_id.in_(filhos_ids),
            Transacao.tipo == 'DEBIT_PAYMENT'
        ).scalar() or 0.0

    # --- Fim dos cálculos ---
    
    # ... (O resto do código de tarefas pendentes e retorno do template continua igual) ...
    
    # VCP06 - Visualizar Tarefas Pendentes:
    # Lista tarefas ATIVAS dos filhos ordenadas por prazo.
    tarefas_pendentes = []
    if filhos_ids:
        tarefas_pendentes = Tarefa.query.filter(
            Tarefa.executor_id.in_(filhos_ids),
            Tarefa.status == TaskStatus.ATIVA
        ).order_by(Tarefa.prazo.asc()).all()

    tarefas_para_avaliar = Submissao.query.join(Tarefa).filter(
        Tarefa.executor_id.in_(filhos_ids),
        Submissao.status == SubmissionStatus.PENDING
    ).order_by(Submissao.enviadaEm.asc()).all()

    return render_template(
        "parent/home.html", 
        parent_member=parent_member,
        total_prometido=total_prometido,
        total_pago=total_pago,
        tarefas_pendentes=tarefas_pendentes,
        tarefas_para_avaliar=tarefas_para_avaliar
    )
# ----------------------------------------------------------------

# VCP04 - Criar Tarefa: (e VCP07)
# Recebe dados do formulário, valida, cria Tarefa e envia notificação ao filho.
@bp.get("/tasks/new")
def new_task_page():
    guard = _require_parent()
    if guard: return guard
    parent_member = Membro.query.filter_by(usuario_id=session.get("user_id"), role=Role.PARENT).first()
    if not parent_member:
        flash("Sessão inválida. Faça login novamente.", "error")
        return redirect(url_for("auth.login_page"))
    filhos = Membro.query.filter_by(familia_id=parent_member.familia_id, role=Role.CHILD).all()
    return render_template("parent/new_task.html", filhos=filhos)

@bp.post("/tasks")
def create_task():
    guard = _require_parent()
    if guard: return guard
    parent_member = Membro.query.filter_by(usuario_id=session.get("user_id"), role=Role.PARENT).first()
    if not parent_member:
        flash("Sessão inválida. Faça login novamente.", "error")
        return redirect(url_for("auth.login_page"))
    
    # --- Pega os dados do formulário ---
    titulo = (request.form.get("titulo") or "").strip()
    descricao = (request.form.get("descricao") or "").strip()
    valor = request.form.get("valor") or "0"
    exige_foto = True if request.form.get("exige_foto") == "on" else False
    prazo_str = (request.form.get("prazo") or "").strip()
    prioridade = request.form.get("prioridade") or None
    icone = request.form.get("icone") or None
    executor_id = request.form.get("executor_id") or None
    # VCP05 - Designar tarefa ao filho:
    # O executor_id define qual filho receberá a tarefa.


    # --- INÍCIO DA VALIDAÇÃO (Passo 3) ---
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
        # Se houver qualquer erro, volta para a página de criação
        return redirect(url_for("parent.new_task_page"))
    # --- FIM DA VALIDAÇÃO ---

    # (O restante do código continua igual, apenas removendo 'recorrencia')
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
        executor_id=executor_id
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
    return redirect(url_for("parent.home"))

@bp.get("/rewards")
def rewards_page():
    """Exibe a tela de Recompensas do PAI com filtros inteligentes."""
    guard = _require_parent()
    if guard: return guard
    
    parent_member = Membro.query.filter_by(usuario_id=session.get("user_id"), role=Role.PARENT).first()
    filhos = Membro.query.filter_by(familia_id=parent_member.familia_id, role=Role.CHILD).all()
    
    # 1. Resumo de XP (Sem mudanças)
    xp_por_filho = [{
        "id": f.id, 
        "nome": f.usuario.nome, 
        "xp": (f.saldoXP or 0),
        "avatar": f.usuario.avatarUrl
    } for f in filhos]
    
    # --- LÓGICA 1: FILTRAR RECOMPENSAS ATIVAS (Esconder as já pegas) ---
    
    # Busca IDs de tudo que JÁ FOI RESGATADO por alguém da família
    resgates_familia = db.session.query(ResgateRecompensa.recompensa_id)\
        .join(Membro, ResgateRecompensa.membro_id == Membro.id)\
        .filter(Membro.familia_id == parent_member.familia_id)\
        .all()
    
    ids_ja_resgatados = [r.recompensa_id for r in resgates_familia]
    
    # Monta a busca das ativas
    query_ativas = Recompensa.query.filter_by(
        familia_id=parent_member.familia_id, 
        ativa=True
    )
    
    # Se tiver itens resgatados, remove eles da lista
    if ids_ja_resgatados:
        query_ativas = query_ativas.filter(Recompensa.id.notin_(ids_ja_resgatados))
        
    ativas = query_ativas.order_by(Recompensa.criadoEm.desc()).all()
    
    
    # --- LÓGICA 2: HISTÓRICO LIMPO (Regra das 36 horas) ---
    
    # Define o tempo de corte (Agora - 36 horas)
    limite_tempo = datetime.utcnow() - timedelta(hours=36)
    
    historico = (
        ResgateRecompensa.query
        .join(Membro, ResgateRecompensa.membro_id == Membro.id)
        .join(Recompensa, ResgateRecompensa.recompensa_id == Recompensa.id)
        .filter(Membro.familia_id == parent_member.familia_id)
        .filter(
            or_(
                # MOSTRA SE: Estiver Pendente (sempre mostra para o pai decidir)
                ResgateRecompensa.status == ResgateStatus.PENDING,
                
                # OU SE: Foi criado há menos de 36 horas (para ver o histórico recente)
                ResgateRecompensa.criadoEm >= limite_tempo
            )
        )
        .order_by(ResgateRecompensa.criadoEm.desc())
        .all()
    )
    plano_atual = parent_member.familia.plano

    return render_template("parent/rewards.html",
                           filhos=filhos,
                           xp_por_filho=xp_por_filho,
                           ativas=ativas,     # Lista filtrada (sem itens pegos)
                           historico=historico,
                           plano_atual=plano_atual) # Lista filtrada (sem itens velhos)

@bp.get("/rewards/new")
def new_reward_page():
    guard = _require_parent()
    if guard: return guard
    return render_template("parent/new_reward.html")

@bp.post("/rewards")
def create_reward():
    guard = _require_parent()
    if guard: return guard
    parent_member = Membro.query.filter_by(usuario_id=session.get("user_id"), role=Role.PARENT).first()
    titulo = (request.form.get("titulo") or "").strip()
    descricao = (request.form.get("descricao") or "").strip()
    custoXP = int(request.form.get("custoXP") or 0)
    if not titulo:
        flash("Informe o título da recompensa.", "error")
        return redirect(url_for("parent.new_reward_page"))
    recompensa = Recompensa(
        id=str(uuid4()),
        titulo=titulo,
        descricao=descricao,
        custoXP=custoXP,
        ativa=True,
        familia_id=parent_member.familia_id,
        criador_id=parent_member.id
    )
    db.session.add(recompensa)
    db.session.commit()
    filhos = Membro.query.filter_by(familia_id=parent_member.familia_id, role=Role.CHILD).all()
    for f in filhos:
        notif = Notificacao(
            tipo="NOVA_RECOMPENSA",
            mensagem=f"Nova recompensa: {recompensa.titulo} ({recompensa.custoXP} XP)",
            usuario_id=f.usuario_id
        )
        db.session.add(notif)
    db.session.commit()
    flash("Recompensa criada!", "success")
    return redirect(url_for("parent.rewards_page"))

# VCP08 - Validar/Rejeitar Submissão:
# Pai aprova (gera XP, adiciona saldo, registra transação)
# ou rejeita (marca tarefa como INATIVA e notifica).
@bp.get("/submission/approve/<submissao_id>")
def approve_submission(submissao_id):
    guard = _require_parent()
    if guard: return guard
    parent_member = Membro.query.filter_by(usuario_id=session.get("user_id"), role=Role.PARENT).first()
    if not parent_member:
        flash("Sessão de PAI inválida.", "error")
        return redirect(url_for("auth.login_page"))
        
    submissao = db.session.get(Submissao, submissao_id)
    if not submissao:
        flash("Submissão não encontrada.", "error")
        return redirect(url_for("parent.home"))
        
    tarefa = submissao.tarefa
    membro_filho = tarefa.executor
    progresso_filho = membro_filho.progresso
    carteira_filho = membro_filho.carteira
    
    if not membro_filho or membro_filho.familia_id != parent_member.familia_id:
        flash("Você não tem permissão para aprovar esta tarefa.", "error")
        return redirect(url_for("parent.home"))
        
    if submissao.status == SubmissionStatus.APPROVED:
        flash("Esta tarefa já foi aprovada.", "warning")
        return redirect(url_for("parent.home"))
        
    try:
        submissao.status = SubmissionStatus.APPROVED
        submissao.aprovadaEm = datetime.utcnow()
        submissao.valorAprovado = tarefa.valorBase
        
        if not carteira_filho: 
            carteira_filho = Carteira(membro_id=membro_filho.id)
            db.session.add(carteira_filho)
            
        carteira_filho.saldo = (carteira_filho.saldo or 0) + tarefa.valorBase
        
        # ADICIONA O XP AO SALDO PARA GASTAR NA LOJA
        # Supondo que 1 Real = 10 XP (ou use uma regra fixa como +100 XP por tarefa)
        xp_ganho = 100 # Defina quanto XP a tarefa vale
        membro_filho.saldoXP = (membro_filho.saldoXP or 0) + xp_ganho
        # VCP11 - Subir de nível:
    # A cada aprovação o filho ganha XP; ao exceder 1000 XP o nível aumenta.

        # Cria o registro da transação para o extrato do filho
        transacao = Transacao(
            tipo=TransactionType.CREDIT_TASK,
            valor=tarefa.valorBase,
            descricao=f"Pagamento da tarefa: {tarefa.titulo}",
            carteira_id=carteira_filho.id
        )
        db.session.add(transacao)

        if not progresso_filho: 
            progresso_filho = Progresso(membro_id=membro_filho.id)
            db.session.add(progresso_filho)
            
        # LÓGICA DE LEVEL UP (XP Fixo 1000)
        # 1. Adiciona o XP ao total acumulativo
        progresso_filho.xp_total = (progresso_filho.xp_total or 0) + 100
        
        # 2. Adiciona o XP à barra do nível atual
        progresso_filho.xp = (progresso_filho.xp or 0) + 100
        progresso_filho.ultimaTarefaEm = datetime.utcnow()

        # 3. Verifica se o filho passou de nível (1000 XP fixo)
        max_xp_nivel_atual = 1000 
        
        while progresso_filho.xp >= max_xp_nivel_atual:
            # Passou de nível!
            progresso_filho.nivel += 1
            # Zera a barra de XP (levando o excesso)
            progresso_filho.xp -= max_xp_nivel_atual
            
        notif = Notificacao(
            tipo="TAREFA_APROVADA",
            mensagem=f"Sua tarefa '{tarefa.titulo}' foi aprovada! +R${tarefa.valorBase} e +100 XP",
            usuario_id=membro_filho.usuario_id
        )
        db.session.add(notif)
        db.session.commit()
        
        flash(f"Tarefa '{tarefa.titulo}' aprovada!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Ocorreu um erro: {e}", "error")
    
    # Redireciona para a página de tarefas (tasks_page), não para a home
    return redirect(url_for("parent.tasks_page"))

# ... (cole isto no lugar da sua rota @bp.get("/profile") antiga) ...
@bp.get("/profile")
def profile_page():
    """Exibe a página de Perfil do PAI."""
    guard = _require_parent()
    if guard: return guard
    
    parent_member = _current_parent_member()
    if not parent_member:
        flash("Sessão inválida. Faça login novamente.", "error")
        return redirect(url_for("auth.login_page"))
    
    usuario = parent_member.usuario
    filhos = Membro.query.filter_by(familia_id=parent_member.familia_id, role=Role.CHILD).all()
    
    # VCP10 - Consultar Saldo:
    filhos_data = [] 
    for filho in filhos:
        # Garante carteira e progresso
        progresso = filho.progresso or Progresso(membro_id=filho.id, xp=0, nivel=1)
        if not filho.progresso: db.session.add(progresso)
        
        carteira = filho.carteira or Carteira(membro_id=filho.id, saldo=0)
        if not filho.carteira: db.session.add(carteira)
        
        # Tarefas Concluídas
        tarefas_concluidas = Submissao.query.join(Tarefa).filter(
            Tarefa.executor_id == filho.id,
            Submissao.status == SubmissionStatus.APPROVED
        ).count()
        
        # CALCULAR O TOTAL GANHO
        total_ganho_bruto = db.session.query(func.sum(Transacao.valor)).filter(
            Transacao.carteira_id == carteira.id,
            Transacao.tipo.in_([TransactionType.CREDIT_TASK, TransactionType.CREDIT_ALLOWANCE])
        ).scalar() or 0.0
        
        # Lógica do Streak (Foguinho)
        is_streak_active = False
        streak_dias = 0
        submissoes_aprovadas = db.session.query(Submissao.aprovadaEm).join(Tarefa).filter(
            Tarefa.executor_id == filho.id,
            Submissao.status == SubmissionStatus.APPROVED
        ).order_by(Submissao.aprovadaEm.desc()).all()
        
        datas_unicas = sorted(list(set([s.aprovadaEm.date() for s in submissoes_aprovadas if s.aprovadaEm])), reverse=True)
        
        if datas_unicas:
            hoje = datetime.utcnow().date()
            ontem = hoje - timedelta(days=1)
            ultima_data = datas_unicas[0]
            
            if ultima_data == hoje or ultima_data == ontem:
                is_streak_active = True
                streak_dias = 1
                data_referencia = ultima_data
                for i in range(1, len(datas_unicas)):
                    proxima_data = datas_unicas[i]
                    if (data_referencia - proxima_data).days == 1:
                        streak_dias += 1
                        data_referencia = proxima_data
                    elif (data_referencia - proxima_data).days > 1:
                        break

        filhos_data.append({
            "membro": filho,
            "tarefas_concluidas": tarefas_concluidas,
            "saldo": carteira.saldo,
            "total_ganho": total_ganho_bruto,
            "is_streak_active": is_streak_active,
            "streak_dias": streak_dias
        })
    
    db.session.commit()

    # --- AQUI ESTÁ A MUDANÇA ---
    # Pegamos o plano direto da família (Texto "FREE" ou "PRO")
    plano_atual = parent_member.familia.plano

    return render_template(
        "parent/profile.html",
        usuario=usuario,
        filhos_data=filhos_data,
        plano_atual=plano_atual  # <--- Passando a variável para o HTML
    )

# VCP13 - Notificações:
# Pai recebe, lê e marca como lidas todas as notificações.
@bp.get("/notifications/read/<notif_id>")
def mark_read(notif_id):
    guard = _require_parent()
    if guard: return guard
    n = Notificacao.query.get(notif_id)
    if n:
        n.lidaEm = datetime.utcnow()
        db.session.commit()
    return redirect(url_for("parent.profile_page"))

@bp.get("/notifications/read_all")
def mark_all_read():
    guard = _require_parent()
    if guard: return guard
    uid = session.get("user_id")
    usuario = Usuario.query.filter_by(id=uid).first()
    if usuario:
        (Notificacao.query
         .filter_by(usuario_id=usuario.id)
         .filter(Notificacao.lidaEm.is_(None))
         .update({Notificacao.lidaEm: datetime.utcnow()}))
        db.session.commit()
    return redirect(url_for("parent.profile_page"))

# --- NOVAS ROTAS PARA EDITAR PERFIL (Substituindo o /profile/avatar) ---

@bp.get("/profile/edit")
def edit_profile_page():
    """Mostra a página para o PAI editar o seu perfil."""
    guard = _require_parent()
    if guard: return guard

    parent_member = _current_parent_member()

    # Envia o 'membro' (que tem o 'usuario' dentro) para o template
    return render_template("parent/edit_profile.html", membro=parent_member)

@bp.post("/profile/edit")
def edit_profile_submit():
    """Processa a submissão do formulário de edição de perfil do PAI."""
    guard = _require_parent()
    if guard: return guard

    parent_member = _current_parent_member()
    usuario = parent_member.usuario

    # 1. Processa a atualização do NOME
    novo_nome = request.form.get("nome")
    if novo_nome and novo_nome.strip() != usuario.nome:
        usuario.nome = novo_nome.strip()
        flash("Nome atualizado com sucesso!", "success")

    # 2. Processa o UPLOAD DA FOTO
    foto = request.files.get('foto_perfil')

    if foto and foto.filename != '':
        try:
            nome_seguro_ficheiro = secure_filename(foto.filename)
            nome_final_ficheiro = f"avatar_parent_{usuario.id}_{nome_seguro_ficheiro}"

            # Garante que a pasta 'static/uploads/avatars' existe
            caminho_salvar_dir = os.path.join(current_app.static_folder, 'uploads', 'avatars')
            os.makedirs(caminho_salvar_dir, exist_ok=True)

            caminho_salvar_ficheiro = os.path.join(caminho_salvar_dir, nome_final_ficheiro)

            # Apaga a foto antiga
            if usuario.avatarUrl:
                # O seu código antigo guardava f"/{path}", o que está errado.
                # Vamos assumir que o 'avatarUrl' é um caminho relativo
                caminho_antigo = os.path.join(current_app.static_folder, usuario.avatarUrl.lstrip('/'))
                if os.path.exists(caminho_antigo):
                    os.remove(caminho_antigo)

            # Salva a nova foto
            foto.save(caminho_salvar_ficheiro)

            # 3. Salva o CAMINHO RELATIVO (corrigido) no banco de dados
            usuario.avatarUrl = os.path.join('uploads', 'avatars', nome_final_ficheiro).replace("\\", "/")
            flash("Foto de perfil atualizada!", "success")

        except Exception as e:
            flash(f"Erro ao salvar a foto: {e}", "error")

    # 4. Salva as alterações
    db.session.commit()

    # 5. Redireciona de volta para a página de perfil
    return redirect(url_for("parent.profile_page"))


@bp.get("/tasks")
def tasks_page():
    """Exibe a página de 'Tarefas' do PAI (Pendentes e Para Avaliar)."""
    guard = _require_parent()
    if guard: return guard
    
    parent_member = _current_parent_member()
    if not parent_member:
        flash("Sessão inválida. Faça login novamente.", "error")
        return redirect(url_for("auth.login_page"))

    # --- Lógica de Busca (similar à da home) ---
    
    # 1. Busca filhos
    filhos = Membro.query.filter_by(familia_id=parent_member.familia_id, role=Role.CHILD).all()
    filhos_ids = [filho.id for filho in filhos]
    
    # 2. Busca tarefas ATIVAS (Pendentes)
    tarefas_pendentes = []
    if filhos_ids:
        tarefas_pendentes = Tarefa.query.filter(
            Tarefa.executor_id.in_(filhos_ids),
            Tarefa.status == TaskStatus.ATIVA
        ).order_by(Tarefa.prazo.asc()).all()

    # 3. Busca tarefas PARA AVALIAR (Submetidas)
    tarefas_para_avaliar = []
    if filhos_ids:
        tarefas_para_avaliar = Submissao.query.join(Tarefa).filter(
            Tarefa.executor_id.in_(filhos_ids),
            Submissao.status == SubmissionStatus.PENDING
        ).order_by(Submissao.enviadaEm.asc()).all()

    # (No próximo passo, criaremos este arquivo HTML)
    return render_template(
        "parent/tasks.html", 
        tarefas_pendentes=tarefas_pendentes,
        tarefas_para_avaliar=tarefas_para_avaliar
    )

# ... (fim da sua rota @bp.get("/submission/approve/<submissao_id>") ) ...

# VCP08 - Validar/Rejeitar Submissão:
# Pai aprova (gera XP, adiciona saldo, registra transação)
# ou rejeita (marca tarefa como INATIVA e notifica).
@bp.get("/submission/reject/<submissao_id>")
def reject_submission(submissao_id):
    """Processa a rejeição de uma submissão de tarefa pelo PAI."""
    guard = _require_parent()
    if guard: return guard
    
    parent_member = Membro.query.filter_by(usuario_id=session.get("user_id"), role=Role.PARENT).first()
    if not parent_member:
        flash("Sessão de PAI inválida.", "error")
        return redirect(url_for("auth.login_page"))
        
    submissao = db.session.get(Submissao, submissao_id)
    if not submissao:
        flash("Submissão não encontrada.", "error")
        return redirect(url_for("parent.tasks_page"))
        
    tarefa = submissao.tarefa
    membro_filho = tarefa.executor
    
    if not membro_filho or membro_filho.familia_id != parent_member.familia_id:
        flash("Você não tem permissão para rejeitar esta tarefa.", "error")
        return redirect(url_for("parent.tasks_page"))
        
    if submissao.status in [SubmissionStatus.APPROVED, SubmissionStatus.REJECTED]:
        flash("Esta tarefa já foi finalizada.", "warning")
        return redirect(url_for("parent.tasks_page"))

    try:
        # 1. Altera o status da Submissão
        submissao.status = SubmissionStatus.REJECTED
        
        # 2. MUDANÇA CRUCIAL: Devolve a Tarefa para INATIVA para exclusão permanente
        tarefa.status = TaskStatus.INATIVA 
        
        # 3. Notifica o filho
        notif = Notificacao(
            tipo="TAREFA_REJEITADA",
            mensagem=f"Sua submissão de '{tarefa.titulo}' foi rejeitada. A tarefa foi encerrada.",
            usuario_id=membro_filho.usuario_id
        )
        db.session.add(notif)
        
        db.session.commit()
        
        flash(f"Tarefa '{tarefa.titulo}' rejeitada. Removida da lista do {membro_filho.usuario.nome}.", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"Ocorreu um erro: {e}", "error")
        
    return redirect(url_for("parent.tasks_page"))

# VCP12 - Resgatar Recompensa:
# Pai entrega (DELIVERED) ou rejeita (REJECTED) retornando XP ao filho.
@bp.get("/rewards/deliver/<resgate_id>")
def deliver_reward(resgate_id):
    """Marca uma recompensa como ENTREGUE (Aprovada)."""
    guard = _require_parent()
    if guard: return guard
    
    parent_member = _current_parent_member()
    resgate = db.session.get(ResgateRecompensa, resgate_id)
    
    # Validações de segurança
    if not resgate:
        flash("Resgate não encontrado.", "error")
        return redirect(url_for("parent.rewards_page"))
        
    # Verifica se o pai tem permissão (se é da mesma família)
    membro_filho = resgate.membro
    if membro_filho.familia_id != parent_member.familia_id:
        flash("Permissão negada.", "error")
        return redirect(url_for("parent.rewards_page"))

    try:
        # Atualiza Status
        resgate.status = ResgateStatus.DELIVERED # Item entregue!
        
        # Notifica o filho
        notif = Notificacao(
            tipo="RECOMPENSA_ENTREGUE",
            mensagem=f"Oba! Sua recompensa '{resgate.recompensa.titulo}' foi entregue!",
            usuario_id=membro_filho.usuario_id
        )
        db.session.add(notif)
        db.session.commit()
        
        flash("Recompensa marcada como entregue!", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro: {e}", "error")
        
    return redirect(url_for("parent.rewards_page"))

# VCP12 - Resgatar Recompensa:
# Pai entrega (DELIVERED) ou rejeita (REJECTED) retornando XP ao filho.
@bp.get("/rewards/reject/<resgate_id>")
def reject_reward(resgate_id):
    """Rejeita o pedido e DEVOLVE O XP para o filho."""
    guard = _require_parent()
    if guard: return guard
    
    parent_member = _current_parent_member()
    resgate = db.session.get(ResgateRecompensa, resgate_id)
    
    if not resgate or resgate.membro.familia_id != parent_member.familia_id:
        flash("Erro ao processar.", "error")
        return redirect(url_for("parent.rewards_page"))

    if resgate.status != ResgateStatus.PENDING:
        flash("Este item já foi processado.", "warning")
        return redirect(url_for("parent.rewards_page"))

    try:
        # 1. Muda status para REJEITADO
        resgate.status = ResgateStatus.REJECTED
        
        # 2. REEMBOLSO: Devolve o XP gasto para a carteira do filho
        filho = resgate.membro
        xp_para_devolver = resgate.xpPago
        filho.saldoXP = (filho.saldoXP or 0) + xp_para_devolver
        
        # 3. Notifica
        notif = Notificacao(
            tipo="RECOMPENSA_REJEITADA",
            mensagem=f"O pedido de '{resgate.recompensa.titulo}' foi cancelado. Seus {xp_para_devolver} XP foram devolvidos.",
            usuario_id=filho.usuario_id
        )
        db.session.add(notif)
        db.session.commit()
        
        flash(f"Pedido rejeitado. {xp_para_devolver} XP foram devolvidos para {filho.usuario.nome}.", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro: {e}", "error")
        
    return redirect(url_for("parent.rewards_page"))

@bp.get("/plans")
def plans_page():
    guard = _require_parent()
    if guard: return guard
    
    parent_member = _current_parent_member()
    plano_atual = parent_member.familia.plano
    
    return render_template("parent/plans.html", plano_atual=plano_atual)

# --- NOVA ROTA PARA ASSINAR ---
@bp.post("/plans/subscribe")
def subscribe_pro():
    """Muda o plano da família para PRO."""
    guard = _require_parent()
    if guard: return guard
    
    parent_member = _current_parent_member()
    familia = parent_member.familia
    
    try:
        # Atualiza diretamente para a string "PRO"
        familia.plano = "PRO"
        db.session.commit()
        
        flash("Pagamento confirmado! Bem-vindo ao TaskPay PRO!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao assinar: {e}", "error")
        
    return redirect(url_for("parent.home"))

# --- NOVAS ROTAS: DETALHES FINANCEIROS DO FILHO ---

@bp.get("/child/<child_id>")
def child_detail(child_id):
    """Exibe detalhes financeiros de um filho específico."""
    guard = _require_parent()
    if guard: return guard

    parent_member = _current_parent_member()
    filho = Membro.query.get(child_id)

    # Segurança: verifica se o filho existe e pertence à mesma família
    if not filho or filho.familia_id != parent_member.familia_id:
        flash("Filho não encontrado ou permissão negada.", "error")
        return redirect(url_for("parent.profile_page"))

    carteira = filho.carteira
    if not carteira:
        carteira = Carteira(membro_id=filho.id, saldo=0)
        db.session.add(carteira)
        db.session.commit()

    # 1. CÁLCULOS FINANCEIROS
    
    # A. Total Prometido (Tudo que ele ganhou de tarefas + mesada na vida toda)
    total_ganho = db.session.query(func.sum(Transacao.valor)).filter(
        Transacao.carteira_id == carteira.id,
        Transacao.tipo.in_([TransactionType.CREDIT_TASK, TransactionType.CREDIT_ALLOWANCE])
    ).scalar() or 0.0

    # B. Total Pago (Tudo que o pai já pagou em dinheiro/pix - DEBIT_PAYMENT)
    # Vamos criar um tipo 'DEBIT_PAYMENT' para representar "Saque/Pagamento do Pai"
    total_pago_historico = db.session.query(func.sum(Transacao.valor)).filter(
        Transacao.carteira_id == carteira.id,
        Transacao.tipo == 'DEBIT_PAYMENT' 
    ).scalar() or 0.0

    # C. Saldo Atual (O que o pai deve HOJE)
    saldo_devedor = carteira.saldo
    # VCP10 - Consultar Saldo:
    # Pai visualiza total ganho, total pago e saldo atual do filho.

    # 2. Histórico Recente (Últimas 5 movimentações)
    historico = Transacao.query.filter_by(carteira_id=carteira.id)\
        .order_by(Transacao.criadoEm.desc())\
        .limit(5).all()

    return render_template(
        "parent/child_detail.html",
        filho=filho,
        total_ganho=total_ganho,
        total_pago_historico=total_pago_historico,
        saldo_devedor=saldo_devedor,
        historico=historico
    )

@bp.post("/child/<child_id>/pay")
def pay_child_submit(child_id):
    """Registra um pagamento (Pix/Dinheiro) feito ao filho."""
    guard = _require_parent()
    if guard: return guard

    parent_member = _current_parent_member()
    filho = Membro.query.get(child_id)

    if not filho or filho.familia_id != parent_member.familia_id:
        flash("Erro de permissão.", "error")
        return redirect(url_for("parent.profile_page"))

    valor_str = request.form.get("valor_pagamento")
    try:
        valor_pagar = Decimal(valor_str.replace(",", "."))
    except:
        flash("Valor inválido.", "error")
        return redirect(url_for("parent.child_detail", child_id=child_id))

    carteira = filho.carteira

    if valor_pagar <= 0:
        flash("O valor deve ser positivo.", "error")
    elif valor_pagar > carteira.saldo:
        flash(f"Você não pode pagar mais do que deve (R$ {carteira.saldo}).", "error")
    else:
        # 1. Abate do saldo
        carteira.saldo -= valor_pagar

        # 2. Registra a transação
        transacao = Transacao(
            tipo='DEBIT_PAYMENT', # Tipo novo: Pagamento feito pelo pai
            valor=valor_pagar,
            descricao="Pagamento de Mesada/Tarefas (Saque)",
            carteira_id=carteira.id
        )
        db.session.add(transacao)

        # 3. Notifica o filho
        notif = Notificacao(
            tipo="PAGAMENTO_RECEBIDO",
            mensagem=f"Seu responsável te pagou R$ {valor_pagar:.2f}!",
            usuario_id=filho.usuario_id
        )
        db.session.add(notif)
        
        db.session.commit()
        flash(f"Pagamento de R$ {valor_pagar:.2f} registrado com sucesso!", "success")

    return redirect(url_for("parent.child_detail", child_id=child_id))