FROM python:3.6-alpine AS build-image

ENV PYTHONDONTWRITEBYTECODE 1

WORKDIR /prepbadge

COPY . /prepbadge/

RUN pip install rest3client
RUN pip install github3api
RUN pip install mp4ansi
RUN pip install mdutils
