from typing import Any, Dict, List

VAR_START = '$('
VAR_END = ')'
VAR_START_OFFSET = len(VAR_START)

def substitute_variables(v: str, var_dictionary: Dict[str, Any], prohibits: List[str]) -> Any:
  # print(f'v:{v}, type:{type(v)},Dict:{var_dictionary}')
  if not var_dictionary or VAR_START not in v:
    return check_prohibits(v, prohibits)

  # print(f'substitute_variables: input={v} ', end=" ")

  try:
    if v.startswith(VAR_START) and v.endswith(VAR_END) and v.count(VAR_START) == 1 and v.count(VAR_END) == 1:
      v = var_dictionary[v[VAR_START_OFFSET:-1].strip()]
    else:
      while VAR_START in v:
        sp = v.find(VAR_START)
        ep = v.find(VAR_END, sp)
        if ep < 0:
          raise ValueError(f'The value "{v}" has wrong format. Fix it and try again.')
        var = v[sp + VAR_START_OFFSET:ep].strip()
        v = v.replace(f'{VAR_START}{var}{VAR_END}', str(var_dictionary[var]))
  except KeyError:
    print(f'''
  ##################################################################################
  - The "{v}" have any undefined variables. Fix it and try again.
  - Dictionary : {var_dictionary}
  ##################################################################################
  ''')
    raise ValueError(f'The "{v}" have any undefined variables. Fix it and try again.')

  return check_prohibits(v, prohibits)

def check_prohibits(v: Any, prohibits: List[str]) -> Any:
  # 금지어 포함여부 체크 및 에러발생
  if prohibits and isinstance(v, str) and len(v) > 2 and any(v in w for w in prohibits):
    print(f'''
  ##################################################################################
  - You cannot use the string "{v}" as a value
  - Prohibit List : {prohibits}
  ##################################################################################
  ''')
    raise ValueError(f'You cannot use the string "{v}" as a value')
  return v

def traverse_leaf(values: Any, var_dictionary: Dict[str, Any], prohibits: List[str]) -> Any:
  if isinstance(values, dict):
    return {k: traverse_leaf(v, var_dictionary, prohibits) for k, v in values.items()}
  elif isinstance(values, list):
    return [traverse_leaf(v, var_dictionary, prohibits) for v in values]
  elif isinstance(values, str):
    return substitute_variables(values, var_dictionary, prohibits)
  return values

def yaml_override(target: Dict[str, Any], v:  Any) -> Dict[str, Any]:
  if not target:
    return v
  if isinstance(v, dict):
    for k, val in v.items():
      target[k] = yaml_override(target.get(k, {}), val)
    return target
  return v
