from tokenize import String
from typing import Dict, List, Optional, Any
import sys
import yaml
import os
import time
import copy
from .helm import Helm
from .repo import Repo, RepoType
from .parameter_aware_yamlmerge import yaml_override, traverse_leaf

class HelmDeployManager:
  class Config:
    DEFAULT_CHECK_INTERVAL = 10
    DEFAULT_KUBECONFIG = '~/.kube/config'

  def __init__(self, kubeconfig: str = Config.DEFAULT_KUBECONFIG, base: str = '', namespace: str = '', verbose: int = 0):
    self.kubeconfig = kubeconfig
    self.namespace = namespace
    self.verbose = verbose
    self.base: Dict[str, Helm] = self.__load_base(base)
    self.manifests = None #Dict[str, Helm]

  def get_repo(self, parsed: Dict[str, Any]) -> Repo:
    chart_spec = parsed['spec']['chart']
    if 'type' in chart_spec:
      repo_type = RepoType.GIT if chart_spec['type'] == 'git' else RepoType.HELMREPO
      return Repo(repo_type, chart_spec['repository'], chart_spec['name'], chart_spec['version'])
    elif 'git' in chart_spec:
      return Repo(RepoType.GIT, chart_spec['git'], chart_spec['path'], chart_spec['ref'])
    elif 'repository' in chart_spec:
      return Repo(RepoType.HELMREPO, chart_spec['repository'], chart_spec['name'], chart_spec['version'])
    else:
      raise ValueError(f'Wrong repo {parsed}')

  def __load_base(self, base: str) -> Dict[str, Helm]:
    manifests: Dict[str, Helm] = {}
    if os.path.isdir(base):
      for item in os.listdir(base):
        item_path = os.path.join(base, item)
        if os.path.isdir(item_path) or item == 'resources.yaml':
          manifests.update(self.__load_base(item_path))
    elif os.path.isfile(base):
      with open(base, 'r') as f:
        for parsed in yaml.safe_load_all(f):
          if parsed is None or 'spec' not in parsed:
            print(f'--- Warn: An invalid resource is given ---\n{parsed}\n--- Warn END ---')
            continue
          try:
            name = parsed['metadata']['name']
            if name in manifests:
              manifests[name].override = yaml_override(manifests[name].override, parsed['spec']['values'])
            else:
              manifests[name] = Helm(
                self.get_repo(parsed),
                parsed['spec']['releaseName'],
                parsed['spec']['targetNamespace'],
                parsed['spec']['values']
              )
          except (yaml.YAMLError, TypeError, KeyError) as exc:
            print(f'Error processing yaml: {exc}')
    else:
      print(f"Error: {base} is neither a file nor a directory")
    return manifests

  def template_yaml(self, gdir: str = 'cd') -> None:
    for chart, helm in self.manifests.items():
      if self.verbose > 0:
        print(f'(DEBUG) Generate resource yamls from {chart}\n{helm}')
      helm.to_separated_resources(gdir, self.verbose)

  def install_and_check_done(self, install: List[str], config: Dict[str, Any], skip_exist: bool = False) -> None:
    check_interval = config.get('metadata', {}).get('checkInterval', self.Config.DEFAULT_CHECK_INTERVAL)
    pending = [chart for chart in install if not (skip_exist and manifests[chart].get_status(self.kubeconfig) == 'deployed')]

    for chart in pending:
      print(f'{self.manifests[chart].override}')
      self.manifests[chart].install(kubeconfig=self.kubeconfig, target_namespace=self.namespace, verbose=self.verbose)

    while pending:
      pending = [chart for chart in pending if self.manifests[chart].get_status(self.kubeconfig) != 'deployed']
      if pending:
        print(f"\nWaiting for finish({check_interval} sec): {pending}")
        time.sleep(check_interval)

  def delete_and_check_done(self, delete: List[str], config: Dict[str, Any]) -> None:
    for chart in delete:
      if os.system(f'helm delete -n {self.namespace} {chart} --kubeconfig {self.kubeconfig}') != 0:
        print(f'FAILED!! {chart} ({self.namespace}) cannot be deleted due to the errors above.')
        sys.exit(1)


  def load_site(self, site: str, prohibits: List[str]):
    self.manifests: Dict[str, Helm] = {}
    with open(site, 'r') as f:
      for parsed in yaml.safe_load_all(f):
        self.preprocess_site(parsed)
        for chart in parsed['charts']:
          chart_name = chart.get('name')
          base_name = chart.get('base', chart_name)
          self.manifests[chart_name] = copy.deepcopy(self.base[base_name])
          self.manifests[chart_name].name = chart_name

          if 'override' in chart and chart['override']:
            self.manifests[chart_name].override = yaml_override(self.manifests[chart_name].override, chart['override'])
          if self.verbose:
            print(f'from ====> {self.manifests[chart_name].override}')
          self.manifests[chart_name].override = traverse_leaf(self.manifests[chart_name].override, parsed.get('global',{}), prohibits)
          if self.verbose:
            print(f'to ====> {self.manifests[chart_name].override}')

  def load_manifest(self, fd: Any, local_repository: Optional[str] = None) -> Dict[str, Helm]:
    manifests: Dict[str, Helm] = {}
    for parsed in yaml.safe_load_all(fd):
      if 'spec' not in parsed:
        print(f'--- Warn: An invalid resource is given ---\n{parsed}\n--- Warn END ---')
        continue
      repo = self.get_repo()
      if local_repository:
        repo.repo = local_repository

      manifests[parsed['metadata']['name']] = Helm(
        repo,
        parsed['spec']['releaseName'],
        parsed['spec']['targetNamespace'],
        parsed['spec']['values']
      )
    return manifests

  def preprocess_site(self, site: Dict[str, Any]) -> None:
    for chart in site['charts']:
      if 'override' in chart and chart['override'] is not None:
        overrides = {}
        for k, v in chart['override'].items():
          v = self.__split_keys(k.split('.'), v) if '.' in k else {k: v}
          overrides = yaml_override(overrides, v)
        chart['override'] = overrides

  def __split_keys(self, sp: List[str], value: Any) -> Dict[str, Any]:
    return {sp[0]: self.__split_keys(sp[1:], value)} if len(sp) > 1 else {sp[0]: value}

  def check_chart_repo(self, fd: Any, target_repo: str, except_list: List[str] = []) -> Dict[str, str]:
    invalid_dic = {}
    for parsed in yaml.safe_load_all(fd):
      repo = parsed.get('spec', {}).get('chart', {}).get('repository')
      if repo and not repo.startswith(target_repo) and repo not in except_list:
        name = parsed.get('metadata', {}).get('name')
        invalid_dic[name] = repo
        if self.verbose >= 1:
          print(f'{name} is defined with wrong repository: {repo}')
    return invalid_dic

  def check_image_repo(self, fd: Any, target_repo: str, except_list: List[str] = []) -> Dict[str, List[str]]:
    helm_dic = self.load_manifest(fd)
    if self.verbose > 0:
      print('(DEBUG) Loaded manifest:', helm_dic)
      for key, value in helm_dic.items():
        print(key, value)

    invalid_dic = {}
    for key, helm in helm_dic.items():
      invalid_images = [image_url for image_url in helm.get_image_list(self.verbose)
                if not image_url.startswith(target_repo) and image_url not in except_list]
      if invalid_images:
        invalid_dic[key] = invalid_images

    return invalid_dic

  def __str__(self):
    sl=[f'(DEBUG) Loaded base manifest: {self.base}']
    if self.verbose:
      for key, value in self.base.items():
        sl.append(f'(DEBUG) key: {key}, {value}')

    if self.verbose and self.manifests:
      sl.append(f'(DEBUG) Loaded base manifest: {self.manifests}')
      for key, value in self.manifests.items():
        sl.append(f'(DEBUG) key: {key}, {value}')
    return "\n".join(sl)