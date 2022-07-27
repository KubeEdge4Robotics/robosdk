# Copyright 2021 The KubeEdge Authors.
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

import os
import sys

from setuptools import find_packages, setup

assert sys.version_info >= (3, 6), "Sorry, Python < 3.6 is not supported."

package_name: str = "robosdk"


class InstallPrepare:
    """
    Parsing dependencies
    """

    package_path = os.path.dirname(__file__)

    def __init__(self):
        self.project = os.path.join(self.package_path, package_name)
        self._long_desc = os.path.join(self.project, "README.md")
        self._version = os.path.join(self.project, "VERSION")
        self._owner = os.path.join(self.project, "..", "OWNERS")
        self._requirements = os.path.join(self.project, "..",
                                          "requirements.txt")
        self._dev_requirements = os.path.join(self.project, "..",
                                              "requirements.dev.txt")

    @property
    def long_desc(self):
        if not os.path.isfile(self._long_desc):
            return ""
        with open(self._long_desc, "r", encoding="utf-8") as fh:
            long_desc = fh.read()
        return long_desc

    @property
    def version(self):
        default_version = "dev"  # non-official version
        if not os.path.isfile(self._version):
            return default_version
        with open(self._version, "r", encoding="utf-8") as fh:
            __version__ = fh.read().strip()
        return __version__ or default_version

    @property
    def owners(self):
        default_owner = "kubeEdge"
        if not os.path.isfile(self._owner):
            return default_owner
        with open(self._owner, "r", encoding="utf-8") as fh:
            check, approver = False, set()
            for line in fh:
                if not line.strip():
                    continue
                if check:
                    approver.add(line.strip().split()[-1])
                check = (line.startswith("approvers:") or
                         (line.startswith(" -") and check))
        return ",".join(approver) or default_owner

    @property
    def basic_dependencies(self):
        return self._read_requirements(self._requirements)

    def extra_dependencies(self, backend):
        _c = os.path.join(self.project, f"requirements-{backend}.txt")
        if os.path.isfile(_c):
            return self._read_requirements(_c)
        return self._read_requirements(self._dev_requirements, backend)

    @staticmethod
    def package_files(data_files, subfix=".yaml"):
        paths = []
        data_prefix = os.path.join("share", package_name)
        for (root, sub_dir, filename) in os.walk(data_files):
            if not len(filename):
                continue
            install_dir = os.path.join(data_prefix, root)
            entry_dir = [os.path.join(root, _f) for _f in
                         filename if _f.endswith(subfix)]

            paths.append((install_dir, entry_dir))
        return paths

    @staticmethod
    def _read_requirements(file_path, section="all"):
        if not os.path.isfile(file_path):
            return []
        with open(file_path, "r", encoding="utf-8") as f:
            install_requires = [p.strip() for p in f.readlines() if p.strip()]
        if section == "all":
            return list(filter(lambda x: not x.startswith("#"),
                               install_requires))
        section_start = False
        section_requires = []
        for p in install_requires:
            if section_start:
                if p.startswith("#"):
                    return section_requires
                section_requires.append(p)
            elif p.startswith(f"# {section}"):
                section_start = True
        return section_requires


_info = InstallPrepare()

setup(
    name=package_name,
    version=_info.version,
    packages=find_packages(exclude=["tests", "*.tests",
                                    "*.tests.*", "tests.*"]),
    package_data={
      'system': [
          _info._long_desc,
          _info._version,
          _info._owner,
      ],
    },
    data_files=_info.package_files("configs"),
    author=_info.owners,
    author_email="",
    maintainer=_info.owners,
    maintainer_email="",
    include_package_data=True,
    python_requires=">=3.6",
    long_description=_info.long_desc,
    long_description_content_type="text/markdown",
    license="Apache License 2.0",
    tests_require=["pytest"],
    install_requires=_info.basic_dependencies,
    extras_require={
        "ros": _info.extra_dependencies("ros"),
    },
    entry_points={
        "console_script": [
            f"build = {package_name}.command.build:main",
        ],
    },
)
