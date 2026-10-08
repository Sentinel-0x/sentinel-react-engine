"""
策略加载与校验。

设计上默认拒绝：profile 缺失、不存在，策略文件缺失或任何字段格式错误，
一律抛出 PolicyError，调用方必须拒绝执行。
profile 由运营方在代码/配置里选定，绝不从 Agent 或其生成的代码里读取。
"""
import json
import os
import re

from ast_guard import BANNED_MODULES

POLICY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policies.json")

VALID_NETWORKS = {"none", "whitelist_proxy"}
REQUIRED_KEYS = {"network", "image", "allowed_imports", "memory", "cpus", "timeout_seconds"}

_MEMORY_RE = re.compile(r"^[1-9][0-9]*[mg]$")
_IMAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*(:[A-Za-z0-9._-]+)?$")
MAX_CPUS = 4.0
MAX_TIMEOUT_SECONDS = 120


class PolicyError(Exception):
    """策略缺失、未知或格式错误。调用方必须拒绝执行。"""


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _validate_profile(name, profile):
    if not isinstance(profile, dict):
        raise PolicyError(f"profile '{name}' must be a JSON object")

    missing = REQUIRED_KEYS - set(profile)
    unknown = set(profile) - REQUIRED_KEYS
    if missing:
        raise PolicyError(f"profile '{name}' is missing keys: {sorted(missing)}")
    if unknown:
        raise PolicyError(f"profile '{name}' has unknown keys: {sorted(unknown)}")

    if profile["network"] not in VALID_NETWORKS:
        raise PolicyError(f"profile '{name}': network must be one of {sorted(VALID_NETWORKS)}")

    image = profile["image"]
    if not isinstance(image, str) or not _IMAGE_RE.match(image):
        raise PolicyError(f"profile '{name}': invalid image reference")

    imports = profile["allowed_imports"]
    if not isinstance(imports, list) or not all(isinstance(m, str) and m for m in imports):
        raise PolicyError(f"profile '{name}': allowed_imports must be a list of non-empty strings")
    granted_banned = sorted(set(imports) & set(BANNED_MODULES))
    if granted_banned:
        raise PolicyError(f"profile '{name}' grants modules the AST guard bans: {granted_banned}")

    memory = profile["memory"]
    if not isinstance(memory, str) or not _MEMORY_RE.match(memory):
        raise PolicyError(f"profile '{name}': memory must look like '512m' or '1g'")

    cpus = profile["cpus"]
    if not _is_number(cpus) or not (0 < cpus <= MAX_CPUS):
        raise PolicyError(f"profile '{name}': cpus must be a number in (0, {MAX_CPUS}]")

    timeout = profile["timeout_seconds"]
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not (0 < timeout <= MAX_TIMEOUT_SECONDS):
        raise PolicyError(f"profile '{name}': timeout_seconds must be an integer in (0, {MAX_TIMEOUT_SECONDS}]")


def load_policies(path=POLICY_PATH):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise PolicyError(f"policy file not found: {path}")
    except (OSError, json.JSONDecodeError) as e:
        raise PolicyError(f"policy file unreadable or invalid JSON: {e}")

    profiles = data.get("profiles") if isinstance(data, dict) else None
    if not isinstance(profiles, dict):
        raise PolicyError("policy file must contain an object under 'profiles'")

    # 任何一个 profile 格式错误，整个文件视为无效（宁可全部拒绝）
    for name, profile in profiles.items():
        _validate_profile(name, profile)
    return profiles


def get_profile(name, path=POLICY_PATH):
    if not isinstance(name, str) or not name:
        raise PolicyError("a profile name is required; there is no default profile")
    profiles = load_policies(path)
    if name not in profiles:
        raise PolicyError(f"unknown profile: {name!r}")
    return profiles[name]
