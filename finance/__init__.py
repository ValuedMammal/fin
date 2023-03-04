import os
from flask import Flask


# Create, configure the app
def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY = "dev",
    )

   # Load instance config
    if test_config is None:
        app.config.from_pyfile("config.py", silent=True)
   
   # Load test config
    else:
        app.config.from_mapping(test_config)
   
    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Test hello
    @app.route("/hello")
    def hello():
        return "hello, world."
    
    from . import db
    db.init_app(app)

    from . import auth
    app.register_blueprint(auth.bp)
    
    from . import stat
    app.register_blueprint(stat.bp)

    from . import main
    app.register_blueprint(main.bp)
    app.add_url_rule("/", endpoint="index")

    return app   