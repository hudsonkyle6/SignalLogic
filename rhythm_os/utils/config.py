import os
import yaml

_CONFIG_CACHE = None


def load_config():
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    utils_dir = os.path.dirname(__file__)
    rhythm_os_dir = os.path.dirname(utils_dir)
    project_root = os.path.dirname(rhythm_os_dir)
    cfg_path = os.path.join(project_root, "config.yaml")

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # MULTI-PASS EXPANSION
    cfg = _expand_all(cfg)

    _CONFIG_CACHE = cfg
    return _CONFIG_CACHE



def _expand_all(cfg):
    """
    Expand all ${...} placeholders recursively until no placeholders remain.
    """
    round_count = 0
    while True:
        text = str(cfg)
        cfg = _expand_vars(cfg, cfg)
        # if no ${ in the entire structure, we're done
        if "${" not in str(cfg):
            return cfg
        round_count += 1
        if round_count > 10:
            # prevent infinite loops
            return cfg


def _expand_vars(node, root):
    """
    Recursively expand placeholders inside a nested YAML structure.
    """
    if isinstance(node, dict):
        return {k: _expand_vars(v, root) for k, v in node.items()}
    elif isinstance(node, list):
        return [_expand_vars(v, root) for v in node]
    elif isinstance(node, str):
        return _expand_string(node, root)
    return node


def _expand_string(value, root_cfg):
    """
    Expand ${a.b} inside a string, with support for chained references.
    """
    # Expand multiple placeholders in a single string
    while "${" in value:
        start = value.index("${") + 2
        end = value.index("}", start)
        key = value[start:end]

        # Walk into config structure to get replacement
        replacement = root_cfg
        for part in key.split("."):
            replacement = replacement[part]

        value = value.replace("${" + key + "}", replacement)

    return value



def _walk(cfg, dotted_key):
    parts = dotted_key.split(".")
    cur = cfg
    for p in parts:
        cur = cur[p]
    return cur


def get_path(key):
    cfg = load_config()
    return _walk(cfg, key)

