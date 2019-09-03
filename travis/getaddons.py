#!/usr/bin/env python
"""
Usage: get-addons [-m] path1 [path2 ...]
Given a list  of paths, finds and returns a list of valid addons paths.
With -m flag, will return a list of modules names instead.
"""

import ast
import os
import sys

from git_run import GitRun

MANIFEST_FILES = [
    '__manifest__.py',
    '__odoo__.py',
    '__openerp__.py',
    '__terp__.py',
]

DOC_FILES = [
    'chengelog.rst',
    'index.rst'
]

def is_module(path):
    """return False if the path doesn't contain an odoo module, and the full
    path to the module manifest otherwise"""

    if not os.path.isdir(path):
        return False
    files = os.listdir(path)
    filtered = [x for x in files if x in (MANIFEST_FILES + ['__init__.py'])]
    if len(filtered) == 2 and '__init__.py' in filtered:
        return os.path.join(
            path, next(x for x in filtered if x != '__init__.py'))
    else:
        return False


def get_changelog_path(path):
    path += '/doc/'
    if not os.path.isdir(path):
        return False
    files = os.listdir(path)
    print('--files-- get changelog is {}'.format(files))
    # filtered = [x for x in files if x in (DOC_FILES)]
    # print('--filtered-- get changelog is {}'.format(filtered))
    if len(files) == 2:
        return os.path.join(
            path, next(x for x in files))
    else:
        return False


def get_modules(path, depth=1):
    """ Return modules of path repo (used in test_server.py)"""
    return sorted(list(get_modules_info(path, depth).keys()))


def get_modules_info(path, depth=1):
    """ Return a digest of each installable module's manifest in path repo"""
    # Avoid empty basename when path ends with slash
    if not os.path.basename(path):
        path = os.path.dirname(path)

    modules = {}
    if os.path.isdir(path) and depth > 0:
        for module in os.listdir(path):
            manifest_path = is_module(os.path.join(path, module))
            if manifest_path:
                manifest = ast.literal_eval(open(manifest_path).read())
                if manifest.get('installable', True):
                    modules[module] = {
                        'application': manifest.get('application'),
                        'depends': manifest.get('depends') or [],
                        'auto_install': manifest.get('auto_install'),
                    }
            else:
                deeper_modules = get_modules_info(
                    os.path.join(path, module), depth-1)
                modules.update(deeper_modules)
    return modules


def get_versions_info(path, modules_pr, depth=1):
    """ Return a digest of each installable module's manifest in path repo"""
    # Avoid empty basename when path ends with slash
    if not os.path.basename(path):
        path = os.path.dirname(path)

    modules = {}
    if os.path.isdir(path) and depth > 0:
        listdir = os.listdir(path)
        for module in listdir:
            if module not in modules_pr:
                continue
            manifest_path = is_module(os.path.join(path, module))
            print('manifest_path is {}'.format(manifest_path))
            changelog_path = get_changelog_path(os.path.join(path, module))
            print('changelog_path is {}'.format(changelog_path))
            if manifest_path:
                if changelog_path:
                    # changelog = ast.literal_eval(open(changelog_path).read())
                    # changelog = os.path.isfile(changelog_path)
                    with open(changelog_path) as f_changelog:
                        changelog = f_changelog.readlines()
                    print('--changelog get_versions_info is \n{}'.format(changelog))
                print('5')
                manifest = ast.literal_eval(open(manifest_path).read())
                if manifest.get('installable', True):
                    modules[module] = {
                        'version': manifest.get('version')
                    }
            else:
                deeper_modules = get_modules_info(
                    os.path.join(path, module), depth-1)
                modules.update(deeper_modules)
    return modules


def is_addons(path):
    res = get_modules(path) != []
    return res


def get_addons(path, depth=1):
    """Return repositories in path. Can search in inner folders as depth."""
    if not os.path.exists(path) or depth < 0:
        return []
    res = []
    if is_addons(path):
        res.append(path)
    else:
        new_paths = [os.path.join(path, x)
                     for x in sorted(os.listdir(path))
                     if os.path.isdir(os.path.join(path, x))]
        for new_path in new_paths:
            res.extend(get_addons(new_path, depth-1))
    return res


def get_modules_changed(path, ref='HEAD'):
    """Get modules changed from git diff-index {ref}
    :param path: String path of git repo
    :param ref: branch or remote/branch or sha to compare
    :return: List of paths of modules changed
    """
    git_run_obj = GitRun(os.path.join(path, '.git'))
    if ref != 'HEAD':
        fetch_ref = ref
        if ':' not in fetch_ref:
            # to force create branch
            fetch_ref += ':' + fetch_ref
        git_run_obj.run(['fetch'] + fetch_ref.split('/', 1))
    items_changed = git_run_obj.get_items_changed(ref)
    folders_changed = set([
        item_changed.split('/')[0]
        for item_changed in items_changed
        if '/' in item_changed]
    )
    modules = set(get_modules(path))
    modules_changed = list(modules & folders_changed)
    modules_changed_path = [
        os.path.join(path, module_changed)
        for module_changed in modules_changed]
    return modules_changed_path


def get_dependencies(modules, module_name):
    """Return a set of all the dependencies in deep of the module_name.
    The module_name is included in the result."""
    result = set()
    for dependency in modules.get(module_name, {}).get('depends', []):
        result |= get_dependencies(modules, dependency)
    return result | set([module_name])


def get_dependents(modules, module_name):
    """Return a set of all the modules that are dependent of the module_name.
    The module_name is included in the result."""
    result = set()
    for dependent in modules.keys():
        if module_name in modules.get(dependent, {}).get('depends', []):
            result |= get_dependents(modules, dependent)
    return result | set([module_name])


def add_auto_install(modules, to_install):
    """ Append automatically installed glue modules to to_install if their
    dependencies are already present. to_install is a set. """
    found = True
    while found:
        found = False
        for module, module_data in modules.items():
            if (module_data.get('auto_install') and
                    module not in to_install and
                    all(dependency in to_install
                        for dependency in module_data.get('depends', []))):
                found = True
                to_install.add(module)
    return to_install


def get_applications_with_dependencies(modules):
    """ Return all modules marked as application with their dependencies.
    For our purposes, l10n modules cannot be an application. """
    result = set()
    for module, module_data in modules.items():
        if module_data.get('application') and not module.startswith('l10n_'):
            result |= get_dependencies(modules, module)
    return add_auto_install(modules, result)


def get_localizations_with_dependents(modules):
    """ Return all localization modules with the modules that depend on them
    """
    result = set()
    for module in modules.keys():
        if module.startswith('l10n_'):
            result |= get_dependents(modules, module)
    return result


def main(argv=None):
    if argv is None:
        argv = sys.argv
    params = argv[1:]
    if not params:
        print(__doc__)
        return 1

    list_modules = False
    application = None
    localization = None
    exclude_modules = []

    while params and params[0].startswith('-'):
        param = params.pop(0)
        if param == '-m':
            list_modules = True
        elif param == '-e':
            exclude_modules = [x for x in params.pop(0).split(',')]
        elif param == '--only-applications':
            application = True
        elif param == '--exclude-applications':
            application = False
        elif param == '--only-localization':
            localization = True
        elif param == '--exclude-localization':
            localization = False
        elif param.startswith('-'):
            raise Exception('Unknown parameter: %s' % param)

    if list_modules:
        modules = {}
        for path in params:
            modules.update(get_modules_info(path))
        res = set(modules.keys())
        applications, localizations = set(), set()
        if application is True or application is False:
            applications = get_applications_with_dependencies(modules)
            if not application:
                res -= applications
                applications = set()
        if localization is True or localization is False:
            localizations = get_localizations_with_dependents(modules)
            if not localization:
                res -= localizations
                localizations = set()
        if application or localization:
            res = applications | localizations
        res = sorted(list(res))
    else:
        lists = [get_addons(path) for path in params]
        res = [x for l in lists for x in l]  # flatten list of lists
    if exclude_modules:
        res = [x for x in res if x not in exclude_modules]
    print(','.join(res))
    return res


if __name__ == "__main__":
    sys.exit(main())
