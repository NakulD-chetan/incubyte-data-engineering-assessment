# Incubyte Data Engineering Assessment

This project processes member data for the SkyPoints airline loyalty program. It reads member profiles and redemption transactions, checks the data, and keeps each member in their latest country.

The project includes a local SQLite demo, tests, and proposed Snowflake table definitions. Python 3 is the only requirement for the local demo.

## Run the demo

From the project folder, run:

```sh
python3 -m unittest discover -s tests -v
python3 -m skypoints.pipeline demo.sqlite
```

The demo loads example members and redemptions into `demo.sqlite`. One member moves from India to the USA. A redemption with no matching member is kept for review. You can run the command again without creating duplicates.

## Try the supplied member files

To check a file without loading it:

```sh
python3 -m skypoints.members australia data/samples/australia.csv --processing-date 2023-01-01
```

Use `india`, `usa`, or `australia` with the matching file. The command prints each record and any errors. It returns exit code 1 if a record has an error and 2 for a file-level error. The Australian sample contains an invalid enrollment date. Some USA dates can have more than one meaning; the program reports them instead of guessing.

To load a sample file into SQLite:

```sh
python3 -m skypoints.ingest india data/samples/india.csv demo.sqlite --feed-id india-example --processing-date 2024-02-03 --source-updated-at 2024-01-01T00:00:00+00:00 --assume-global-ids
```

The supplied samples do not establish global member IDs or update timestamps. The command above uses those values as demo assumptions. A real source must supply them.

## Try the pipe-delimited feed

The assessment also describes a file with a header and detail records. An example is in `data/demo/member_feed.psv`:

```sh
python3 -m skypoints.ingest flat data/demo/member_feed.psv demo.sqlite --feed-id flat-example --processing-date 2024-02-03 --source-updated-at 2024-01-01T00:00:00+00:00 --assume-global-ids
```

The loader stores the original file, saves invalid rows with their errors, and stages valid rows. A file with a broken header is kept with a failed status. The example treats DOB as `MMDDYYYY` and the other dates as `YYYYMMDD`, as shown in the assessment. The header omits postcode even though the field list includes it, so this reader does not parse postcode. India, the USA, and Australia are supported; other countries are rejected for review.

## Load a redemption file

```sh
python3 -m skypoints.ingest_redemptions data/demo/redemption_feed.json demo.sqlite --feed-id redemption-example
```

Each transaction becomes a row. The loader keeps pending transactions and saves the original file even if validation fails. It accepts an exact retry and rejects conflicting data for the same transaction ID. Transactions can be joined to current members by member ID; unmatched transactions remain in the database.

## How the data is stored

- `landed_file` keeps the original file bytes and load status.
- `rejected_record` holds invalid member rows and their errors.
- `staged_member` holds valid member rows, age, and stale-member status.
- `current_member` holds one current profile per member. Country views show the members in each country.
- `redemption_transaction` holds transactions. `redemption_observation` records which feeds contained them.

Age and stale status are calculated for the processing date. A member is stale when their last flight was more than 90 days before that date. Missing optional dates produce an unknown value.

## Design and limits

See [docs/design.md](docs/design.md) for the data flow, assumptions, and scaling approach. The proposed Snowflake tables are in [sql/schema.sql](sql/schema.sql); they have not been tested in Snowflake.

SQLite makes the solution easy to run locally, but it is not intended to process billions of records per day. For production, the design needs distributed storage and processing, source-provided ordering and IDs, monitoring, and a rule for versioning transaction status changes.
