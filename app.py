from flask import Flask, redirect, url_for, session, render_template, flash
from config import Config
from extensions import db, sess

# --- MUDANÇA 1: Importar os 10 novos Controllers (Blueprints) ---
from controllers.cadastro_controller import cadastro_bp
from controllers.login_controller import login_bp
from controllers.newtask_controller import newtask_bp
from controllers.taskspending_controller import taskspending_bp
from controllers.taskssubmission_controller import taskssubmission_bp
from controllers.notificacoes_controller import notificacoes_bp
from controllers.carteira_controller import carteira_bp
from controllers.resgatarrecompensa_controller import resgatar_bp
from controllers.criarrecompensa_controller import criarrecompensa_bp
from controllers.melhorarplano_controller import melhorarplano_bp

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="views")
    app.config.from_object(Config)

    # Conecta o db e a sessão ao app
    db.init_app(app)
    sess.init_app(app)

    # Importa os modelos para que o SQLAlchemy saiba sobre eles
    with app.app_context():
        from models import models
        # db.create_all() # Descomente se precisar criar as tabelas do zero

    # --- MUDANÇA 2: Registrar os 10 Blueprints ---
    app.register_blueprint(cadastro_bp)
    app.register_blueprint(login_bp)
    app.register_blueprint(newtask_bp)
    app.register_blueprint(taskspending_bp)
    app.register_blueprint(taskssubmission_bp)
    app.register_blueprint(notificacoes_bp)
    app.register_blueprint(carteira_bp)
    app.register_blueprint(resgatar_bp)
    app.register_blueprint(criarrecompensa_bp)
    app.register_blueprint(melhorarplano_bp)

    # --- MUDANÇA 3: Rota Root Atualizada ---
    # Agora aponta para os novos locais das Homes e do Login
    @app.get("/")
    def root():
        if session.get("user_email"):
            role = session.get("role")
            
            # Se for PAI, vai para a Home do Pai no Notificações Controller
            if role == "PARENT":
                return redirect(url_for("notificacoes.home_parent"))
            
            # Se for FILHO, vai para a Home do Filho no Notificações Controller
            elif role == "CHILD":
                return redirect(url_for("notificacoes.home_child"))

        # Se não estiver logado, vai para a tela de Login
        return redirect(url_for("login.login_page"))

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True, port=8000)