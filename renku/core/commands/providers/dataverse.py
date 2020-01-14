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
"""Dataverse API integration."""
import json
import pathlib
import re
import urllib
import urllib.parse as urlparse
from string import Template

import attr
import requests
from tqdm import tqdm

from renku.core import errors
from renku.core.commands.providers.api import ExporterApi, ProviderApi
from renku.core.commands.providers.doi import DOIProvider
from renku.core.models.datasets import Dataset, DatasetFile
from renku.core.utils.doi import extract_doi, is_doi

DATAVERSE_DEMO_URL = 'https://demo.dataverse.org/'

DATAVERSE_API_PATH = 'api/v1'

DATAVERSE_VERSION_API = 'info/version'
DATAVERSE_METADATA_API = 'datasets/export'
DATAVERSE_FILE_API = 'access/datafile/:persistentId/'
DATAVERSE_EXPORTER = 'schema.org'

DATAVERSE_DATASET_API = 'dataverses/{dataverseName}/datasets'


def check_dataverse_uri(url):
    """Check if an URL points to a dataverse instance."""
    url_parts = list(urlparse.urlparse(url))
    url_parts[2] = pathlib.posixpath.join(
        DATAVERSE_API_PATH, DATAVERSE_VERSION_API
    )
    url_parts[3:6] = [''] * 3
    version_url = urlparse.urlunparse(url_parts)

    response = requests.get(version_url)
    if response.status_code != 200:
        return False

    version_data = response.json()

    if 'status' not in version_data or 'data' not in version_data:
        return False

    version_info = version_data['data']

    if 'version' not in version_info or 'build' not in version_info:
        return False

    return True


def check_dataverse_doi(doi):
    """Check if a DOI points to a dataverse dataset."""
    try:
        doi = DOIProvider().find_record(doi)
    except LookupError:
        return False

    return check_dataverse_uri(doi.url)


def make_records_url(record_id, base_url):
    """Create URL to access record by ID."""
    url_parts = list(urlparse.urlparse(base_url))
    url_parts[2] = pathlib.posixpath.join(
        DATAVERSE_API_PATH, DATAVERSE_METADATA_API
    )
    args_dict = {'exporter': DATAVERSE_EXPORTER, 'persistentId': record_id}
    url_parts[4] = urllib.parse.urlencode(args_dict)
    return urllib.parse.urlunparse(url_parts)


def make_file_url(file_id, base_url):
    """Create URL to access record by ID."""
    url_parts = list(urlparse.urlparse(base_url))
    url_parts[2] = pathlib.posixpath.join(
        DATAVERSE_API_PATH, DATAVERSE_FILE_API
    )
    args_dict = {'persistentId': file_id}
    url_parts[4] = urllib.parse.urlencode(args_dict)
    return urllib.parse.urlunparse(url_parts)


@attr.s
class DataverseProvider(ProviderApi):
    """Dataverse API provider."""

    is_doi = attr.ib(default=False)
    _accept = attr.ib(default='application/json')

    @staticmethod
    def supports(uri):
        """Whether or not this provider supports a given uri."""
        is_doi_ = is_doi(uri)

        is_dataverse_uri = is_doi_ is None and check_dataverse_uri(uri)
        is_dataverse_doi = is_doi_ and check_dataverse_doi(is_doi_.group(0))

        return is_dataverse_uri or is_dataverse_doi

    @staticmethod
    def record_id(uri):
        """Extract record id from uri."""
        parsed = urlparse.urlparse(uri)
        return urlparse.parse_qs(parsed.query)['persistentId'][0]

    def make_request(self, uri):
        """Execute network request."""
        response = requests.get(uri, headers={'Accept': self._accept})
        if response.status_code != 200:
            raise LookupError('record not found')
        return response

    def find_record(self, uri):
        """Retrieves a record from Dataverse.

        :raises: ``LookupError``
        :param uri: DOI or URL
        :return: ``DataverseRecord``
        """
        if self.is_doi:
            doi = DOIProvider().find_record(uri)
            uri = doi.url

        uri = self.get_export_uri(uri)

        return self.get_record(uri)

    def get_export_uri(self, uri):
        """Gets a dataverse api export URI from a dataverse entry."""
        record_id = DataverseProvider.record_id(uri)
        uri = make_records_url(record_id, uri)
        return uri

    def get_record(self, uri):
        """Retrieve metadata and return ``DataverseRecordSerializer``."""
        response = self.make_request(uri)

        return DataverseRecordSerializer(
            json=response.json(), dataverse=self, uri=uri
        )

    def get_exporter(self, dataset, access_token):
        """Create export manager for given dataset."""
        return DataverseExporter(dataset=dataset, access_token=access_token)


@attr.s
class DataverseRecordSerializer:
    """Dataverse record Serializer."""

    _dataverse = attr.ib(default=None, kw_only=True)

    _uri = attr.ib(default=None, kw_only=True)

    _json = attr.ib(default=None, kw_only=True)

    def is_last_version(self, uri):
        """Check if record is at last possible version."""
        return True

    def _convert_json_property_name(self, property_name):
        """Removes '@' and converts names to snake_case."""
        property_name = property_name.strip('@')
        property_name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', property_name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', property_name).lower()

    @property
    def files(self):
        """Get all file metadata entries."""
        file_list = []

        for f in self._json['distribution']:
            mapped_file = {
                self._convert_json_property_name(k): v
                for k, v in f.items()
            }
            mapped_file['parent_url'] = self._uri
            file_list.append(mapped_file)
        return file_list

    def get_jsonld(self):
        """Get record metadata as jsonld."""
        response = self._dataverse.accept_jsonld().make_request(self._uri)
        self._jsonld = response.json()
        return self._jsonld

    def get_files(self):
        """Get Dataverse files metadata as ``DataverseFileSerializer``."""
        if len(self.files) == 0:
            raise LookupError('no files have been found')

        return [DataverseFileSerializer(**file_) for file_ in self.files]

    def as_dataset(self, client):
        """Deserialize `DataverseRecordSerializer` to `Dataset`."""
        files = self.get_files()
        dataset = Dataset.from_jsonld(self._json, client=client)

        serialized_files = []
        for file_ in files:
            remote_ = file_.remote_url
            dataset_file = DatasetFile(
                url=remote_.geturl(),
                id=file_._id if file_._id else file_.name,
                filename=file_.name,
                filesize=file_.content_size,
                filetype=file_.file_format,
                path='',
            )
            serialized_files.append(dataset_file)

        dataset.files = serialized_files

        return dataset


@attr.s
class DataverseFileSerializer:
    """Dataverse record file."""

    _id = attr.ib(default=None, kw_only=True)

    identifier = attr.ib(default=None, kw_only=True)

    name = attr.ib(default=None, kw_only=True)

    file_format = attr.ib(default=None, kw_only=True)

    content_size = attr.ib(default=None, kw_only=True)

    description = attr.ib(default=None, kw_only=True)

    content_url = attr.ib(default=None, kw_only=True)

    parent_url = attr.ib(default=None, kw_only=True)

    _type = attr.ib(default=None, kw_only=True)

    @property
    def remote_url(self):
        """Get remote URL as ``urllib.ParseResult``."""
        if self.content_url is not None:
            return urllib.parse.urlparse(self.content_url)

        if self.identifier is None:
            return None

        doi = extract_doi(self.identifier)

        if doi is None:
            return None

        file_url = make_file_url('doi:' + doi, self.parent_url)

        return urllib.parse.urlparse(file_url)


@attr.s
class DataverseExporter(ExporterApi):
    """Dataverse export manager."""

    dataset = attr.ib(kw_only=True)
    access_token = attr.ib(kw_only=True)
    base_url = attr.ib(default=DATAVERSE_DEMO_URL, kw_only=True)

    def set_access_token(self, access_token):
        """Set access token."""
        self.access_token = access_token

    def access_token_url(self):
        """Endpoint for creation of access token."""
        return urllib.parse.urljoin(
            self.base_url, '/dataverseuser.xhtml?selectTab=apiTokenTab'
        )

    def export(self, publish, base_url=None, dataverse=None, **kwargs):
        """Execute export process."""
        deposition = _DataverseDeposition(
            base_url=self.base_url, access_token=self.access_token
        )
        metadata = self._get_dataset_metadata()
        response = deposition.create_dataset(
            dataverse_name='SDSC-Test', metadata=metadata
        )
        dataset_pid = response.json()['data']['persistentId']

        with tqdm(total=len(self.dataset.files)) as progressbar:
            for file_ in self.dataset.files:
                deposition.upload_file(file_.full_path)
                progressbar.update(1)

        if publish:
            deposition.publish_dataset()

        return dataset_pid

    def _get_dataset_metadata(self):
        authors, contacts = self._get_creators()
        metadata_template = Template(DATASET_METADATA_TEMPLATE)
        metadata = metadata_template.substitute(
            name=self.dataset.name,
            authors=json.dumps(authors),
            contacts=json.dumps(contacts),
            description=self.dataset.description
        )
        return json.loads(metadata)

    def _get_creators(self):
        authors = []
        contacts = []

        for creator in self.dataset.creator:
            author_template = Template(AUTHOR_METADATA_TEMPLATE)
            author = author_template.substitute(
                name=creator.name, affiliation=creator.affiliation
            )
            authors.append(json.loads(author))

            contact_template = Template(CONTACT_METADATA_TEMPLATE)
            contact = contact_template.substitute(
                name=creator.name, email=creator.email
            )
            contacts.append(json.loads(contact))

        return authors, contacts


@attr.s
class _DataverseDeposition:
    """Dataverse record for deposit."""

    base_url = attr.ib(default=DATAVERSE_DEMO_URL, kw_only=True)
    access_token = attr.ib(kw_only=True)
    dataset_pid = attr.ib(default=None)

    def _post(self, api_path, metadata):
        url = pathlib.posixpath.join(
            self.base_url, DATAVERSE_API_PATH, api_path
        )
        headers = {'X-Dataverse-key': self.access_token}
        # FIXME catch errors
        return requests.post(url=url, json=metadata, headers=headers)

    def create_dataset(self, dataverse_name, metadata):
        """Create a dataset in a given dataverse."""
        api_path = DATAVERSE_DATASET_API.format(dataverseName=dataverse_name)
        response = self._post(api_path=api_path, metadata=metadata)
        # api = Api(base_url=self.base_url, api_token=self.access_token)
        # response = api.create_dataset(dataverse, json.dumps(metadata))

        if response.status_code != 201:
            error_msg = response.json()['message']
            print('==== CREATE FAILED', error_msg)
            # FIXME raise a better error here
            raise errors.OperationError(
                'ERROR: HTTP {} - Cannot create dataset. Message: {}'.format(
                    response.status_code, error_msg
                )
            )

        self.dataset_pid = response.json()['data']['persistentId']
        return response

    def upload_file(self, filepath):
        """Upload a file to a previously-created dataset."""
        if self.dataset_pid is None:
            raise ValueError('Dataset not created.')

        # api_path = '/datasets/:persistentId/add?persistentId={0}'.format(self.dataset_pid)
        # url = pathlib.posixpath.join(self.base_url, DATAVERSE_API_PATH, api_path)
        headers = {'X-Dataverse-key': self.access_token}

        url = self._make_url(
            'datasets/:persistentId/add', persistentId=self.dataset_pid
        )
        print('==== URL', url)

        # FIXME
        params = {'directoryLabel': 'some/directory/structure'}
        payload = dict(jsonData=json.dumps(params))

        # FIXME
        files = {'file': ('sample_file.txt', open(filepath, 'rb'))}

        response = requests.post(
            url, data=payload, files=files, headers=headers
        )

        print('==== RESP', response.status_code, response.text)

        # api = Api(base_url=self.base_url, api_token=self.access_token)
        # return api.upload_file(self.dataset_pid, filepath)

        return response

    def publish_dataset(self):
        """Publish a previously-created dataset."""
        if self.dataset_pid is None:
            raise ValueError('Dataset not created.')

        url = self._make_url(
            'datasets/:persistentId/actions/:publish',
            persistentId=self.dataset_pid,
            type='major'
        )
        headers = {'X-Dataverse-key': self.access_token}

        response = requests.post(url=url, headers=headers)
        print('==== RESP', response.status_code, response.text)
        return response

        # api = Api(base_url=self.base_url, api_token=self.access_token)
        # api.publish_dataset(pid=self.dataset_pid, type='major')

    def _make_url(self, api_path, **query_params):
        """Create URL for creating a dataset."""
        url_parts = urlparse.urlparse(self.base_url)
        path = pathlib.posixpath.join(DATAVERSE_API_PATH, api_path)

        # args_dict = {'persistentId': self.dataset_pid}
        query_params = urllib.parse.urlencode(query_params)
        url_parts = url_parts._replace(path=path, query=query_params)
        return urllib.parse.urlunparse(url_parts)


DATASET_METADATA_TEMPLATE = '''
{
    "datasetVersion": {
        "metadataBlocks": {
            "citation": {
                "fields": [
                    {
                        "value": "${name}",
                        "typeClass": "primitive",
                        "multiple": false,
                        "typeName": "title"
                    },
                    {
                        "value": ${authors},
                        "typeClass": "compound",
                        "multiple": true,
                        "typeName": "author"
                    },
                    {
                        "value": ${contacts},
                        "typeClass": "compound",
                        "multiple": true,
                        "typeName": "datasetContact"
                    },
                    {
                        "value": [
                            {
                                "dsDescriptionValue": {
                                    "value": "${description}",
                                    "multiple": false,
                                    "typeClass": "primitive",
                                    "typeName": "dsDescriptionValue"
                                }
                            }
                        ],
                        "typeClass": "compound",
                        "multiple": true,
                        "typeName": "dsDescription"
                    },
                    {
                        "value": [],
                        "typeClass": "controlledVocabulary",
                        "multiple": true,
                        "typeName": "subject"
                    }
                ],
                "displayName": "Citation Metadata"
            }
        }
    }
}'''

AUTHOR_METADATA_TEMPLATE = '''
{
    "authorName": {
        "value": "${name}",
        "typeClass": "primitive",
        "multiple": false,
        "typeName": "authorName"
    },
    "authorAffiliation": {
        "value": "${affiliation}",
        "typeClass": "primitive",
        "multiple": false,
        "typeName": "authorAffiliation"
    }
}
'''

CONTACT_METADATA_TEMPLATE = '''
{
    "datasetContactEmail": {
        "typeClass": "primitive",
        "multiple": false,
        "typeName": "datasetContactEmail",
        "value": "${email}"
    },
    "datasetContactName": {
        "typeClass": "primitive",
        "multiple": false,
        "typeName": "datasetContactName",
        "value": "${name}"
    }
}
'''
