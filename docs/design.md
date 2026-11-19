# Pipeline design

## Data flow

1. Save the incoming file before processing it. This allows a failed file to be inspected and retried.
2. Read and validate member records. Save invalid rows with their errors. Put valid rows in staging and calculate age and stale-member status for the processing date.
3. Use the member ID and source update time to choose the latest profile. Keep one current profile per member and show it in the matching country view.
4. Read each redemption JSON feed and save one row per transaction. Join transactions to members by ID, keeping transactions that do not yet have a match.

The local implementation uses SQLite. A single `current_member` table has one row per member, with views for India, the USA, and Australia. The country change and current profile update happen in one database transaction. Replaying the same feed is safe; conflicting data is rejected.

## Decisions and open questions

- **Member ID:** The field list marks member name as a key, but names can change or be shared. This solution uses member ID. The country samples reuse IDs, so the source must confirm whether IDs are globally unique or provide a mapping.
- **Latest record:** A country move requires a source update timestamp with a timezone. The sample files do not contain one. The demo supplies an example timestamp; a real feed must provide a reliable ordering field.
- **Dates:** Each source has its own format. Some USA dates are ambiguous, so they are rejected until the format is confirmed. Missing optional dates remain unknown. Age and stale status are snapshots for the processing date and need to be refreshed if current values are required later.
- **Country:** The country CSV files do not include a country field, so the loader takes it from the chosen file type. The pipe-delimited feed contains a country field. Only configured countries are loaded.
- **Redemptions:** The solution assumes transaction IDs are globally unique. It keeps pending transactions and rejects conflicting versions of an ID. The source must define how status changes are versioned. Unmatched transactions are retained.
- **Postcode:** The assessment's field list includes postcode, but its example header and detail rows do not. The pipe reader follows the example layout until the source confirms the field position.

## Data checks

The code checks required member fields, field lengths, dates, country values, and conflicting member updates. It also checks required transaction fields, dates, non-negative miles, and duplicate transaction IDs. Failed files and invalid member rows are available for review.

## Snowflake and scale

`sql/schema.sql` defines proposed landing, staging, country, and redemption tables for Snowflake. The SQL has not been run in a Snowflake account. The local SQLite loader implements the rules for small files; it is not a performance test.

For billions of records a day, use durable object storage for original feeds and a distributed engine or cloud warehouse for batch processing. Partition by feed date and source, load in bulk, and track counts and failures. Publish current members atomically, keep rejected data for investigation, and support safe retries. These are design recommendations, not features demonstrated at production scale here.
