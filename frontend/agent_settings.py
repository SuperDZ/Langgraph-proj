"""Atomic per-agent draft edits; aliases isolate parameters from sibling roles."""
from copy import deepcopy
import re
from urllib.parse import urlparse
from agentloop.core.contracts.phase2 import RuntimeConfig, ModelProfile
from agentloop.core.runtime.configuration import effective_config

EDITABLE = {'token_budget','cost_budget','max_steps','concurrency'}


def edit_agent(current, body):
    config = deepcopy(current)
    role = body.get('role')
    if role not in config['roles']: raise ValueError('Agent 不存在')
    entry = config['roles'][role]
    agent = entry.setdefault('agent', {})
    if body.get('inherit') is True:
        for field in {*EDITABLE, 'primary', 'fallbacks'}: agent.pop(field, None)
        alias = 'agent-'+role
        layers = [config['platform'], *config['departments'].values(),
                  *(layer for r in config['roles'].values() for layer in (r.get('agent',{}),r.get('task',{})))]
        if not any(layer.get('primary') == alias or alias in (layer.get('fallbacks') or []) for layer in layers):
            config['models'].pop(alias,None)
            for layer in layers:
                policy = layer.get('policy')
                if policy: policy['models'] = [key for key in policy.get('models',[]) if key != alias]
    else:
        source = body.get('profile_id')
        if source not in config['models']: raise ValueError('模型模板不存在')
        profile = ModelProfile.model_validate(body.get('profile', {}))
        alias = 'agent-'+role
        config['models'][alias] = profile.model_dump(mode='json')
        for layer in [config['platform'], config['departments'][entry['department']], agent, entry.get('task',{})]:
            policy = layer.get('policy')
            if policy and source in policy.get('models', []) and alias not in policy['models']:
                policy['models'].append(alias)
        agent['primary'] = alias
        agent['fallbacks'] = body.get('fallbacks', [])
        for field in EDITABLE:
            value = body.get(field)
            if value is None: agent.pop(field, None)
            else: agent[field] = value
    validated = RuntimeConfig.model_validate(config)
    effective = {role:effective_config(validated,role).model_dump(mode='json') for role in validated.roles}
    return validated.model_dump(mode='json'), effective[role]


def validate_config(config):
    """Validate the complete draft before any credential or persistent state changes."""
    validated = RuntimeConfig.model_validate(config)
    effective = {role: effective_config(validated, role).model_dump(mode='json')
                 for role in validated.roles}
    return validated.model_dump(mode='json'), effective


def edit_global(current, body):
    """Edit platform defaults and limits without replacing model/role policies."""
    config = deepcopy(current)
    platform = config['platform']
    primary = body.get('primary')
    if primary not in config['models']:
        raise ValueError('默认模型不存在')
    if primary not in platform['policy']['models']:
        raise ValueError('默认模型未加入平台可用模型白名单')
    platform['primary'] = primary
    for field in ('token_budget', 'cost_budget', 'max_steps', 'concurrency'):
        value = body.get(field)
        if value is not None:
            platform[field] = value
    for field in ('run_token_budget', 'run_cost_budget'):
        value = body.get(field)
        if value is not None:
            config[field] = value
    validated, effective = validate_config(config)
    return validated, effective


def save_model(current, body):
    """Create/update a global model and grant only its required platform resources."""
    config = deepcopy(current)
    profile_id = body.get('profile_id', '')
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,40}', profile_id) or profile_id.startswith('agent-'):
        raise ValueError('模型标识需为 1–41 位小写字母、数字或连字符，且不能以 agent- 开头')
    exists = profile_id in config['models']
    if body.get('is_new') is True and exists:
        raise ValueError('模型标识已存在')
    if body.get('is_new') is not True and not exists:
        raise ValueError('要编辑的模型不存在')
    profile = ModelProfile.model_validate(body.get('profile', {}))
    config['models'][profile_id] = profile.model_dump(mode='json')
    policy = config['platform']['policy']
    for field, value in (('models', profile_id), ('secrets', profile.secret_ref),
                         ('network_hosts', urlparse(profile.endpoint).hostname)):
        if value not in policy[field]:
            policy[field].append(value)
    validated, effective = validate_config(config)
    return validated, effective


def delete_model(current, profile_id):
    """Delete only unused global profiles; run snapshots remain immutable."""
    config = deepcopy(current)
    if profile_id not in config['models'] or profile_id.startswith('agent-'):
        raise ValueError('全局模型不存在或不可删除')
    layers = [config['platform'], *config['departments'].values(),
              *(layer for role in config['roles'].values()
                for layer in (role.get('agent', {}), role.get('task', {})))]
    if any(layer.get('primary') == profile_id or profile_id in (layer.get('fallbacks') or [])
           for layer in layers):
        raise ValueError('模型仍被默认配置、角色或后备链使用，请先调整引用')
    config['models'].pop(profile_id)
    policy = config['platform']['policy']
    policy['models'] = [name for name in policy['models'] if name != profile_id]
    validated, effective = validate_config(config)
    return validated, effective


def register_credential(current, ref):
    """Register a standalone API Key reference so it can be saved before model creation."""
    if not isinstance(ref, str) or not re.fullmatch(r'env:[A-Z][A-Z0-9_]{0,80}_API_KEY', ref):
        raise ValueError('凭据名称必须为大写英文字母、数字和下划线，并以 _API_KEY 结尾')
    config = deepcopy(current)
    secrets = config['platform']['policy']['secrets']
    if ref not in secrets:
        secrets.append(ref)
    validated, effective = validate_config(config)
    return validated, effective


def select_run_models(current, selections):
    """Create a per-run draft; never mutate the shared global draft."""
    if not isinstance(selections, dict):
        raise ValueError('角色模型选择必须为对象')
    config = deepcopy(current)
    baseline = RuntimeConfig.model_validate(config)
    for role, profile_id in selections.items():
        if role not in config['roles']:
            raise ValueError('Agent 不存在：' + str(role))
        effective = effective_config(baseline, role)
        if profile_id not in effective.policy.models or profile_id not in config['models']:
            raise ValueError(f'{role} 无权使用模型 {profile_id}')
        agent = config['roles'][role].setdefault('agent', {})
        agent['primary'] = profile_id
        if agent.get('fallbacks'):
            agent['fallbacks'] = [name for name in agent['fallbacks'] if name != profile_id]
    validated, effective = validate_config(config)
    return validated, effective
