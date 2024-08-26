FROM python:3.12.4-alpine

LABEL AUTHOR sungil(usnexp@gmail.com)

ENV HELM_VER v3.9.0
ENV GH_VER 2.11.3

RUN apk update && apk add curl
RUN curl -sL -o helm.tar.gz  https://get.helm.sh/helm-${HELM_VER}-linux-amd64.tar.gz && \
    tar xf helm.tar.gz && \
    mv linux-amd64/helm /usr/local/bin/helm

RUN curl -sL -o gh.tar.gz https://github.com/cli/cli/releases/download/v${GH_VER}/gh_${GH_VER}_linux_amd64.tar.gz && \
    tar xf gh.tar.gz && \
    mv gh_2.11.3_linux_amd64/bin/gh /usr/local/bin/gh

COPY helm2yaml /helm2yaml

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

ENTRYPOINT [ "/helm2yaml/template" ]
# sktcloud/decapod-render:v3.0.0 (23.8.14)
# - support oci protocol for a helm repository
# - generate CRDs using helm cli
# Build CLI: docker build --network host -t siim/helm2yaml:v3.0.0 .
