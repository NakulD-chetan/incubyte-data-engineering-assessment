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

## Try member validation

Python 3 is the only requirement for this step. From the project directory:

```sh
python3 -m unittest discover -s tests -v
python3 -m skypoints.members australia data/samples/australia.csv --processing-date 2023-01-01
```

Choose `india`, `usa`, or `australia` and the matching sample file. The command prints each normalized record and its validation errors as JSON. It returns exit code 1 if any records have errors, and 2 if the file cannot be read or has the wrong columns. The processing date makes age and stale-member calculations repeatable. USA dates that have more than one valid interpretation are reported as ambiguous instead of guessed.

This command reads files into memory and does not yet write to the database, resolve duplicates, or move members between countries. It is a local demonstration, not the production-scale processing engine.

## Latest member profiles

`skypoints.current_members.resolve_members` selects one current profile per global member ID using a source update timestamp. A newer profile in another country replaces the old one. Identical replays are accepted; conflicting profiles with the same timestamp are rejected. Timestamps must include a timezone. This in-memory function illustrates the rule and is not yet connected to the file reader or database. The supplied samples lack global IDs and update timestamps, so they cannot safely demonstrate country moves without additional source information.
