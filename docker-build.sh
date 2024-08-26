set -ex

VER=v3.0.0
IMG=harbor.taco-cat.xyz/tks/decapod-render:${VER}

docker build . -f package/Dockerfile --network host --tag ${IMG}
# docker build ./package --network host --tag $IMG
sudo docker push $IMG
