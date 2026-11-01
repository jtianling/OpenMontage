import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile


def fields(value, required, optional=()):
    if not isinstance(value, dict):
        raise ValueError('Expected a JSON object.')
    missing = set(required) - value.keys()
    unknown = value.keys() - set(required) - set(optional)
    if missing or unknown:
        raise ValueError(
            f'Invalid fields. Missing: {sorted(missing)}; unknown: {sorted(unknown)}'
        )


def number(value, name, *, minimum=0, positive=False, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a number.')
    if not math.isfinite(value) or value < minimum or (positive and value == 0):
        raise ValueError(f'{name} is out of range.')
    if integer and not isinstance(value, int):
        raise ValueError(f'{name} must be an integer.')
    return value


def local_path(root, value, *, exists=False):
    if not isinstance(value, str) or not value.strip() or '://' in value:
        raise ValueError('Expected a local file path.')
    base = Path(root).resolve(strict=True)
    path = (base / value).resolve(strict=exists)
    if not path.is_relative_to(base):
        raise ValueError(f'Path is outside the workspace: {value}')
    if any(part.startswith('.env') for part in path.relative_to(base).parts):
        raise ValueError('Environment files are not media inputs.')
    return path


def command(args, *, cwd=None, timeout=120):
    result = subprocess.run(
        [str(arg) for arg in args], cwd=cwd, capture_output=True,
        text=True, timeout=timeout, check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            f'{args[0]} exited with {result.returncode}: {detail[-12000:]}'
        )
    return result


def probe(path):
    result = command([
        'ffprobe', '-v', 'error', '-show_streams', '-show_format',
        '-of', 'json', path,
    ])
    return json.loads(result.stdout)


def duration(info):
    return number(float(info.get('format', {}).get('duration', 0)), 'duration')


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result = {**result, key: value}
    return result


def _invalid_constant(value):
    raise ValueError(f'Invalid JSON number: {value}')


def read_json(path):
    return json.loads(
        Path(path).read_text(encoding='utf-8'),
        object_pairs_hook=_unique_pairs, parse_constant=_invalid_constant,
    )


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, suffix='.json.tmp')
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as output:
            json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
            output.write('\n')
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
