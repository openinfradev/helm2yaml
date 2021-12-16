FROM python:3.11.0a1-slim-bullseye

ENV KUSTOMIZE_PLUGIN_HOME /root/.config/kustomize/plugin
COPY Docker/src /
COPY Docker/helm /usr/local/bin

COPY Docker/requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

ENTRYPOINT [ "/template" ]