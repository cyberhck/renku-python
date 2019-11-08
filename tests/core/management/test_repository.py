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
"""Repository tests."""

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest


def raises(error):
    """Wrapper around pytest.raises to support None."""
    if error:
        return pytest.raises(error)
    else:

        @contextmanager
        def not_raises():
            try:
                yield
            except Exception as e:
                raise e

        return not_raises()


def test_init_empty_repository(local_client):
    """Test initializing an empty repository."""
    local_client.init_empty_repository()
    ls = os.listdir(local_client.path)
    assert len(ls) == 1
    assert ls[0] == '.git'


def test_update_repository_metadata(local_client):
    """Test updating metadata in an empty repository."""
    local_client.init_empty_repository()
    local_client.update_repository_metadata()
    ls = sorted(os.listdir(local_client.path))
    assert len(ls) == 2
    assert ls[1] == '.renku'


def test_import_from_template(local_client):
    """Test importing data from template."""
    OUTPUT_FILE = 'metadata.yml'
    local_client.init_empty_repository()
    with tempfile.TemporaryDirectory() as tempdir:
        template_path = Path(tempdir)
        fake_template_file = template_path / OUTPUT_FILE
        with fake_template_file.open('w') as dest:
            dest.writelines([
                'name: {{ name }}', 'description: {{ description }}',
                'created: {{ date_created }}', 'updated: {{ date_updated }}'
            ])
            metadata = {
                'name': 'name',
                'description': 'description',
                'date_created': 'now',
                'date_updated': 'now',
            }
        local_client.import_from_template(template_path, metadata)
        compiled_file = local_client.path / OUTPUT_FILE
        with open(compiled_file) as fr:
            compiled_content = fr.read()
            expected_content = (
                'name: name'
                'description: description'
                'created: now'
                'updated: now'
            )
            assert compiled_content == expected_content


# TODO: update this, should be checked somewhere else
def test_commit_cloned_repo(local_client):
    """Test committing after initializing a new repo."""
    local_client.init_empty_repository()
    local_client.update_repository_metadata()
    with local_client.commit():
        path = local_client.path
        file_path = path / 'text.txt'
        with file_path.open('w') as dest:
            dest.write('random text')
    ls = sorted(os.listdir(local_client.path))
    assert len(ls) == 3
    assert ls[2] == 'text.txt'
