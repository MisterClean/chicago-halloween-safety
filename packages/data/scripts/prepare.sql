-- All aggregation and geographic assignment runs in DuckDB. Raw CSVs stay local and are excluded from Git.
LOAD spatial;
SET geometry_always_xy=true;
SET threads=4;
CREATE OR REPLACE MACRO dt(v) AS coalesce(try_strptime(v, '%m/%d/%Y %I:%M:%S %p'), try_strptime(v, '%m/%d/%Y'), try_cast(v AS TIMESTAMP));
CREATE OR REPLACE TABLE crash_source AS SELECT
 crash_record_id, dt(crash_date) AS ts, try_cast(crash_hour AS INTEGER) AS hour,
 try_cast(injuries_total AS INTEGER) AS injuries,
 try_cast(injuries_incapacitating AS INTEGER) AS serious,
 try_cast(injuries_fatal AS INTEGER) AS fatal,
 try_cast(latitude AS DOUBLE) AS lat, try_cast(longitude AS DOUBLE) AS lon,
 weather_condition, lighting_condition, first_crash_type, hit_and_run_i
FROM read_csv('{{CACHE}}/crashes.csv', all_varchar=true, normalize_names=true);
CREATE OR REPLACE TABLE person_source AS SELECT person_id, crash_record_id, person_type,
 try_cast(age AS INTEGER) AS age, injury_classification AS injury, dt(crash_date) AS ts
FROM read_csv('{{CACHE}}/people.csv', all_varchar=true, normalize_names=true);
CREATE OR REPLACE TABLE person_crash AS SELECT crash_record_id,
 count(*) AS persons,
 count(*) FILTER(WHERE injury IN ('FATAL','INCAPACITATING INJURY','NONINCAPACITATING INJURY','REPORTED, NOT EVIDENT')) AS person_injuries,
 count(*) FILTER(WHERE injury='FATAL') AS person_fatal,
 count(*) FILTER(WHERE injury='INCAPACITATING INJURY') AS person_serious,
 count(*) FILTER(WHERE person_type='PEDESTRIAN') AS pedestrians,
 count(*) FILTER(WHERE person_type='PEDESTRIAN' AND injury IN ('FATAL','INCAPACITATING INJURY','NONINCAPACITATING INJURY','REPORTED, NOT EVIDENT')) AS ped_injuries,
 count(*) FILTER(WHERE person_type='PEDESTRIAN' AND injury='FATAL') AS ped_fatal,
 count(*) FILTER(WHERE person_type='PEDESTRIAN' AND injury='INCAPACITATING INJURY') AS ped_serious,
 count(*) FILTER(WHERE person_type='PEDESTRIAN' AND age BETWEEN 0 AND 17 AND injury IN ('FATAL','INCAPACITATING INJURY','NONINCAPACITATING INJURY','REPORTED, NOT EVIDENT')) AS child_injuries,
 count(*) FILTER(WHERE person_type='PEDESTRIAN' AND age BETWEEN 0 AND 17 AND injury='FATAL') AS child_fatal,
 count(*) FILTER(WHERE person_type='PEDESTRIAN' AND age BETWEEN 0 AND 17 AND injury='INCAPACITATING INJURY') AS child_serious,
 count(*) FILTER(WHERE person_type='PEDESTRIAN' AND (age IS NULL OR age NOT BETWEEN 0 AND 110)) AS ped_age_missing,
 count(*) FILTER(WHERE person_type='PEDESTRIAN' AND (age IS NULL OR age NOT BETWEEN 0 AND 110) AND injury IN ('FATAL','INCAPACITATING INJURY','NONINCAPACITATING INJURY','REPORTED, NOT EVIDENT')) AS ped_unknown_injuries,
 count(*) FILTER(WHERE person_type='BICYCLE' AND injury IN ('FATAL','INCAPACITATING INJURY','NONINCAPACITATING INJURY','REPORTED, NOT EVIDENT')) AS bike_injuries
FROM person_source GROUP BY ALL;
CREATE OR REPLACE TABLE wards AS
 SELECT '2003' AS era, try_cast(ward AS INTEGER) AS ward, geom FROM ST_Read('{{CACHE}}/wards-2003.geojson') WHERE try_cast(ward AS INTEGER) BETWEEN 1 AND 50
 UNION ALL SELECT '2015' AS era, cast(ward AS INTEGER) AS ward, geom FROM ST_Read('{{CACHE}}/wards-2015.geojson')
 UNION ALL SELECT '2023', cast(ward AS INTEGER), geom FROM ST_Read('{{CACHE}}/wards-2023.geojson');
CREATE OR REPLACE TABLE crashes AS SELECT c.*, cast(c.ts AS DATE) AS day,
 CASE WHEN ts < TIMESTAMP '2023-05-15' THEN '2015' ELSE '2023' END AS era,
 coalesce(p.persons,0) AS persons, coalesce(p.person_injuries,0) AS person_injuries,
 coalesce(p.person_fatal,0) AS person_fatal, coalesce(p.person_serious,0) AS person_serious,
 coalesce(p.pedestrians,0) AS pedestrians, coalesce(p.ped_injuries,0) AS ped_injuries,
 coalesce(p.ped_fatal,0) AS ped_fatal, coalesce(p.ped_serious,0) AS ped_serious,
 coalesce(p.child_injuries,0) AS child_injuries, coalesce(p.child_fatal,0) AS child_fatal,
 coalesce(p.child_serious,0) AS child_serious, coalesce(p.ped_age_missing,0) AS ped_age_missing,
 coalesce(p.bike_injuries,0) AS bike_injuries, coalesce(p.ped_unknown_injuries,0) AS ped_unknown_injuries, p.crash_record_id IS NOT NULL AS has_people
 FROM crash_source c LEFT JOIN person_crash p USING(crash_record_id)
 WHERE c.ts >= TIMESTAMP '2017-09-01' AND c.ts < TIMESTAMP '2026-10-06';
-- Spatial containment, longitude first; min ward resolves exact shared boundary ties deterministically.
CREATE OR REPLACE TABLE crash_wards AS SELECT c.crash_record_id, min(w.ward) AS ward,
 count(w.ward) AS matches FROM crashes c LEFT JOIN wards w ON c.era=w.era
 AND c.lon BETWEEN -88 AND -87 AND c.lat BETWEEN 41 AND 43
 AND ST_Covers(w.geom, ST_Point(c.lon,c.lat)) GROUP BY c.crash_record_id;
ALTER TABLE crashes ADD COLUMN ward INTEGER;
UPDATE crashes SET ward=w.ward FROM crash_wards w WHERE crashes.crash_record_id=w.crash_record_id;
CREATE OR REPLACE TABLE permit_raw AS
 SELECT * EXCLUDE (ward), 0 AS priority FROM read_csv('{{CACHE}}/permits.csv', all_varchar=true, normalize_names=true)
 UNION ALL BY NAME SELECT *, 1 AS priority FROM read_csv('{{CACHE}}/permits-current.csv', all_varchar=true, normalize_names=true);
CREATE OR REPLACE TABLE permits AS SELECT uniquekey, applicationnumber, applicationname,
 currentmilestone, applicationstatus, dt(applicationissueddate) AS issued,
 dt(applicationstartdate) AS start_ts, dt(applicationenddate) AS end_ts,
 try_cast(latitude AS DOUBLE) AS lat, try_cast(longitude AS DOUBLE) AS lon,
 streetclosure, direction, streetname, suffix, streetnumberfrom, streetnumberto,
 CASE WHEN dt(applicationstartdate)<TIMESTAMP '2015-05-18' THEN '2003' WHEN dt(applicationstartdate)<TIMESTAMP '2023-05-15' THEN '2015' ELSE '2023' END AS era
 FROM permit_raw WHERE worktype='BlockParty'
 QUALIFY row_number() OVER(PARTITION BY uniquekey ORDER BY priority DESC)=1;
CREATE OR REPLACE TABLE permit_wards AS SELECT p.uniquekey, min(w.ward) AS ward, count(w.ward) AS matches
 FROM permits p LEFT JOIN wards w ON p.era=w.era
 AND p.lon BETWEEN -88 AND -87 AND p.lat BETWEEN 41 AND 43
 AND ST_Covers(w.geom,ST_Point(p.lon,p.lat)) GROUP BY p.uniquekey;
ALTER TABLE permits ADD COLUMN ward INTEGER;
UPDATE permits SET ward=w.ward FROM permit_wards w WHERE permits.uniquekey=w.uniquekey;
CREATE OR REPLACE TABLE legacy_permits AS SELECT * FROM read_csv('{{CACHE}}/permits-legacy.csv',all_varchar=true,normalize_names=true);

CREATE OR REPLACE TABLE legacy_wards AS SELECT l.id,min(w.ward) AS ward FROM legacy_permits l LEFT JOIN wards w ON w.era=CASE WHEN dt(l.effective_date)<TIMESTAMP '2015-05-18' THEN '2003' ELSE '2015' END AND try_cast(l.longitude AS DOUBLE) BETWEEN -88 AND -87 AND try_cast(l.latitude AS DOUBLE) BETWEEN 41 AND 43 AND ST_Covers(w.geom,ST_Point(try_cast(l.longitude AS DOUBLE),try_cast(l.latitude AS DOUBLE))) GROUP BY l.id;
