FROM python:3.10-slim-buster
COPY . /src
WORKDIR /src
RUN pip install .
