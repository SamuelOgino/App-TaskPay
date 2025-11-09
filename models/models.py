from extensions import db  # Importa o objeto 'db' que criamos
from datetime import datetime
import uuid
from decimal import Decimal # Importante para dinheiro

# --- Função Auxiliar para gerar IDs UUID ---
def generate_uuid():
    return str(uuid.uuid4())

# --- Enums (Definições do seu diagrama) ---
# Usamos classes de string simples para fácil armazenamento no banco
class Role(str):
    PARENT = "PARENT"
    CHILD = "CHILD"

class TaskStatus(str):
    ATIVA = "ATIVA"
    INATIVA = "INATIVA"
    
class SubmissionStatus(str):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVISION = "NEEDS_REVISION"

class TransactionType(str):
    CREDIT_TASK = "CREDIT_TASK"
    CREDIT_ALLOWANCE = "CREDIT_ALLOWANCE"
    DEBIT_REWARD = "DEBIT_REWARD"
    ADJUSTMENT = "ADJUSTMENT"

class ResgateStatus(str):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DELIVERED = "DELIVERED"

# --- 1. Entidade Usuario ---
class Usuario(db.Model):
    __tablename__ = 'usuario'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senhaHash = db.Column(db.String(128), nullable=False)
    criadoEm = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    avatarUrl = db.Column(db.String(255), nullable=True)  
    
    # Relacionamentos (1-para-N)
    membros = db.relationship('Membro', back_populates='usuario', lazy=True)
    notificacoes = db.relationship('Notificacao', back_populates='usuario', lazy=True)

# --- 2. Entidade Familia ---
class Familia(db.Model):
    __tablename__ = 'familia'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    nome = db.Column(db.String(100), nullable=False)
    criadoEm = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relacionamentos (1-para-N)
    membros = db.relationship('Membro', back_populates='familia', lazy=True)
    convites = db.relationship('Convite', back_populates='familia', lazy=True)
    recompensas = db.relationship('Recompensa', back_populates='familia', lazy=True)

# --- 3. Entidade Membro ---
# (Classe central que liga Usuario e Familia)
class Membro(db.Model):
    __tablename__ = 'membro'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    role = db.Column(db.String(20), nullable=False, default=Role.CHILD)
    entradaEm = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Chaves Estrangeiras
    usuario_id = db.Column(db.String(36), db.ForeignKey('usuario.id'), nullable=False)
    familia_id = db.Column(db.String(36), db.ForeignKey('familia.id'), nullable=False)
    
    # Relacionamentos (N-para-1)
    usuario = db.relationship('Usuario', back_populates='membros')
    familia = db.relationship('Familia', back_populates='membros')
    
    # Relacionamentos (1-para-1)
    carteira = db.relationship('Carteira', back_populates='membro', uselist=False, lazy=True)
    progresso = db.relationship('Progresso', back_populates='membro', uselist=False, lazy=True)

    # Relacionamentos (1-para-N com Tarefa e Resgate)
    tarefas_criadas = db.relationship('Tarefa', back_populates='criador', foreign_keys='Tarefa.criador_id', lazy=True)
    tarefas_atribuidas = db.relationship('Tarefa', back_populates='executor', foreign_keys='Tarefa.executor_id', lazy=True)
    resgates = db.relationship('ResgateRecompensa', back_populates='membro', lazy=True)

    saldoXP = db.Column(db.Integer, nullable=False, default=0)

# --- 4. Entidade Carteira ---
class Carteira(db.Model):
    __tablename__ = 'carteira'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    saldo = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal('0.0'))
    moeda = db.Column(db.String(10), default='BRL')
    
    # Chave Estrangeira (Relação 1-para-1 com Membro)
    membro_id = db.Column(db.String(36), db.ForeignKey('membro.id'), nullable=False, unique=True)
    
    # Relacionamentos
    membro = db.relationship('Membro', back_populates='carteira')
    transacoes = db.relationship('Transacao', back_populates='carteira', lazy=True) # "Extrato"

# --- 5. Entidade Transacao (Extrato) ---
class Transacao(db.Model):
    __tablename__ = 'transacao'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    tipo = db.Column(db.String(50), nullable=False) # Usa TransactionType
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    descricao = db.Column(db.String(255), nullable=True)
    criadoEm = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Chave Estrangeira
    carteira_id = db.Column(db.String(36), db.ForeignKey('carteira.id'), nullable=False)
    
    # Relacionamento
    carteira = db.relationship('Carteira', back_populates='transacoes')

# --- 6. Entidade Progresso ---
class Progresso(db.Model):
    __tablename__ = 'progresso'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    xp = db.Column(db.Integer, default=0, nullable=False)
    nivel = db.Column(db.Integer, default=1, nullable=False)
    xp_total = db.Column(db.Integer, default=0, nullable=False)
    ultimaTarefaEm = db.Column(db.DateTime, nullable=True)
    # Chave Estrangeira (Relação 1-para-1 com Membro)
    membro_id = db.Column(db.String(36), db.ForeignKey('membro.id'), nullable=False, unique=True)
    
    # Relacionamento
    membro = db.relationship('Membro', back_populates='progresso')

# --- 7. Entidade Tarefa ---
class Tarefa(db.Model):
    __tablename__ = 'tarefa'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    titulo = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    valorBase = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal('0.0'))
    status = db.Column(db.String(30), nullable=False, default=TaskStatus.ATIVA)
    exigeFoto = db.Column(db.Boolean, default=False, nullable=False)
    prazo = db.Column(db.DateTime, nullable=True)
    prioridade = db.Column(db.String(10), nullable=True)      # 'BAIXA' | 'MEDIA' | 'ALTA'
    icone = db.Column(db.String(30), nullable=True)           # ex: 'fa-broom', 'fa-book', etc.
    
    # Chaves Estrangeiras (para Membro)
    criador_id = db.Column(db.String(36), db.ForeignKey('membro.id'), nullable=False) # PARENT
    executor_id = db.Column(db.String(36), db.ForeignKey('membro.id'), nullable=True) # CHILD
    
    # Relacionamentos
    criador = db.relationship('Membro', back_populates='tarefas_criadas', foreign_keys=[criador_id])
    executor = db.relationship('Membro', back_populates='tarefas_atribuidas', foreign_keys=[executor_id])
    submissao = db.relationship('Submissao', back_populates='tarefa', uselist=False, lazy=True) # 1-para-0..1

# --- 8. Entidade Submissao ---
class Submissao(db.Model):
    __tablename__ = 'submissao'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    nota = db.Column(db.Text, nullable=True)
    fotoUrl = db.Column(db.String(255), nullable=True)
    enviadaEm = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(30), nullable=False, default=SubmissionStatus.PENDING)
    valorAprovado = db.Column(db.Numeric(10, 2), nullable=True)
    aprovadaEm = db.Column(db.DateTime, nullable=True)

    # Chave Estrangeira (Relação 1-para-0..1 com Tarefa)
    tarefa_id = db.Column(db.String(36), db.ForeignKey('tarefa.id'), nullable=False, unique=True)
    
    # Relacionamento
    tarefa = db.relationship('Tarefa', back_populates='submissao')


# --- 9. Entidade Recompensa ---
class Recompensa(db.Model):
    __tablename__ = "recompensa"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    titulo = db.Column(db.String(120), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    custoXP = db.Column(db.Integer, nullable=False, default=0)
    ativa = db.Column(db.Boolean, nullable=False, default=True)
    criadoEm = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    familia_id = db.Column(db.String(36), db.ForeignKey("familia.id"), nullable=False)
    criador_id = db.Column(db.String(36), db.ForeignKey("membro.id"), nullable=False)

    familia = db.relationship("Familia", back_populates="recompensas")
    
    # --- CORREÇÃO 1 ---
    # Precisamos dizer ao SQLAlchemy qual 'foreign_keys' usar,
    # já que a tabela 'Membro' pode ter várias ligações.
    criador = db.relationship("Membro", foreign_keys=[criador_id])
    
    # --- CORREÇÃO 2 ---
    # Faltava este relacionamento de volta para ResgateRecompensa
    resgates = db.relationship("ResgateRecompensa", back_populates="recompensa", lazy=True)


# --- 10. Entidade Resgate ---
class ResgateRecompensa(db.Model):
    __tablename__ = "resgate_recompensa"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    recompensa_id = db.Column(db.String(36), db.ForeignKey("recompensa.id"), nullable=False)
    membro_id = db.Column(db.String(36), db.ForeignKey("membro.id"), nullable=False)
    xpPago = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default=ResgateStatus.PENDING)
    criadoEm = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # --- CORREÇÃO 3 ---
    # Adicionamos o 'back_populates' para completar a ligação
    recompensa = db.relationship("Recompensa", back_populates="resgates")
    membro = db.relationship("Membro", back_populates="resgates")


# ... (resto das classes, Convite e Notificacao) ...
# --- 11. Entidade Convite ---
class Convite(db.Model):
    __tablename__ = 'convite'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    expiraEm = db.Column(db.DateTime, nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    
    # Chave Estrangeira
    familia_id = db.Column(db.String(36), db.ForeignKey('familia.id'), nullable=False)
    
    # Relacionamento
    familia = db.relationship('Familia', back_populates='convites')

# --- 12. Entidade Notificacao ---
class Notificacao(db.Model):
    __tablename__ = 'notificacao'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    tipo = db.Column(db.String(50), nullable=False)
    mensagem = db.Column(db.String(255), nullable=False)
    enviadaEm = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    lidaEm = db.Column(db.DateTime, nullable=True) # Nulo se não foi lida
    
    # Chave Estrangeira
    usuario_id = db.Column(db.String(36), db.ForeignKey('usuario.id'), nullable=False)
    
    # Relacionamento
    usuario = db.relationship('Usuario', back_populates='notificacoes')

