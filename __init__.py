from flask import Flask
from .database import init_db # databaseモジュールをインポート

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your_secret_key_here'

    # アプリケーション起動時にデータベースを初期化
    init_db()

    from .auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .views import views_bp
    app.register_blueprint(views_bp, url_prefix='/')

    return app