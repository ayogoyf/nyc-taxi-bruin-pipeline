/* @bruin
name: staging.trips
type: bq.sql

depends:
  - ingestion.trips
  - ingestion.payment_lookup

materialization:
  type: table

columns:
  - name: pickup_datetime
    type: timestamp
    primary_key: true
    checks:
      - name: not_null
  - name: dropoff_datetime
    type: timestamp
  - name: passenger_count
    type: integer
  - name: trip_distance
    type: float
  - name: payment_type
    type: integer
  - name: fare_amount
    type: float
  - name: vendor_id
    type: integer
  - name: pickup_location_id
    type: integer
  - name: dropoff_location_id
    type: integer
  - name: taxi_type
    type: string
  - name: extracted_at
    type: timestamp
  - name: payment_type_name
    type: string

custom_checks:
  - name: row_count_greater_than_zero
    query: |
      SELECT CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END
      FROM staging.trips
    value: 1
@bruin */

SELECT
    t.pickup_datetime AS pickup_datetime,
    t.dropoff_datetime AS dropoff_datetime,
    t.passenger_count,
    t.trip_distance,
    t.payment_type,
    t.fare_amount,
    t.vendor_id,
    t.pickup_location_id,
    t.dropoff_location_id,
    t.taxi_type,
    t.extracted_at,
    p.payment_type_name
FROM ingestion.trips t
LEFT JOIN ingestion.payment_lookup p
    ON t.payment_type = p.payment_type_id
WHERE t.pickup_datetime >= '{{ start_datetime }}'
  AND t.pickup_datetime < '{{ end_datetime }}'
  AND t.fare_amount >= 0
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY t.pickup_datetime, t.dropoff_datetime,
                 t.pickup_location_id, t.dropoff_location_id, t.fare_amount
    ORDER BY t.pickup_datetime
) = 1