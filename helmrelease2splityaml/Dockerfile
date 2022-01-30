FROM python

ENV KUSTOMIZE_PLUGIN_HOME /root/.config/kustomize/plugin
COPY installer/ /installer
COPY artifact/helm /usr/local/bin

COPY helmrelease2splityaml/requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

ENTRYPOINT [ "/installer/template" ]