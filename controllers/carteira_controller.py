from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from decimal import Decimal
import os
from werkzeug.utils import secure_filename
from extensions import db
from models.models import (
    Membro, Role, Carteira, Progresso, Transacao, TransactionType, 
    Submissao, SubmissionStatus, Usuario, Notificacao
)

# Blueprint para Carteira e Perfil
carteira_bp = Blueprint("carteira", __name__, url_prefix="/wallet")

# --- Auxiliar ---
def _get_current_member():
    uid = session.get("user_id")
    role = session.get("role")
    if not uid or not role: return None
    return Membro.query.filter_by(usuario_id=uid, role=role).first()

# ==========================================================
# VCP 09 - CONSULTAR SALDO E PERFIL (Geral)
# ==========================================================

@carteira_bp.get("/profile")
def profile_page():
    """
    Rota inteligente: detecta se é PAI ou FILHO e mostra o perfil correto.
    Substitui as rotas antigas /parent/profile e /child/profile.
    """
    membro = _get_current_member()
    if not membro:
        return redirect(url_for("login.login_page"))

    # --- LÓGICA DO FILHO (XP, Nível, Streak, Saldo) ---
    if membro.role == Role.CHILD:
        # Garante estruturas
        progresso = membro.progresso or Progresso(membro_id=membro.id)
        if not membro.progresso: db.session.add(progresso)
        
        carteira = membro.carteira or Carteira(membro_id=membro.id, saldo=0)
        if not membro.carteira: db.session.add(carteira)
        db.session.commit()

        # Cálculo do Streak (Foguinho)
        is_streak_active = False
        streak_dias = 0
        submissoes_aprovadas = db.session.query(Submissao.aprovadaEm).join(Submissao.tarefa).filter(
            Submissao.tarefa.has(executor_id=membro.id),
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

        # Dados de XP
        current_xp = progresso.xp
        max_xp = 1000
        xp_percent = (current_xp / max_xp) * 100 if max_xp > 0 else 0
        
        tarefas_concluidas_count = Submissao.query.join(Submissao.tarefa).filter(
            Submissao.tarefa.has(executor_id=membro.id),
            Submissao.status == SubmissionStatus.APPROVED
        ).count()

        return render_template(
            "child/profile.html",
            membro=membro,
            progresso=progresso,
            current_xp=current_xp,
            max_xp=max_xp,
            xp_percent=xp_percent,
            nivel=progresso.nivel,
            saldo_atual=carteira.saldo,
            is_streak_active=is_streak_active,
            streak_dias=streak_dias,
            xp_total_acumulado=membro.saldoXP,
            tarefas_concluidas_count=tarefas_concluidas_count
        )

    # --- LÓGICA DO PAI (Resumo dos Filhos) ---
    else:
        filhos = Membro.query.filter_by(familia_id=membro.familia_id, role=Role.CHILD).all()
        filhos_data = [] 
        
        for filho in filhos:
            carteira_f = filho.carteira or Carteira(membro_id=filho.id, saldo=0)
            if not filho.carteira: db.session.add(carteira_f)
            
            # Tarefas Concluídas
            concluidas = Submissao.query.join(Submissao.tarefa).filter(
                Submissao.tarefa.has(executor_id=filho.id),
                Submissao.status == SubmissionStatus.APPROVED
            ).count()
            
            # Total Ganho (Histórico)
            total_ganho = db.session.query(func.sum(Transacao.valor)).filter(
                Transacao.carteira_id == carteira_f.id,
                Transacao.tipo.in_([TransactionType.CREDIT_TASK, TransactionType.CREDIT_ALLOWANCE])
            ).scalar() or 0.0

            # Lógica Streak simplificada para visualização do pai
            is_streak = False # (Pode replicar a lógica acima se quiser exibir o fogo para o pai)
            
            filhos_data.append({
                "membro": filho,
                "tarefas_concluidas": concluidas,
                "saldo": carteira_f.saldo,
                "total_ganho": total_ganho
            })
        
        db.session.commit()
        plano_atual = membro.familia.plano

        return render_template(
            "parent/profile.html",
            usuario=membro.usuario,
            filhos_data=filhos_data,
            plano_atual=plano_atual
        )

# ==========================================================
# VCP 09 - DETALHES FINANCEIROS (Visão do Pai)
# ==========================================================

@carteira_bp.get("/details/<child_id>")
def child_detail(child_id):
    """Exibe o extrato detalhado de um filho específico para o PAI."""
    parent = _get_current_member()
    if not parent or parent.role != Role.PARENT:
        return redirect(url_for("login.login_page"))

    filho = Membro.query.get(child_id)
    if not filho or filho.familia_id != parent.familia_id:
        flash("Permissão negada.", "error")
        return redirect(url_for("carteira.profile_page"))

    carteira = filho.carteira
    if not carteira:
        carteira = Carteira(membro_id=filho.id, saldo=0)
        db.session.add(carteira)
        db.session.commit()

    # Total Ganho (Tarefas + Mesada)
    total_ganho = db.session.query(func.sum(Transacao.valor)).filter(
        Transacao.carteira_id == carteira.id,
        Transacao.tipo.in_([TransactionType.CREDIT_TASK, TransactionType.CREDIT_ALLOWANCE])
    ).scalar() or 0.0

    # Total Pago pelo pai (Saques)
    total_pago_historico = db.session.query(func.sum(Transacao.valor)).filter(
        Transacao.carteira_id == carteira.id,
        Transacao.tipo == 'DEBIT_PAYMENT' 
    ).scalar() or 0.0

    saldo_devedor = carteira.saldo

    # Histórico Recente
    historico = Transacao.query.filter_by(carteira_id=carteira.id)\
        .order_by(Transacao.criadoEm.desc())\
        .limit(10).all()

    return render_template(
        "parent/child_detail.html",
        filho=filho,
        total_ganho=total_ganho,
        total_pago_historico=total_pago_historico,
        saldo_devedor=saldo_devedor,
        historico=historico
    )

@carteira_bp.post("/pay/<child_id>")
def pay_child_submit(child_id):
    """Pai registra um pagamento manual (Mesada/Pix)."""
    parent = _get_current_member()
    if not parent or parent.role != Role.PARENT:
        return redirect(url_for("login.login_page"))

    filho = Membro.query.get(child_id)
    if not filho or filho.familia_id != parent.familia_id:
        return redirect(url_for("carteira.profile_page"))

    valor_str = request.form.get("valor_pagamento")
    try:
        valor_pagar = Decimal(valor_str.replace(",", "."))
    except:
        flash("Valor inválido.", "error")
        return redirect(url_for("carteira.child_detail", child_id=child_id))

    carteira = filho.carteira

    if valor_pagar <= 0:
        flash("O valor deve ser positivo.", "error")
    elif valor_pagar > carteira.saldo:
        flash(f"Você não pode pagar mais do que deve (R$ {carteira.saldo}).", "error")
    else:
        # Abate do saldo e registra transação
        carteira.saldo -= valor_pagar
        transacao = Transacao(
            tipo='DEBIT_PAYMENT',
            valor=valor_pagar,
            descricao="Pagamento (Saque)",
            carteira_id=carteira.id
        )
        db.session.add(transacao)

        notif = Notificacao(
            tipo="PAGAMENTO_RECEBIDO",
            mensagem=f"Pagamento recebido: R$ {valor_pagar:.2f}!",
            usuario_id=filho.usuario_id
        )
        db.session.add(notif)
        db.session.commit()
        flash(f"Pagamento de R$ {valor_pagar:.2f} registrado!", "success")

    return redirect(url_for("carteira.child_detail", child_id=child_id))


# ==========================================================
# EDIÇÃO DE PERFIL (Foto e Nome) - Comum a Pai e Filho
# ==========================================================

@carteira_bp.get("/edit")
def edit_profile_page():
    """Exibe tela de edição de perfil."""
    membro = _get_current_member()
    if not membro: return redirect(url_for("login.login_page"))

    template = "child/edit_profile.html" if membro.role == Role.CHILD else "parent/edit_profile.html"
    return render_template(template, membro=membro)

@carteira_bp.post("/edit")
def edit_profile_submit():
    """Processa upload de foto e mudança de nome."""
    membro = _get_current_member()
    if not membro: return redirect(url_for("login.login_page"))
    
    usuario = membro.usuario

    # 1. Atualiza Nome
    novo_nome = request.form.get("nome")
    if novo_nome and novo_nome.strip() != usuario.nome:
        usuario.nome = novo_nome.strip()
        flash("Nome atualizado!", "success")

    # 2. Atualiza Foto
    foto = request.files.get('foto_perfil')
    if foto and foto.filename != '':
        try:
            nome_seguro = secure_filename(foto.filename)
            nome_final = f"avatar_{usuario.id}_{nome_seguro}"
            
            caminho_dir = os.path.join(current_app.static_folder, 'uploads', 'avatars')
            os.makedirs(caminho_dir, exist_ok=True)
            foto.save(os.path.join(caminho_dir, nome_final))
            
            # Remove foto antiga se existir
            if usuario.avatarUrl:
                # Lógica simples de limpeza (opcional)
                pass 

            # Salva caminho relativo (ex: uploads/avatars/foto.jpg)
            # O replace garante barras normais mesmo no Windows
            usuario.avatarUrl = os.path.join('uploads', 'avatars', nome_final).replace("\\", "/")
            flash("Foto atualizada!", "success")
        except Exception as e:
            flash(f"Erro na foto: {e}", "error")

    db.session.commit()
    return redirect(url_for("carteira.profile_page"))