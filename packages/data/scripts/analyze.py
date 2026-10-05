#!/usr/bin/env python3
"""Reproduce Halloween comparisons, audited ward assignments and permit associations.

Run fetch.py first, then uv run --locked python pipeline.py build. SQL is in prepare.sql.
"""
import argparse
from datetime import timedelta

import click
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import t
from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parents[3]
METRICS = ['crashes','injury_crashes','injuries','serious','fatal','ped_injuries','ped_serious','ped_fatal','child_injuries','child_serious','child_fatal','bike_injuries']
SUMS = ', '.join(['count(*) AS crashes','count(*) FILTER(WHERE injuries>0) AS injury_crashes'] + [f'coalesce(sum({m}),0) AS {m}' for m in METRICS[2:]])


def rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    frame = con.execute(sql).fetchdf()
    return json.loads(frame.to_json(orient='records', date_format='iso'))


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n', encoding='utf-8')


def residualize(values: np.ndarray, groups: list[np.ndarray]) -> np.ndarray:
    result = values.copy().astype(float)
    for _ in range(200):
        before = result.copy()
        for group in groups:
            count = np.bincount(group)
            for col in range(result.shape[1]):
                means = np.bincount(group, weights=result[:, col]) / count
                result[:, col] -= means[group]
        if np.max(np.abs(result - before)) < 1e-9:
            return result
    raise RuntimeError('Fixed effect projections did not converge')


def association(panel: pd.DataFrame, outcome: str, exposure: str, sample: str, *, halloween: bool=False) -> dict:
    # Ward-era × year × weekday and exact-date effects; two-way clustered covariance.
    units=panel['era'].astype(str)+':'+panel['ward'].astype(str)
    fixed_groups=units if halloween else units+':'+panel['year'].astype(str)+':'+panel['dow'].astype(str)
    group1 = pd.factorize(fixed_groups)[0]
    group2 = pd.factorize(panel['day'])[0]
    x, y = residualize(panel[[exposure,outcome]].to_numpy(), [group1,group2]).T
    bread = float(x @ x)
    if bread < 1e-10:
        raise ValueError('No within-group permit variation')
    coefficient = float(x @ y / bread)
    score = x * (y - coefficient*x)
    cluster = pd.factorize(panel['ward'])[0]
    pair = pd.factorize(pd.MultiIndex.from_arrays([cluster,group2]))[0]
    n = len(panel)
    # Conservative upper bound on absorbed FE rank (redundant levels retained).
    k = len(np.unique(group1)) + len(np.unique(group2))
    def meat(g: np.ndarray) -> float:
        number = len(np.unique(g))
        return float(np.sum(np.bincount(g, weights=score)**2) * number/(number-1) * (n-1)/(n-k))
    variance = (meat(cluster)+meat(group2)-meat(pair))/(bread*bread)
    if variance <= 0:
        raise ValueError('Invalid two-way covariance')
    se = float(np.sqrt(variance))
    critical = float(t.ppf(.975, min(len(np.unique(cluster)),len(np.unique(group2)))-1))
    return {'outcome':outcome,'exposure':exposure,'sample':sample,'coefficient':coefficient,
            'low':coefficient-critical*se,'high':coefficient+critical*se,'se':se,'observations':n,
            'wardClusters':len(np.unique(cluster)), 'dates':len(np.unique(group2)),
            'meanOutcome':float(panel[outcome].mean()), 'treatedWardDays':int((panel[exposure]>0).sum())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,default=ROOT/'.cache/halloween')
    parser.add_argument('--reuse',action='store_true',help='Reuse prepared DuckDB tables')
    parser.add_argument('--output',type=Path,default=ROOT/'packages/data/processed',help='Generated files for CDN upload; never commit data artifacts')
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True,exist_ok=True)
    con = duckdb.connect(str(args.cache/'analysis-v1.5.duckdb'), config={'storage_compatibility_version':'v1.5.0'})
    con.execute('INSTALL spatial')
    con.execute('LOAD spatial')
    con.execute('SET threads=4')
    if not args.reuse:
        click.echo('Reading the full exports and locating records in historical wards…')
        sql=(ROOT/'packages/data/scripts/prepare.sql').read_text(encoding='utf-8').replace('{{CACHE}}',str(args.cache.resolve()).replace("'","''"))
        con.execute(sql)
    audit = rows(con, """SELECT (SELECT count(*) FROM crash_source) AS crashRows,
      (SELECT count(DISTINCT crash_record_id) FROM crash_source) AS uniqueCrashes,
      (SELECT count(*) FROM person_source) AS personRows,
      (SELECT count(DISTINCT person_id) FROM person_source) AS uniquePersons,
      (SELECT count(*) FROM person_source p ANTI JOIN crash_source c USING(crash_record_id)) AS orphanPeople,
      (SELECT count(*) FROM crashes WHERE NOT has_people) AS crashesWithoutPeople,
      (SELECT count(*) FROM crashes WHERE ward IS NULL) AS unassignedCrashes,
      (SELECT count(*) FROM crash_wards WHERE matches>1) AS boundaryTies,
      (SELECT count(*) FROM crashes WHERE injuries IS NULL) AS missingInjuryCounts,
      (SELECT sum(ped_age_missing) FROM crashes) AS missingPedestrianAge,
      (SELECT sum(pedestrians) FROM crashes) AS pedestrians,
      (SELECT count(*) FROM crashes WHERE has_people AND injuries!=person_injuries) AS injuryDisagreements,
      (SELECT count(*) FROM crashes WHERE has_people AND fatal!=person_fatal) AS fatalDisagreements,
      (SELECT max(ts) FROM crashes) AS latestCrash,
      (SELECT count(*) FROM permits) AS modernPermitLocations,
      (SELECT count(DISTINCT applicationnumber) FROM permits) AS modernApplications,
      (SELECT count(*) FROM legacy_permits) AS legacyPermitLocations""")[0]
    current_dates=con.execute(f"SELECT count(*) AS n,count(start_ts) AS parsed_start,count(end_ts) AS parsed_end FROM permits WHERE uniquekey IN (SELECT uniquekey FROM read_csv('{args.cache.resolve()}/permits-current.csv',all_varchar=true,normalize_names=true))").fetchone()
    assert current_dates[0]==current_dates[1]==current_dates[2], 'Current-view CSV dates must parse'
    assert audit['crashRows']==audit['uniqueCrashes'] and audit['personRows']==audit['uniquePersons']
    # Complete citywide calendar years only. Unknown crash injury counts are separately audited.
    con.execute(f"""CREATE OR REPLACE TABLE observed_daily AS SELECT day, {SUMS},
      coalesce(sum(child_injuries) FILTER(WHERE hour BETWEEN 16 AND 21),0) AS child_evening,
      coalesce(sum(ped_injuries) FILTER(WHERE hour BETWEEN 16 AND 21),0) AS ped_evening,
      coalesce(sum(ped_age_missing),0) AS ped_age_missing, coalesce(sum(ped_unknown_injuries),0) AS ped_unknown_injuries,
      count(*) FILTER(WHERE injuries IS NULL) AS missing_injuries
      FROM crashes WHERE day BETWEEN DATE '2018-01-01' AND DATE '2025-12-31' GROUP BY day""")
    con.execute("""CREATE OR REPLACE TABLE daily AS SELECT cast(d AS DATE) AS day,
      o.* EXCLUDE(day) FROM generate_series(DATE '2018-01-01',DATE '2025-12-31',INTERVAL 1 DAY) t(d)
      LEFT JOIN observed_daily o ON o.day=cast(d AS DATE)""")
    assert con.execute('SELECT count(*) FROM daily WHERE crashes IS NULL').fetchone()[0]==0
    metrics = METRICS + ['child_evening','ped_evening','ped_unknown_injuries']
    daily=rows(con,'SELECT * FROM daily ORDER BY day')
    frame=con.execute('SELECT * FROM daily ORDER BY day').fetchdf().set_index('day')
    frame.index=frame.index.as_unit('ns')
    comparisons=[]
    for year in range(2018,2026):
        halloween=pd.Timestamp(year,10,31)
        h=frame.loc[halloween]
        november=pd.Timestamp(year,11,1)
        thanksgiving=november+timedelta(days=(3-november.dayofweek)%7+21)
        control=frame.loc[[halloween+timedelta(days=k*7) for k in [-4,-3,-2,-1,1,2,3,4] if halloween+timedelta(days=k*7)!=thanksgiving]]
        comparisons.append({'year':year,'weekday':halloween.day_name(),
          'halloween':{m:float(h[m]) for m in metrics},
          'baseline':{m:float(control[m].mean()) for m in metrics},
          'controls':{m:[float(v) for v in control[m]] for m in metrics},
          'controlDates':[d.strftime('%Y-%m-%d') for d in control.index]})
    rng=np.random.default_rng(20261005)
    samples=rng.integers(0,8,(20000,8))
    pooled={}
    for m in metrics:
        h=np.array([r['halloween'][m] for r in comparisons]); b=np.array([r['baseline'][m] for r in comparisons])
        denominators=b[samples].sum(axis=1)
        boot=h[samples].sum(axis=1)/np.maximum(denominators,1e-12)
        ci=np.quantile(boot,[.025,.975]).tolist() if h.sum()>=5 and b.sum()>=5 and (denominators>0).all() else None
        # Calendar-placebo randomization within each year's observed matched block.
        placebo=np.zeros(50000)
        for r in comparisons:
            block=np.array([r['halloween'][m]]+r['controls'][m])
            selected=block[rng.integers(0,len(block),50000)]
            placebo += selected-(block.sum()-selected)/(len(block)-1)
        difference=float(h.sum()-b.sum())
        p=float((1+(np.abs(placebo)>=abs(difference)).sum())/50001)
        pooled[m]={'halloweenTotal':float(h.sum()),'baselineTotal':float(b.sum()),
          'ratio':float(h.sum()/b.sum()) if b.sum()>0 else None,'ci':ci,'placeboP':p,
          'yearsAbove':int((h>b).sum()),'without2020Ratio':float(np.delete(h,2).sum()/np.delete(b,2).sum()) if np.delete(b,2).sum()>0 else None,
          'threeWeekRatio':float(h.sum()/sum(np.mean([v for d,v in zip(r['controlDates'],r['controls'][m],strict=True) if abs((pd.Timestamp(d)-pd.Timestamp(r['year'],10,31)).days)<=21]) for r in comparisons)) if b.sum()>0 else None,
          'leaveOneYearOut':[float(np.delete(h,i).sum()/np.delete(b,i).sum()) if np.delete(b,i).sum()>0 else None for i in range(8)]}
    calendar=rows(con, 'SELECT strftime(day,\'%m-%d\') AS md, '+ ','.join(f'sum({m}) AS {m}' for m in metrics)+" FROM daily WHERE strftime(day,'%m-%d')!='02-29' GROUP BY md ORDER BY md")
    hrow=next(r for r in calendar if r['md']=='10-31')
    for m in metrics:
        pooled[m]['calendarRank']=1+sum(r[m]>hrow[m] for r in calendar)
        pooled[m]['calendarTies']=sum(r[m]==hrow[m] for r in calendar)
    hours=rows(con, 'SELECT extract(hour FROM ts)::INTEGER AS hour, '+SUMS+" FROM crashes WHERE extract(year FROM day) BETWEEN 2018 AND 2025 AND strftime(day,'%m-%d')='10-31' GROUP BY ALL ORDER BY hour")
    # Separate full-closure eligibility and timing from application status.
    con.execute("""CREATE OR REPLACE TABLE eligible_permits AS SELECT * FROM permits
      WHERE currentmilestone='Complete' AND issued IS NOT NULL AND streetclosure='Full'
      AND start_ts>=TIMESTAMP '2013-01-01' AND start_ts<TIMESTAMP '2027-01-01'
      AND end_ts>=start_ts AND end_ts<start_ts+INTERVAL 3 DAY
      AND issued<date_trunc('day',start_ts)+INTERVAL 1 DAY""")
    audit['permitFilters']=rows(con,"""SELECT count(*) AS allLocations,
      count(*) FILTER(WHERE currentmilestone='Complete' AND issued IS NOT NULL) AS approvedLocations,
      count(*) FILTER(WHERE currentmilestone='Complete' AND issued IS NOT NULL AND streetclosure='Full') AS fullClosureLocations,
      count(*) FILTER(WHERE start_ts<DATE '2013-01-01' OR start_ts>=DATE '2027-01-01') AS invalidDates,
      count(*) FILTER(WHERE end_ts IS NULL OR end_ts<start_ts OR end_ts>=start_ts+INTERVAL 3 DAY) AS invalidDurations,
      count(*) FILTER(WHERE currentmilestone='Complete' AND issued>=date_trunc('day',start_ts)+INTERVAL 1 DAY) AS issuedAfterEventDay,
      count(*) FILTER(WHERE ward IS NULL) AS unassignedLocations,
      (SELECT count(*) FROM eligible_permits) AS eligibleLocations FROM permits""")[0]
    con.execute("""CREATE OR REPLACE TABLE permit_days AS SELECT DISTINCT applicationnumber,
      cast(d AS DATE) AS day, ward, CASE WHEN d<TIMESTAMP '2015-05-18' THEN '2003' WHEN d<TIMESTAMP '2023-05-15' THEN '2015' ELSE '2023' END AS era
      FROM eligible_permits, generate_series(cast(start_ts AS DATE)::TIMESTAMP,
      cast(end_ts AS DATE)::TIMESTAMP,INTERVAL 1 DAY) t(d) WHERE ward IS NOT NULL""")
    # Recompute ward on each event day where a multi-day permit crosses a map change.
    assert con.execute("SELECT count(*) FROM permit_days d JOIN permits p USING(applicationnumber) WHERE d.era!=p.era").fetchone()[0]==0
    con.execute(f"""CREATE OR REPLACE TABLE ward_observed AS SELECT ward,day,{SUMS},
      coalesce(sum(ped_injuries) FILTER(WHERE hour BETWEEN 16 AND 21),0) AS ped_evening
      FROM crashes WHERE ward IS NOT NULL AND day BETWEEN DATE '2018-01-01' AND DATE '2025-12-31' GROUP BY ward,day""")
    con.execute("""CREATE OR REPLACE TABLE panel AS WITH counts AS (
      SELECT ward,day,count(DISTINCT applicationnumber) AS permits FROM permit_days GROUP BY ward,day)
      SELECT w.ward, d.day, extract(year FROM d.day)::INTEGER AS year, extract(dow FROM d.day)::INTEGER AS dow,
      CASE WHEN d.day<DATE '2023-05-15' THEN '2015' ELSE '2023' END AS era,
      coalesce(p.permits,0) AS permits, coalesce(f.permits,0) AS lead7,
      coalesce(l.permits,0) AS lag1,
      coalesce(c.crashes,0) AS crashes, coalesce(c.injury_crashes,0) AS injury_crashes,
      coalesce(c.injuries,0) AS injuries, coalesce(c.ped_injuries,0) AS ped_injuries,
      coalesce(c.child_injuries,0) AS child_injuries, coalesce(c.ped_evening,0) AS ped_evening
      FROM (SELECT DISTINCT ward FROM wards) w CROSS JOIN daily d
      LEFT JOIN ward_observed c ON c.ward=w.ward AND c.day=d.day
      LEFT JOIN counts p ON p.ward=w.ward AND p.day=d.day
      LEFT JOIN counts f ON f.ward=w.ward AND f.day=d.day+7
      LEFT JOIN counts l ON l.ward=w.ward AND l.day=d.day-1""")
    panel=con.execute("SELECT * FROM panel WHERE extract(month FROM day) BETWEEN 5 AND 10 ORDER BY day,ward").fetchdf()
    click.echo('Checking how permits and reported harm vary across wards and dates…')
    models=[association(panel,m,'permits','May–October 2018–2025') for m in ['injury_crashes','ped_injuries','child_injuries']]
    models.extend([association(panel,'ped_injuries','lead7','Future permit: 7-day lead placebo'),
      association(panel,'ped_injuries','lag1','Day after permitted events'),
      association(panel[panel.year!=2020],'ped_injuries','permits','Excluding 2020'),
      association(panel[panel.era=='2015'],'ped_injuries','permits','2015 boundaries only'),
      association(panel[panel.era=='2023'],'ped_injuries','permits','2023 boundaries only')])
    wardHalloween=rows(con,"""SELECT h.ward,h.year,h.era,h.permits,h.injuries,h.ped_injuries,h.child_injuries,h.injury_crashes,
      avg(c.injuries) AS baseline_injuries, avg(c.ped_injuries) AS baseline_ped_injuries,
      avg(c.child_injuries) AS baseline_child_injuries, avg(c.permits) AS baseline_permits
      FROM panel h JOIN (SELECT unnest([-28,-21,-14,-7,7,14,21,28]) AS offset_days) k ON true
      JOIN panel c ON c.ward=h.ward AND c.day=h.day+k.offset_days
      WHERE strftime(h.day,'%m-%d')='10-31' AND NOT (extract(month FROM c.day)=11 AND extract(dow FROM c.day)=4 AND extract(day FROM c.day) BETWEEN 22 AND 28) GROUP BY ALL ORDER BY h.year,h.ward""")
    holiday=pd.DataFrame(wardHalloween)
    holiday['day']=[pd.Timestamp(y,10,31) for y in holiday.year]
    holiday['excess_permits']=holiday.permits-holiday.baseline_permits
    holiday['excess_ped_injuries']=holiday.ped_injuries-holiday.baseline_ped_injuries
    holiday_model=association(holiday,'excess_ped_injuries','excess_permits','Halloween minus matched weekdays',halloween=True)
    permitYears=rows(con,"""SELECT extract(year FROM start_ts)::INTEGER AS year,
      count(*) AS locations,count(DISTINCT applicationnumber) AS applications,
      count(*) FILTER(WHERE ward IS NULL) AS unassigned FROM eligible_permits GROUP BY year ORDER BY year""")
    future=rows(con,"""SELECT p.applicationnumber,p.currentmilestone,p.streetclosure,p.ward,p.lat,p.lon,
      p.start_ts,p.end_ts,concat_ws(' ',p.streetnumberfrom,p.direction,p.streetname,p.suffix) AS street,
      p.uniquekey IN (SELECT uniquekey FROM eligible_permits) AS approved
      FROM permits p WHERE p.end_ts>=TIMESTAMP '2026-10-30' AND p.start_ts<TIMESTAMP '2026-11-02' AND p.start_ts>=TIMESTAMP '2026-10-28'
      ORDER BY p.start_ts,p.applicationnumber""")
    features=[]
    for p in future:
        if p['lat'] is not None and p['lon'] is not None and -88<p['lon']<-87 and 41<p['lat']<43:
            features.append({'type':'Feature','geometry':{'type':'Point','coordinates':[p['lon'],p['lat']]},'properties':p})
    save(output/'permits-2026.geojson',{'type':'FeatureCollection','features':features})
    for era in ['2003','2015','2023']:
        path=args.cache/f'wards-{era}.geojson'
        if not path.exists():
            continue
        geo=json.loads(path.read_text(encoding='utf-8'))
        geo['features']=[f for f in geo['features'] if str(f['properties']['ward']).isdigit() and 1<=int(f['properties']['ward'])<=50]
        for f in geo['features']:
            f['properties']={'ward':int(f['properties']['ward'])}; f['id']=f['properties']['ward']
            f['geometry']=mapping(shape(f['geometry']).simplify(.000015,preserve_topology=True))
        assert len(geo['features'])==50
        save(output/f'wards-{era}.geojson',geo)
    earlier=[]
    for year in [2015,2016,2017]:
        halloween=pd.Timestamp(year,10,31)
        days=[halloween+timedelta(days=k*7) for k in [-4,-3,-2,-1,0,1,2,3,4]]
        literals=','.join("DATE '"+d.strftime('%Y-%m-%d')+"'" for d in days)
        raw=rows(con,f"""SELECT cast(c.ts AS DATE) AS day,count(*) AS crashes,
          coalesce(sum(c.injuries),0) AS injuries,coalesce(sum(c.serious),0) AS serious,
          coalesce(sum(c.fatal),0) AS fatal,coalesce(sum(p.ped_injuries),0) AS ped_injuries,
          coalesce(sum(p.child_injuries),0) AS child_injuries
          FROM crash_source c LEFT JOIN person_crash p USING(crash_record_id)
          WHERE cast(c.ts AS DATE) IN ({literals}) GROUP BY day ORDER BY day""")
        event=next((r for r in raw if r['day'][:10]==halloween.strftime('%Y-%m-%d')),None)
        controls=[r for r in raw if r is not event]
        earlier.append({'year':year,'citywide':year==2017,'halloween':event,
          'baseline':{m:sum(r[m] for r in controls)/8 for m in ['crashes','injuries','serious','fatal','ped_injuries','child_injuries']}})
    archive=rows(con,"""SELECT 'modern' AS source,extract(year FROM p.start_ts)::INTEGER AS year,p.era,p.ward,count(*) AS locations,count(DISTINCT p.applicationnumber) AS applications FROM permits p WHERE p.start_ts BETWEEN DATE '2013-01-01' AND DATE '2026-12-31' GROUP BY ALL UNION ALL SELECT 'legacy',extract(year FROM dt(l.effective_date))::INTEGER,CASE WHEN dt(l.effective_date)<DATE '2015-05-18' THEN '2003' ELSE '2015' END,w.ward,count(*),count(DISTINCT l.permit_number) FROM legacy_permits l JOIN legacy_wards w USING(id) WHERE dt(l.effective_date) BETWEEN DATE '2011-01-01' AND DATE '2015-12-06' GROUP BY ALL ORDER BY source,year,ward""")
    save(output/'permit-archive.json',archive)
    receipts=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(args.cache.glob('*.receipt.json'))]
    data={'meta':{'snapshot':max(r['retrievedAt'][:10] for r in receipts),'studyPrepared':'2026-10-05','completeYears':list(range(2018,2026)),
      'engine':con.execute('SELECT version()').fetchone()[0],'sources':receipts,'audit':audit},
      'metrics':[m for m in metrics if m!='ped_unknown_injuries'],'pooled':pooled,'comparisons':comparisons,'calendar':calendar,'hours':hours,
      'wardHalloween':wardHalloween,'models':models,'halloweenModel':holiday_model,'permitYears':permitYears,'futurePermits':future}
    ch=pooled['child_injuries']; unknown=pooled['ped_unknown_injuries']
    data['ageSensitivity']={'unknownHalloween':unknown['halloweenTotal'],'unknownBaseline':unknown['baselineTotal'], 'lowerRatio':ch['halloweenTotal']/(ch['baselineTotal']+unknown['baselineTotal']), 'upperRatio':(ch['halloweenTotal']+unknown['halloweenTotal'])/ch['baselineTotal']}
    data['additionalHalloweens']=earlier
    data['permitArchive']=archive
    save(output/'analysis.json',data)
    save(output/'audit.json',audit)
    for name,query in [('daily','SELECT * FROM daily ORDER BY day'),('ward-day','SELECT * FROM panel ORDER BY day,ward')]:
        con.execute(f"COPY ({query}) TO '{str(output/f'{name}.csv')}' (HEADER, DELIMITER ',')")
    click.echo(f'Analysis ready: {output}. Counts, source receipts and estimates are in analysis.json.')


if __name__=='__main__':
    main()
