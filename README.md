# helm2yaml
Create k8s resources files based on the decapod manifest file derived from [helm-release](https://fluxcd.io/flux/components/helm/helmreleases/).

## Simple Usage
```
> git clone https://github.com/openinfradev/helm2yaml.git
> cd helm2yaml
> pip install -r requirements.txt
> helm2yaml/helm2yaml -m lma_manifest.yaml -t -o gen
```

## Options
- -m [decapod-manifest-file] # a yaml file derived from helm-relese
- -t # make template
- -o [output-directory] # target to generate resource files
