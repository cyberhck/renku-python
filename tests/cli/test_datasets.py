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
"""Test ``dataset`` command."""

from __future__ import absolute_import, print_function

import json
import os
from pathlib import Path

import pytest
import requests
import yaml

from renku.cli import cli
from renku.core.commands.format.dataset_files import DATASET_FILES_FORMATS
from renku.core.commands.format.datasets import DATASETS_FORMATS
from renku.core.commands.providers import DataverseProvider, ProviderFactory, \
    ZenodoProvider
from renku.core.management.config import RENKU_HOME
from renku.core.management.datasets import DatasetsApiMixin
from renku.core.models.refs import LinkReference
from renku.core.utils.datetime8601 import validate_iso8601


def test_datasets_create_clean(runner, project, client):
    """Test creating a dataset in clean repository."""
    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    dataset = client.load_dataset(name='dataset')
    assert dataset

    staged = client.repo.index.diff('HEAD')
    for file_path in staged:
        assert 'datasets' not in file_path

    untracked = client.repo.untracked_files
    for file_path in untracked:
        assert 'datasets' not in file_path


def test_datasets_create_with_metadata(runner, client):
    """Test creating a dataset with metadata."""
    result = runner.invoke(
        cli, [
            'dataset', 'create', 'my-dataset', '--short-name', 'short-name',
            '--description', 'some description here', '-c',
            'John Doe <john.doe@mail.ch>', '-c',
            'John Smiths<john.smiths@mail.ch>'
        ]
    )
    assert 0 == result.exit_code
    assert 'OK' in result.output

    dataset = client.load_dataset(name='short-name')
    assert dataset.name == 'my-dataset'
    assert dataset.short_name == 'short-name'
    assert dataset.description == 'some description here'
    assert 'John Doe' in [c.name for c in dataset.creator]
    assert 'john.doe@mail.ch' in [c.email for c in dataset.creator]
    assert 'John Smiths' in [c.name for c in dataset.creator]
    assert 'john.smiths@mail.ch' in [c.email for c in dataset.creator]


def test_datasets_create_different_short_names(runner, client):
    """Test creating datasets with same name but different short_name."""
    result = runner.invoke(
        cli, ['dataset', 'create', 'dataset', '--short-name', 'dataset-1']
    )
    assert 0 == result.exit_code
    assert 'OK' in result.output

    result = runner.invoke(
        cli, ['dataset', 'create', 'dataset', '--short-name', 'dataset-2']
    )
    assert 0 == result.exit_code
    assert 'OK' in result.output


def test_datasets_create_with_same_name(runner, client):
    """Test creating datasets with same name."""
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 1 == result.exit_code
    assert 'Dataset exists: "dataset"' in result.output


@pytest.mark.parametrize(
    'name,short_name',
    [('v.a.l.i.d_internal-name', 'v.a.l.i.d_internal-name'),
     ('any name /@#$!', 'any_name'),
     ('name longer than 24 characters', 'name_longer_than_24_char'),
     ('semi valid-name', 'semi_validname'), ('dataset/new', 'datasetnew'),
     ('/dataset', 'dataset'), ('dataset/', 'dataset')]
)
def test_datasets_valid_name(runner, client, name, short_name):
    """Test creating datasets with valid name."""
    result = runner.invoke(cli, ['dataset', 'create', name])
    assert 0 == result.exit_code
    assert 'Use the name "{}"'.format(short_name) in result.output
    assert 'OK' in result.output

    dataset = client.load_dataset(name=short_name)
    assert dataset.name == name
    assert dataset.short_name == short_name


def test_datasets_create_dirty(runner, project, client):
    """Test creating a dataset in dirty repository."""
    # Create a file in root of the repository.
    with (client.path / 'a').open('w') as fp:
        fp.write('a')

    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    dataset = client.load_dataset(name='dataset')
    assert dataset

    staged = client.repo.index.diff('HEAD')
    for file_path in staged:
        assert 'datasets' not in file_path

    untracked = client.repo.untracked_files
    for file_path in untracked:
        assert 'datasets' not in file_path


def test_datasets_create_dirty_exception_untracked(runner, project, client):
    """Test exception raise for untracked file in renku directory."""
    # 1. Create a problem.
    datasets_dir = client.path / RENKU_HOME / DatasetsApiMixin.DATASETS
    if not datasets_dir.exists():
        datasets_dir.mkdir()

    with (datasets_dir / 'a').open('w') as fp:
        fp.write('a')

    # 2. Ensure correct error has been raised.
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 1 == result.exit_code
    assert '.renku contains uncommitted changes.' in result.output


def test_datasets_create_dirty_exception_staged(runner, project, client):
    """Test exception raise for staged file in renku directory."""
    # 1. Create a problem within .renku directory
    datasets_dir = client.path / RENKU_HOME / DatasetsApiMixin.DATASETS
    if not datasets_dir.exists():
        datasets_dir.mkdir()

    with (datasets_dir / 'a').open('w') as fp:
        fp.write('a')

    # 2. Stage a problem without committing it.
    client.repo.git.add(datasets_dir / 'a')

    # 3. Ensure correct error has been raised.
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 1 == result.exit_code
    assert '.renku contains uncommitted changes.' in result.output


def test_dataset_create_dirty_exception_all_untracked(runner, project, client):
    """Test exception raise for all untracked files."""
    # 1. Create unclean root to enforce ensure checks.
    with (client.path / 'a').open('w') as fp:
        fp.write('a')

    # 2. Create a problem.
    datasets_dir = client.path / RENKU_HOME / DatasetsApiMixin.DATASETS
    if not datasets_dir.exists():
        datasets_dir.mkdir()

    with (datasets_dir / 'a').open('w') as fp:
        fp.write('a')

    # 3. Ensure correct error has been raised.
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 1 == result.exit_code
    assert '.renku contains uncommitted changes.' in result.output


def test_datasets_create_dirty_exception_all_staged(runner, project, client):
    """Test exception raise for all staged files."""
    # 1. Create unclean root to enforce ensure checks.
    with (client.path / 'a').open('w') as fp:
        fp.write('a')

    client.repo.git.add('a')

    # 2. Create a problem.
    datasets_dir = client.path / RENKU_HOME / DatasetsApiMixin.DATASETS
    if not datasets_dir.exists():
        datasets_dir.mkdir()

    with (datasets_dir / 'a').open('w') as fp:
        fp.write('a')

    client.repo.git.add(datasets_dir / 'a')

    # 3. Ensure correct error has been raised.
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 1 == result.exit_code
    assert '.renku contains uncommitted changes.' in result.output


def test_dataset_create_exception_refs(runner, project, client):
    """Test untracked/unstaged exception raise in dirty renku home dir."""
    with (client.path / 'a').open('w') as fp:
        fp.write('a')

    datasets_dir = client.path / RENKU_HOME / DatasetsApiMixin.DATASETS
    if not datasets_dir.exists():
        datasets_dir.mkdir()

    with (datasets_dir / 'a').open('w') as fp:
        fp.write('a')

    refs_dir = client.path / RENKU_HOME / LinkReference.REFS
    if not refs_dir.exists():
        refs_dir.mkdir()

    with (refs_dir / 'b').open('w') as fp:
        fp.write('b')

    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 1 == result.exit_code
    assert 'a' in result.output


@pytest.mark.parametrize(
    'creator,field', [('John Doe', 'Email'), ('John Doe<>', 'Email'),
                      ('<john.doe@mail.ch>', 'Name'),
                      ('John Doe<john.doe@mail>', 'Email')]
)
def test_dataset_creator_is_invalid(client, runner, creator, field):
    """Test create dataset with invalid creator format."""
    result = runner.invoke(cli, ['dataset', 'create', 'ds', '-c', creator])
    assert 2 == result.exit_code
    assert field + ' is invalid' in result.output


@pytest.mark.parametrize('output_format', DATASETS_FORMATS.keys())
def test_datasets_list_empty(output_format, runner, project):
    """Test listing without datasets."""
    format_option = '--format={0}'.format(output_format)
    result = runner.invoke(cli, ['dataset', format_option])
    assert 0 == result.exit_code


@pytest.mark.parametrize('output_format', DATASETS_FORMATS.keys())
def test_datasets_list_non_empty(output_format, runner, project):
    """Test listing with datasets."""
    format_option = '--format={0}'.format(output_format)
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    result = runner.invoke(cli, ['dataset', format_option])
    assert 0 == result.exit_code
    assert 'dataset' in result.output

    result = runner.invoke(
        cli, ['dataset', '--revision=HEAD~1', format_option]
    )
    assert result.exit_code == 0
    assert 'dataset' not in result.output


def test_add_and_create_dataset(directory_tree, runner, project, client):
    """Test add data to a non-existing dataset."""
    result = runner.invoke(
        cli, ['dataset', 'add', 'new-dataset',
              str(directory_tree)],
        catch_exceptions=False
    )
    assert result.exit_code == 1
    assert 'Dataset "new-dataset" does not exist.' in result.output

    # Add succeeds with --create
    result = runner.invoke(
        cli,
        ['dataset', 'add', '--create', 'new-dataset',
         str(directory_tree)],
        catch_exceptions=False
    )
    assert result.exit_code == 0

    # Further add with --create fails
    result = runner.invoke(
        cli,
        ['dataset', 'add', '--create', 'new-dataset',
         str(directory_tree)],
        catch_exceptions=False
    )
    assert result.exit_code == 1


def test_multiple_file_to_dataset(tmpdir, runner, project, client):
    """Test importing multiple data into a dataset at once."""
    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    with client.with_dataset('dataset') as dataset:
        assert dataset.name == 'dataset'

    paths = []
    for i in range(3):
        new_file = tmpdir.join('file_{0}'.format(i))
        new_file.write(str(i))
        paths.append(str(new_file))

    # add data
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'dataset'] + paths,
        catch_exceptions=False,
    )
    assert 0 == result.exit_code


def test_repository_file_to_dataset(runner, project, client):
    """Test adding a file from the repository into a dataset."""
    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    with (client.path / 'a').open('w') as fp:
        fp.write('a')

    client.repo.git.add('a')
    client.repo.git.commit(message='Added file a')

    # add data
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'dataset', 'a'],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    with client.with_dataset('dataset') as dataset:
        assert dataset.name == 'dataset'
        assert dataset.find_file('a') is not None


def test_relative_import_to_dataset(tmpdir, runner, client):
    """Test importing data from a directory structure."""
    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    with client.with_dataset('dataset') as dataset:
        assert dataset.name == 'dataset'

    zero_data = tmpdir.join('zero.txt')
    zero_data.write('zero')

    first_level = tmpdir.mkdir('first')
    second_level = first_level.mkdir('second')

    first_data = first_level.join('first.txt')
    first_data.write('first')

    second_data = second_level.join('second.txt')
    second_data.write('second')

    paths = [str(zero_data), str(first_level), str(second_level)]

    # add data in subdirectory
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'dataset'] + paths,
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    assert os.stat(os.path.join('data', 'dataset', 'zero.txt'))
    assert os.stat(os.path.join('data', 'dataset', 'first', 'first.txt'))
    assert os.stat(
        os.path.join('data', 'dataset', 'first', 'second', 'second.txt')
    )


@pytest.mark.parametrize(
    'params,message', [
        (['-s', 'file', 'https://example.com'
          ], 'Cannot use "--source" with URLs or local files.'),
        (['-s', 'file', '/some/local/path'
          ], 'Cannot use "--source" with URLs or local files.'),
    ]
)
def test_usage_error_in_add_from_url(runner, client, params, message):
    """Test user's errors when adding URL/local file to a dataset."""
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'remote', '--create'] + params,
        catch_exceptions=False,
    )
    assert result.exit_code == 2
    assert message in result.output


def test_add_from_local_repo_warning(
    runner, client, data_repository, directory_tree
):
    """Test a warning is printed when adding from a local git repo."""
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'dataset', '--create',
         str(directory_tree)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert 'Use remote\'s Git URL instead to enable lineage ' in result.output


def test_dataset_add_with_link(tmpdir, runner, project, client):
    """Test adding data to dataset with --link flag."""
    import stat

    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    paths = []
    expected_inodes = []
    for i in range(3):
        new_file = tmpdir.join('file_{0}'.format(i))
        new_file.write(str(i))
        expected_inodes.append(os.lstat(str(new_file))[stat.ST_INO])
        paths.append(str(new_file))

    # add data
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'my-dataset', '--link'] + paths,
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    received_inodes = []
    with client.with_dataset('my-dataset') as dataset:
        assert dataset.name == 'my-dataset'
        for file_ in dataset.files:
            path_ = (client.path / file_.path).resolve()
            received_inodes.append(os.lstat(str(path_))[stat.ST_INO])

    # check that original and dataset inodes are the same
    assert sorted(expected_inodes) == sorted(received_inodes)


def test_dataset_add_with_copy(tmpdir, runner, project, client):
    """Test adding data to dataset with copy."""
    import os
    import stat

    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    paths = []
    original_inodes = []
    for i in range(3):
        new_file = tmpdir.join('file_{0}'.format(i))
        new_file.write(str(i))
        original_inodes.append(os.lstat(str(new_file))[stat.ST_INO])
        paths.append(str(new_file))

    # add data
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'my-dataset'] + paths,
    )
    assert 0 == result.exit_code

    received_inodes = []
    with client.with_dataset('my-dataset') as dataset:
        assert dataset.name == 'my-dataset'

        for file_ in dataset.files:
            path_ = (client.path / file_.path).resolve()
            received_inodes.append(os.lstat(str(path_))[stat.ST_INO])

    # check that original inodes are within created ones
    for inode in received_inodes:
        assert inode not in original_inodes


def test_dataset_file_path_from_subdirectory(runner, project, client):
    """Test adding a file into a dataset and check path independent
    of the CWD """
    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    with (client.path / 'a').open('w') as fp:
        fp.write('a')

    client.repo.git.add('a')
    client.repo.git.commit(message='Added file a')

    # add data
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'dataset', 'a'],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    with client.with_dataset('dataset') as dataset:
        datasetfile = dataset.find_file('a')
        assert datasetfile is not None

        assert datasetfile.full_path == client.path / 'a'

        os.chdir('./data')

        assert datasetfile.full_path == client.path / 'a'


def test_datasets_ls_files_tabular_empty(runner, project):
    """Test listing of data within empty dataset."""
    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    # list all files in dataset
    result = runner.invoke(cli, ['dataset', 'ls-files', 'my-dataset'])
    assert 0 == result.exit_code

    # check output
    output = result.output.split('\n')
    assert output.pop(0).split() == ['ADDED', 'CREATORS', 'DATASET', 'PATH']
    assert set(output.pop(0)) == {' ', '-'}
    assert output.pop(0) == ''
    assert not output


@pytest.mark.parametrize('output_format', DATASET_FILES_FORMATS.keys())
def test_datasets_ls_files_check_exit_code(output_format, runner, project):
    """Test file listing exit codes for different formats."""
    format_option = '--format={0}'.format(output_format)
    result = runner.invoke(cli, ['dataset', 'ls-files', format_option])
    assert 0 == result.exit_code


def test_datasets_ls_files_tabular_dataset_filter(tmpdir, runner, project):
    """Test listing of data within dataset."""
    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create some data
    paths = []
    created_files = []
    for i in range(3):
        new_file = tmpdir.join('file_{0}'.format(i))
        new_file.write(str(i))
        paths.append(str(new_file))
        created_files.append(new_file.basename)

    # add data to dataset
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'my-dataset'] + paths,
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    # list all files in non empty dataset
    result = runner.invoke(cli, ['dataset', 'ls-files', 'my-dataset'])
    assert 0 == result.exit_code

    # check output from ls-files command
    output = result.output.split('\n')
    assert output.pop(0).split() == ['ADDED', 'CREATORS', 'DATASET', 'PATH']
    assert set(output.pop(0)) == {' ', '-'}

    # check listing
    added_at = []
    for i in range(3):
        row = output.pop(0).split(' ')
        assert Path(row.pop()).name in created_files
        added_at.append(row.pop(0))

    # check if sorted by added_at
    assert added_at == sorted(added_at)


def test_datasets_ls_files_tabular_patterns(tmpdir, runner, project):
    """Test listing of data within dataset with include/exclude filters."""

    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create some data
    subdir = tmpdir.mkdir('sub')
    paths = [str(subdir)]
    for i in range(3):
        new_file = tmpdir.join('file_{0}'.format(i))
        new_file.write(str(i))
        paths.append(str(new_file))

        sub_file = subdir.join('sub_file_{0}'.format(i))
        sub_file.write(str(i))

    # add data to dataset
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'my-dataset'] + paths,
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    # check include / exclude filters
    result = runner.invoke(
        cli,
        ['dataset', 'ls-files', '--include=**/file*', '--exclude=**/file_2']
    )
    assert 0 == result.exit_code

    # check output
    assert 'file_0' in result.output
    assert 'file_1' in result.output
    assert 'file_2' not in result.output

    # check directory pattern
    result = runner.invoke(cli, ['dataset', 'ls-files', '--include=**/sub/*'])
    assert 0 == result.exit_code

    # check output
    assert 'sub_file_0' in result.output
    assert 'sub_file_1' in result.output
    assert 'sub_file_2' in result.output


def test_datasets_ls_files_tabular_creators(tmpdir, runner, project, client):
    """Test listing of data within dataset with creators filters."""
    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create some data
    paths = []
    for i in range(3):
        new_file = tmpdir.join('file_{0}'.format(i))
        new_file.write(str(i))
        paths.append(str(new_file))

    # add data to dataset
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'my-dataset'] + paths,
    )
    assert 0 == result.exit_code

    creator = None
    with client.with_dataset('my-dataset') as dataset:
        creator = dataset.creator[0].name

    assert creator is not None
    assert len(dataset.creator) > 0

    # check creators filters
    result = runner.invoke(
        cli, ['dataset', 'ls-files', '--creators={0}'.format(creator)]
    )
    assert 0 == result.exit_code

    # check output
    for file_ in paths:
        assert str(Path(file_).name) in result.output


def test_datasets_ls_files_correct_paths(tmpdir, runner, project):
    """Test listing of data within dataset and check that paths are correct."""
    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create some data
    paths = []
    for i in range(3):
        new_file = tmpdir.join('file_{0}'.format(i))
        new_file.write(str(i))
        paths.append(str(new_file))

    # add data to dataset
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'my-dataset'] + paths,
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    # check include / exclude filters
    result = runner.invoke(cli, ['dataset', 'ls-files', '--format=json-ld'])
    assert 0 == result.exit_code

    output = json.loads(result.output)
    for record in output:
        assert Path(record['path']).exists()


def test_datasets_ls_files_with_display_name(directory_tree, runner, project):
    """Test listing of data within dataset with include/exclude filters."""
    # create a dataset
    result = runner.invoke(
        cli, ['dataset', 'create', 'my-dataset', '--short-name', 'short-name']
    )
    assert 0 == result.exit_code

    # add data to dataset
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'short-name', directory_tree.strpath],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    # list files with dataset name
    result = runner.invoke(cli, ['dataset', 'ls-files', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'dir2/file2' not in result.output

    # list files with short_name
    result = runner.invoke(cli, ['dataset', 'ls-files', 'short-name'])
    assert 0 == result.exit_code
    assert 'dir2/file2' in result.output


def test_dataset_unlink_file_not_found(runner, project):
    """Test unlinking of file from dataset with no files found."""
    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    result = runner.invoke(
        cli, ['dataset', 'unlink', 'my-dataset', '--include', 'notthere.csv']
    )

    assert 2 == result.exit_code


def test_dataset_unlink_file_abort_unlinking(tmpdir, runner, project):
    """Test unlinking of file from dataset and aborting."""
    # create a dataset
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

    # unlink file from dataset
    result = runner.invoke(
        cli,
        ['dataset', 'unlink', 'my-dataset', '--include', new_file.basename],
        input='n'
    )
    assert 1 == result.exit_code

    # check output
    assert 'Aborted!' in result.output


def test_dataset_unlink_file(tmpdir, runner, client):
    """Test unlinking of file and check removal from dataset"""
    # create a dataset
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
        assert new_file.basename in {
            Path(file_.path).name
            for file_ in dataset.files
        }

    result = runner.invoke(
        cli, [
            'dataset', 'unlink', 'my-dataset', '--include', new_file.basename,
            '-y'
        ]
    )
    assert 0 == result.exit_code

    with client.with_dataset('my-dataset') as dataset:
        assert new_file.basename not in [
            file_.path.name for file_ in dataset.files
        ]


def test_dataset_rm(tmpdir, runner, project, client):
    """Test removal of a dataset."""
    # try to delete non existing dataset
    result = runner.invoke(cli, ['dataset', 'rm'])
    assert 2 == result.exit_code

    result = runner.invoke(cli, ['dataset', 'rm', 'does-not-exist'])
    assert 2 == result.exit_code

    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create some data
    paths = []
    for i in range(3):
        new_file = tmpdir.join('file_{0}'.format(i))
        new_file.write(str(i))
        paths.append(str(new_file))

    # add data to dataset
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'my-dataset'] + paths,
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    # try to delete a non empty dataset
    result = runner.invoke(cli, ['dataset', 'rm', 'my-dataset'])
    assert 0 == result.exit_code

    # check output
    assert 'OK' in result.output
    assert not client.load_dataset(name='my-dataset')

    result = runner.invoke(cli, ['doctor'], catch_exceptions=False)
    assert 0 == result.exit_code


def test_dataset_rm_commit(tmpdir, runner, project, client):
    """Test removal of a dataset repository state."""
    # create a dataset
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    # try to delete a non empty dataset
    result = runner.invoke(cli, ['dataset', 'rm', 'my-dataset'])
    assert 0 == result.exit_code

    # check output
    assert 'OK' in result.output
    assert not client.load_dataset(name='my-dataset')

    # Dirty repository check.
    result = runner.invoke(cli, ['status'])
    assert 0 == result.exit_code


def test_dataset_overwrite_no_confirm(runner, project):
    """Check dataset overwrite behaviour without confirmation."""
    result = runner.invoke(cli, ['dataset', 'create', 'rokstar'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    result = runner.invoke(cli, ['dataset', 'create', 'rokstar'])
    assert 1 == result.exit_code
    assert 'OK' not in result.output


def test_dataset_edit(runner, client, project):
    """Check dataset metadata editing."""
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    dataset = client.load_dataset(name='dataset')

    result = runner.invoke(
        cli, ['dataset', 'edit', dataset.identifier],
        input='wq',
        catch_exceptions=False
    )
    assert 0 == result.exit_code


def test_dataset_edit_dirty(runner, client, project):
    """Check dataset metadata editing when dirty repository."""
    # Create a file in root of the repository.
    with (client.path / 'a').open('w') as fp:
        fp.write('a')

    # Create a dataset.
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    dataset = client.load_dataset(name='dataset')

    result = runner.invoke(
        cli, ['dataset', 'edit', dataset.identifier], input='wq'
    )
    assert 0 == result.exit_code


def test_dataset_date_created_format(runner, client, project):
    """Check format of date created field."""
    # Create a dataset.
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    path = client.get_dataset_path('dataset')
    assert path.exists()

    with path.open(mode='r') as fp:
        import dateutil.parser as dp
        data_yaml = yaml.safe_load(fp)

        assert 'created' in data_yaml
        assert dp.parse(data_yaml['created'])
        assert validate_iso8601(data_yaml['created'])


def test_dataset_file_date_created_format(tmpdir, runner, client, project):
    """Check format of date created field."""
    # Create a dataset.
    result = runner.invoke(cli, ['dataset', 'create', 'dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    path = client.get_dataset_path('dataset')
    assert path.exists()

    # Create data file.
    new_file = tmpdir.join('datafile.csv')
    new_file.write('1,2,3')

    # Add data to dataset.
    result = runner.invoke(cli, ['dataset', 'add', 'dataset', str(new_file)])
    assert 0 == result.exit_code

    with path.open(mode='r') as fp:
        import dateutil.parser as dp
        data_yaml = yaml.safe_load(fp)

        assert 'created' in data_yaml
        assert 'files' in data_yaml
        assert dp.parse(data_yaml['files'][0]['added'])
        assert dp.parse(data_yaml['created'])
        assert validate_iso8601(data_yaml['created'])
        assert validate_iso8601(data_yaml['files'][0]['added'])


@pytest.mark.parametrize(
    'uri', [
        '10.5281/zenodo.3363060', 'doi:10.5281/zenodo.3363060',
        'https://zenodo.org/record/3363060'
    ]
)
def test_dataset_provider_resolution_zenodo(doi_responses, uri):
    """Check that zenodo uris resolve to ZenodoProvider."""
    provider, _ = ProviderFactory.from_uri(uri)
    assert type(provider) is ZenodoProvider


@pytest.mark.parametrize(
    'uri', [
        '10.7910/DVN/TJCLKP', 'doi:10.7910/DVN/TJCLKP',
        (
            'https://dataverse.harvard.edu/dataset.xhtml'
            '?persistentId=doi:10.7910/DVN/TJCLKP'
        )
    ]
)
def test_dataset_provider_resolution_dataverse(doi_responses, uri):
    """Check that dataverse URIs resolve to ``DataverseProvider``."""
    provider, _ = ProviderFactory.from_uri(uri)
    assert type(provider) is DataverseProvider


def test_dataset_tag(tmpdir, runner, project):
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create some data
    new_file = tmpdir.join('file')
    new_file.write(str('test'))

    # add data to dataset
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'my-dataset',
         str(new_file)],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    # tag dataset
    result = runner.invoke(
        cli,
        ['dataset', 'tag', 'my-dataset', '1.0'],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    result = runner.invoke(
        cli,
        ['dataset', 'tag', 'my-dataset', 'A', '-d', 'short descriptiön'],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    result = runner.invoke(
        cli,
        ['dataset', 'tag', 'my-dataset', 'aBc9.34-11_55.t'],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code


@pytest.mark.parametrize('form', ['tabular', 'json-ld'])
def test_dataset_ls_tags(tmpdir, runner, project, client, form):
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create some data
    new_file = tmpdir.join('file')
    new_file.write(str('test'))

    # add data to dataset
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'my-dataset',
         str(new_file)],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    commit1 = client.repo.head.commit.hexsha

    # tag dataset
    result = runner.invoke(
        cli,
        ['dataset', 'tag', 'my-dataset', '1.0', '-d', 'first tag!'],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    commit2 = client.repo.head.commit.hexsha

    result = runner.invoke(
        cli,
        ['dataset', 'tag', 'my-dataset', 'aBc9.34-11_55.t'],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    result = runner.invoke(
        cli,
        ['dataset', 'ls-tags', 'my-dataset', '--format={}'.format(form)],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code
    assert '1.0' in result.output
    assert 'aBc9.34-11_55.t' in result.output
    assert 'first tag!' in result.output
    assert commit1 in result.output
    assert commit2 in result.output


def test_dataset_rm_tag(tmpdir, runner, project, client):
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create some data
    new_file = tmpdir.join('file')
    new_file.write(str('test'))

    # add data to dataset
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'my-dataset',
         str(new_file)],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    commit1 = client.repo.head.commit.hexsha

    # tag dataset
    result = runner.invoke(
        cli,
        ['dataset', 'tag', 'my-dataset', '1.0', '-d', 'first tag!'],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    result = runner.invoke(
        cli,
        ['dataset', 'ls-tags', 'my-dataset'],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code
    assert '1.0' in result.output
    assert 'first tag!' in result.output
    assert commit1 in result.output

    result = runner.invoke(
        cli,
        ['dataset', 'rm-tags', 'my-dataset', '2.0'],
        catch_exceptions=False,
    )
    assert 2 == result.exit_code
    assert 'not found' in result.output

    result = runner.invoke(
        cli,
        ['dataset', 'rm-tags', 'my-dataset', '1.0'],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    result = runner.invoke(
        cli,
        ['dataset', 'rm-tags', 'my-dataset', '1.0'],
        catch_exceptions=False,
    )
    assert 2 == result.exit_code
    assert 'not found' in result.output


def test_dataset_rm_tags_multiple(tmpdir, runner, project, client):
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create some data
    new_file = tmpdir.join('file')
    new_file.write(str('test'))

    # add data to dataset
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'my-dataset',
         str(new_file)],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    for i in range(1, 4):
        # tag dataset
        result = runner.invoke(
            cli,
            ['dataset', 'tag', 'my-dataset',
             str(i)],
            catch_exceptions=False,
        )
        assert 0 == result.exit_code

    result = runner.invoke(
        cli,
        ['dataset', 'rm-tags', 'my-dataset', '1', '2', '3'],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code
    assert '1' not in result.output
    assert '2' not in result.output
    assert '3' not in result.output


def test_dataset_rm_tags_failure(tmpdir, runner, project, client):
    result = runner.invoke(
        cli,
        ['dataset', 'rm-tags', 'my-dataset', '1'],
        catch_exceptions=False,
    )

    assert 2 == result.exit_code
    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code
    assert 'OK' in result.output

    # create some data
    new_file = tmpdir.join('file')
    new_file.write(str('test'))

    # add data to dataset
    result = runner.invoke(
        cli,
        ['dataset', 'add', 'my-dataset',
         str(new_file)],
        catch_exceptions=False,
    )
    assert 0 == result.exit_code

    result = runner.invoke(
        cli,
        ['dataset', 'rm-tags', 'my-dataset', '1'],
        catch_exceptions=False,
    )
    assert 2 == result.exit_code


def test_dataset_clean_up_when_add_fails(runner, client):
    """Test project is cleaned when dataset add fails for a new dataset."""
    # add a non-existing path to a new dataset
    result = runner.invoke(
        cli,
        ['dataset', 'add', '--create', 'new-dataset', 'non-existing-file'],
        catch_exceptions=True,
    )

    assert result.exit_code == 2
    ref = client.renku_path / 'refs' / 'datasets' / 'new-dataset'
    assert not ref.is_symlink() and not ref.exists()


def test_avoid_empty_commits(runner, client, directory_tree):
    """Test no empty commit is created when adding existing data."""
    runner.invoke(cli, ['dataset', 'create', 'my-dataset'])

    commit_sha_before = client.repo.head.object.hexsha
    result = runner.invoke(
        cli, ['dataset', 'add', 'my-dataset', directory_tree.strpath]
    )

    assert 0 == result.exit_code

    commit_sha_after = client.repo.head.object.hexsha
    assert commit_sha_before != commit_sha_after

    commit_sha_before = commit_sha_after
    result = runner.invoke(
        cli, ['dataset', 'add', 'my-dataset', directory_tree.strpath]
    )
    assert 1 == result.exit_code

    commit_sha_after = client.repo.head.object.hexsha
    assert commit_sha_before == commit_sha_after
    assert 'Error: File already exists in dataset.' in result.output


def test_multiple_dataset_commits(runner, client, directory_tree):
    """Check adding existing data to multiple datasets."""
    commit_sha_before = client.repo.head.object.hexsha
    result = runner.invoke(
        cli, ['dataset', 'add', '-c', 'my-dataset1', directory_tree.strpath]
    )

    assert 0 == result.exit_code

    commit_sha_after = client.repo.head.object.hexsha
    assert commit_sha_before != commit_sha_after

    commit_sha_before = commit_sha_after
    result = runner.invoke(
        cli, ['dataset', 'add', '-c', 'my-dataset2', directory_tree.strpath]
    )
    assert 0 == result.exit_code

    commit_sha_after = client.repo.head.object.hexsha
    assert commit_sha_before != commit_sha_after


def test_add_same_filename_multiple(runner, client, directory_tree):
    """Check adding same filename multiple times."""
    result = runner.invoke(
        cli, ['dataset', 'add', '-c', 'my-dataset1', directory_tree.strpath]
    )

    assert 0 == result.exit_code

    result = runner.invoke(
        cli, ['dataset', 'add', 'my-dataset1', directory_tree.strpath]
    )
    assert 1 == result.exit_code
    assert 'Error: File already exists in dataset.' in result.output

    result = runner.invoke(
        cli,
        ['dataset', 'add', '--force', 'my-dataset1', directory_tree.strpath]
    )
    assert 1 == result.exit_code
    assert 'Error: There is nothing to commit.' in result.output

    result = runner.invoke(
        cli, [
            'dataset', 'add', '--force', 'my-dataset1', directory_tree.strpath,
            'Dockerfile'
        ]
    )
    assert 0 == result.exit_code


def test_add_removes_local_path_information(runner, client, directory_tree):
    """Test local paths are removed when adding to a dataset."""
    result = runner.invoke(
        cli, ['dataset', 'add', '-c', 'my-dataset', directory_tree.strpath]
    )
    assert 0 == result.exit_code

    with client.with_dataset('my-dataset') as dataset:
        for file_ in dataset.files:
            assert file_.url.startswith('file://../')
            assert file_.url.endswith(file_.name)


def test_add_remove_credentials(runner, client, monkeypatch):
    """Check removal of credentials during adding of remote data files."""
    url = 'https://username:password@example.com/index.html'

    def get(u, *args, **kwargs):
        """Mocked response."""
        response = requests.Response()
        response._content = b'{}'
        response._content_consumed = True
        response.status_code = 200
        return response

    result = runner.invoke(cli, ['dataset', 'create', 'my-dataset'])
    assert 0 == result.exit_code

    monkeypatch.setattr(requests, 'get', get)
    dataset = client.load_dataset('my-dataset')
    o = client._add_from_url(dataset, url, client.path, extract=False)

    assert 'https://example.com/index.html' == o[0]['url']
