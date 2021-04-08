import json
import logging
from os import getenv

from rest3client import RESTclient 
from mp4ansi import MP4ansi

logger = logging.getLogger(__name__)

logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.CRITICAL)


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


def get_client():
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
    logger.debug(f'getting code coverage information for {owner} repos')
    # owner = owner.strip()
    data = []
    client = get_client()
    repos = client.get(f'/api/gh/{owner}?limit=100')['repos']
    logger.debug(f'{owner} has a total of {len(repos)} repos registered in codecov.io')
    for repo in repos:
        logger.debug(f"retrieving codecov data for {repo['name']} repo")
        settings = client.get(f"/api/gh/{owner}/{repo['name']}/settings")
        data.append({
            'repo': repo['name'],
            'coverage': repo['coverage'],
            'url': f"https://{client.hostname}/gh/{owner}/{repo['name']}/branch/master/graph/badge.svg?token={settings['repo']['image_token']}"
        })
    return data


def write_file(process_data):
    """ write data to json file
    """
    filename = 'codecov.json'
    with open(filename, 'w') as fp:
        json.dump(process_data, fp, indent=2)
        print(f'Codecov report written to {filename}')


def check_result(process_data):
    """ raise exception if any result in process data is exception
    """
    if any([isinstance(process.get('result'), Exception) for process in process_data]):
        raise Exception('one or more processes had errors - check logfile for more information')


if __name__ == '__main__':

    configure_logging()
    print(f'Retrieving codecov.io data ...')
    process_data = [
        {'owner': 'edgexfoundry'},
        {'owner': 'soda480'}
    ]
    mp4ansi = MP4ansi(
        function=get_codecov_data,
        process_data=process_data,
        config={
            'id_regex': r'^getting code coverage information for (?P<value>.*) repos$',
            'progress_bar': {
                'total': r'^.* has a total of (?P<value>\d+) repos registered in codecov.io$',
                'count_regex': r'^retrieving codecov data for (?P<value>.*) repo$',
                'progress_message': 'Retrieval of codecov.io data complete'
            }
        })
    mp4ansi.execute()
    check_result(process_data)
    write_file(process_data)
