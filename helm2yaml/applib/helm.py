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

  def toString(self):
    return('[HELM: {}, {}, {}, {}]'.format(    self.repo.toString(),
      self.name,
      self.namespace,
      self.override))

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

  def __imageName(self, fullname):
    if fullname.find('/') < 0:
      return fullname

    return fullname.rsplit('/', 1)[1]

  def __replaceImages(self, parsed, local_repository, verbose=0):
    if parsed is not None and 'spec' in parsed:
      spec = parsed['spec']
      if 'template' in spec:
        template = spec['template']
        if 'spec' in template:
          spec = template['spec']
          if 'containers' in spec:
            for container in spec['containers']:
              if verbose > 0:
                print("Case 1 - container: {}".format(container['image']))
              container['image']=local_repository+'/'+self.__imageName(container['image'])
              if verbose > 0:
                print('changed '+container['image'])
          if 'initContainers' in spec:
            for initcontainer in spec['initContainers']:
              if verbose > 0:
                print("Case 2 - Init container: {}".format(initcontainer['image']))
              initcontainer['image']=local_repository+'/'+self.__imageName(initcontainer['image'])
              if verbose > 0:
                print('changed '+initcontainer['image'])
      if 'containers' in spec:
        for container in spec['containers']:
          if verbose > 0:
            print("Case 3 - spec container: {}".format(container['image']))
          container['image']=local_repository+'/'+self.__imageName(container['image'])
          if verbose > 0:
            print('changed '+container['image'])
      if 'image' in spec:
        if verbose > 0:
          print("Case 4 - spec image: {}".format(spec['image']))
        spec['image']=local_repository+'/'+self.__imageName(spec['image'])
        if verbose > 0:
          print('changed '+spec['image'])

  def toSeperatedResources(self, targetdir='/output', verbose=False, local_repository=None):
    target = '{}/{}/'.format(targetdir, self.name)
    os.system('mkdir -p {}'.format(target))

    genfile=self.genTemplateFile(verbose)

    if verbose > 0:
      print('(DEBUG) seperate all-in-one yaml into each resource yaml')
    os.system('mv {} {}'.format(genfile, target))

    # Split into each k8s resource yaml
    splitcmd = "awk '{f=\""+target+"/_\" NR; print $0 > f}' RS='\n---\n' "+target+genfile
    os.system(splitcmd)
    os.system('rm {0}{1}'.format(target,genfile))

    isCrd=self.name.endswith('-crds')
    if isCrd:
      for entry in os.scandir(target):
        if entry.is_file():
          splitcmd = "awk '{f=\""+target+"/"+entry.name+"-\" NR; print $0 > f}' RS='' "+target+"/"+entry.name
          os.system(splitcmd)
          os.system('rm {0}{1}'.format(target,entry.name))

    # Rename yaml to "KIND_RESOURCENAME.yaml"
    if verbose > 0:
      print('(DEBUG) rename resource yaml files')
    for entry in os.scandir(target):
      refinedname =''
      with open(entry, 'r') as stream:
        try:
          parsed = yaml.safe_load(stream)
          refinedname = '{}_{}.yaml'.format(parsed['kind'],parsed['metadata']['name'])

          if(local_repository!=None):
            self.__replaceImages(parsed, local_repository)

        except yaml.YAMLError as exc:
          print('(WARN)',exc,":::", parsed)
        except TypeError as exc:
          if os.path.getsize(entry)>80:
            print('(WARN)',exc,":::", parsed)
            if verbose > 0:
              print("(DEBUG) Contents in the file :", entry.name)
              print(stream.readlines())
      if (refinedname!=''):
        with open(target+refinedname, 'w') as file:
          documents = yaml.dump(parsed, file)
        if os.path.exists(target+refinedname):
          os.remove(entry)
        else:
          os.rename(entry, target+'/'+refinedname)
      else:
        os.remove(entry)

  def get_image_list(self, verbose=False):

    # For crd-only argoCD app, just copy crd files into output directory
    if self.name.endswith('-crds'):
      print(f'[do nothing for {self.name}]')
      return []

    fd=open(self.genTemplateFile(verbose))
    image_list=[]

    for parsed in list(yaml.load_all(fd, Loader=yaml.loader.SafeLoader)):
      if parsed is not None and 'spec' in parsed:
        spec = parsed['spec']
        if 'template' in spec:
          template = spec['template']
          if 'spec' in template:
            spec = template['spec']
            if 'containers' in spec:
              for container in spec['containers']:
                if verbose > 0:
                  print("Case 1 - container: {}".format(container['image']))
                image_list.append(container['image'])
            if 'initContainers' in spec and spec.get('initContainers',False):
              for initcontainer in spec['initContainers']:
                if verbose > 0:
                  print("Case 2 - Init container: {}".format(initcontainer['image']))
                image_list.append(initcontainer['image'])
        if 'containers' in spec and spec.get('containers',False):
          for container in spec['containers']:
            if verbose > 0:
              print("Case 3 - spec container: {}".format(container['image']))
              image_list.append(container['image'])
        if 'image' in spec:
          if verbose > 0:
            print("Case 4 - spec image: {}".format(spec['image']))
          image_list.append(spec['image'])

    return image_list

  def genTemplateFile(self, verbose=0):
    # For crd-only argoCD app, using other cmd 'helm show crds'
    isCrd=self.name.endswith('-crds')

    yaml.dump(self.override, open('vo', 'w') , default_flow_style=False)
    print('[Generate resource yamls for {} from {}/{} in {}]'.
      format(self.name, self.repo.repository(), self.repo.chart(), self.namespace))

    if self.repo.repotype == RepoType.HELMREPO:
      if isCrd:
        helmcmd='helm show crds --repo {2} {3} --version {4} > {1}.plain.yaml'.format(self.namespace, self.name, self.repo.repository(), self.repo.chart(), self.repo.version())
      else:
        helmcmd='helm template -n {0} {1} --repo {2} {3} --version {4} -f vo > {1}.plain.yaml'.format(self.namespace, self.name, self.repo.repository(), self.repo.chart(), self.repo.version())
      # Generate template file
      if verbose > 0:
        print('(DEBUG) gernerate template file')
        print(self.toString())
        print(helmcmd)

      os.system(helmcmd)

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
        os.system('helm template -n {0} {1} .temporary-clone/{2} -f vo  > {1}.plain.yaml (or show crds)'
            .format(self.namespace, self.name, self.repo.path()))

      if isCrd:
        helmcmd='helm show crds .temporary-clone/{2} > {1}.plain.yaml'.format(self.namespace, self.name, self.repo.path())
      else:
        helmcmd='helm template -n {0} {1} .temporary-clone/{2} -f vo > {1}.plain.yaml'.format(self.namespace, self.name, self.repo.path())
      os.system(helmcmd)

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
      os.system('mkdir -p {}/{}'.format(targetdir, name))

      if verbose > 0:
        print('(DEBUG) gernerate a template file')

      if name.endswith('-operator'):
        os.system('helm template -n {0} {1} --repo {2} {3} --version {4} -f vo --include-crds  > {5}/{1}.plain.yaml'
          .format(namespace, name, self.repo.repository(), self.chart(), self.version(), targetdir))
      else:
        os.system('helm template -n {0} {1} --repo {2} {3} --version {4} -f vo > {5}/{1}.plain.yaml'
          .format(namespace, name, self.repo.repository(), self.chart(), self.version(), targetdir))

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
