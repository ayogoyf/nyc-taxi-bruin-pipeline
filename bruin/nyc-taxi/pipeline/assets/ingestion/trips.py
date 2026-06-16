"""@bruin
name: ingestion.trips
type: python
image: python:3.11
connection: gcp-default

materialization:
  type: table
  strategy: append

columns:
  - name: pickup_datetime
    type: timestamp
    description: "When the trip was picked up."
  - name: dropoff_datetime
    type: timestamp
    description: "When the trip was dropped off."
  - name: passenger_count
    type: integer
    description: "Number of passengers on the trip."
  - name: trip_distance
    type: float
    description: "Distance of the trip in miles."
  - name: payment_type
    type: integer
    description: "Payment type identifier."
  - name: fare_amount
    type: float
    description: "Fare amount in USD."
  - name: vendor_id
    type: integer
    description: "Vendor identifier for the taxi provider."
  - name: pickup_location_id
    type: integer
    description: "Pickup location ID."
  - name: dropoff_location_id
    type: integer
    description: "Dropoff location ID."
  - name: taxi_type
    type: string
    description: "Taxi service type, e.g. yellow or green."
  - name: extracted_at
    type: timestamp
    description: "UTC timestamp when the source batch was ingested."
@bruin"""

import io
import json
import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests

SOURCE_BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"


def _load_env_date(name: str, default: Optional[str] = None) -> str:
  """Load a date from the environment or return the provided default.

  If neither is available, raise a ValueError to preserve previous behavior.
  """
  value = os.environ.get(name)
  if value:
    return value
  if default is not None:
    return default
  raise ValueError(f"Missing required environment variable: {name}")


def _load_taxi_types() -> list[str]:
    raw_vars = os.environ.get("BRUIN_VARS", "{}")
    try:
        vars_json = json.loads(raw_vars)
    except json.JSONDecodeError as exc:
        raise ValueError("BRUIN_VARS must be valid JSON") from exc

    taxi_types = vars_json.get("taxi_types")
    if taxi_types is None:
        return ["yellow"]
    if not isinstance(taxi_types, list) or not all(isinstance(value, str) for value in taxi_types):
        raise ValueError("BRUIN_VARS.taxi_types must be an array of strings")
    return taxi_types


def _build_month_list(start_date: str, end_date: str) -> list[str]:
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    if end < start:
        raise ValueError("BRUIN_END_DATE must be greater than or equal to BRUIN_START_DATE")

    if end.day == 1:
        end = end - pd.Timedelta(days=1)

    return [dt.strftime("%Y-%m") for dt in pd.date_range(start=start, end=end, freq="MS")]


def _download_parquet(source_url: str) -> pd.DataFrame:
    response = requests.get(source_url, stream=True, timeout=(10, 120))
    response.raise_for_status()
    return pd.read_parquet(io.BytesIO(response.content))


def materialize() -> pd.DataFrame:
    # Default to loading the 2022 calendar year for local/dev runs when env vars are not provided.
    start_date = _load_env_date("BRUIN_START_DATE", "2022-01-01")
    end_date = _load_env_date("BRUIN_END_DATE", "2022-12-31")
    taxi_types = _load_taxi_types()
    months = _build_month_list(start_date, end_date)

    frames: list[pd.DataFrame] = []
    extracted_at = datetime.now(timezone.utc)
    for taxi_type in taxi_types:
        for month in months:
            source_file = f"{taxi_type}_tripdata_{month}.parquet"
            source_url = f"{SOURCE_BASE_URL}/{source_file}"
            print(f"Fetching {source_url}")
            try:
                df = _download_parquet(source_url)
            except requests.exceptions.HTTPError as exc:
                # If a file is not found (404) or other HTTP error occurs, skip it and continue.
                print(f"Warning: failed to fetch {source_url}: {exc}")
                continue
            except requests.exceptions.RequestException as exc:
                # Network or timeout errors - surface as warnings and continue so other files can run.
                print(f"Warning: network error fetching {source_url}: {exc}")
                continue

            # Normalize common column names from NYC TLC parquet files to our canonical schema
            rename_map = {}
            # Datetime columns
            if "tpep_pickup_datetime" in df.columns:
              rename_map["tpep_pickup_datetime"] = "pickup_datetime"
            if "tpep_dropoff_datetime" in df.columns:
              rename_map["tpep_dropoff_datetime"] = "dropoff_datetime"
            # Location ID columns (different capitalizations in various datasets)
            if "pu_location_id" in df.columns:
              rename_map["pu_location_id"] = "pickup_location_id"
            if "do_location_id" in df.columns:
              rename_map["do_location_id"] = "dropoff_location_id"
            if "PULocationID" in df.columns:
              rename_map["PULocationID"] = "pickup_location_id"
            if "DOLocationID" in df.columns:
              rename_map["DOLocationID"] = "dropoff_location_id"
            # Vendor and fare/payment
            if "VendorID" in df.columns:
              rename_map["VendorID"] = "vendor_id"
            if "fare_amount" not in df.columns and "total_amount" in df.columns:
              rename_map["total_amount"] = "fare_amount"

            if rename_map:
                df = df.rename(columns=rename_map)

            # Ensure datetime types for pickup/dropoff
            if "pickup_datetime" in df.columns:
                df["pickup_datetime"] = pd.to_datetime(df["pickup_datetime"], errors="coerce")
            if "dropoff_datetime" in df.columns:
                df["dropoff_datetime"] = pd.to_datetime(df["dropoff_datetime"], errors="coerce")

            df["taxi_type"] = taxi_type
            df["extracted_at"] = extracted_at

            expected_columns = [
                "pickup_datetime",
                "dropoff_datetime",
                "passenger_count",
                "trip_distance",
                "payment_type",
                "fare_amount",
                "vendor_id",
                "pickup_location_id",
                "dropoff_location_id",
                "taxi_type",
                "extracted_at",
            ]

            for col in expected_columns:
                if col not in df.columns:
                    df[col] = pd.NA

            df = df[expected_columns]
            frames.append(df)

    if not frames:
        # Return an empty DataFrame with expected schema so downstream assets see consistent columns.
        cols = [
            "pickup_datetime",
            "dropoff_datetime",
            "passenger_count",
            "trip_distance",
            "payment_type",
            "fare_amount",
            "vendor_id",
            "pickup_location_id",
            "dropoff_location_id",
            "taxi_type",
            "extracted_at",
        ]
        return pd.DataFrame(columns=cols)

    return pd.concat(frames, ignore_index=True)
