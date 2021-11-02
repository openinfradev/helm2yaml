FROM python

ENV KUSTOMIZE_PLUGIN_HOME /root/.config/kustomize/plugin
COPY Docker/src /
COPY Docker/helm /usr/local/bin

COPY Docker/requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

ENTRYPOINT [ "/template" ]