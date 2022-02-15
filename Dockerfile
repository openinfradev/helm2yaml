FROM python

ENV KUSTOMIZE_PLUGIN_HOME /root/.config/kustomize/plugin
COPY helm2yaml/ /helm2yaml
COPY artifact/helm /usr/local/bin

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

ENTRYPOINT [ "/helm2yaml/helm2yaml" ]
