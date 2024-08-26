import os
import sys
from pickle import FALSE
from typing import List, Optional, Dict, Any
import yaml
from .repo import Repo, RepoType

class Helm:
  def __init__(self, repo: Repo, name: str, namespace: str, override: Dict[str, Any]):
    self.repo = repo
    self.name = name
    self.namespace = namespace
    self.override = override

  def __str__(self) -> str:
    return f'[HELM: {self.repo}, {self.name}, {self.namespace}, {self.override}]'

  def install(self, kubeconfig: str = '~/.kube/config', verbose: bool = False, target_namespace: str = '') -> str:
    self._dump_override()
    self.namespace = target_namespace or self.namespace
    print(
      f'[install {self.repo.chart()} from {self.repo.repository()} as {self.name} in {self.namespace} using {kubeconfig}]')

    if self.repo.repotype == RepoType.HELMREPO:
      self._install_from_helm_repo(kubeconfig)
    elif self.repo.repotype == RepoType.GIT:
      self._install_git_repo(kubeconfig, verbose)
    else:
      print(f'(WARN) Unsupported repo type: {self.repo.repotype}')

    os.system(f'rm {self.name}.vo')

    return f'{self.name}.plain.yaml'

  def _dump_override(self):
    with open(f'{self.name}.vo', 'w') as f:
      yaml.dump(self.override, f, default_flow_style=False)

  def _install_from_helm_repo(self, kubeconfig: str):
    cmd = f'helm upgrade --install -n {self.namespace} {self.name} --repo {self.repo.repository()} {self.repo.chart()} --version {self.repo.version()} -f {self.name}.vo --kubeconfig {kubeconfig} --create-namespace'
    if os.system(cmd):
      print(f'FAILED!! {self.name} cannot be installed due to the errors above.')
      print(f'- overrides: {self.override}')
      sys.exit(-1)

  def _install_git_repo(self, kubeconfig: str, verbose: bool):
    self._clone_repo_and_dependency_update(verbose)
    cmd = f'helm upgrade --install -n {self.namespace} {self.name} .temporary-clone/{self.repo.chartOrPath} -f {self.name}.vo --kubeconfig {kubeconfig}'
    if verbose > 0:
      print(f'(DEBUG) install helm:{cmd}')
    os.system(cmd)
    os.system('rm -rf .temporary-clone')

  def _clone_repo_and_dependency_update(self, verbose: bool):
    cmd = f'git clone -b {self.repo.versionOrReference} {self.repo} .temporary-clone'
    if verbose:
      print(f'(DEBUG) {cmd}')
      os.system(cmd)
    else:
      os.system(f'{cmd} </dev/null 2>t; cat t | grep fatal; rm t')
    os.system(f'helm dependency update .temporary-clone/{self.repo.chartOrPath}')

  def uninstall(self, verbose: bool = False):
    cmd = f'helm delete -n {self.namespace} {self.name} | grep status'
    if verbose:
      print(cmd)
    os.system(cmd)

  def get_status(self, kubeconfig: str = '~/.kube/config') -> Optional[str]:
    stream = os.popen(f'helm status -n {self.namespace} {self.name} --kubeconfig {kubeconfig}')
    try:
      return stream.read().rsplit("STATUS:")[1].split()[0].strip()
    except IndexError:
      return None

  def get_status_full(self):
    os.system(f'helm status -n {self.namespace} {self.name}')

  # local_repository 가 정의되면 생성되는 자원에서 이미지 주소의 repository를 주어진 것으로 무조건 변경함
  def to_separated_resources(self, target_base_dir: str = '/output', verbose: bool = False,
                 local_repository: Optional[str] = None):
    target = f'{target_base_dir}/{self.name}/'
    os.makedirs(target, exist_ok=True, mode=0o755)

    if self.name.endswith('-crds'): # very conner case.......
      self._handle_crd_only_connercase_solver(target_base_dir, verbose)
    else:
      self._handle_general_app(target, verbose, local_repository)

  def _handle_crd_only_connercase_solver(self, target_base_dir: str, verbose: bool):
    # helm template을 통해 생성되는 자원에서 crd가 포함되지 않으므로 수동으로 해주는 프로세스가 필요.
    print(f'[Copy CRD yamls for {self.name} from {self.repo.repository()}/{self.repo.chart()}]')

    # self._pull_helm_chart(verbose)
    cmd = f'helm pull --repo {self.repo.repository()} {self.repo.chart()} --version {self.repo.version()} | grep -i error'
    if verbose:
      print(f'(DEBUG) Pull helm chart: {cmd}')
    os.system(cmd)

    # self._extract_helm_chart(verbose)
    cmd = f'tar xf {self.repo.chart()}-{self.repo.version()}.tgz'
    if verbose:
      print(f'(DEBUG) Extract helm chart: {cmd}')
    os.system(cmd)

    os.system(f'cp {self.repo.chart()}/crds/* {target_base_dir}/{self.name}/')
    os.system(f'rm -rf ./{self.repo.chart()}')

  def _handle_general_app(self, target: str, verbose: bool, local_repository: Optional[str]):
    genfile = self.gen_template_file(verbose)
    if genfile == None:
      print(f'!!!!! Error to generate template using {self}')
    cmd = f'mv {genfile} {target}{genfile}'
    os.system(cmd)
    # os.rename(genfile, f'{target}{genfile}')
    if verbose:
      print(f'(DEBUG) splite {genfile}')
    self._split_yaml(target, f'{target}{genfile}')
    if verbose:
      print(f'(DEBUG) rename {genfile}')
    self._rename_yaml_files(target, verbose, local_repository)

  def _split_yaml(self, target: str, genfile: str):
    cmd = f"awk '{{f=\"{target}_\" NR; print $0 > f}}' RS='\\n---\\n' {genfile}"
    os.system(cmd)
    os.remove(f'{genfile}')

  def _rename_yaml_files(self, target: str, verbose: bool, local_repository: Optional[str]):
    for entry in os.scandir(target):
      self._process_yaml_file(entry, target, verbose, local_repository)

  # rename upon metadata
  def _process_yaml_file(self, entry, target: str, verbose: bool, local_repository: Optional[str]):
    try:
      with open(entry, 'r') as stream:
        meta = self._read_yaml_until_spec(stream)
        parsed = next(yaml.safe_load_all(meta), None)
        stream.close()
        if parsed is None:
          os.remove(entry)
          return
        refined_name = f'{parsed["kind"]}_{parsed["metadata"]["name"]}.yaml'
        cmd=f'mv {entry.path} {target}{refined_name}'
        os.system(cmd)
        # if local_repository:
        #   self._replace_images(parsed, local_repository, verbose)
        # with open(f'{target}{refined_name}', 'w') as file:
        #   yaml.dump(parsed, file)
      # os.remove(entry)
    except (yaml.YAMLError, TypeError, KeyError) as exc:
      if os.path.getsize(entry) > 80:
        print(f'(WARN) {exc} ::: {parsed}')
        if verbose:
          print(f'(DEBUG) Contents in the file : {entry.name}')
          with open(entry, 'r') as stream:
            print(stream.read())
      else:
        os.remove(entry)

  def _read_yaml_until_spec(self, file):
    buffer = []
    for line in file:
      if line.strip() == 'spec:':
        break
      buffer.append(line)
    return ''.join(buffer)

  def _replace_images(self, parsed: Dict[str, Any], local_repository: str, verbose: int = 0):
    spec = parsed.get('spec', {})
    template = spec.get('template', {})
    containers = template.get('spec', {}).get('containers', []) + template.get('spec', {}).get('initContainers',
                []) + spec.get('containers', [])

    for container in containers:
      if 'image' in container:
        old_image = container['image']
        container['image'] = f"{local_repository}/{self._image_name(old_image)}"
        if verbose > 0:
          print(f'changed {old_image} to {container["image"]}')

    if 'image' in spec:
      old_image = spec['image']
      spec['image'] = f"{local_repository}/{self._image_name(old_image)}"
      if verbose > 0:
        print(f'changed {old_image} to {spec["image"]}')

  @staticmethod
  def _image_name(fullname: str) -> str:
    return fullname.rsplit('/', 1)[-1] if '/' in fullname else fullname

  def get_image_list(self, verbose: bool = False) -> List[str]:
    if self.name.endswith('-crds'):
      print(f'[do nothing for {self.name}]')
      return []

    image_list = []
    with open(self.gen_template_file(verbose)) as fd:
      for parsed in yaml.safe_load_all(fd):
        image_list.extend(self._extract_images(parsed, verbose))
    return image_list

  def _extract_images(self, parsed: Dict[str, Any], verbose: bool) -> List[str]:
    images = []
    if parsed and 'spec' in parsed:
      spec = parsed['spec']
      template = spec.get('template', {})
      template_spec = template.get('spec', {})

      for container in template_spec.get('containers', []) + template_spec.get('initContainers', []) + spec.get(
          'containers', []):
        if 'image' in container:
          images.append(container['image'])
          if verbose:
            print(f"Container image: {container['image']}")

      if 'image' in spec:
        images.append(spec['image'])
        if verbose:
          print(f"Spec image: {spec['image']}")

    return images

  def gen_template_file(self, verbose: int = 0) -> str:
    self._dump_override()
    print(
      f'[Generate resource yamls for {self.name} from {self.repo.repository()}/{self.repo.chart()} in {self.namespace}]')

    if self.repo.repotype == RepoType.HELMREPO:
      return self._gen_helm_template(verbose)
    elif self.repo.repotype == RepoType.GIT:
      return self._gen_git_template(verbose)
    else:
      raise ValueError(f'!!!!! Error: Wrong repo type for {self.name}')

  def _gen_helm_template(self, verbose: bool=False) -> str:
    cmd = f'helm pull --repo {self.repo.repository()} {self.repo.chart()} --version {self.repo.version()};  helm template -n {self.namespace} {self.name} {self.repo.chart()}-{self.repo.version()}.tgz -f {self.name}.vo  --include-crds > {self.name}.plain.yaml; rm {self.repo.chart()}-{self.repo.version()}.tgz'
    # if verbose:
    #   print(f'(DEBUG) generate template file\n{self}\n{cmd}')
    os.system(cmd)

    return f'{self.name}.plain.yaml'

  def _gen_git_template(self, verbose: bool=FALSE) -> str:
    self._clone_repo_and_dependency_update(verbose)
    cmd = f'helm template -n {self.namespace} {self.name} .temporary-clone/{self.repo.path()} -f {self.name}.vo --include-crds > {self.name}.plain.yaml'
    # if verbose > 0:
    #   print(f'(DEBUG) generate template file\n{cmd}')
    os.system(cmd)
    os.system('rm -rf .temporary-clone')
    return f'{self.name}.plain.yaml'
