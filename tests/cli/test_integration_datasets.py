# -*- coding: utf-8 -*-
#
# Copyright 2017-2019 - Swiss Data Science Center (SDSC)
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
"""Integration tests for dataset command."""
import os
import subprocess
from pathlib import Path

import git
import pytest

from renku.cli import cli
from renku.core.commands.clone import renku_clone
from renku.core.utils.contexts import chdir


@pytest.mark.parametrize(
    'doi', [{
        'doi': '10.5281/zenodo.2658634',
        'input': 'y',
        'file': 'pyndl_naive_discriminat_v064',
        'creator': 'K.Sering,M.Weitz,D.Künstle,L.Schneider',
        'version': 'v0.6.4'
    }, {
        'doi': '10.7910/DVN/S8MSVF',
        'input': 'y',
        'file': 'hydrogen_mapping_laws_a_1',
        'creator': 'M.Trevor',
        'version': '1'
    }]
)
@pytest.mark.integration
def test_dataset_import_real_doi(runner, project, doi, sleep_after):
    """Test dataset import for existing DOI."""
    result = runner.invoke(
        cli, ['dataset', 'import', doi['doi']], input=doi['input']
    )
    assert 0 == result.exit_code
    assert 'OK' in result.output

    result = runner.invoke(cli, ['dataset'])

    assert 0 == result.exit_code
    assert doi['file'] in result.output
    assert doi['creator'] in result.output

    result = runner.invoke(cli, ['dataset', 'ls-tags', doi['file']])
    assert 0 == result.exit_code
    assert doi['version'] in result.output


@pytest.mark.parametrize(
    'doi', [
        ('10.5281/zenodo.3239980', 'n'),
        ('10.5281/zenodo.3188334', 'y'),
        ('10.7910/DVN/TJCLKP', 'n'),
        ('10.7910/DVN/S8MSVF', 'y'),
        ('10.5281/zenodo.597964', 'y'),
        ('10.5281/zenodo.3236928', 'n'),
        ('10.5281/zenodo.2671633', 'n'),
        ('10.5281/zenodo.3237420', 'n'),
        ('10.5281/zenodo.3236928', 'n'),
        ('10.5281/zenodo.3188334', 'y'),
        ('10.5281/zenodo.3236928', 'n'),
        ('10.5281/zenodo.2669459', 'n'),
        ('10.5281/zenodo.2371189', 'n'),
        ('10.5281/zenodo.2651343', 'n'),
        ('10.5281/zenodo.1467859', 'n'),
        ('10.5281/zenodo.3240078', 'n'),
        ('10.5281/zenodo.3240053', 'n'),
        ('10.5281/zenodo.3240010', 'n'),
        ('10.5281/zenodo.3240012', 'n'),
        ('10.5281/zenodo.3240006', 'n'),
        ('10.5281/zenodo.3239996', 'n'),
        ('10.5281/zenodo.3239256', 'n'),
        ('10.5281/zenodo.3237813', 'n'),
        ('10.5281/zenodo.3239988', 'y'),
    ]
)
@pytest.mark.integration
def test_dataset_import_real_param(doi, runner, project, sleep_after):
    """Test dataset import and check metadata parsing."""
    result = runner.invoke(cli, ['dataset', 'import', doi[0]], input=doi[1])

    if 'y' == doi[1]:
        assert 0 == result.exit_code
        assert 'OK' in result.output
    else:
        assert 1 == result.exit_code

    result = runner.invoke(cli, ['dataset'])
    assert 0 == result.exit_code


@pytest.mark.parametrize(
    'doi', [
        ('10.5281/zenodo.3239984', 'n'),
        ('zenodo.org/record/3239986', 'n'),
        ('10.5281/zenodo.3239982', 'n'),
    ]
)
@pytest.mark.integration
def test_dataset_import_uri_404(doi, runner, project, sleep_after):
    """Test dataset import and check that correct exception is raised."""
    result = runner.invoke(cli, ['dataset', 'import', doi[0]], input=doi[1])
    assert 2 == result.exit_code

    result = runner.invoke(cli, ['dataset'])
    assert 0 == result.exit_code


@pytest.mark.integration
def test_dataset_import_real_doi_warnings(runner, project, sleep_after):
    """Test dataset import for existing DOI and dataset"""
    result = runner.invoke(
        cli, ['dataset', 'import', '10.5281/zenodo.1438326'], input='y'
    )
    assert 0 == result.exit_code
    assert 'Warning: Newer version found' in result.output
    assert 'OK'

    result = runner.invoke(
        cli, ['dataset', 'import', '10.5281/zenodo.1438326'], input='y'
    )
    assert 1 == result.exit_code
    assert 'Warning: Newer version found' in result.output
    assert 'Error: Dataset exists:' in result.output

    result = runner.invoke(
        cli, ['dataset', 'import', '10.5281/zenodo.597964'], input='y'
    )
    assert 0 == result.exit_code
    assert 'Warning: Newer version found' not in result.output
    assert 'Error: Dataset exists:' not in result.output
    assert 'OK' in result.output

    result = runner.invoke(cli, ['dataset'])

    assert 0 == result.exit_code
    assert 'pyndl_naive_discriminat_v064' in result.output
    assert 'K.Sering,M.Weitz,D.Künstle,L.Schneider' in result.output


@pytest.mark.parametrize(
    'doi', [('10.5281/zenodo.5979642342', 'Zenodo'),
            ('10.7910/DVN/S8MSVFXXXX', 'DVN')]
)
@pytest.mark.integration
def test_dataset_import_fake_doi(runner, project, doi):
    """Test error raising for non-existing DOI."""
    result = runner.invoke(cli, ['dataset', 'import', doi[0]], input='y')

    assert 2 == result.exit_code
    assert 'URI not found.' in result.output \
           or 'Provider {} not found'.format(doi[1]) in result.output


@pytest.mark.parametrize(
    'url', [
        'https://zenodo.org/record/2621208',
        (
            'https://dataverse.harvard.edu/dataset.xhtml'
            '?persistentId=doi:10.7910/DVN/S8MSVF'
        )
    ]
)
@pytest.mark.integration
def test_dataset_import_real_http(runner, project, url, sleep_after):
    """Test dataset import through HTTPS."""
    result = runner.invoke(cli, ['dataset', 'import', url], input='y')

    assert 0 == result.exit_code
    assert 'OK' in result.output


@pytest.mark.parametrize(
    'url', [
        'https://zenodo.org/record/2621201248',
        'https://dataverse.harvard.edu/dataset.xhtml' +
        '?persistentId=doi:10.7910/DVN/S8MSVFXXXX'
    ]
)
@pytest.mark.integration
def test_dataset_import_fake_http(runner, project, url):
    """Test dataset import through HTTPS."""
    result = runner.invoke(cli, ['dataset', 'import', url], input='y')

    assert 2 == result.exit_code
    assert 'URI not found.' in result.output


@pytest.mark.integration
def test_dataset_import_and_extract(runner, project, client, sleep_after):
    """Test dataset import and extract files."""
    URL = 'https://zenodo.org/record/2658634'
    result = runner.invoke(
        cli, ['dataset', 'import', '--extract', '--short-name', 'remote', URL],
        input='y'
    )
    assert 0 == result.exit_code

    with client.with_dataset('remote') as dataset:
        AN_EXTRACTED_FILE = 'data/remote/quantling-pyndl-c34259c/doc/make.bat'
        assert dataset.find_file(AN_EXTRACTED_FILE)


@pytest.mark.integration
def test_dataset_import_different_names(runner, client, sleep_after):
    """Test can import same DOI under different names."""
    DOI = '10.5281/zenodo.2658634'
    result = runner.invoke(
        cli, ['dataset', 'import', '--short-name', 'name-1', DOI], input='y'
    )
    assert 0 == result.exit_code
    assert 'OK' in result.output

    result = runner.invoke(
        cli, ['dataset', 'import', '--short-name', 'name-2', DOI], input='y'
    )
    assert 0 == result.exit_code
    assert 'OK' in result.output


@pytest.mark.integration
def test_dataset_import_ignore_uncompressed_files(
    runner, project, sleep_after
):
    """Test dataset import ignores uncompressed files."""
    URL = 'https://zenodo.org/record/3251128'
    result = runner.invoke(
        cli, ['dataset', 'import', '--extract', URL], input='y'
    )
    assert 0 == result.exit_code
    assert 'Gorne_Diaz_database_2019.csv' in result.output


@pytest.mark.integration
def test_dataset_reimport_removed_dataset(runner, project, sleep_after):
    """Test re-importing of deleted datasets works."""
    DOI = '10.5281/zenodo.2658634'
    result = runner.invoke(
        cli, ['dataset', 'import', DOI, '--short-name', 'my-dataset'],
        input='y'
    )
    assert 0 == result.exit_code

    result = runner.invoke(cli, ['dataset', 'rm', 'my-dataset'])
    assert 0 == result.exit_code

    result = runner.invoke(
        cli, ['dataset', 'import', DOI, '--short-name', 'my-dataset'],
        input='y'
    )
    assert 0 == result.exit_code


@pytest.mark.integration
def test_dataset_export_upload_file(
    runner, project, tmpdir, client, zenodo_sandbox
):
    """Test successful uploading of a file to Zenodo deposit."""
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])

    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create data file
    new_file = tmpdir.join('datafile.csv')
    new_file.write('1,2,3')

    # add data to dataset
    result = runner.invoke(
        cli, ['dataset', 'add', 'my-dataset',
              str(new_file)]
    )
    assert 0 == result.exit_code

    with client.with_dataset('my-dataset') as dataset:
        dataset.description = 'awesome dataset'
        dataset.creator[0].affiliation = 'eth'

    data_repo = git.Repo(str(project))
    data_repo.git.add(update=True)
    data_repo.index.commit('metadata updated')

    result = runner.invoke(cli, ['dataset', 'export', 'my-dataset', 'zenodo'])

    assert 0 == result.exit_code
    assert 'Exported to:' in result.output
    assert 'zenodo.org/deposit' in result.output


@pytest.mark.integration
def test_dataset_export_upload_tag(
    runner, project, tmpdir, client, zenodo_sandbox
):
    """Test successful uploading of a file to Zenodo deposit."""
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create data file
    new_file = tmpdir.join('datafile.csv')
    new_file.write('1,2,3')

    # add data to dataset
    result = runner.invoke(
        cli, ['dataset', 'add', 'my-dataset',
              str(new_file)]
    )
    assert 0 == result.exit_code

    with client.with_dataset('my-dataset') as dataset:
        dataset.description = 'awesome dataset'
        dataset.creator[0].affiliation = 'eth'

    data_repo = git.Repo(str(project))
    data_repo.git.add(update=True)
    data_repo.index.commit('metadata updated')

    # tag dataset
    result = runner.invoke(cli, ['dataset', 'tag', 'my-dataset', '1.0'])
    assert 0 == result.exit_code

    # create data file
    new_file = tmpdir.join('datafile2.csv')
    new_file.write('1,2,3,4')

    # add data to dataset
    result = runner.invoke(
        cli, ['dataset', 'add', 'my-dataset',
              str(new_file)]
    )
    assert 0 == result.exit_code

    # tag dataset
    result = runner.invoke(cli, ['dataset', 'tag', 'my-dataset', '2.0'])
    assert 0 == result.exit_code

    result = runner.invoke(
        cli, ['dataset', 'export', 'my-dataset', 'zenodo'], input='3'
    )

    assert 0 == result.exit_code
    assert 'Exported to:' in result.output
    assert 'zenodo.org/deposit' in result.output
    assert '2/2' in result.output

    result = runner.invoke(
        cli, ['dataset', 'export', 'my-dataset', 'zenodo'], input='2'
    )

    assert 0 == result.exit_code
    assert 'Exported to:' in result.output
    assert 'zenodo.org/deposit' in result.output
    assert '1/1' in result.output

    result = runner.invoke(
        cli, ['dataset', 'export', 'my-dataset', 'zenodo'], input='1'
    )

    assert 0 == result.exit_code
    assert 'Exported to:' in result.output
    assert 'zenodo.org/deposit' in result.output
    assert '2/2' in result.output


@pytest.mark.integration
def test_dataset_export_upload_multiple(
    runner, project, tmpdir, client, zenodo_sandbox
):
    """Test successful uploading of a files to Zenodo deposit."""
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])

    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create data file
    paths = []
    for i in range(3):
        new_file = tmpdir.join('file_{0}'.format(i))
        new_file.write(str(i))
        paths.append(str(new_file))

    # add data
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'my-dataset'] + paths,
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    with client.with_dataset('my-dataset') as dataset:
        dataset.description = 'awesome dataset'
        dataset.creator[0].affiliation = 'eth'

    data_repo = git.Repo(str(project))
    data_repo.git.add(update=True)
    data_repo.index.commit('metadata updated')

    result = runner.invoke(cli, ['dataset', 'export', 'my-dataset', 'zenodo'])

    assert 0 == result.exit_code
    assert 'Exported to:' in result.output
    assert 'zenodo.org/deposit' in result.output


@pytest.mark.integration
def test_dataset_export_upload_failure(runner, tmpdir, client, zenodo_sandbox):
    """Test failed uploading of a file to Zenodo deposit."""
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])

    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create data file
    new_file = tmpdir.join('datafile.csv')
    new_file.write('1,2,3')

    # add data to dataset
    result = runner.invoke(
        cli, ['dataset', 'add', 'my-dataset',
              str(new_file)]
    )
    assert 0 == result.exit_code

    result = runner.invoke(cli, ['dataset', 'export', 'my-dataset', 'zenodo'])

    assert 2 == result.exit_code
    assert 'metadata.creators.0.affiliation' in result.output
    assert 'metadata.description' in result.output


@pytest.mark.integration
def test_dataset_export_published_url(
    runner, project, tmpdir, client, zenodo_sandbox
):
    """Test publishing of dataset."""
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])

    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create data file
    new_file = tmpdir.join('datafile.csv')
    new_file.write('1,2,3')

    # add data to dataset
    result = runner.invoke(
        cli, ['dataset', 'add', 'my-dataset',
              str(new_file)]
    )
    assert 0 == result.exit_code

    with client.with_dataset('my-dataset') as dataset:
        dataset.description = 'awesome dataset'
        dataset.creator[0].affiliation = 'eth'

    data_repo = git.Repo(str(project))
    data_repo.git.add(update=True)
    data_repo.index.commit('metadata updated')

    result = runner.invoke(
        cli, ['dataset', 'export', 'my-dataset', 'zenodo', '--publish']
    )

    assert 0 == result.exit_code
    assert 'Exported to:' in result.output
    assert 'zenodo.org/record' in result.output


@pytest.mark.integration
def test_export_dataset_wrong_provider(
    runner, project, tmpdir, client, zenodo_sandbox
):
    """Test non-existing provider."""
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])

    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create data file
    new_file = tmpdir.join('datafile.csv')
    new_file.write('1,2,3')

    # add data to dataset
    result = runner.invoke(
        cli, ['dataset', 'add', 'my-dataset',
              str(new_file)]
    )
    assert 0 == result.exit_code

    result = runner.invoke(
        cli, ['dataset', 'export', 'my-dataset', 'notzenodo']
    )
    assert 2 == result.exit_code
    assert 'Unknown provider.' in result.output


@pytest.mark.integration
def test_dataset_export(runner, client, project):
    """Check dataset not found exception raised."""
    result = runner.invoke(
        cli, ['dataset', 'export', 'doesnotexists', 'somewhere']
    )

    assert 2 == result.exit_code
    assert 'Dataset is not found.' in result.output


@pytest.mark.integration
def test_export_dataset_unauthorized(
    runner, project, client, tmpdir, zenodo_sandbox
):
    """Test unauthorized exception raised."""
    client.set_value('zenodo', 'access_token', 'not-a-token')
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create data file
    new_file = tmpdir.join('datafile.csv')
    new_file.write('1,2,3')

    # add data to dataset
    result = runner.invoke(
        cli, ['dataset', 'add', 'my-dataset',
              str(new_file)]
    )
    assert 0 == result.exit_code

    result = runner.invoke(cli, ['dataset', 'export', 'my-dataset', 'zenodo'])

    assert 2 == result.exit_code
    assert 'Access unauthorized - update access token.' in result.output

    secret = client.get_value('zenodo', 'secret')
    assert secret is None


@pytest.mark.integration
@pytest.mark.parametrize(
    'params,path',
    [
        # add data with no destination
        (['-s', 'docker'], 'data/remote/docker/r/Dockerfile'),
        (['-s', 'docker/r/Dockerfile'], 'data/remote/Dockerfile'),
        # add data to a non-existing destination
        (['-s', 'docker', '-d', 'new'], 'data/remote/new/r/Dockerfile'),
        (['-s', 'docker/r', '-d', 'new'], 'data/remote/new/Dockerfile'),
        (['-s', 'docker/r/Dockerfile', '-d', 'new'], 'data/remote/new'),
        # add data to an existing destination
        (['-s', 'docker', '-d', 'existing'
          ], 'data/remote/existing/docker/r/Dockerfile'),
        (['-s', 'docker/r', '-d', 'existing'
          ], 'data/remote/existing/r/Dockerfile'),
        (['-s', 'docker/r/Dockerfile', '-d', 'existing'
          ], 'data/remote/existing/Dockerfile'),
    ]
)
def test_add_data_from_git(runner, client, params, path):
    """Test add data to datasets from a git repository."""
    REMOTE = 'https://github.com/SwissDataScienceCenter/renku-jupyter.git'

    # create a dataset and add a file to it
    result = runner.invoke(
        cli,
        [
            'dataset', 'add', 'remote', '--create', '--ref', '0.3.0', '-s',
            'LICENSE', '-d', 'existing/LICENSE', REMOTE
        ],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    result = runner.invoke(
        cli,
        ['dataset', 'add', 'remote', '--ref', '0.3.0', REMOTE] + params,
        catch_exceptions=False,
    )

    assert 0 == result.exit_code
    assert Path(path).exists()


@pytest.mark.integration
def test_add_from_git_copies_metadata(runner, client):
    """Test an import from a git repository keeps creators name."""
    # create a dataset and add a file to it
    result = runner.invoke(
        cli,
        [
            'dataset', 'add', 'remote', '--create', '--ref', 'v0.3.0', '-s',
            'README.rst',
            'https://github.com/SwissDataScienceCenter/renku-python.git'
        ],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    dataset = client.load_dataset('remote')
    assert dataset.files[0].name == 'README.rst'
    assert 'mailto:jiri.kuncar@gmail.com' in str(dataset.files[0].creator)
    assert 'mailto:rokroskar@gmail.co' in str(dataset.files[0].creator)


@pytest.mark.integration
@pytest.mark.parametrize(
    'params,n_urls,message', [
        ([], 0, 'No URL is specified'),
        (['-s', 'file', '-d', 'new-file'], 0, 'No URL is specified'),
        (['-s', 'file'], 2, 'Cannot add multiple URLs'),
        (['-d', 'file'], 2, 'Cannot add multiple URLs'),
        (['-s', 'non-existing'], 1, 'No such file or directory'),
        (['-s', 'docker', '-d', 'LICENSE'
          ], 1, 'Cannot copy multiple files or directories to a file'),
        (['-s', 'LICENSE', '-s', 'Makefile', '-d', 'LICENSE'
          ], 1, 'Cannot copy multiple files or directories to a file'),
        (['-d', 'LICENSE'], 1, 'Cannot copy repo to file'),
    ]
)
def test_usage_error_in_add_from_git(runner, client, params, n_urls, message):
    """Test user's errors when adding to a dataset from a git repository."""
    REMOTE = 'https://github.com/SwissDataScienceCenter/renku-jupyter.git'

    # create a dataset and add a file to it
    result = runner.invoke(
        cli,
        [
            'dataset', 'add', 'remote', '--create', '--ref', '0.3.0', '-s',
            'LICENSE', REMOTE
        ],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    urls = n_urls * [REMOTE]

    result = runner.invoke(
        cli,
        ['dataset', 'add', 'remote', '--ref', '0.3.0'] + params + urls,
        catch_exceptions=False,
    )
    assert result.exit_code == 2
    assert message in result.output


def read_dataset_file_metadata(client, dataset_name, filename):
    """Return metadata from dataset's YAML file."""
    with client.with_dataset(dataset_name) as dataset:
        assert client.get_dataset_path(dataset.name).exists()

        for file_ in dataset.files:
            if file_.path.endswith(filename):
                return file_


@pytest.mark.integration
@pytest.mark.parametrize(
    'params', [[], ['-I', 'CHANGES.rst'], ['-I', 'C*'], ['remote']]
)
def test_dataset_update(client, runner, params):
    """Test local copy is updated when remote file is updates."""
    # Add dataset to project
    result = runner.invoke(
        cli, [
            'dataset', 'add', '--create', 'remote', '--ref', 'v0.3.0', '-s',
            'CHANGES.rst',
            'https://github.com/SwissDataScienceCenter/renku-python.git'
        ],
        catch_exceptions=False
    )
    assert 0 == result.exit_code

    before = read_dataset_file_metadata(client, 'remote', 'CHANGES.rst')

    result = runner.invoke(
        cli, ['dataset', 'update'] + params, catch_exceptions=False
    )
    assert 0 == result.exit_code

    after = read_dataset_file_metadata(client, 'remote', 'CHANGES.rst')
    assert after._id == before._id
    assert after._label != before._label
    assert after.added == before.added
    assert after.url == before.url
    assert after.based_on._id == before.based_on._id
    assert after.based_on._label != before.based_on._label
    assert after.based_on.path == before.based_on.path
    assert after.based_on.based_on is None


@pytest.mark.integration
def test_dataset_update_remove_file(client, runner):
    """Test local copy is removed when remote file is removed."""
    # Add dataset to project
    result = runner.invoke(
        cli, [
            'dataset', 'add', '--create', 'remote', '-s', 'docs/authors.rst',
            '--ref', 'v0.3.0',
            'https://github.com/SwissDataScienceCenter/renku-python.git'
        ],
        catch_exceptions=False
    )
    assert 0 == result.exit_code
    file_path = client.path / 'data' / 'remote' / 'authors.rst'
    assert file_path.exists()

    # docs/authors.rst does not exists in v0.5.0

    result = runner.invoke(
        cli, ['dataset', 'update', '--ref', 'v0.5.0'], catch_exceptions=False
    )
    assert 0 == result.exit_code
    assert 'Some files are deleted from remote.' in result.output
    assert file_path.exists()

    result = runner.invoke(
        cli, ['dataset', 'update', '--ref', 'v0.5.0', '--delete'],
        catch_exceptions=False
    )
    assert 0 == result.exit_code
    assert not file_path.exists()


@pytest.mark.integration
@pytest.mark.parametrize(
    'params', [['-I', 'non-existing'], ['non-existing-dataset']]
)
def test_dataset_invalid_update(client, runner, params):
    """Test updating a non-existing path."""
    # Add dataset to project
    result = runner.invoke(
        cli, [
            'dataset', 'add', '--create', 'remote', '-s', 'docs/authors.rst',
            '--ref', 'v0.3.0',
            'https://github.com/SwissDataScienceCenter/renku-python.git'
        ],
        catch_exceptions=False
    )
    assert 0 == result.exit_code

    result = runner.invoke(
        cli, ['dataset', 'update'] + params, catch_exceptions=False
    )
    assert 2 == result.exit_code


@pytest.mark.integration
@pytest.mark.parametrize(
    'params',
    [[], ['-I', 'CHANGES.rst'], ['-I', 'CH*'], ['dataset-1', 'dataset-2']]
)
def test_dataset_update_multiple_datasets(
    client, runner, data_repository, directory_tree, params
):
    """Test update with multiple datasets."""
    path1 = client.path / 'data' / 'dataset-1' / 'CHANGES.rst'
    path2 = client.path / 'data' / 'dataset-2' / 'CHANGES.rst'
    # Add dataset to project
    result = runner.invoke(
        cli, [
            'dataset', 'add', '--create', 'dataset-1', '--ref', 'v0.3.0', '-s',
            'CHANGES.rst',
            'https://github.com/SwissDataScienceCenter/renku-python.git'
        ],
        catch_exceptions=False
    )
    assert 0 == result.exit_code
    result = runner.invoke(
        cli, [
            'dataset', 'add', '--create', 'dataset-2', '--ref', 'v0.3.0', '-s',
            'CHANGES.rst',
            'https://github.com/SwissDataScienceCenter/renku-python.git'
        ],
        catch_exceptions=False
    )
    assert 0 == result.exit_code

    assert 'v0.4.0' not in path1.read_text()
    assert 'v0.4.0' not in path2.read_text()

    result = runner.invoke(
        cli, ['dataset', 'update'] + params, catch_exceptions=False
    )
    assert 0 == result.exit_code

    assert 'v0.4.0' in path1.read_text()
    assert 'v0.4.0' in path2.read_text()


@pytest.mark.integration
def test_empty_update(client, runner, data_repository, directory_tree):
    """Test update when nothing changed does not create a commit."""
    # Add dataset to project
    result = runner.invoke(
        cli, [
            'dataset', 'add', '--create', 'remote', '--ref', 'v0.3.0', '-s',
            'CHANGES.rst',
            'https://github.com/SwissDataScienceCenter/renku-python.git'
        ],
        catch_exceptions=False
    )
    assert 0 == result.exit_code

    commit_sha_before = client.repo.head.object.hexsha
    result = runner.invoke(
        cli, ['dataset', 'update', '--ref', 'v0.3.0'], catch_exceptions=False
    )
    assert 0 == result.exit_code
    commit_sha_after = client.repo.head.object.hexsha
    assert commit_sha_after == commit_sha_before


@pytest.mark.integration
def test_import_from_renku_project(tmpdir, client, runner):
    """Test an imported dataset from other renku repos will have metadata."""
    from renku.core.management import LocalClient

    REMOTE = 'https://dev.renku.ch/gitlab/virginiafriedrich/datasets-test.git'

    path = tmpdir.strpath
    os.environ['GIT_LFS_SKIP_SMUDGE'] = '1'
    git.Repo.clone_from(REMOTE, path, recursive=True)

    remote_client = LocalClient(path)
    remote = read_dataset_file_metadata(
        remote_client, 'zhbikes',
        '2019_verkehrszaehlungen_werte_fussgaenger_velo.csv'
    )

    result = runner.invoke(
        cli,
        [
            'dataset', 'add', '--create', 'remote-dataset', '-s',
            'data/zhbikes/2019_verkehrszaehlungen_werte_fussgaenger_velo.csv',
            '-d', 'file', '--ref', 'b973db5', REMOTE
        ],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    metadata = read_dataset_file_metadata(client, 'remote-dataset', 'file')
    assert metadata.creator[0].name == remote.creator[0].name
    assert metadata.based_on._id == remote._id
    assert metadata.based_on._label == remote._label
    assert metadata.based_on.path == remote.path
    assert metadata.based_on.based_on is None
    assert metadata.based_on.url == REMOTE


@pytest.mark.integration
@pytest.mark.parametrize(
    'ref', ['v0.3.0', 'fe6ec65cc84bcf01e879ef38c0793208f7fab4bb']
)
def test_add_specific_refs(ref, runner, client):
    """Test adding a specific version of files."""
    FILENAME = 'CHANGES.rst'
    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code

    # add data from a git repo
    result = runner.invoke(
        cli, [
            'dataset', 'add', 'dataset', '-s', FILENAME, '--ref', ref,
            'https://github.com/SwissDataScienceCenter/renku-python.git'
        ]
    )
    assert 0 == result.exit_code
    content = (client.path / 'data' / 'dataset' / FILENAME).read_text()
    assert 'v0.3.0' in content
    assert 'v0.3.1' not in content


@pytest.mark.integration
@pytest.mark.parametrize(
    'ref', ['v0.3.1', '27e29abd409c83129a3fdb8b8b0b898b23bcb229']
)
def test_update_specific_refs(ref, runner, client):
    """Test updating to a specific version of files."""
    FILENAME = 'CHANGES.rst'
    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code

    # add data from a git repo
    result = runner.invoke(
        cli, [
            'dataset', 'add', 'dataset', '-s', FILENAME, '--ref', 'v0.3.0',
            'https://github.com/SwissDataScienceCenter/renku-python.git'
        ]
    )
    assert 0 == result.exit_code
    content = (client.path / 'data' / 'dataset' / FILENAME).read_text()
    assert 'v0.3.1' not in content

    # update data to a later version
    result = runner.invoke(cli, ['dataset', 'update', '--ref', ref])
    assert 0 == result.exit_code
    content = (client.path / 'data' / 'dataset' / FILENAME).read_text()
    assert 'v0.3.1' in content
    assert 'v0.3.2' not in content


@pytest.mark.integration
def test_update_with_multiple_remotes_and_ref(runner, client):
    """Test updating fails when ref is ambiguous."""
    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code

    # add data from a git repo
    result = runner.invoke(
        cli, [
            'dataset', 'add', 'dataset', '-s', 'CHANGES.rst',
            'https://github.com/SwissDataScienceCenter/renku-python.git'
        ]
    )
    assert 0 == result.exit_code

    # add data from another git repo
    result = runner.invoke(
        cli, [
            'dataset', 'add', 'dataset', '-s', 'LICENSE',
            'https://github.com/SwissDataScienceCenter/renku-notebooks.git'
        ]
    )
    assert 0 == result.exit_code

    # update data to a later version
    result = runner.invoke(cli, ['dataset', 'update', '--ref', 'any-value'])
    assert 2 == result.exit_code
    assert 'Cannot use "--ref" with more than one Git repo' in result.output


@pytest.mark.integration
def test_files_are_tracked_in_lfs(runner, client):
    """Test files added from a Git repo are tacked in Git LFS."""
    FILENAME = 'CHANGES.rst'
    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code

    # add data from a git repo
    result = runner.invoke(
        cli, [
            'dataset', 'add', 'dataset', '-s', FILENAME,
            'https://github.com/SwissDataScienceCenter/renku-python.git'
        ]
    )
    assert 0 == result.exit_code
    path = 'data/dataset/{}'.format(FILENAME)
    assert path in subprocess.check_output(['git', 'lfs', 'ls-files']).decode()


@pytest.mark.integration
def test_renku_clone(runner, monkeypatch):
    """Test cloning of a Renku repo and existence of required settings."""
    from renku.core.management.storage import StorageApiMixin

    REMOTE = 'https://dev.renku.ch/gitlab/virginiafriedrich/datasets-test.git'

    with runner.isolated_filesystem() as project_path:
        result = runner.invoke(cli, ['clone', REMOTE, project_path])
        assert 0 == result.exit_code
        assert (Path(project_path) / 'Dockerfile').exists()

        # Check Git hooks are installed
        result = runner.invoke(cli, ['githooks', 'install'])
        assert 0 == result.exit_code
        assert 'Hook already exists.' in result.output

        # Check Git LFS is enabled
        with monkeypatch.context() as monkey:
            # Pretend that git-lfs is not installed.
            monkey.setattr(StorageApiMixin, 'storage_installed', False)
            # Repo is using external storage but it's not installed.
            result = runner.invoke(cli, ['run', 'touch', 'output'])
            assert 'is not configured' in result.output
            assert 1 == result.exit_code


@pytest.mark.integration
def test_renku_clone_with_config(tmpdir):
    """Test cloning of a Renku repo and existence of required settings."""
    REMOTE = 'https://dev.renku.ch/gitlab/virginiafriedrich/datasets-test.git'

    with chdir(tmpdir):
        renku_clone(
            REMOTE,
            config={
                'user.name': 'sam',
                'user.email': 's@m.i',
                'filter.lfs.custom': '0'
            }
        )

        repo = git.Repo('datasets-test')
        reader = repo.config_reader()
        reader.values()

        lfs_config = dict(reader.items('filter.lfs'))
        assert '0' == lfs_config.get('custom')


@pytest.mark.integration
@pytest.mark.parametrize(
    'path,expected_path', [('', 'datasets-test'), ('.', '.'),
                           ('new-name', 'new-name')]
)
def test_renku_clone_uses_project_name(
    runner, monkeypatch, path, expected_path
):
    """Test renku clone uses project name as target-path by default."""
    REMOTE = 'https://dev.renku.ch/gitlab/virginiafriedrich/datasets-test.git'

    with runner.isolated_filesystem() as project_path:
        result = runner.invoke(cli, ['clone', REMOTE, path])
        assert 0 == result.exit_code
        assert (Path(project_path) / expected_path / 'Dockerfile').exists()


@pytest.mark.integration
def test_add_removes_credentials(runner, client):
    """Check removal of credentials during adding of remote data files."""
    url = 'https://username:password@example.com/index.html'
    result = runner.invoke(cli, ['dataset', 'add', '-c', 'my-dataset', url])
    assert 0 == result.exit_code

    with client.with_dataset('my-dataset') as dataset:
        file_ = dataset.files[0]
        assert file_.url == 'https://example.com/index.html'
