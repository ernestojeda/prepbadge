import json
import logging
from os import getenv
from time import sleep

from rest3client import RESTclient 
from github3api import GitHubAPI
from mp4ansi import MP4ansi
from mdutils import MdUtils

logger = logging.getLogger(__name__)


CODECOV_HOST = 'codecov.io'
JENKINS_HOST = 'jenkins.edgexfoundry.org'


def configure_logging():
    """ configure logging
    """
    rootLogger = logging.getLogger()
    # must be set to this level so handlers can filter from this level
    rootLogger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler('prepbadge.log')
    file_formatter = logging.Formatter("%(asctime)s %(processName)s [%(funcName)s] %(levelname)s %(message)s")
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    rootLogger.addHandler(file_handler)


def get_github_client():
    """ return instance of RESTclient for codecov.io
    """
    token = getenv('GH_TOKEN_PSW')
    if not token:
        raise ValueError('GH_TOKEN_PSW environment variable must be set to token')
    return GitHubAPI.get_client()


def get_github_data(*args):
    """ return non-archived and non-disabled github repos for owner
    """
    owner = args[0]['owner']
    logger.debug(f'getting github information for {owner} repos')
    repos = []
    client = get_github_client()
    all_repos = client.get(f'/orgs/{owner}/repos', _get='all', _attributes=['name', 'full_name', 'archived', 'disabled', 'languages_url', 'html_url', 'license', 'tags_url'])
    attributes = {'archived': False, 'disabled': False}
    logger.debug(f'{owner} has a total of {len(all_repos)} matching repos in github')
    for repo in all_repos:
        logger.debug(f"checking repo {repo['name']}")
        sleep(.02)
        match_attributes = all(repo[key] == value for key, value in attributes.items() if key in repo)
        if match_attributes:
            logger.debug(f"checking language for {repo['name']}")
            languages = client.get(repo['languages_url'].replace(f'https://{client.hostname}', ''))
            logger.debug(f"checking tags for {repo['name']}")
            tags = client.get(repo['tags_url'].replace(f'https://{client.hostname}', ''))
            repos.append({
                'name': repo['name'],
                'owner_repo': repo['full_name'],
                'github_location': repo['html_url'].replace('https://', ''),
                'github_url': repo['html_url'],
                'is_go_based': True if languages.get('Go') else False,
                'has_license': not repo['license'] is None,
                'has_tags': len(tags) > 1
            })
    return repos


def get_codecov_client():
    """ return instance of RESTclient for codecov.io
    """
    token = getenv('CC_TOKEN_PSW')
    if not token:
        raise ValueError('CC_TOKEN_PSW environment variable must be set to token')
    return RESTclient(CODECOV_HOST, token=token)


def get_codecov_data(*args):
    """ get codecov data
    """
    owner = args[0]['owner']
    logger.debug(f'getting codecov information for {owner} repos')
    data = []
    client = get_codecov_client()
    repos = client.get(f'/api/gh/{owner}?limit=100')['repos']
    logger.debug(f'{owner} has a total of {len(repos)} repos registered in codecov.io')
    for repo in repos:
        logger.debug(f"retrieving codecov data for {repo['name']} repo")
        settings = client.get(f"/api/gh/{owner}/{repo['name']}/settings")
        data.append({
            'repo': repo['name'],
            'codecov_coverage': repo['coverage'],
            'codecov_badge': f"https://{client.hostname}/gh/{owner}/{repo['name']}/branch/master/graph/badge.svg?token={settings['repo']['image_token']}",
            'codecov_url': f"https://codecov.io/gh/{owner}/{repo['name']}"
        })
    return data


def get_jenkins_client():
    """ return instance of RESTclient for jenkins api
    """
    user = getenv('JN_TOKEN_USR')
    if not user:
        raise ValueError('JN_TOKEN_USR environment variable must be set to token')
    password = getenv('JN_TOKEN_PSW')
    if not password:
        raise ValueError('JN_TOKEN_PSW environment variable must be set to token')
    return RESTclient(JENKINS_HOST, user=user, password=password)


def get_jenkins_data(*args):
    """ return jenkins data for owner
    """
    owner = args[0]['owner']
    logger.debug(f'getting jenkins information for {owner} repos')
    data = []
    client = get_jenkins_client()
    jobs = client.get(f'/job/{owner}/api/json?tree=displayName,name,url,jobs[name,url,jobs[name,url,buildable]]')
    logger.debug(f"{owner} has a total of {len(jobs['jobs'])} repos registered in jenkins")
    display_name = jobs['displayName']
    for job in jobs['jobs']:
        sleep(.02)
        repo = job['name']
        logger.debug(f"retrieving jenkins data for {repo} repo")
        index = find(job['jobs'], 'master')
        if index > -1:
            data.append({
                'repo': repo,
                'jenkins_badge': f'https://{JENKINS_HOST}/view/{display_name}/job/{owner}/job/{repo}/job/master/badge/icon'.replace(" ", "%20"),
                'jenkins_url': f'https://{JENKINS_HOST}/view/{display_name}/job/{owner}/job/{repo}/job/master/'.replace(" ", "%20")
            })
    return data


def write_file(process_data, name):
    """ write data to json file
    """
    filename = f'{name}.json'
    with open(filename, 'w') as fp:
        json.dump(process_data, fp, indent=2)
        print(f'{name} report written to {filename}')


def check_result(process_data):
    """ raise exception if any result in process data is exception
    """
    if any([isinstance(process.get('result'), Exception) for process in process_data]):
        raise Exception('one or more processes had errors - check logfile for more information')


def find(items, name):
    """ return index of item with name in items
    """
    for index, item in enumerate(items):
        if item['name'] == name:
            return index
    logger.warn(f'no item with name {name} in target list')
    return -1


def coalesce_data(github, codecov, jenkins):
    """ coalesce repos from codecov and jenkins into github
    """
    for item in codecov[0]['result']:
        repo = item.pop('repo')
        index = find(github[0]['result'], repo)
        if index > -1:
            github[0]['result'][index].update(item)
    for item in jenkins[0]['result']:
        repo = item.pop('repo')
        index = find(github[0]['result'], repo)
        if index > -1:
            github[0]['result'][index].update(item)
    # write_file(github, 'badges')


def md_jenkins_build(repo, md):
    """ add jenkins build badge to md
    """
    if 'jenkins_badge' in repo:
        md.write(f"[![Build Status]({repo['jenkins_badge']})]({repo['jenkins_url']}) ")


def md_code_coverage(repo, md):
    """ add code coverage badge to md
    """
    if 'codecov_badge' in repo:
        md.write(f"[![Code Coverage]({repo['codecov_badge']})]({repo['codecov_url']}) ")


def md_go_report_card(repo, md):
    """ add go report card badge to md
    """
    if repo['is_go_based']:
        md.write(f"[![Go Report Card](https://goreportcard.com/badge/{repo['github_location']})](https://goreportcard.com/report/{repo['github_location']}) ")


def md_tags(repo, md):
    if repo['has_tags']:
        md.write(f"[![GitHub Tag)](https://img.shields.io/github/v/tag/{repo['owner_repo']}?include_prereleases&sort=semver&label=latest)]({repo['github_url']}/tags) ")


def md_license(repo, md):
    if repo['has_license']:
        md.write(f"[![GitHub License](https://img.shields.io/github/license/{repo['owner_repo']})](https://choosealicense.com/licenses/apache-2.0/) ")


def md_go_version(repo, md):
    """ add go version badge to md
    """
    if repo['is_go_based']:
        md.write(f"![GitHub go.mod Go version](https://img.shields.io/github/go-mod/go-version/{repo['owner_repo']}) ")


def create_markdown(github):
    """ create markdown for repos in github dict
    """
    filename = 'prepbadge'
    print(f'Creating markdown file {filename}.md')
    md = MdUtils(file_name=filename, title='EdgeXFoundry Repo Badges Preview')
    for repo in github[0]['result']:
        md.new_header(level=1, title=md.new_inline_link(link=repo['github_url'], text=repo['name']))
        md_jenkins_build(repo, md)
        md_code_coverage(repo, md)
        md_go_report_card(repo, md)
        md_tags(repo, md)
        md_license(repo, md)
        md_go_version(repo, md)
        md.write(f"[![GitHub Pull Requests](https://img.shields.io/github/issues-pr-raw/{repo['owner_repo']})]({repo['github_url']}/pulls) ")
        md.write(f"[![GitHub Contributors](https://img.shields.io/github/contributors/{repo['owner_repo']})]({repo['github_url']}/contributors) ")
        md.write(f"[![GitHub Commit Activity](https://img.shields.io/github/commit-activity/m/{repo['owner_repo']})]({repo['github_url']}/commits) ")
        md.new_line("")
    md.create_md_file()


def run_github_data_collection(owner):
    """ run github data collection
    """
    print(f'Retrieving github repos for {owner}')
    process_data = [{'owner': owner}]
    MP4ansi(
        function=get_github_data,
        process_data=process_data,
        config={
            'id_regex': r'^getting github information for (?P<value>.*) repos$',
            'progress_bar': {
                'total': r'^.* has a total of (?P<value>\d+) matching repos in github$',
                'count_regex': r'^checking repo (?P<value>.*)$',
                'progress_message': 'Retrieval of github.com repos complete'
            }
        }).execute()
    check_result(process_data)
    # write_file(process_data, 'github')
    return process_data


def run_codecov_data_collection(owner):
    """ run codecov data collection
    """
    print(f'Retrieving codecov.io data for {owner} ...')
    process_data = [{'owner': owner}]
    MP4ansi(
        function=get_codecov_data,
        process_data=process_data,
        config={
            'id_regex': r'^getting codecov information for (?P<value>.*) repos$',
            'progress_bar': {
                'total': r'^.* has a total of (?P<value>\d+) repos registered in codecov.io$',
                'count_regex': r'^retrieving codecov data for (?P<value>.*) repo$',
                'progress_message': 'Retrieval of codecov.io data complete'
            }
        }).execute()
    check_result(process_data)
    # write_file(process_data, 'codecov')
    return process_data


def run_jenkins_data_collection(owner):
    """ run jenkins data collection
    """
    print(f'Retrieving jenkins data for {owner} ...')
    process_data = [{'owner': owner}]
    MP4ansi(
        function=get_jenkins_data,
        process_data=process_data,
        config={
            'id_regex': r'^getting jenkins information for (?P<value>.*) repos$',
            'progress_bar': {
                'total': r'^.* has a total of (?P<value>\d+) repos registered in jenkins$',
                'count_regex': r'^retrieving jenkins data for (?P<value>.*) repo$',
                'progress_message': 'Retrieval of jenkins data complete'
            }
        }).execute()
    check_result(process_data)
    # write_file(process_data, 'jenkins')
    return process_data


def main(owner):
    """ main function
    """
    configure_logging()
    github_data = run_github_data_collection(owner)
    codecov_data = run_codecov_data_collection(owner)
    jenkins_data = run_jenkins_data_collection(owner)
    coalesce_data(github_data, codecov_data, jenkins_data)
    create_markdown(github_data)


if __name__ == '__main__':
    main('edgexfoundry')
