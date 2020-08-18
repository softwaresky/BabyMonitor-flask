
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# app = Flask(__name__, instance_relative_config=True)
# app = Flask("BabyMonitor", instance_relative_config=True)
# app.secret_key = b'A(\xeb\xf5\x0b'
# app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///./store/database.db"
#
# db = SQLAlchemy(app)

db = SQLAlchemy()

def create_app():
    app = Flask("BabyMonitor", instance_relative_config=True)
    app.secret_key = b'A(\xeb\xf5\x0b'
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///./store/database.db"
    db.init_app(app)
    return app