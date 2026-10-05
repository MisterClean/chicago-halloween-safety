#!/usr/bin/env python3
"""Independent source cross-checks and substantive grain/model checks."""
import argparse
import json
import hashlib

import duckdb
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from analyze import residualize

ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts',type=Path,default=ROOT/'packages/data/processed')
    parser.add_argument('--cache',type=Path,default=ROOT/'.cache/halloween')
    args=parser.parse_args()
    artifacts=args.artifacts
    cache=args.cache
    # Verify the exact downloaded files before independently reading source CSVs.
    for receipt in sorted(cache.glob('*.receipt.json')):
        source=json.loads(receipt.read_text(encoding='utf-8'))
        extension='geojson' if source['name'].startswith('wards') else 'csv'
        path=cache/f"{source['name']}.{extension}"
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):
                digest.update(block)
        assert path.stat().st_size==source['bytes'] and digest.hexdigest()==source['sha256'],source['name']
    con=duckdb.connect()
    date_expression="coalesce(try_strptime(crash_date, '%m/%d/%Y %I:%M:%S %p'),try_cast(crash_date AS TIMESTAMP))"
    crashes=con.read_csv(str(cache/'crashes.csv'),all_varchar=True,normalize_names=True)
    people=con.read_csv(str(cache/'people.csv'),all_varchar=True,normalize_names=True)
    crashes.create_view('source_crashes')
    people.create_view('source_people')
    data=json.loads((artifacts/'analysis.json').read_text(encoding='utf-8'))
    assert data['meta']['completeYears']==list(range(2018,2026))
    assert len(data['calendar'])==365 and all(r['md']!='02-29' for r in data['calendar'])
    independent=con.execute(f"""SELECT extract(year FROM {date_expression})::INTEGER AS year,
      count(*) AS crashes, sum(try_cast(injuries_total AS BIGINT)) AS injuries,
      sum(try_cast(injuries_incapacitating AS BIGINT)) AS serious,
      sum(try_cast(injuries_fatal AS BIGINT)) AS fatal FROM source_crashes
      WHERE strftime({date_expression},'%m-%d')='10-31'
      AND extract(year FROM {date_expression}) BETWEEN 2018 AND 2025 GROUP BY year""").fetchdf().to_dict('records')
    for raw in independent:
        row=next(r for r in data['comparisons'] if r['year']==raw['year'])
        for metric in ['crashes','injuries','serious','fatal']:
            assert row['halloween'][metric]==raw[metric],(row['year'],metric)
    child=con.execute(f"""SELECT extract(year FROM {date_expression})::INTEGER AS year,count(*) AS injured
      FROM source_people WHERE person_type='PEDESTRIAN' AND try_cast(age AS INTEGER) BETWEEN 0 AND 17
      AND injury_classification IN ('FATAL','INCAPACITATING INJURY','NONINCAPACITATING INJURY','REPORTED, NOT EVIDENT')
      AND strftime({date_expression},'%m-%d')='10-31'
      AND extract(year FROM {date_expression}) BETWEEN 2018 AND 2025 GROUP BY year""").fetchdf().to_dict('records')
    expected={r['year']:r['injured'] for r in child}
    for r in data['comparisons']:
        assert r['halloween']['child_injuries']==expected.get(r['year'],0)
        assert len(r['controlDates'])==(7 if r['weekday']=='Thursday' else 8)
        for day in r['controlDates']:
            difference=(pd.Timestamp(day)-pd.Timestamp(r['year'],10,31)).days
            assert difference in [-28,-21,-14,-7,7,14,21,28]
            assert pd.Timestamp(day).day_name()==r['weekday']
            assert not(pd.Timestamp(day).month==11 and pd.Timestamp(day).dayofweek==3 and 22<=pd.Timestamp(day).day<=28)
    a=data['meta']['audit']
    assert a['crashRows']==a['uniqueCrashes'] and a['personRows']==a['uniquePersons']
    assert a['modernPermitLocations']>0 and a['legacyPermitLocations']>0
    daily=pd.read_csv(artifacts/'daily.csv',parse_dates=['day'])
    panel=pd.read_csv(artifacts/'ward-day.csv',parse_dates=['day'])
    assert len(daily)==2922 and daily.day.is_unique
    assert len(panel)==len(daily)*50 and not panel.duplicated(['day','ward']).any()
    assert set(panel.ward)==set(range(1,51))
    # Person subset and geographic subset counts must not exceed corresponding city totals.
    for metric in ['crashes','injury_crashes','injuries','ped_injuries','child_injuries']:
        ward=panel.groupby('day')[metric].sum()
        city=daily.set_index('day')[metric]
        assert (ward<=city).all(),metric
    assert (daily.child_injuries<=daily.ped_injuries).all()
    assert (panel.permits>=0).all() and (panel.permits%1==0).all()
    assert (panel.loc[panel.day<pd.Timestamp('2023-05-15'),'era']==2015).all()
    assert (panel.loc[panel.day>=pd.Timestamp('2023-05-15'),'era']==2023).all()
    # Ward comparisons must use the same holiday exclusions as the city comparison.
    assert len(data['wardHalloween'])==400
    for row in data['wardHalloween']:
        dates=next(r['controlDates'] for r in data['comparisons'] if r['year']==row['year'])
        controls=panel[(panel.ward==row['ward'])&panel.day.isin(pd.to_datetime(dates))]
        assert len(controls)==len(dates)
        for metric in ['injuries','ped_injuries','child_injuries','permits']:
            assert np.isclose(row['baseline_'+metric],controls[metric].mean()),(row['ward'],row['year'],metric)
    assert data['halloweenModel']['observations']==400 and data['halloweenModel']['dates']==8
    future=json.loads((artifacts/'permits-2026.geojson').read_text(encoding='utf-8'))
    located=[r for r in data['futurePermits'] if r['lat'] is not None and r['lon'] is not None and -88<r['lon']<-87 and 41<r['lat']<43]
    assert [f['properties'] for f in future['features']]==located
    # Independently fit explicit dummy variables on a bounded real panel slice.
    sample=panel[(panel.year==2024)&(panel.ward<=5)&(panel.day.dt.month.between(6,8))].copy()
    sample['unit']=sample.ward.astype(str)+':'+sample.dow.astype(str)
    g1=pd.factorize(sample['unit'])[0];g2=pd.factorize(sample['day'])[0]
    x,y=residualize(sample[['permits','ped_injuries']].to_numpy(),[g1,g2]).T
    estimate=float(x@y/(x@x))
    reference=smf.ols('ped_injuries ~ permits + C(unit) + C(day)',data=sample).fit()
    assert np.isclose(estimate,reference.params['permits'],atol=1e-10)
    for era in ['2003','2015','2023']:
        geo=json.loads((artifacts/f'wards-{era}.geojson').read_text(encoding='utf-8'))
        assert len(geo['features'])==50 and {f['properties']['ward'] for f in geo['features']}==set(range(1,51))
    for model in [*data['models'],data['halloweenModel']]:
        assert model['low']<model['coefficient']<model['high']
        assert all(np.isfinite(model[k]) for k in ['coefficient','low','high','se'])
    # Public analysis must not accidentally contain raw contact/residence columns.
    text=(artifacts/'analysis.json').read_text(encoding='utf-8').lower()
    for forbidden in ['primarycontactfirst','emergencycontactname','drivers_license','hospital','ems_run_no']:
        assert forbidden not in text
    print('PASS: source file checksums, independent CSV totals, weekday/holiday baselines, complete panel grain, geographic/subset reconciliation, explicit-dummy model agreement, boundary eras, and public field audit.')


if __name__=='__main__':
    main()
