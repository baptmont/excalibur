#!/bin/python3
# -*- coding: utf-8 -*-


import json
import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from flask import Flask, Blueprint
from werkzeug.utils import find_modules, import_string

from .. import configuration as conf
from .views import views


def to_pretty_json(value):
    value = json.loads(value)
    return json.dumps(value, sort_keys=True,
                      indent=4, separators=(',', ': '))


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(conf)
    app.register_blueprint(views)
    app.jinja_env.filters['pretty'] = to_pretty_json
    return app

myapp = create_app()

if __name__ == "__main__":
    application.run(host='0.0.0.0')
