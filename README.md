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

## Design

See [docs/design.md](docs/design.md) for the proposed data flow, validation rules, and open assumptions.

## Database schema

[`sql/schema.sql`](sql/schema.sql) defines the proposed Snowflake landing, staging, current-member, and redemption tables. The SQL is a starting point; the transformation and validation logic are still to come. Snowflake standard-table uniqueness constraints are not enforced, so the pipeline must check keys explicitly.
