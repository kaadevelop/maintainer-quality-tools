#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import check_tags
import travis_helpers


version = os.environ.get('VERSION', '')
token = os.environ.get('GITHUB_TOKEN')
travis_pull_request_number = os.environ.get('TRAVIS_PULL_REQUEST')
travis_repo_slug = os.environ.get('TRAVIS_REPO_SLUG')
travis_branch = os.environ.get('TRAVIS_BRANCH')
error_msg = "Check guidelines: https://gitlab.com/itpp/handbook/blob/master/documenting-updates.md If you are not IT-Projects' employee, you can ignore it and we'll handle it by our own"
exit_status = 0
result = check_tags.get_errors_msgs_commits(travis_repo_slug, travis_pull_request_number, travis_branch, version, token)
count_errors = len(result.keys())
if count_errors > 0:
    for key, value in result.items():
        print('Wrong commit:')
        print(travis_helpers.yellow("{commit}".format(commit=key)))
        print(travis_helpers.red("{errors}".format(errors=value)))
        print(error_msg)
        print()
    print()
    print(travis_helpers.red("check tags errors: found {number_errors}!".format(
              number_errors=count_errors)))
    exit_status = 1
exit(exit_status)
