#!/usr/bin/env python3
"""Fetch public sources, rebuild and check the analysis, or open a local preview."""
from pathlib import Path
import subprocess
import sys

import click

ROOT = Path(__file__).resolve().parent
DATA_SCRIPTS = ROOT / 'packages/data/scripts'


def run(script: Path, *args: str) -> None:
    subprocess.run([sys.executable, str(script), *args], cwd=ROOT, check=True)


@click.command()
@click.argument('stage', type=click.Choice(['all', 'fetch', 'build', 'check', 'serve', 'export']), default='all')
@click.option('--refresh', is_flag=True, help='Replace cached downloads with fresh city exports.')
@click.option('--reuse', is_flag=True, help='Reuse an already prepared local DuckDB database.')
@click.option('--port', type=click.IntRange(1024, 65535), default=8766, show_default=True)
def main(stage: str, refresh: bool, reuse: bool, port: int) -> None:
    if refresh and stage not in ['all', 'fetch']:
        raise click.UsageError('--refresh applies to all or fetch.')
    if stage in ['all', 'fetch']:
        run(DATA_SCRIPTS / 'fetch.py', *(['--refresh'] if refresh else []))
    if stage in ['all', 'build']:
        run(DATA_SCRIPTS / 'analyze.py', *(['--reuse'] if reuse else []))
    if stage in ['all', 'build', 'check']:
        run(DATA_SCRIPTS / 'validate.py')
    if stage in ['all', 'build', 'export']:
        run(ROOT / 'scripts/build_web.py', *(['--dist'] if stage == 'export' else []))
    if stage == 'serve':
        page = ROOT / 'apps/web/public'
        if not (page / 'data/halloween/manifest.json').is_file():
            raise click.ClickException('Build the analysis first: uv run --locked python pipeline.py')
        click.echo(f'Open http://127.0.0.1:{port}/ — press Ctrl+C to stop.')
        subprocess.run([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1', '--directory', str(page)], check=True)


if __name__ == '__main__':
    main()
