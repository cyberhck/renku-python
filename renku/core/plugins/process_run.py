# -*- coding: utf-8 -*-
#
# Copyright 2017-2019- Swiss Data Science Center (SDSC)
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
"""Plugin hooks for ``ProcessRun`` customization."""
import pluggy

hookspec = pluggy.HookspecMarker('renku')


@hookspec
def process_run_annotations(run):
    """Plugin Hook to add ``Annotation`` entry list to a ``ProcessRun``.

    :param run: A ``ProcessRun`` object to get annotations for.
    :returns: A list of ``renku.core.models.provenance.activities.Annotation``
              objects.
    """
    pass
