import re
import base64
import logging
import subprocess
from time import sleep
from datetime import datetime
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)


class ForkExists(Exception):
    """ Raise when fork already exists
    """
    pass


class PullRequestVerificationFailure(Exception):
    """ Raise when pull request verification fails
    """
    pass


class NotFound(Exception):
    """ Raise when something is expected but not found
    """
    pass


def fork_exists(client, owner_repo, user):
    """ return True if fork for owner_repo exists
    """
    try:
        repo = owner_repo.split('/')[-1]
        response = client.get(f'/repos/{user}/{repo}')
        if response['fork'] and response['source']['full_name'] == owner_repo:
            return True
        return False

    except HTTPError:
        return False


def create_fork(client, owner_repo, user, sleep_time=None):
    """ create fork for repo
    """
    logger.debug(f'creating fork for {owner_repo}')
    if fork_exists(client, owner_repo, user):
        raise ForkExists(f'a fork for {owner_repo} already exists for {user}')

    if not sleep_time:
        sleep_time = 5

    response = client.post(f'/repos/{owner_repo}/forks')
    url = response['url'].replace(f'https://{client.hostname}', '')
    while True:
        try:
            client.get(url)
            logger.debug(f'fork for {owner_repo} has been created')
            break

        except HTTPError:
            logger.debug(f'fork for {owner_repo} is not yet ready')
            sleep(sleep_time)


def create_pull_request(client, owner_repo, user):
    """ create pull request
    """
    logger.debug(f'creating pull request for {owner_repo}')
    response = client.post(
        f'/repos/{owner_repo}/pulls',
        json={
            'title': 'this is a test - ignore',
            'body': 'created via automation. this is a test - ignore',
            'draft': True,
            'base': 'master',
            'head': f'{user}:master'
        })
    return response['number']


def verify_pull_request(client, owner_repo, pull_number):
    """ verify pull request
    """
    logger.debug(f'verifying {owner_repo} pull request {pull_number}')
    response = client.get(f'/repos/{owner_repo}/pulls/{pull_number}/files')
    if len(response) == 1:
        if response[0]['filename'] == 'README.md':
            logger.debug(f'pull request {pull_number} has been verified')
        else:
            raise PullRequestVerificationFailure(f'{owner_repo} pull request for {pull_number} filename verification failure')
    else:
        raise PullRequestVerificationFailure(f'{owner_repo} pull request for {pull_number} files verification failure')


def update_pull_request(client, owner_repo, pull_number, reviewers):
    """ add reviewers to pull request
    """
    logger.debug(f'adding reviewers to {owner_repo} pull request {pull_number}')
    client.post(
        f'/repos/{owner_repo}/pulls/{pull_number}/requested_reviewers',
        json={
            'reviewers': reviewers
        })


def create_commit2(client, user_repo, badges):
    """ create commit for update readme change
    """
    try:
        # get the current branch
        logger.debug(f'getting current branch for {user_repo}')
        current_branch = client.get(f'/repos/{user_repo}/branches/master')
        tree_sha = current_branch['commit']['commit']['tree']['sha']

        # get the current tree
        current_tree = client.get(f'/repos/{user_repo}/git/trees/{tree_sha}')

        # ensure we are always working with the full tree
        if current_tree['truncated']:
            raise Exception('the current tree retrieved was truncated')

        # update reference in current tree
        update_readme(client, current_tree['tree'], user_repo, badges)

        # create new tree from current tree with updated blob
        logger.debug(f'creating an updated tree for {user_repo}')
        updated_tree = client.post(
            f'/repos/{user_repo}/git/trees?recursive=1',
            json={'tree': current_tree['tree']})

        # create new commit for the updated tree
        logger.debug(f'creating new commit for {user_repo}')
        commit_payload = {
            'message': 'Add badges to README',
            'tree': updated_tree['sha'],
            'parents': [current_branch['commit']['sha']],
            'author': {
                'name': 'Emilio Reyes',
                'email': 'soda480@gmail.com'
            },
            'committer': {
                'name': 'Emilio Reyes',
                'email': 'soda480@gmail.com'
            }
        }
        add_signature(commit_payload, user_repo)
        new_commit = client.post(f'/repos/{user_repo}/git/commits', json=commit_payload)

        # point branch to new commit
        logger.debug(f'pointing {user_repo} master branch to new commit')
        client.patch(
            f'/repos/{user_repo}/git/refs/heads/master',
            json={'sha': new_commit['sha']})

    except Exception as exception:
        raise Exception(f'unable to create commit for {user_repo} branch master: {exception}')


def find(items, key, value):
    """ return index, item tuple of item with key and value in list of dicts
    """
    for index, item in enumerate(items):
        if item[key] == value:
            return index, item
    raise NotFound(f'no item with {key} {value} in items')


def get_heading_index(first_line, repo):
    """ return index of repo heading from list of contents
    """
    found_index = -1
    regex = rf'^#\s*{repo}$'
    if re.match(regex, first_line):
        found_index = 0
    return found_index


def update_readme2(client, current_tree, user_repo, badges):
    """ update readme with badges
    """
    logger.debug('updating README.md with badge info')

    index_blob, item = find(current_tree, 'path', 'README.md')

    # get blob associated with readme file
    logger.debug('getting blob for readme')
    endpoint_get_blob = item['url'].replace(f'https://{client.hostname}', '')
    current_blob = client.get(endpoint_get_blob)
    
    # get contents of readme file
    content = base64.b64decode(current_blob['content']).decode()
    contents = content.split('\n')
    
    # update readme contents
    logger.debug('updating readme contents with badges')
    repo = user_repo.split('/')[-1]
    # get index of repo heading
    index_heading = get_heading_index(contents[0], repo)
    contents.insert(index_heading + 1, badges)

    # create blob containing updated readme contents
    logger.debug('creating blob containing updated readme')
    updated_content = '\n'.join(contents)
    encoded_content = base64.b64encode(bytes(updated_content, 'utf-8'))
    create_blob = client.post(
        f'/repos/{user_repo}/git/blobs',
        json={
            'content': encoded_content.decode('utf-8'),
            'encoding': 'base64'
        })

    # update current tree with new blob containing updated readme
    logger.debug('updating current tree with new blob containing updated readme')
    endpoint_blob = create_blob['url'].replace(f'https://{client.hostname}', '')
    new_blob = client.get(endpoint_blob)
    current_tree[index_blob]['url'] = new_blob['url']
    current_tree[index_blob]['size'] = new_blob['size']
    current_tree[index_blob]['sha'] = new_blob['sha']


def add_signature(payload, user_repo):
    """ add pgp signature of payload to payload
    """
    logger.debug('adding signature to payload')
    repo = user_repo.split('/')[1]
    now = datetime.now()
    payload_date = now.isoformat('T', 'seconds') + 'Z'
    write_date = str(now.timestamp()).split('.')[0] + ' -0700'
    with open(f'commit-{repo}', 'w') as outfile:
        outfile.write(f"tree {payload['tree']}\n")
        outfile.write(f"parent {payload['parents'][0]}\n")
        outfile.write(f"author {payload['author']['name']} <{payload['author']['email']}> {write_date}\n")
        outfile.write(f"committer {payload['committer']['name']} <{payload['committer']['email']}> {write_date}\n")
        outfile.write(f"{payload['message']}")
    command = f'gpg --clear-sign --digest-algo SHA1 --armor commit-{repo}'
    logger.debug(f'executing command: {command}')
    subprocess.call(command.split())
    with open(f'commit-{repo}.asc', 'r') as infile:
        content = infile.read()
    contents = content.split('\n')
    index = contents.index('-----BEGIN PGP SIGNATURE-----')
    signature = '\n'.join(contents[index:])
    payload['signature'] = signature
    payload['author']['date'] = payload_date
    payload['committer']['date'] = payload_date
    logger.debug(f'signature: {signature}')


def update_readme(badges, filename):
    """ update readme with badges
    """
    logger.debug(f'updating {filename} with badges')
    with open(filename, 'r') as infile:
        contents = infile.readlines()
    index = get_heading_index(contents[0], repo)
    contents.insert(index + 1, badges)
    with open(filename, 'w') as outfile:
        outfile.writelines(contents)


def create_commit(repo, repo_url, badges):
    """ execute steps to clone update commit and push changes on repo
    """
    working_dir = '/prebadge/github.com'
    command = f'mkdir -p {working_dir}'
    subprocess.run(command)

    command = f'git clone {repo_url}'
    logger.debug(f'{command} [{working_dir}]')
    subprocess.run(command, cwd=working_dir)

    working_dir = f'{working_dir}/{repo}'
    update_readme(badges, f'{working_dir}/README.md')

    command = f"git commit -am 'Add badges to readme' -s"
    logger.debug(f'{command} [{working_dir}]')
    subprocess.run(command, cwd=working_dir)

    command = 'git push origin master'
    logger.debug(f'{command} [{workingdir}]')
    subprocess.run(command, cwd=working_dir)
