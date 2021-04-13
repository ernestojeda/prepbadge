# prepbadge

A CLI to create pull request workflows for updating edgeXfoundry repos with badges. The script will also create a preview of all EdgeXFoundry repo badges.

Queries all non-archived non-disabled repos for the `EdgeXFoundry` organization from GitHub. Queries codecov.io for badge and coverage data. Queries Jenkins for jobs and build information. Coalesces all the data and adds relevant bagesto repos and creates markdown file to preview the badges.

Execute github pull request workflows for the specified `--repos`.  The pull request work flow includes:
* fork repo
* clone repo
* update readme with badges
* commit change and sign
* push change to forked repo
* create pull request
* verify pull request
* update pull request with reviewers, labels, assignee and milestone


## `prepbadge`
```
usage: prepbadge [-h] [--org ORG] [--repos REPOS_REGEX]

A CLI to create pull request workflows for updating edgeXfoundry repos with
badges

optional arguments:
  -h, --help           show this help message and exit
  --org ORG            GitHub organization containing repos to process
  --repos REPOS_REGEX  a regex to match name of repos to include for
                       processing, if not specified then all non-archived,
                       non-disabled repos in org will be processed
```

Build the Docker image:
```bash
docker image build \
--build-arg http_proxy \
--build-arg https_proxy \
-t prepbadge:latest .
```

Run the Docker container:
```bash
docker container run \
--rm \
-it \
-e http_proxy \
-e https_proxy \
-v $PWD:/prepbadge \
prepbadge:latest /bin/sh
```

Set the required enviornment variables:
```bash
export GH_TOKEN_PSW=--github-token--
export JN_TOKEN_USR=--jenkins-username--
export JN_TOKEN_PSW=--jenkins-username-token--
export CC_TOKEN_PSW=--codecov.io-token--
```

Execute the Python script:
```bash
prepbadge --org edgexfoundry --repos 'ci-|cd-|edgex-global-pipelines|sample-service'
```

Script will generate the markdown containing the [badge preview](prepbadge.md)

![preview](https://raw.githubusercontent.com/soda480/prepbadge/master/docs/images/prepbadge.gif)