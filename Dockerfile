FROM harbor.taco-cat.xyz/tks/decapod-kustomize:v2.0.1 AS gobuilder
LABEL AUTHOR sungil(usnexp@gmail.com)

FROM python:3.10.5-alpine3.16 AS builder
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

FROM python:3.10.5-alpine3.16
LABEL AUTHOR sungil(usnexp@gmail.com)

ENV PATH /root/helm2yaml:$PATH

USER root
RUN mkdir -p /root/.config/kustomize/plugin/openinfradev.github.com/v1/helmvaluestransformer
RUN apk add --no-cache bash git curl
COPY --from=gobuilder /root/.config/kustomize/plugin/openinfradev.github.com/v1/helmvaluestransformer/HelmValuesTransformer.so /root/.config/kustomize/plugin/openinfradev.github.com/v1/helmvaluestransformer/
COPY --from=gobuilder /usr/local/bin/kustomize /usr/local/bin/kustomize

COPY --from=builder /usr/local/bin/helm /usr/local/bin/helm
COPY --from=builder /usr/local/bin/gh /usr/local/bin/gh

WORKDIR /root
COPY . ./
RUN pip install -r requirements.txt

CMD [ "/root/helm2yaml/helm2yaml" ]
# sktcloud/decapod-render:v3.0.0 (23.8.14)
# - support oci protocol for a helm repository
# - generate CRDs using helm cli
# Build CLI: docker build --network host -t siim/helm2yaml:v3.0.0 .
