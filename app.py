from flask import Flask, redirect, url_for, session, render_template, flash
from config import Config
from extensions import db, sess
from controllers.auth_controller import bp as auth_bp
from controllers.parent_controller import bp as parent_bp
from controllers.child_controller import bp as child_bp


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="views")
    app.config.from_object(Config)

    # Conecta o db e a sessão ao app
    db.init_app(app)
    sess.init_app(app)

    # Importa os modelos para que o SQLAlchemy saiba sobre eles
    with app.app_context():
        from models import models

    # --- MUDANÇA 3: Registrar TODOS os blueprints ---
    app.register_blueprint(auth_bp)
    app.register_blueprint(parent_bp)
    app.register_blueprint(child_bp)  # <-- Agora está registrado

    # --- Rota Root (Corrigida para os novos nomes) ---
    @app.get("/")
    def root():
        if session.get("user_email"):
            # Agora aponta para 'parent.home' e 'child.home'
            return redirect(url_for("parent.home" if session.get("role") == "PARENT" else "child.home"))

        return redirect(url_for("auth.login_page"))
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True, port=8000)
