from applib.helm import Helm
from applib.repo import Repo, RepoType
import sys, yaml, os, time, getopt

def template_yaml(manifests, gdir='cd', verbose=False):
  for chart in manifests.keys():
    if verbose>0:
      print('(DEBUG) Generate resource yamls from {}'.format(chart))
    manifests[chart].toSeperatedResources(gdir, verbose)

def install_and_check_done(manifests, install, config, verbose=False, kubeconfig='~/.kube/config'):
  # os.system("helm install -n monstar {} monstarrepo/{} -f vo".format())
  try:
    cinterval=int(config['metadata']['checkInterval'])
  except KeyError:
    cinterval=10
  pending = []
  for chart in install:
    manifests[chart].install(verbose,kubeconfig)
    pending.append(chart)

  while True:
    successed = []
    for chart in pending:
      if manifests[chart].getStatus()=='deployed':
        successed.append(chart)

    for chart in successed:
      pending.remove(chart)

    print("\nWaiting for finish: ")
    print(pending)
    if not pending:
      break
    time.sleep(cinterval)
  return

def load_manifest(manifest):
  os.system("awk '{f=\"split_\" NR; print $0 > f}' RS='---' "+manifest)

  manifests = dict()
  for entry in os.scandir():
    if entry.name.startswith('split_'):
      with open(entry, 'r') as stream:
        try:
          parsed = yaml.safe_load(stream)
          if parsed['spec']['chart'].get('type')!=None:
            repotype = RepoType.HELMREPO
            if parsed['spec']['chart'].get('type')=='git':
              repotype = RepoType.GIT
            repo = Repo(
              repotype,
              parsed['spec']['chart']['repository'],
              parsed['spec']['chart']['name'],
              parsed['spec']['chart']['version'])
          elif parsed['spec']['chart'].get('git')!=None:
            repo = Repo(
              # repotype, repo, chartOrPath, versionOrReference):
              RepoType.GIT,
              parsed['spec']['chart']['git'],
              parsed['spec']['chart']['path'],
              parsed['spec']['chart']['ref'])
          elif parsed['spec']['chart'].get('repository')!=None:
            repo = Repo(
              # repotype, repo, chartOrPath, versionOrReference):
              RepoType.HELMREPO,
              parsed['spec']['chart']['repository'],
              parsed['spec']['chart']['name'],
              parsed['spec']['chart']['version'])
          else:
            print('Wrong repo {0}',parsed)

          # self, repo, name, namespace, override):
          manifests[parsed['metadata']['name']]=Helm( 
            repo,
            parsed['spec']['releaseName'],
            parsed['spec']['targetNamespace'],
            parsed['spec']['values'])
        except yaml.YAMLError as exc:
          print(exc)
        except TypeError as exc:
          print(exc)
  os.system("rm  split_*")

  return manifests