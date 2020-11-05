import json

from flask import Flask
from jinja2 import select_autoescape
from .. import configuration as conf
from .views import views


def to_pretty_json(value):
    value = json.loads(value)
    return json.dumps(value, sort_keys=True, indent=4, separators=(",", ": "))


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(conf)
    app.register_blueprint(views)
    app.jinja_env.filters["pretty"] = to_pretty_json
    app.jinja_env.autoescape = select_autoescape(       
        default_for_string=True,    
        enabled_extensions=('html', 'jinja', 'html.jinja')
    )
    return app
