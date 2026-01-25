import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'voce-precisa-mudar-este-segredo'
    
    # --- Ajuste da Sessão ---
    SESSION_PERMANENT = False
    # No Render, "filesystem" apaga os logins quando o app reinicia.
    # Por enquanto vamos manter, mas saiba que você será deslogado a cada deploy.
    SESSION_TYPE = "filesystem" 
    
    # --- Ajuste do Banco de Dados ---
    # Tenta pegar a URL do Render (Postgres). Se não existir, usa seu SQLite local.
    _db_url = os.environ.get('DATABASE_URL')
    if _db_url and _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = _db_url or 'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False