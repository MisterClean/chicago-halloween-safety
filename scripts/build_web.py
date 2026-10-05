#!/usr/bin/env python3
"""Prepare a self-contained local page from the generated, checked aggregates."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import click

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'analysis.json', 'daily.csv', 'ward-day.csv', 'permit-archive.json',
    'permits-2026.geojson', 'wards-2003.geojson', 'wards-2015.geojson', 'wards-2023.geojson',
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', action='store_true', help='Also write an upload-ready static folder.')
    args = parser.parse_args()
    artifacts = ROOT / 'packages/data/processed'
    missing = [name for name in FILES if not (artifacts / name).is_file()]
    if missing:
        raise SystemExit('Run the analysis first; missing outputs: ' + ', '.join(missing))
    page = ROOT / 'apps/web/public'
    output = page / 'data/halloween'
    output.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {'files': {}}
    entries: dict[str, dict[str, str | int]] = {}
    for name in FILES:
        contents = (artifacts / name).read_bytes()
        (output / name).write_bytes(contents)
        entries[name] = {'url': f'data/halloween/{name}', 'sha256': hashlib.sha256(contents).hexdigest(), 'bytes': len(contents)}
    manifest['files'] = entries
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    config = page / 'config.local.js'
    if not config.is_file():
        config.write_text('window.__CONFIG__ = { PROTOMAPS_KEY: "" };\n', encoding='utf-8')
    if args.dist:
        # Only the web directory is exported. Raw People/contact records are never included.
        shutil.copytree(page, ROOT / 'apps/web/dist', dirs_exist_ok=True)
        click.echo('Ready to host: apps/web/dist/ (aggregates and public permit locations only).')
    click.echo('Local page ready. Run: uv run --locked python pipeline.py serve')


if __name__ == '__main__':
    main()
