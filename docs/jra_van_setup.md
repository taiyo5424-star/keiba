# JRA-VAN Data Lab. setup notes

This project is built around JRA-VAN Data Lab. as the practical data source for JRA official racing data.

## Current confirmed cost

- JRA-VAN Data Lab.: 2,090 JPY/month including tax
- Official page mentions a one-month free trial
- Payment/signup is intentionally left to the user

Official pages:

- https://jra-van.jp/dlb/
- https://developer.jra-van.jp/

## Practical constraints

- Data Lab. is a Windows PC-oriented service.
- JV-Link is the basic client software used by many third-party tools.
- A local registration key/subscription is required for actual data access.
- Python automation usually needs a Windows COM bridge such as `pywin32`.
- This repository keeps the JRA-VAN extraction boundary isolated so signup/install can happen later without changing the EV pipeline.

## Planned ingestion boundary

Raw JRA-VAN data should be exported into normalized CSV files under `data/jra_van_exports/`.

Minimum useful files:

- `races.csv`
- `starts.csv`
- `odds_snapshots.csv`
- `results.csv`
- `payouts.csv`

The modeling and EV scripts should only depend on normalized CSVs, not directly on JV-Link. This makes backtests reproducible and keeps paid-data access separate from model logic.
