#!/usr/bin/env python3
"""Download unfiltered Chicago CSV exports; keep raw files on your computer."""
import argparse
import csv
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
SOURCES = {
    'crashes': '85ca-t3if', 'people': 'u6pd-qa9d',
    'permits': 'pubx-yq2d', 'permits-current': '9zhy-9n5f',
    'permits-legacy': 'hwmb-iu8j',
    'wards-2003': 'awaf-s7ux', 'wards-2015': 'k9yb-bpqx', 'wards-2023': 'p293-wvbd',
}


def fetch_source(item: tuple[str, str], cache: Path, refresh: bool) -> dict:
    name, dataset = item
    extension = 'geojson' if name.startswith('wards') else 'csv'
    url = (f'https://data.cityofchicago.org/resource/{dataset}.geojson?$limit=100'
           if extension == 'geojson' else
           f'https://data.cityofchicago.org/api/views/{dataset}/rows.csv?accessType=DOWNLOAD')
    if name in ('permits', 'permits-legacy'):
        query = {'$where': "worktype='BlockParty'" if name == 'permits' else "permit_type_code='BLKPARTY'", '$limit': 1000000}
        url = f'https://data.cityofchicago.org/resource/{dataset}.csv?' + urlencode(query)
    path = cache / f'{name}.{extension}'
    receipt = cache / f'{name}.receipt.json'
    if path.exists() and receipt.exists() and not refresh:
        cached=json.loads(receipt.read_text(encoding='utf-8'))
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):
                digest.update(block)
        if path.stat().st_size!=cached['bytes'] or digest.hexdigest()!=cached['sha256']:
            raise ValueError(f'Cached file does not match its receipt: {name}. Run fetch with --refresh.')
        return cached
    partial = path.with_suffix(path.suffix + f'.{uuid4().hex}.partial')
    print(f'Downloading full {name}: {url}', flush=True)
    subprocess.run(['curl', '--fail', '--location', '--retry', '4', '--retry-delay', '3',
                    '--silent', '--show-error', '--output', str(partial), url], check=True)
    digest = hashlib.sha256()
    with partial.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if partial.stat().st_size < 100:
        raise ValueError(f'Export is unexpectedly small: {name}')
    metadata=cache/f'{name}.metadata.json'
    subprocess.run(['curl','--fail','--location','--retry','4','--silent','--show-error','--output',str(metadata),f'https://data.cityofchicago.org/api/views/{dataset}.json'],check=True)
    expected_rows=None
    if name in ('permits','permits-legacy'):
        count_url=f'https://data.cityofchicago.org/resource/{dataset}.json?'+urlencode({'$select':'count(*) as rows','$where':query['$where']})
        result=subprocess.run(['curl','--fail','--location','--retry','4','--silent','--show-error',count_url],check=True,capture_output=True,text=True)
        expected_rows=int(json.loads(result.stdout)[0]['rows'])
        with partial.open(newline='',encoding='utf-8-sig') as stream:
            records=csv.reader(stream)
            next(records)
            actual_rows=sum(1 for _ in records)
        if actual_rows!=expected_rows:
            partial.unlink()
            raise ValueError(f'{name}: downloaded {actual_rows} rows but the portal reports {expected_rows}. The source may have changed; retry --refresh.')
    partial.replace(path)
    info = {'name': name, 'dataset': dataset, 'url': url, 'bytes': path.stat().st_size,
            'sha256': digest.hexdigest(), 'expectedRows':expected_rows, 'retrievedAt': datetime.now(timezone.utc).isoformat()}
    receipt.write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    print(f'Finished {name}: {info["bytes"]:,} bytes', flush=True)
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=ROOT / '.cache/halloween')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--only', nargs='+', choices=SOURCES)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(lambda item: fetch_source(item, args.cache, args.refresh), [(name, SOURCES[name]) for name in (args.only or SOURCES)]))
    receipts = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(args.cache.glob('*.receipt.json'))]
    (args.cache / 'sources.json').write_text(json.dumps(receipts, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
