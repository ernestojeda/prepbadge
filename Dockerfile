FROM python:3.6-alpine AS build-image

ENV PYTHONDONTWRITEBYTECODE 1

WORKDIR /codecov

COPY . /codecov/

RUN pip install rest3client
RUN pip install github3api
RUN pip install mp4ansi
