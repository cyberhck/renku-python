# -*- coding: utf-8 -*-
#
# Copyright 2018-2019- Swiss Data Science Center (SDSC)
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
"""Represent provenance agents."""

import configparser
import re

from attr.validators import instance_of

from renku.core import errors
from renku.core.models import jsonld as jsonld
from renku.version import __version__, version_url


@jsonld.s(
    type=[
        'prov:Person',
        'schema:Person',
    ],
    context={
        'schema': 'http://schema.org/',
        'prov': 'http://www.w3.org/ns/prov#',
        'rdfs': 'http://www.w3.org/2000/01/rdf-schema#'
    },
    slots=True,
)
class Person:
    """Represent a person."""

    name = jsonld.ib(
        context='schema:name', kw_only=True, validator=instance_of(str)
    )
    email = jsonld.ib(context='schema:email', default=None, kw_only=True)
    label = jsonld.ib(context='rdfs:label', kw_only=True)
    affiliation = jsonld.ib(
        default=None, kw_only=True, context='schema:affiliation'
    )
    alternate_name = jsonld.ib(
        default=None, kw_only=True, context='schema:alternateName'
    )
    _id = jsonld.ib(context='@id', kw_only=True)

    @_id.default
    def default_id(self):
        """Set the default id."""
        import string
        if self.email:
            return 'mailto:{email}'.format(email=self.email)

        # prep name to be a valid ntuple string
        name = self.name.translate(str.maketrans('', '', string.punctuation))
        name = ''.join(filter(lambda x: x in string.printable, name))
        return '_:{}'.format(''.join(name.lower().split()))

    @email.validator
    def check_email(self, attribute, value):
        """Check that the email is valid."""
        if self.email and not (
            isinstance(value, str) and re.match(r'[^@]+@[^@]+\.[^@]+', value)
        ):
            raise ValueError('Email address is invalid.')

    @label.default
    def default_label(self):
        """Set the default label."""
        return self.name

    @classmethod
    def from_commit(cls, commit):
        """Create an instance from a Git commit."""
        return cls(
            name=commit.author.name,
            email=commit.author.email,
        )

    @property
    def short_name(self):
        """Gives full name in short form."""
        names = self.name.split()
        if len(names) == 1:
            return self.name

        last_name = names[-1]
        initials = [name[0] for name in names]
        initials.pop()

        return '{0}.{1}'.format('.'.join(initials), last_name)

    @classmethod
    def from_git(cls, git):
        """Create an instance from a Git repo."""
        git_config = git.config_reader()
        try:
            name = git_config.get_value('user', 'name', None)
            email = git_config.get_value('user', 'email', None)
        except (
            configparser.NoOptionError, configparser.NoSectionError
        ):  # pragma: no cover
            raise errors.ConfigurationError(
                'The user name and email are not configured. '
                'Please use the "git config" command to configure them.\n\n'
                '\tgit config --global --add user.name "John Doe"\n'
                '\tgit config --global --add user.email '
                '"john.doe@example.com"\n'
            )

        # Check the git configuration.
        if not name:  # pragma: no cover
            raise errors.MissingUsername()
        if not email:  # pragma: no cover
            raise errors.MissingEmail()

        return cls(name=name, email=email)

    @classmethod
    def from_string(cls, string):
        """Create an instance from a 'Name <email>' string."""
        regex_pattern = r'([^<]*)<{0,1}([^@<>]+@[^@<>]+\.[^@<>]+)*>{0,1}'
        name, email = re.search(regex_pattern, string).groups()
        name = name.rstrip()

        # Check the git configuration.
        if not name:  # pragma: no cover
            raise errors.ParameterError(
                'Name is invalid: A valid format is "Name <email>"'
            )

        if not email:  # pragma: no cover
            raise errors.ParameterError(
                'Email is invalid: A valid format is "Name <email>"'
            )

        return cls(name=name, email=email)

    @classmethod
    def from_dict(cls, obj):
        """Create and instance from a dictionary."""
        return cls(**obj)

    def __attrs_post_init__(self):
        """Finish object initialization."""
        # handle the case where ids were improperly set
        if self._id == 'mailto:None':
            self._id = self.default_id()


@jsonld.s(
    type=[
        'prov:SoftwareAgent',
        'wfprov:WorkflowEngine',
    ],
    context={
        'prov': 'http://www.w3.org/ns/prov#',
        'wfprov': 'http://purl.org/wf4ever/wfprov#',
        'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
    },
    frozen=True,
    slots=True,
)
class SoftwareAgent:
    """Represent executed software."""

    label = jsonld.ib(context='rdfs:label', kw_only=True)
    was_started_by = jsonld.ib(
        context='prov:wasStartedBy',
        default=None,
        kw_only=True,
    )

    _id = jsonld.ib(context='@id', kw_only=True)

    @classmethod
    def from_commit(cls, commit):
        """Create an instance from a Git commit."""
        author = Person.from_commit(commit)
        if commit.author != commit.committer:
            return cls(
                label=commit.committer.name,
                id=commit.committer.email,
                was_started_by=author,
            )
        return author


# set up the default agent

renku_agent = SoftwareAgent(
    label='renku {0}'.format(__version__), id=version_url
)
