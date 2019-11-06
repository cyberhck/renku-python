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
"""Project initialization tests."""

import os
import shutil
from contextlib import contextmanager
from tempfile import TemporaryDirectory

import pytest

from renku.core.commands.init import fetch_remote_template, validate_template
from renku.core.management.config import RENKU_HOME

TEMPLATE_URL = (
    'https://github.com/SwissDataScienceCenter/renku-project-template'
)
TEMPLATE_FOLDER = 'python-minimal'
TEMPLATE_BRANCH = 'master'
FAKE = 'NON_EXISTING'


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


@pytest.mark.parametrize(
    'url, folder, branch, result, error',
    [
        (TEMPLATE_URL, TEMPLATE_FOLDER, TEMPLATE_BRANCH, True, None),
        (TEMPLATE_URL, FAKE, TEMPLATE_BRANCH, None, ValueError),
        (TEMPLATE_URL, TEMPLATE_FOLDER, FAKE, None, ValueError),
        (None, None, None, None, Exception),
    ],
)
@pytest.mark.integration
def test_fetch_remote_template(url, folder, branch, result, error):
    """Test remote templates are correctly fetched"""
    with TemporaryDirectory() as tempdir:
        with raises(error):
            temp_folder = fetch_remote_template(url, folder, branch, tempdir)
            assert os.path.isdir(temp_folder) is True
            assert (
                os.path.isfile(os.path.join(temp_folder, 'Dockerfile')) is True
            )


@pytest.mark.integration
def test_validate_template():
    """Test template validation"""

    with TemporaryDirectory() as tempdir:
        # file error
        with raises(ValueError):
            validate_template(tempdir)

        # folder error
        shutil.rmtree(tempdir)
        os.makedirs(os.path.join(tempdir, RENKU_HOME))
        with raises(ValueError):
            validate_template(tempdir)

        # valid template
        shutil.rmtree(tempdir)
        template_folder = fetch_remote_template(
            TEMPLATE_URL, TEMPLATE_FOLDER, TEMPLATE_BRANCH, tempdir
        )
        assert validate_template(template_folder) is True
