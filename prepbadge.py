import json
import logging
from os import getenv
from time import sleep

from rest3client import RESTclient 
from github3api import GitHubAPI
from mp4ansi import MP4ansi
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)
# logging.getLogger('rest3client').setLevel(logging.CRITICAL)


JENKINS_HOST = 'jenkins.edgexfoundry.org'


def configure_logging():
    """ configure logging
    """
    rootLogger = logging.getLogger()
    # must be set to this level so handlers can filter from this level
    rootLogger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler('codecov.log')
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


def get_github_repos(*args):
    """ return non-archived and non-disabled github repos for owner
    """
    owner = args[0]['owner']
    logger.debug(f'getting github information for {owner} repos')
    repos = []
    client = get_github_client()
    all_repos = client.get(f'/orgs/{owner}/repos', _get='all', _attributes=['name', 'archived', 'disabled', 'languages_url', 'svn_url'])
    attributes = {'archived': False, 'disabled': False}
    logger.debug(f'{owner} has a total of {len(all_repos)} matching repos in github')
    for repo in all_repos:
        logger.debug(f"checking repo {repo['name']}")
        sleep(.05)
        match_attributes = all(repo[key] == value for key, value in attributes.items() if key in repo)
        if match_attributes:
            logger.debug(f"checking language for {repo['name']}")
            endpoint = repo['languages_url'].replace(f'https://{client.hostname}', '')
            languages = client.get(endpoint)
            repos.append({
                'name': repo['name'],
                'github_location': repo['svn_url'].replace('https://', ''),
                'is_go_based': True if languages.get('Go') else False
            })
    return repos


def get_codecov_client():
    """ return instance of RESTclient for codecov.io
    """
    token = getenv('CC_TOKEN_PSW')
    if not token:
        raise ValueError('CC_TOKEN_PSW environment variable must be set to token')
    return RESTclient('codecov.io', token=token)


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
            'codecov_badge': f"https://{client.hostname}/gh/{owner}/{repo['name']}/branch/master/graph/badge.svg?token={settings['repo']['image_token']}"
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
    return RESTclient('jenkins.edgexfoundry.org', user=user, password=password)


def get_jenkins_data(*args):
    """ return jenkins data for owner
    """
    owner = args[0]['owner']
    logger.debug(f'getting jenkins information for {owner} repos')
    data = []
    client = get_jenkins_client()
    jobs = client.get(f'/job/{owner}/api/json?tree=displayName,name,url,jobs[name,url]')
    logger.debug(f"{owner} has a total of {len(jobs['jobs'])} repos registered in jenkins")
    display_name = jobs['displayName']
    for job in jobs['jobs']:
        sleep(.05)
        repo = job['name']
        logger.debug(f"retrieving jenkins data for {repo} repo")
        data.append({
            'repo': repo,
            'jenkins_badge': f'https://{JENKINS_HOST}/view/{display_name}/job/{owner}/job/{repo}/job/master/badge/icon',
            'jenkins_build': f'https://{JENKINS_HOST}/view/{display_name}/job/{owner}/job/{repo}/job/master/'
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


def main(owner):
    """ main function
    """
    configure_logging()
    print(f'Retrieving github repos for {owner}')
    gh_process_data = [{'owner': owner}]
    MP4ansi(
        function=get_github_repos,
        process_data=gh_process_data,
        config={
            'id_regex': r'^getting github information for (?P<value>.*) repos$',
            'progress_bar': {
                'total': r'^.* has a total of (?P<value>\d+) matching repos in github$',
                'count_regex': r'^checking repo (?P<value>.*)$',
                'progress_message': 'Retrieval of github.com repos complete'
            }
        }).execute()
    check_result(gh_process_data)
    write_file(gh_process_data, 'github')

    print(f'Retrieving codecov.io data for {owner} ...')
    cc_process_data = [{'owner': owner}]
    MP4ansi(
        function=get_codecov_data,
        process_data=cc_process_data,
        config={
            'id_regex': r'^getting codecov information for (?P<value>.*) repos$',
            'progress_bar': {
                'total': r'^.* has a total of (?P<value>\d+) repos registered in codecov.io$',
                'count_regex': r'^retrieving codecov data for (?P<value>.*) repo$',
                'progress_message': 'Retrieval of codecov.io data complete'
            }
        }).execute()
    check_result(cc_process_data)
    write_file(cc_process_data, 'codecov')

    print(f'Retrieving jenkins data for {owner} ...')
    jn_process_data = [{'owner': owner}]
    MP4ansi(
        function=get_jenkins_data,
        process_data=jn_process_data,
        config={
            'id_regex': r'^getting jenkins information for (?P<value>.*) repos$',
            'progress_bar': {
                'total': r'^.* has a total of (?P<value>\d+) repos registered in jenkins$',
                'count_regex': r'^retrieving jenkins data for (?P<value>.*) repo$',
                'progress_message': 'Retrieval of jenkins data complete'
            }
        }).execute()
    check_result(jn_process_data)
    write_file(jn_process_data, 'jenkins')


if __name__ == '__main__':
    main('edgexfoundry')
