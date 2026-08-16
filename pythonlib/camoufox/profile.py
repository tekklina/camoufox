import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import orjson


PROFILE_FINGERPRINT_FILE = '.camoufox-fingerprint.json'
PROFILE_FINGERPRINT_SCHEMA = 1
REQUIRED_FINGERPRINT_KEYS = {
    'navigator.userAgent',
    'navigator.hardwareConcurrency',
    'fonts:spacing_seed',
    'audio:seed',
    'canvas:seed',
}


def profile_fingerprint_path(user_data_dir: Union[str, Path]) -> Path:
    return Path(user_data_dir) / PROFILE_FINGERPRINT_FILE


def load_profile_fingerprint(
    user_data_dir: Union[str, Path],
) -> Optional[Dict[str, Any]]:
    path = profile_fingerprint_path(user_data_dir)
    if not path.exists():
        return None

    try:
        state = orjson.loads(path.read_bytes())
    except (OSError, orjson.JSONDecodeError) as exc:
        raise ValueError(f'Unable to read Camoufox fingerprint state at {path}') from exc

    if not isinstance(state, dict) or state.get('schema_version') != PROFILE_FINGERPRINT_SCHEMA:
        raise ValueError(f'Unsupported Camoufox fingerprint state at {path}')

    config = state.get('config')
    if not isinstance(config, dict):
        raise ValueError(f'Invalid Camoufox fingerprint state at {path}')
    missing = REQUIRED_FINGERPRINT_KEYS.difference(config)
    if missing:
        raise ValueError(
            f'Incomplete Camoufox fingerprint state at {path}: missing {sorted(missing)}'
        )

    return config


def save_profile_fingerprint(
    user_data_dir: Union[str, Path],
    config: Dict[str, Any],
) -> Path:
    path = profile_fingerprint_path(user_data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f'{path.name}.tmp-{os.getpid()}')
    state = {
        'schema_version': PROFILE_FINGERPRINT_SCHEMA,
        'config': config,
    }

    try:
        temporary_path.write_bytes(
            orjson.dumps(state, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS)
        )
        try:
            temporary_path.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass

    return path
