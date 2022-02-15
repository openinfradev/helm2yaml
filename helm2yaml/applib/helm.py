import yaml,os
from .repo import Repo, RepoType


class Helm:
  def __init__(self, repo, name, namespace, override):
    self.repo = repo
    self.name = name
    self.namespace = namespace
    self.override = override

  def checkPrerequisitions(self):
  #  stream = os.popen('kubectl get ns {}'
  #     .format(self.namespace))
  #   try:
  #     return stream.read().rsplit("STATUS:")[1].split()[0].strip()
  #   except IndexError as exc:
  #     return None
    return True

  def autoApplyPrerequisitions(self):
    return True

  def install(self, verbose=False, kubeconfig='~/.kube/config'):
    if self.getStatus() == None:
      self.repo.install(self.name, self.namespace, self.override, verbose, kubeconfig)
    else:
      print("{} in the namespace-{} already installed".format(self.name, self.namespace))

  def uninstall(self, verbose=False):
    print('helm delete -n {} {} | grep status'
      .format(self.namespace, self.name, verbose))

  def getStatus(self):
    stream = os.popen('helm status -n {} {}'
      .format(self.namespace, self.name))
    try:
      return stream.read().rsplit("STATUS:")[1].split()[0].strip()
    except IndexError as exc:
      return None

  def getStatusfull(self):
    os.system('helm status -n {} {}'
      .format(self.namespace, self.name))

  def template(self):
    self.repo.template(self.name, self.namespace, self.override)

  def toSeperatedResources(self, targetdir='/output', verbose=False):
    target = '{}/{}/'.format(targetdir, self.name)
    os.system('mkdir -p {}'.format(target))

    # For crd-only argoCD app, just copy crd files into output directory
    if self.name.endswith('-crds'):
      print('[Copy CRD yamls for {} from {}/{}]'.
      format(self.name, self.repo.repository(), self.repo.chart()))

      os.system('helm repo add monstarrepo {} | grep -i error'.format(self.repo.repository()))

      # Pull helm chart from chart repo
      if verbose > 0:
        print('(DEBUG) Pull helm chart: helm pull monstarrepo/{} --version {}'.format(self.repo.chart(), self.repo.version()))
      os.system('helm pull monstarrepo/{} --version {} | grep -i error'.format(self.repo.chart(), self.repo.version()))

      # Untar chart tarball file
      if verbose > 0:
        print('(DEBUG) Extract helm chart: tar xf {}-{}.tgz'.format(self.repo.chart(), self.repo.version()))
      os.system('tar xf {}-{}.tgz'.format(self.repo.chart(), self.repo.version()))

      # Copy crd files into output directory
      os.system('cp {}/crds/* {}/{}/'.format(self.repo.chart(), targetdir, self.name))
      # Cleanup
      os.system('rm -rf ./{}'.format(self.repo.chart()))
      os.system('helm repo rm monstarrepo | grep -i error')

    # For general argoCD app, render helm chart into single manifest yaml
    else:
      genfile=self.genTemplateFile(verbose)

      if verbose > 0:
        print('(DEBUG) seperate all-in-one yaml into each resource yaml')
      os.system('mv {} {}'.format(genfile, target))

      # Split into each k8s resource yaml
      splitcmd = "awk '{f=\""+target+"/_\" NR; print $0 > f}' RS='\n---\n' "+target+genfile
      os.system(splitcmd)
      os.system('rm {0}{1}'.format(target,genfile))

      # Rename yaml to "KIND_RESOURCENAME.yaml"
      if verbose > 0:
        print('(DEBUG) rename resource yaml files')
      for entry in os.scandir(target):
        refinedname =''
        with open(entry, 'r') as stream:
          try:
            parsed = yaml.safe_load(stream)
            refinedname = '{}_{}.yaml'.format(parsed['kind'],parsed['metadata']['name'])
          except yaml.YAMLError as exc:
            print('(WARN)',exc,":::", parsed)
          except TypeError as exc:
            if os.path.getsize(entry)>80:
              print('(WARN)',exc,":::", parsed)
              if verbose > 0:
                print("(DEBUG) Contents in the file :", entry.name)
                print(stream.readlines())
        if (refinedname!=''):
          os.rename(entry, target+refinedname)
        else: 
          os.remove(entry)

  def genTemplateFile(self, verbose=0):
    yaml.dump(self.override, open('vo', 'w') , default_flow_style=False)
    print('[Generate resource yamls for {} from {}/{} in {}]'.
      format(self.name, self.repo.repository(), self.repo.chart(), self.namespace))

    if self.repo.repotype == RepoType.HELMREPO:
      # prepare repository
      if verbose > 0:
        print('(DEBUG) Register repository:: helm repo add monstarrepo {}'
          .format(self.repo.repository()))
      os.system('helm repo add monstarrepo {} | grep -i error'.format(self.repo.repository()))

      # Generate template file
      if verbose > 0:
        print('(DEBUG) gernerate template file')

      os.system('helm template -n {0} {1} monstarrepo/{2} --version {3} -f vo > {1}.plain.yaml'
          .format(self.namespace, self.name, self.repo.chart(), self.repo.version()))

      # clean reposiotry
      os.system('helm repo rm monstarrepo | grep -i error')
    elif self.repo.repotype == RepoType.GIT:
      # prepare repository
      if verbose > 0:
        print('(DEBUG) git clone -b {0} {1} .temporary-clone'.format(self.repo.reference(), self.repo.getUrl()))
        os.system('git clone -b {0} {1} .temporary-clone'
          .format(self.repo.reference(), self.repo.getUrl()))
        if verbose > 2:
          print('(DEBUG) Cloned dir :')
          os.system('ls -al .temporary-clone')
      else:
        os.system('git clone -b {0} {1} .temporary-clone </dev/null 2>t; cat t | grep fatal; rm t'
          .format(self.repo.reference(), self.repo.getUrl()))

      os.system('helm dependency update .temporary-clone/{}'.format(self.repo.path()))
      # generate template file
      if verbose > 0:
        print('(DEBUG) gernerat a template file')
        print('(DEBUG) helm template -n {0} {1} .temporary-clone/{2} -f vo > {1}.plain.yaml'
          .format(self.namespace, self.name, self.repo.path()))
      
      os.system('helm template -n {0} {1} .temporary-clone/{2} -f vo > {1}.plain.yaml'
          .format(self.namespace, self.name, self.repo.path()))

      # clean reposiotry
      os.system('rm -rf .temporary-clone')
      # os.system('mv .temporary-clone '+name)
    else:
      print('(Error) Wrong repo type!')
      print('(Error) Name: '+self.name)
    return (self.name+'.plain.yaml')

  def dump(self, name, namespace, override, targetdir='/cd', verbose=False):
    yaml.dump(override, open('vo', 'w') , default_flow_style=False)
    print('[generate resource yamls {} from {} as {} in {}]'.
      format(self.chart(), self.repository(), name, namespace))

    if self.repotype == RepoType.HELMREPO:
      os.system('helm repo add monstarrepo {} | grep -i error'
        .format(self.repository()))
      os.system('mkdir -p {}/{}'.format(targetdir, name))

      if verbose > 0:
        print('(DEBUG) gernerate a template file')

      if name.endswith('-operator'):
        os.system('helm template -n {0} {1} monstarrepo/{2} --version {3} -f vo --include-crds  > {4}/{1}.plain.yaml'
          .format(namespace, name, self.chart(), self.version(), targetdir))
      else:
        os.system('helm template -n {0} {1} monstarrepo/{2} --version {3} -f vo > {4}/{1}.plain.yaml'
          .format(namespace, name, self.chart(), self.version(), targetdir))

      if verbose > 0:
        print('(DEBUG) seperate the template file')
      target = '{}/{}'.format(targetdir, name)
      splitcmd = "awk '{f=\""+target+"/_\" NR; print $0 > f}' RS='\n---\n' "+target+".plain.yaml"
      os.system(splitcmd)
      
      if verbose > 0:
        print('(DEBUG) rename resource yaml files')
      for entry in os.scandir(target):
        refinedname =''
        with open(entry, 'r') as stream:
          try:
            parsed = yaml.safe_load(stream)
            refinedname = '{}_{}.yaml'.format(parsed['kind'],parsed['metadata']['name'])
          except yaml.YAMLError as exc:
            print('(WARN)',exc,":::", parsed)
          except TypeError as exc:
            if os.path.getsize(entry)>80:
              print('(WARN)',exc,":::", parsed)
              if verbose > 0:
                print("(DEBUG) Contents in the file :", entry.name)
                print(stream.readlines())
        if (refinedname!=''):
          os.rename(entry, target+'/'+refinedname)
        else: 
          os.remove(entry)

      # os.system("""awk '{f="tmp/{0}/_" NR; print $0 > f}' RS='---' tmp/{0}.plain.yaml""".format(name))
      os.system("rm {}/{}.plain.yaml".format(targetdir, name))
      os.system('helm repo rm monstarrepo | grep -i error')
    elif self.repotype == RepoType.GIT:
      if verbose > 0:
        print('git clone -b {0} {1} temporary-clone'.format(self.versionOrReference, self.getUrl()))
      os.system('git clone -b {0} {1} temporary-clone </dev/null 2>t; cat t | grep fatal; rm t'
        .format(self.versionOrReference, self.getUrl()))

      os.system('rm -rf temporary-clone')
    else:
      print('(WARN) I CANNOT APPLY THIS. (email me - usnexp@gmail)')
      print('(WARN) '+self.getUrl())
      print('(WARN) '+self.repotype)
