from pybuilder.core import use_plugin
from pybuilder.core import init
from pybuilder.core import Author

use_plugin('python.core')
use_plugin('python.unittest')
use_plugin('python.install_dependencies')
use_plugin('python.flake8')
use_plugin('python.distutils')
use_plugin('pypi:pybuilder_radon', '~=0.1.2')
use_plugin('pypi:pybuilder_bandit', '~=0.1.3')

name = 'prepbadge'
authors = [Author('Emilio Reyes', 'emilio.reyes@intel.com')]
summary = 'A CLI to create pull request workflows for updating edgeXfoundry repos.'
url = 'https://github.com/soda480/prepbadge'
version = '0.1.0'
default_task = [
    'clean',
    'analyze',
    'radon',
    'bandit',
    'package']
license = 'Apache License, Version 2.0'
description = summary


@init
def set_properties(project):
    project.set_property('flake8_max_line_length', 120)
    project.set_property('flake8_verbose_output', True)
    project.set_property('flake8_break_build', True)
    project.set_property('flake8_include_scripts', True)
    project.set_property('flake8_include_test_sources', True)
    project.set_property('flake8_ignore', 'F401, E501')  # W503, F401')
    project.build_depends_on_requirements('requirements-build.txt')
    project.depends_on_requirements('requirements.txt')
    project.set_property('distutils_console_scripts',
        ['prepbadge = prepbadge.prepbadge:main'])
    project.set_property('radon_break_build_average_complexity_threshold', 4)
    project.set_property('radon_break_build_complexity_threshold', 10)
    project.set_property('bandit_break_build', False)
