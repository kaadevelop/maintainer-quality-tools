import ast
import re
import requests

from getaddons import get_modules_changed, get_versions_info

DEVELOPMENT_TAGS = [':memo:', ':fire:', ':fire_engine:', ':tv:', ':lock:', ':bath:', ':green_heart:', ':cat:', ':bomb:']
RELEASE_TAGS = [':tada:', ':zap:', ':sparkles:', ':rainbow:', ':ambulance:', ':heart_eyes:', ':cherries:', ':book:',
                ':euro:', ':handshake:', ':shield:', ':arrow_up:', ':arrow_down:', ':x:', ':sos:', ':peace_symbol:',
                ':alien',
]
VERSION_TAGS_DICT = {'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6',
                    'seven': '7', 'eight': '8', 'nine': '9'}
VERSION_TAGS = [':zero:', ':one:', ':two:', ':three:', ':four:', ':five:', ':six:', ':seven:', ':eight:', ':nine:']
REQUIREMENTS_TAGS_OF_VERSION = [':x:', ':arrow_up:', ':arrow_down:', ':tada:']


def get_errors_msgs_commits(travis_repo_slug, travis_pull_request_number, travis_branch, version, token, travis_build_dir, travis_pr_slug):
    symbol_in_branch = re.search(r'-', str(travis_branch))

    #GET /repos/:owner/:repo/pulls/:pull_number/commits
    #See API Github: https://developer.github.com/v3/repos/commits/#list-commits-on-a-repository
    real_errors = {}
    if not travis_pull_request_number or travis_pull_request_number == "false":
        return real_errors
    # GET / repos /: owner /:repo / commits
    url_request = 'https://github.it-projects.info/repos/%s/pulls/%s/commits' % (str(travis_repo_slug), str(travis_pull_request_number))
    resp = requests.get(url_request)
    commits = resp.json()
    if resp.status_code != 200:
        print('GITHUB API response for commits: %s', [resp, resp.headers, commits])
    links_to_files_version = get_links_to_files_version(travis_repo_slug, travis_pull_request_number)
    print('files of pr \n {}'.format(links_to_files_version))
    for key, value in links_to_files_version.items():
        html = requests.get(value)
        html = html.text
        if '__manifest__.py' in key:
            version = ''
            installable = ast.literal_eval(html).get('installable', True)
            if installable:
                version = ast.literal_eval(html).get('version')
        elif 'doc/changelog.rst' in key:
            version = re.search(r'`(\d.\d.\d)`', html)
        print('file if {}\nhtml: \n{}'.format(key, version))
    for commit in commits:
        parents_commit = commit.get('parents')
        if len(parents_commit) > 1:
            # we don't check merge commits
            continue
        commit = commit.get('commit').get('message')
        print('Commit: %s' % commit)
        if commit:
            first_word = commit.split(' ', 1)[0]
            if first_word == 'Revert':
                continue
            errors_commit = handler_commit(commit, symbol_in_branch, version, travis_build_dir, travis_repo_slug, travis_pull_request_number, travis_branch, travis_pr_slug)
            real_errors.update(errors_commit)
    return real_errors


def get_links_to_files_version(travis_repo_slug, travis_pull_request_number):
    url_request_files = 'https://github.it-projects.info/repos/%s/pulls/%s/files' % (
    str(travis_repo_slug), str(travis_pull_request_number))
    resp_files = requests.get(url_request_files)
    files = resp_files.json()
    if resp_files.status_code != 200:
        print('GITHUB API response for files: %s', [resp_files, resp_files.headers, files])
    links_to_files_version = {}
    for file in files:
        filename = file.get('filename')
        if any(x in filename for x in ['__manifest__.py', 'doc/changelog.rst', 'doc/index.rst']):
            links_to_files_version[filename] = file.get('raw_url')
    return links_to_files_version


def handler_commit(commit, symbol_in_branch, version, travis_build_dir, travis_repo_slug, travis_pull_request_number, travis_branch, travis_pr_slug):
    errors_commit = {}
    # looks tags starting at the beginning of the line and until first whitespace
    match_tags_commit = re.search(r'^(:[^\s]+:)', commit)
    if not match_tags_commit:
        error = {commit: 'There are no tags in the commit!'}
        errors_commit.update(error)
        return errors_commit
    match_tags_commit = match_tags_commit.group(1)
    # list of tags from match_tags_commit
    list_tags = re.findall(r'(:\w+:)', match_tags_commit)
    # list of tags that should not be in the commit
    extra_tags = [i for i in list_tags if i not in DEVELOPMENT_TAGS + RELEASE_TAGS + VERSION_TAGS]
    if extra_tags != []:
        error = {commit: 'There should not be such tags in the commit!'}
        errors_commit.update(error)
        return errors_commit
    # lists of Development tag and Release tag in commit
    dev_tag = list(set(list_tags) & set(DEVELOPMENT_TAGS))
    release_tag = list(set(list_tags) & set(RELEASE_TAGS))
    version_tags = list(set(list_tags) & set(VERSION_TAGS))
    if symbol_in_branch:
        errors_dev = check_dev_branch_tags(release_tag, dev_tag, commit)
        errors_commit.update(errors_dev)
    else:
        errors_stable = check_stable_branch_tags(dev_tag, release_tag, commit)
        errors_commit.update(errors_stable)
    # errors_stable_docs = check_stable_branch_docs(release_tag, commit, travis_build_dir, travis_repo_slug,
    #                                                   travis_pull_request_number, travis_branch, travis_pr_slug)
    # errors_commit.update(errors_stable_docs)
    if any(tag in REQUIREMENTS_TAGS_OF_VERSION for tag in list_tags):
        errors_version = check_version_tags(version_tags, list_tags, commit, version)
        errors_commit.update(errors_version)
    return errors_commit


def check_stable_branch_docs(release_tag, commit, travis_build_dir, travis_repo_slug, travis_pull_request_number, travis_branch, travis_pr_slug):
    errors_stable_docs = {}
    modules_changed = get_modules_changed(travis_build_dir, travis_branch)
    print('-------------------------modules_changed:\n{}'.format(modules_changed))
    modules_pr = []
    for module in modules_changed:
        module = re.search(r'/(\w+)$', module)
        modules_pr.append(module.group(1))
    modules_info = get_versions_info(travis_build_dir, modules_pr)
    print('-------------------------modules_info:\n{}'.format(modules_info))
    return errors_stable_docs

def check_version_tags(version_tags, list_tags, commit, version):
    errors_version = {}
    if version_tags == []:
        error = {commit: 'Must be Version tags!'}
        errors_version.update(error)
        return errors_version
    # # list of digit from tag's of commit
    # list_digits = [x.replace(':', '') for x in list_tags if x in VERSION_TAGS]
    # version_in_commit = ''
    # for digit in list_digits:
    #     # calculates version in commit
    #     version_in_commit += VERSION_TAGS_DICT.get(digit)
    # if version.replace(".", "") != version_in_commit:
    #     error = {commit: 'Version in commit is wrong!'}
    #     errors_version.update(error)
    #     return errors_version
    # # list of indices (requirements of version's tags in commit)
    # index_requirements_tags_version = [list_tags.index(i) for i in list_tags if i in REQUIREMENTS_TAGS_OF_VERSION]
    # # list of indices (version's tags in commit)
    # index_verion_tags = [list_tags.index(i) for i in list_tags if i in VERSION_TAGS]
    # # Check proper order of tags in commit: comparison indices "requirements of versions tags" and "versions tags"
    # if not index_requirements_tags_version[-1] < index_verion_tags[0]:
    #     error = {commit: 'Version tag must be after the main tag!'}
    #     errors_version.update(error)
    #     return errors_version
    return errors_version


def check_dev_branch_tags(release_tag, dev_tag, commit):
    errors_dev = {}
    if release_tag != []:
        error = {commit: 'You cannot use release tags in development branch!'}
        errors_dev.update(error)
        return errors_dev
    if dev_tag == []:
        error = {commit: 'There should be a Development tag in the dev branches!'}
        errors_dev.update(error)
        return errors_dev
    # checking the number of dev tags in commit
    if len(dev_tag) > 1:
        error = {commit: 'You must use only one Development tag!'}
        errors_dev.update(error)
        return errors_dev
    return errors_dev


def check_stable_branch_tags(dev_tag, release_tag, commit):
    errors_stable = {}
    if dev_tag != []:
        error = {commit: 'You cannot use Development tag in stable branch!'}
        errors_stable.update(error)
        return errors_stable
    if release_tag == []:
        error = {commit: 'There should be a Release tag in the stable branches!'}
        errors_stable.update(error)
        return errors_stable
    # checking the number of release tags in commit
    if len(release_tag) > 1:
        error = {commit: 'You must use only one Release tag (along with version tags when they are required)!'}
        errors_stable.update(error)
        return errors_stable
    return errors_stable
