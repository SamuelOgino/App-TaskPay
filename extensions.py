# Em extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session

# Crie as instâncias das extensões aqui, "vazias".
# Elas serão conectadas ao nosso app no arquivo app.py
db = SQLAlchemy()
sess = Session()