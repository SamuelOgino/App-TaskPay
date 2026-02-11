from flask import Flask, redirect, url_for, session, render_template, flash
from config import Config
from extensions import db, sess

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

    db.init_app(app)
    sess.init_app(app)

    with app.app_context():
        from models import models
        db.create_all()

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

    @app.get("/")
    def root():
        if session.get("user_email"):
            role = session.get("role")
            
            if role == "PARENT":
                return redirect(url_for("notificacoes.home_parent"))
            
            elif role == "CHILD":
                return redirect(url_for("notificacoes.home_child"))

        return redirect(url_for("login.login_page"))

    return app

app = create_app()

if __name__ == "__main__":
   app.run(host='0.0.0.0', debug=True, port=8000)