# Copyright 2019 DeepMind Technologies Limited.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================

"""Install script for setuptools."""

from distutils import sysconfig
import fnmatch
import os
import posixpath
import re
import shutil
import sys

import setuptools
from setuptools.command import build_ext

__version__ = '1.0.5'

PROJECT_NAME = 'labmaze'

REQUIRED_PACKAGES = [
    'absl-py',
    'numpy>=1.8.0',
    'setuptools!=50.0.0',  # https://github.com/pypa/setuptools/issues/2350
]

WORKSPACE_PYTHON_HEADERS_PATTERN = re.compile(
    r'(?<=path = ").*(?=",  # May be overwritten by setup\.py\.)')

IS_WINDOWS = sys.platform.startswith('win')


class BazelExtension(setuptools.Extension):
  """A C/C++ extension that is defined as a Bazel BUILD target."""

  def __init__(self, bazel_target):
    self.bazel_target = bazel_target
    self.relpath, self.target_name = (
        posixpath.relpath(bazel_target, '//').split(':'))
    ext_name = os.path.join(
        self.relpath.replace(posixpath.sep, os.path.sep), self.target_name)
    setuptools.Extension.__init__(self, ext_name, sources=[])


class BuildBazelExtension(build_ext.build_ext):
  """A command that runs Bazel to build a C/C++ extension."""

  def run(self):
    for ext in self.extensions:
      self.bazel_build(ext)
    build_ext.build_ext.run(self)

  def bazel_build(self, ext):
    with open('WORKSPACE', 'r') as f:
      workspace_contents = f.read()

    with open('WORKSPACE', 'w') as f:
      f.write(WORKSPACE_PYTHON_HEADERS_PATTERN.sub(
          sysconfig.get_python_inc().replace(os.path.sep, posixpath.sep),
          workspace_contents))

    if not os.path.exists(self.build_temp):
      os.makedirs(self.build_temp)

    bazel_argv = [
        'bazel',
        'build',
        ext.bazel_target,
        '--symlink_prefix=' + os.path.join(self.build_temp, 'bazel-'),
        '--compilation_mode=' + ('dbg' if self.debug else 'opt'),
    ]

    if IS_WINDOWS:
      for library_dir in self.library_dirs:
        bazel_argv.append('--linkopt=/LIBPATH:' + library_dir)

    self.spawn(bazel_argv)

    shared_lib_suffix = '.dll' if IS_WINDOWS else '.so'

    ext_bazel_bin_path = os.path.join(
        self.build_temp, 'bazel-bin',
        ext.relpath, ext.target_name + shared_lib_suffix)
    ext_dest_path = self.get_ext_fullpath(ext.name)
    ext_dest_dir = os.path.dirname(ext_dest_path)
    if not os.path.exists(ext_dest_dir):
      os.makedirs(ext_dest_dir)
    shutil.copyfile(ext_bazel_bin_path, ext_dest_path)


def find_data_files(package_dir, patterns):
  """Recursively finds files whose names match the given shell patterns."""
  paths = set()
  for directory, _, filenames in os.walk(package_dir):
    for pattern in patterns:
      for filename in fnmatch.filter(filenames, pattern):
        # NB: paths must be relative to the package directory.
        relative_dirpath = os.path.relpath(directory, package_dir)
        paths.add(os.path.join(relative_dirpath, filename))
  return list(paths)


setuptools.setup(
    name=PROJECT_NAME,
    version=__version__,
    description='LabMaze: DeepMind Lab\'s text maze generator.',
    author='DeepMind',
    license='Apache 2.0',
    ext_modules=[
        BazelExtension('//labmaze/cc/python:_defaults'),
        BazelExtension('//labmaze/cc/python:_random_maze'),
    ],
    cmdclass=dict(build_ext=BuildBazelExtension),
    packages=setuptools.find_packages(),
    package_data={'labmaze':
                  find_data_files(package_dir='labmaze', patterns=['*.png'])},
    install_requires=REQUIRED_PACKAGES,
)
