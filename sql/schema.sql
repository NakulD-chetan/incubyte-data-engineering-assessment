-- Snowflake-oriented schema. Apply in a selected database and schema.
-- Raw payloads are kept for replay and investigation.
CREATE TABLE IF NOT EXISTS raw_feed (
    feed_id VARCHAR(128) NOT NULL,
    source_name VARCHAR(100) NOT NULL,
    file_name VARCHAR(1000) NOT NULL,
    feed_type VARCHAR(20) NOT NULL, -- MEMBER or REDEMPTION
    feed_date DATE NOT NULL,
    ingested_at TIMESTAMP_NTZ NOT NULL,
    row_number NUMBER(38, 0) NOT NULL,
    payload VARIANT NOT NULL
);

-- A staging row retains its source location and any validation errors.
-- Derived values are calculated using processing_date for reproducible runs.
CREATE TABLE IF NOT EXISTS staged_member (
    feed_id VARCHAR(128) NOT NULL,
    row_number NUMBER(38, 0) NOT NULL,
    processing_date DATE NOT NULL,
    member_id VARCHAR(18),
    member_name VARCHAR(255),
    enrollment_date DATE,
    last_flight_date DATE,
    tier_code VARCHAR(5),
    agent_name VARCHAR(255),
    state VARCHAR(5),
    country VARCHAR(5),
    post_code VARCHAR(5),
    date_of_birth DATE,
    active_member VARCHAR(1),
    source_updated_at TIMESTAMP_NTZ,
    age NUMBER(3, 0),
    stale_member BOOLEAN,
    validation_errors ARRAY
);

-- Current member tables share a layout. A global member ID and a source
-- ordering field are required to resolve moves safely; see docs/design.md.
CREATE TABLE IF NOT EXISTS table_india (
    member_id VARCHAR(18) NOT NULL,
    member_name VARCHAR(255) NOT NULL,
    enrollment_date DATE NOT NULL,
    last_flight_date DATE,
    tier_code VARCHAR(5),
    agent_name VARCHAR(255),
    state VARCHAR(5),
    country VARCHAR(5) NOT NULL,
    post_code VARCHAR(5),
    date_of_birth DATE,
    active_member VARCHAR(1),
    source_updated_at TIMESTAMP_NTZ NOT NULL,
    age NUMBER(3, 0),
    stale_member BOOLEAN,
    processing_date DATE NOT NULL,
    feed_id VARCHAR(128) NOT NULL,
    row_number NUMBER(38, 0) NOT NULL
);

CREATE TABLE IF NOT EXISTS table_usa LIKE table_india;
CREATE TABLE IF NOT EXISTS table_australia LIKE table_india;

-- Keep transactions even when a matching member has not arrived yet.
CREATE TABLE IF NOT EXISTS redemption_transaction (
    transaction_id VARCHAR(128) NOT NULL,
    member_id VARCHAR(18) NOT NULL,
    feed_date DATE NOT NULL,
    transaction_date DATE NOT NULL,
    partner VARCHAR(255) NOT NULL,
    miles_redeemed NUMBER(38, 0) NOT NULL,
    status VARCHAR(32) NOT NULL,
    feed_id VARCHAR(128) NOT NULL,
    row_number NUMBER(38, 0) NOT NULL
);
