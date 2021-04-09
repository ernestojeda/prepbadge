# prepbadge

A Python script to create a preview of all EdgeXFoundry repo badges.  

Queries all non-archived non-disabled repos for organization from GitHub. Queries codecov.io for badge and coverage data. Queries Jenkins for jobs and build information. Coalesces all the data and creates markdown file to preview the badges.


## `prepbadge.py`

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
python prepbadge.py
```

Script will generate the markdown containing the [badge preview](prepbadge.md)

![preview](https://raw.githubusercontent.com/soda480/prepbadge/master/docs/images/prepbadge.gif)