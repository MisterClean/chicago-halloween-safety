#!/usr/bin/env python3
"""Check the exact Git index before publishing this source-only project."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {'.csv', '.geojson', '.parquet', '.duckdb', '.xlsx', '.zip', '.json'}
SECRET_PATTERNS = (
    rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    rb'gh[pousr]_[A-Za-z0-9]{20,}',
    rb'github_pat_[A-Za-z0-9_]{30,}',
    rb'AKIA[A-Z0-9]{16}',
    rb'(?:RAILWAY_TOKEN|AWS_SECRET_ACCESS_KEY|PROTOMAPS_KEY)\s*[:=]\s*[\"\x27][^\"\x27\s]{8,}[\"\x27]',
)


def main() -> None:
    names = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, check=True, capture_output=True).stdout.decode().split('\0')
    problems: list[str] = []
    for name in filter(None, names):
        path = Path(name)
        if path.suffix in FORBIDDEN_SUFFIXES or name.startswith(('.cache/', '.venv/', 'apps/web/dist/', 'apps/web/public/data/', 'packages/data/processed/')) or path.name in {'config.local.js', '.env'}:
            problems.append(f'Generated data or local configuration: {name}')
        # Inspect the staged bytes, rather than an unstaged working copy.
        contents = subprocess.run(['git', 'show', f':{name}'], cwd=ROOT, check=True, capture_output=True).stdout
        if any(re.search(pattern, contents) for pattern in SECRET_PATTERNS):
            problems.append(f'Possible credential: {name}')
        if any(marker in contents for marker in [b'/' + b'Users' + b'/', b'mclean' + b'-website', b'railway' + b'.app', b'SOURCE_' + b'SECRET_ACCESS_KEY']):
            problems.append(f'Private project reference: {name}')
    if problems:
        raise SystemExit('\n'.join(problems))
    print(f'PASS: {len(list(filter(None, names)))} tracked files; no data artifacts, local config, known credentials or private project references.')


if __name__ == '__main__':
    main()
