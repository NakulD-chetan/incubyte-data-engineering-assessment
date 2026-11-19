# Pipeline design

## What the pipeline needs to do

The source sends member profiles and redemption transactions each day. We need to keep a current member profile in the right country table and make redemption transactions available for analysis. The input files in this repository are small examples; they are not a measure of the production volume.

## Data flow

1. **Landing:** Keep the original input and its source, file name, feed date, and ingestion time. This makes it possible to investigate and replay a file.
2. **Staging:** Map source-specific fields to a common member format. Parse dates, validate records, and calculate age and stale-member status using a supplied processing date. Keep rejected records with a reason.
3. **Current members:** Select the latest valid profile for each member and put it in the matching country table. When a member changes country, remove the previous current profile from the old country table as part of the same update.
4. **Redemptions:** Flatten each JSON redemption array into transaction rows. Join transactions to the current profile on member ID; retain transactions that do not yet have a matching member for later reconciliation.

## Assumptions to confirm

- **Member identity:** The specification marks member name as a key, but names can be shared or changed. We will use a globally unique member ID as the business key and check uniqueness. The sample country files reuse IDs, so they cannot establish that the same ID in different files identifies the same person. A real source must provide a global ID or a mapping before country moves can be resolved safely.
- **Latest record:** Use a source-provided update timestamp or sequence, with a deterministic tie-breaker. Feed date and file position alone do not reliably establish when a profile changed. The sample files do not include an update timestamp, so any demonstration using them must state its ordering assumption.
- **Dates:** Parse each source according to its documented format. The USA sample uses compact dates of varying lengths; the exact format must be agreed with the source, since some values can be ambiguous. Invalid dates are rejected rather than guessed. Optional missing dates remain null.
- **Derived values:** Age is the number of completed years on the processing date. A member is stale when their last flight was more than 90 days before that date. If date of birth or flight date is missing, the corresponding derived value is unknown.
- **Transactions:** Assume transaction IDs are unique across partner feeds; if that is not guaranteed, use an agreed partner and transaction ID key. Preserve transaction status, including pending transactions.
- **Countries:** Country comes from the record or trusted source-file metadata. The three supplied country files do not contain a country column. Unknown countries require an explicit handling rule and should not silently enter a known country table.

## Validation

Check required member name, ID, and enrollment date; valid dates and field lengths; supported country values; and duplicate or conflicting keys. Validate redemption fields, transaction IDs, dates, and non-negative miles. Reject or quarantine invalid records with enough context to investigate, and count accepted, rejected, and duplicate records for each run.

## Scale and reliability

For billions of daily records, store immutable input files in object storage and process them with a distributed engine or cloud warehouse in batches. Partition input by feed date and source, and use bulk operations rather than one database request per row. Use idempotent loads, run-level counts, monitoring, and safe retries. Country moves and updates need an atomic publish step so a member is not current in two countries at once. The local implementation will demonstrate the rules on sample data; it will not by itself prove production-scale throughput.

## Table definitions

The initial Snowflake DDL is in `sql/schema.sql`. Raw input is stored in a `VARIANT` payload with source metadata. Staging holds normalized fields, derived values, and validation errors. The country tables hold current profiles, and the redemption table holds flattened transactions. Postcodes are stored as text to preserve leading zeroes. Snowflake standard-table primary and unique constraints do not enforce uniqueness, so the load must validate keys and resolve updates explicitly.
