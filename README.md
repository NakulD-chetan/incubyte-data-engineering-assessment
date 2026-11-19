# SkyPoints Data Pipeline

A data engineering assessment for a global airline loyalty program. The goal is to process member profiles and mileage redemption transactions, validate the data, and maintain country-specific member tables.

## Project status

A runnable SQLite demonstration, Snowflake-oriented schema, and tests are available. The distributed production design is documented but not deployed.

## Sample data

The `data/samples` directory contains the supplied sample member files for India, the USA, and Australia. They have different headers and date formats; the Australian sample also contains an invalid date. These examples will help guide validation and tests.

## Assessment scope

- Define landing, staging, country-specific, and redemption tables.
- Normalize and validate member profiles, derive age and stale-member status, and route the latest member record to the appropriate country.
- Flatten the JSON redemption feed and link it to member profiles.
- Add tests and document how to run the pipeline and scale the design.

## Design

See [docs/design.md](docs/design.md) for the proposed data flow, validation rules, and open assumptions.

## Database schema

[`sql/schema.sql`](sql/schema.sql) defines the proposed Snowflake landing, staging, current-member, and redemption tables. The SQL describes the intended warehouse tables; the runnable implementation uses SQLite. Snowflake standard-table uniqueness constraints are not enforced, so the pipeline must check keys explicitly.

## Try member validation

Python 3 is the only requirement for this step. From the project directory:

```sh
python3 -m unittest discover -s tests -v
python3 -m skypoints.members australia data/samples/australia.csv --processing-date 2023-01-01
```

Choose `india`, `usa`, or `australia` and the matching sample file. The command prints each normalized record and its validation errors as JSON. It returns exit code 1 if any records have errors, and 2 if the file cannot be read or has the wrong columns. The processing date makes age and stale-member calculations repeatable. USA dates that have more than one valid interpretation are reported as ambiguous instead of guessed.

This validation command reads files into memory and prints results. The separate database-backed loader below handles persistence and member updates.

## Latest member profiles

`skypoints.current_members.resolve_members` selects one current profile per global member ID using a source update timestamp. A newer profile in another country replaces the old one. Identical replays are accepted; conflicting profiles with the same timestamp are rejected. Timestamps must include a timezone. The SQLite loader applies the same ordering and conflict rules when publishing members. The supplied samples lack global IDs and update timestamps, so they cannot safely demonstrate country moves without additional source information.

## Redemption feeds

`skypoints.redemptions.flatten_feed` validates a partner JSON object and returns one row per transaction. It preserves pending transactions, removes exact duplicate transactions within a feed, and rejects conflicting duplicates or invalid input. An invalid transaction rejects the whole feed; the caller must retain it for investigation. `join_current_members` joins rows to current profiles by member ID and retains unmatched transactions. The SQLite loader also checks transaction uniqueness across feeds and persists the resulting rows.

## Run the demonstration

```sh
python3 -m skypoints.demo
```

The JSON output reports validation results for the supplied country files as of 2023-01-01. It then uses separately labeled synthetic events in `data/demo` to show a member moving from India to the USA, a matched redemption, and an unmatched redemption. These events are illustrative: they are not inferred from the sample files. The demo runs in memory and does not write to Snowflake.

## Database-backed local run

The Python standard library provides SQLite; no installation or cloud account is needed:

```sh
python3 -m skypoints.pipeline demo.sqlite
python3 -m unittest discover -s tests -v
```

This loads synthetic member updates and redemption feeds into persistent landing, staging, current-member, and transaction tables. Country views expose the current members by country. Running it again replays the same feeds safely. A transaction joins to the current member with a left join, so an unmatched member stays visible.

To load valid rows from a supplied country CSV, the loader requires an update timestamp and explicit confirmation that IDs are global. The examples do **not** establish either fact; the following is only a local demonstration assumption:

```sh
python3 -m skypoints.ingest india data/samples/india.csv demo.sqlite --feed-id india-example --processing-date 2024-02-03 --source-updated-at 2024-01-01T00:00:00+00:00 --assume-global-ids
```

The loader preserves original file bytes in `landed_file` and row-level errors in `rejected_record`; accepted records retain their original line numbers in staging. A structural file failure leaves the original file marked as failed. Valid records publish atomically; exact feed replays are safe.

To load the specified pipe-delimited header/detail format:

```sh
python3 -m skypoints.ingest flat data/demo/member_feed.psv demo.sqlite --feed-id flat-example --processing-date 2024-02-03 --source-updated-at 2024-01-01T00:00:00+00:00 --assume-global-ids
```

The pipe example uses `YYYYMMDD` for enrollment and flight dates and `MMDDYYYY` for DOB, matching the assessment examples. Its header omits postcode although the field table lists it, so postcode is not parsed. Only India, USA, and Australia have configured destinations; other country codes are quarantined until their tables and mapping are agreed. A production source must provide actual update ordering and globally unique IDs rather than the demo assumptions.

The SQLite implementation uses a single current-member table with country views to enforce one current location. The Snowflake DDL instead describes physical country tables. SQLite is for the local demonstration and is not a solution for billions of daily records; production would require the distributed design in `docs/design.md`. Snowflake SQL has not been executed against a Snowflake account. Transaction status changes with the same transaction ID are treated as conflicts until the source defines versioning rules.
