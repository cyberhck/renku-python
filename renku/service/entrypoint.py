# -*- coding: utf-8 -*-
#
# Copyright 2019 - Swiss Data Science Center (SDSC)
# A partnership between École Polytechnique Fédérale de Lausanne (EPFL) and
# Eidgenössische Technische Hochschule Zürich (ETHZ).
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Renku service entry point."""
import logging
import os
import uuid

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from flask import Flask
from flask_apispec import FlaskApiSpec
from flask_swagger_ui import get_swaggerui_blueprint

from renku.service.cache import ServiceCache
from renku.service.config import API_SPEC_URL, API_VERSION, CACHE_DIR, \
    CACHE_PROJECTS_PATH, CACHE_UPLOADS_PATH, OPENAPI_VERSION, SERVICE_NAME, \
    SWAGGER_URL
from renku.service.views.cache import CACHE_BLUEPRINT_TAG, cache_blueprint, \
    list_projects_view, list_uploaded_files_view, project_clone, \
    upload_file_view
from renku.service.views.datasets import DATASET_BLUEPRINT_TAG, \
    add_file_to_dataset_view, create_dataset_view, dataset_blueprint, \
    list_dataset_files_view, list_datasets_view

logging.basicConfig(level=logging.DEBUG)


def make_cache():
    """Create cache structure."""
    sub_dirs = [CACHE_UPLOADS_PATH, CACHE_PROJECTS_PATH]

    for subdir in sub_dirs:
        if not subdir.exists():
            subdir.mkdir()

    return ServiceCache()


def create_app():
    """Creates a Flask app with necessary configuration."""
    app = Flask(__name__)
    app.secret_key = os.getenv('RENKU_SVC_SERVICE_KEY', uuid.uuid4().hex)

    app.config['UPLOAD_FOLDER'] = CACHE_DIR

    max_content_size = os.getenv('MAX_CONTENT_LENGTH')
    if max_content_size:
        app.config['MAX_CONTENT_LENGTH'] = max_content_size

    cache = make_cache()
    app.config['cache'] = cache

    build_routes(app)

    @app.route('/health')
    def health():
        import renku
        return 'renku repository service version {}\n'.format(
            renku.__version__
        )

    return app


def build_routes(app):
    """Register routes to given app instance."""
    app.config.update({
        'APISPEC_SPEC':
            APISpec(
                title=SERVICE_NAME,
                openapi_version=OPENAPI_VERSION,
                version=API_VERSION,
                plugins=[MarshmallowPlugin()],
            ),
        'APISPEC_SWAGGER_URL': API_SPEC_URL,
    })
    app.register_blueprint(cache_blueprint)
    app.register_blueprint(dataset_blueprint)

    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL, API_SPEC_URL, config={'app_name': 'Renku Service'}
    )
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    docs = FlaskApiSpec(app)

    docs.register(upload_file_view, blueprint=CACHE_BLUEPRINT_TAG)
    docs.register(list_uploaded_files_view, blueprint=CACHE_BLUEPRINT_TAG)
    docs.register(project_clone, blueprint=CACHE_BLUEPRINT_TAG)
    docs.register(list_projects_view, blueprint=CACHE_BLUEPRINT_TAG)

    docs.register(create_dataset_view, blueprint=DATASET_BLUEPRINT_TAG)
    docs.register(add_file_to_dataset_view, blueprint=DATASET_BLUEPRINT_TAG)
    docs.register(list_datasets_view, blueprint=DATASET_BLUEPRINT_TAG)
    docs.register(list_dataset_files_view, blueprint=DATASET_BLUEPRINT_TAG)


app = create_app()

if __name__ == '__main__':
    app.run()
