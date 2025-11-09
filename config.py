import os

# Pega o caminho absoluto da pasta onde este arquivo está
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Chave secreta para proteger as sessões
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'voce-precisa-mudar-este-segredo'
    
    # Configuração da Sessão (que você usava antes)
    SESSION_PERMANENT = False
    SESSION_TYPE = "filesystem"
    
    # --- A MÁGICA DO BANCO DE DADOS COMEÇA AQUI ---
    
    # Define onde o arquivo do banco de dados será salvo
    # 'app.db' será criado na sua pasta principal 
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
    
    # Desativa um recurso do SQLAlchemy que não precisamos e consome memória
    SQLALCHEMY_TRACK_MODIFICATIONS = False