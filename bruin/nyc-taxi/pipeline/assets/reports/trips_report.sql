/* @bruin
name: reports.trips_report
type: bq.sql

depends:
  - staging.trips

materialization:
  type: table

columns:
  - name: trip_date
    type: date
    primary_key: true
  - name: taxi_type
    type: string
    primary_key: true
  - name: payment_type
    type: string
    primary_key: true
  - name: trips
    type: bigint
    checks:
      - name: non_negative
  - name: total_fare
    type: float
    checks:
      - name: non_negative
  - name: avg_distance
    type: float
@bruin */

SELECT
    CAST(pickup_datetime AS DATE) AS trip_date,
    taxi_type,
    payment_type_name AS payment_type,
    COUNT(*) AS trips,
    SUM(fare_amount) AS total_fare,
    AVG(fare_amount) AS avg_distance
FROM staging.trips
WHERE pickup_datetime >= '{{ start_datetime }}'
  AND pickup_datetime < '{{ end_datetime }}'
GROUP BY 1, 2, 3