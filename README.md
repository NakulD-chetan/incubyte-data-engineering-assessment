# SkyPoints Data Pipeline

A data engineering assessment for a global airline loyalty program. The goal is to process member profiles and mileage redemption transactions, validate the data, and maintain country-specific member tables.

## Project status

Initial setup. The pipeline, database schemas, and tests are still to be implemented.

## Sample data

The `data/samples` directory contains the supplied sample member files for India, the USA, and Australia. They have different headers and date formats; the Australian sample also contains an invalid date. These examples will help guide validation and tests.

## Planned work

- Define landing, staging, country-specific, and redemption tables.
- Normalize and validate member profiles, derive age and stale-member status, and route the latest member record to the appropriate country.
- Flatten the JSON redemption feed and link it to member profiles.
- Add tests and document how to run the pipeline and scale the design.
