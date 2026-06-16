# NYC Taxi Data Platform (Bruin + BigQuery)

An end-to-end ELT pipeline for NYC TLC taxi trip data, built with [Bruin](https://getbruin.com). It ingests raw parquet trip files from the TLC public endpoint, cleans and deduplicates them, and produces aggregated reporting tables. Local development runs against DuckDB; production runs against BigQuery, with the warehouse resources provisioned through Terraform.

I went with Bruin instead of stitching together a separate ingestion tool, dbt, an orchestrator, and a data quality framework. For a pipeline this size, one tool that handles ingestion, transformation, dependency resolution, and checks in version-controlled text is less moving parts to maintain and reason about. The trade-offs would change at larger scale, but here the single-tool approach kept the project tight.

## Architecture

Three layers, executed as a DAG in dependency order:

```
ingestion  →  staging  →  reports
```

- **Ingestion** pulls raw trip parquet files from the TLC endpoint (Python) and loads a static payment-type lookup from CSV (seed). Raw data lands untouched, no cleaning, so the source of truth is preserved and any transformation bug can be replayed from raw.
- **Staging** cleans, deduplicates, and enriches the raw trips by joining the payment lookup.
- **Reports** aggregates the staged data by date, taxi type, and payment type into analytics-ready tables.

Splitting it this way means each layer has one job, and a change in business logic only touches the layer that owns it.

## Design decisions worth calling out

**Materialization strategy per layer.** Ingestion uses `append`, since raw files arrive immutable and duplicates get resolved downstream. Staging and reports use `time_interval` keyed on `pickup_datetime`, so a given month can be reprocessed by deleting and re-inserting just that date range instead of rebuilding the whole table. Same incremental key flows through both layers so the data stays consistent end to end.

**Deduplication without a natural key.** TLC data has no unique trip ID, so I dedupe on a composite key (`pickup_datetime`, `dropoff_datetime`, `pickup_location_id`, `dropoff_location_id`, `fare_amount`) using `ROW_NUMBER()` to keep one row per trip. It's not perfect, two genuinely identical trips would collapse, but it's the pragmatic choice given the data.

**Infrastructure as code.** The BigQuery datasets and related resources are defined in Terraform (`bruin-infras/`) rather than clicked together in the console. Anyone can stand up the same warehouse layout from scratch, and teardown is clean.

**Dev/prod parity.** The same pipeline definition runs locally on DuckDB and in the cloud on BigQuery. Only the connection and a few SQL dialect details change between environments, so most iteration happens locally and fast.

**Quality checks as part of the build, not an afterthought.** Column-level checks (`not_null`, `non_negative`, `accepted_values`, etc.) are declared alongside the assets and run as part of the pipeline, so a bad load fails loudly instead of silently feeding bad data downstream.

## Project layout

```
.
├── bruin/
│   └── nyc-taxi/
│       └── pipeline/
│           ├── pipeline.yml
│           └── assets/
│               ├── ingestion/
│               │   ├── trips.py                 # Python ingestion from TLC endpoint
│               │   ├── requirements.txt
│               │   ├── payment_lookup.asset.yml  # Seed asset
│               │   └── payment_lookup.csv
│               ├── staging/
│               │   └── trips.sql                 # Clean, dedupe, enrich
│               └── reports/
│                   └── trips_report.sql          # Aggregations
└── bruin-infras/                                 # Terraform for BigQuery resources
    ├── main.tf
    └── variables.tf
```

`.bruin.yml` (connections/credentials) and the service account key are gitignored.

## Running it

Install the Bruin CLI, then from the project root:

```bash
# Validate before running, much faster than a full run
bruin validate ./bruin/nyc-taxi/pipeline/pipeline.yml

# Local dev run, one month, yellow only, to keep it fast
bruin run ./bruin/nyc-taxi/pipeline/pipeline.yml \
  --full-refresh \
  --start-date 2022-01-01 \
  --end-date 2022-02-01 \
  --var 'taxi_types=["yellow"]'

# Inspect results
bruin query --connection duckdb-default \
  --query "SELECT COUNT(*) FROM staging.trips"
```

The parquet files are large (hundreds of MB per month), so develop against 1-3 months, then backfill the full range once the pipeline is solid. TLC data isn't available past November 2025, so keep date ranges before then.

## Provisioning the warehouse

```bash
cd bruin-infras
terraform init
terraform apply
```

This creates the `ingestion`, `staging`, and `reports` datasets in BigQuery. Point `.bruin.yml` at the GCP connection and switch the asset types from `duckdb.sql`/`duckdb.seed` to `bq.sql`/`bq.seed` to run against the cloud. Watch for DuckDB vs BigQuery dialect differences (type names like `INTEGER` vs `INT64`, timestamp handling) when you make the switch.

## Notes

TLC trip data has real quality quirks, zero-fare trips, null vendor IDs, occasional out-of-range timestamps, which is part of why the staging layer and quality checks matter. The pipeline is built to surface those rather than quietly pass them through.