from enum import Enum, unique
from typing import Optional


@unique
class RepoType(Enum):
  HELMREPO = 1
  GIT = 2
  LOCAL = 3

class Repo:
  def __init__(self, repotype: RepoType, repo: str, chart_or_path: str, version_or_reference: str):
    self.repotype = repotype
    self.repo = repo
    self.chart_or_path = chart_or_path
    self.version_or_reference = version_or_reference

  def __str__(self) -> str:
    return f'[REPO: {self.repotype} {self.repo}, {self.chart_or_path}, {self.version_or_reference}]'

  def version(self) -> Optional[str]:
      return self.version_or_reference if self.repotype == RepoType.HELMREPO else None

  def reference(self) -> Optional[str]:
    return self.version_or_reference if self.repotype == RepoType.GIT else None

  def chart(self) -> Optional[str]:
    return self.chart_or_path if self.repotype == RepoType.HELMREPO else None

  def path(self) -> Optional[str]:
    return self.chart_or_path if self.repotype == RepoType.GIT else None

  def repository(self) -> str:
    return self.repo

  def get_url(self) -> Optional[str]:
    if self.repotype == RepoType.GIT:
      if self.repo.startswith('git@'):
        url = self.repo.replace(':', '/').replace('git@', 'https://')
        return url if url.endswith('.git') else f"{url}.git"
      return self.repo
    return None