# Feature Spec: Data Catalog

## Purpose
Maintains a registry of available data sources (MySQL databases, local files) that agents
query to understand what data is available. Shared org-wide. Populated manually by users;
auto-scan is future scope.

## User-Facing Behaviour

### Adding a data source
1. User navigates to `/catalog` in the UI
2. Clicks "Add Data Source"
3. Selects type: MySQL or File
4. **MySQL:** enters host, port, database name, username, password
5. **File:** enters absolute path to directory containing flat files
6. Clicks "Test Connection" — system verifies connectivity before saving
7. On success: source appears in catalog list with status "not yet scanned"

### Scanning a data source
1. User clicks "Scan" on a data source (or "Scan All")
2. System connects to the source and inspects its schema
3. Progress shown inline — "Scanning tables..." with a spinner
4. On completion: tables appear under the source with column metadata, row count estimates, sample values
5. `last_scanned_at` updates on the source record

### Using the catalog in an analysis
- When creating a new analysis, user can optionally select specific data sources from the catalog
- If none selected, all active sources are passed to the Analyzer agent
- Catalog entries (table names, columns) are pre-fetched and passed to agents at session start — agents do not query the catalog DB directly

## Technical Implementation

### Connection test endpoint
Before saving a data source, `POST /catalog/test-connection` verifies:
- **MySQL:** `SELECT 1` via SQLAlchemy — timeout 5s. [LOCKED] Also enforces that the
  supplied credentials are read-only: query `SHOW GRANTS FOR CURRENT_USER()` and reject
  (400, "MySQL user must be read-only — grants include write privileges") if any grant
  includes `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, or `TRUNCATE` (or `ALL
  PRIVILEGES`). This was previously "documented but not enforced" — now a hard gate,
  since Coder-generated SQL has no other mechanism stopping a write statement from
  reaching a writable database (see `specs/agents/coder.md`).
- **File:** `os.path.isdir(path)` and read permission check

### Credential storage
MySQL passwords are encrypted at rest using **Fernet symmetric encryption** (`cryptography` library).
- Encryption key stored in `DATABASE_ENCRYPTION_KEY` env var
- Stored in `data_sources.connection_config` as `{"host": ..., "encrypted_password": "<fernet_token>"}`
- Decrypted in-memory only when needed for scans or agent execution
- Never returned in API responses

### MySQL scanner (`catalog/scanner.py`)
```python
def scan_mysql_source(data_source: DataSource) -> list[CatalogTable]:
    engine = create_engine(decrypt_connection_string(data_source))
    inspector = inspect(engine)
    tables = []
    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        row_count = engine.execute(f"SELECT COUNT(*) FROM `{table_name}`").scalar()
        sample = engine.execute(f"SELECT * FROM `{table_name}` LIMIT 5").fetchall()
        tables.append(CatalogTable(
            table_name=table_name,
            column_metadata=[{
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col["nullable"],
                "sample_values": [row[col["name"]] for row in sample if col["name"] in row]
            } for col in columns],
            row_count_estimate=row_count,
        ))
    return tables
```

### File scanner (`catalog/scanner.py`)
- Walks the registered directory (non-recursive by default, configurable)
- Supported extensions: `.csv`, `.xlsx`, `.xls`, `.tsv`, `.json`, `.parquet`
- For each file: reads headers + 5 rows using pandas (CSV/Excel) or pyarrow (parquet)
- Stores column names, inferred dtypes, sample values in `column_metadata`
- Files > 500MB: stores headers only, marks `row_count_estimate: null`

### Upsert logic
On each scan, tables are upserted by `(data_source_id, schema_name, table_name)`:
- New tables → INSERT
- Existing tables → UPDATE `column_metadata`, `row_count_estimate`, `scanned_at`
- Tables no longer present → soft-delete (mark `active: false`) — not hard-deleted

### Agent integration
At `POST /api/v1/analyses`, the API pre-fetches catalog entries for the requested `data_source_ids` and stores them in the LangGraph session state. Agents receive this context directly — they do not make DB calls to the catalog.

## Data Model (from database-schema.sql)
- `data_sources` — one row per registered source
- `catalog_tables` — one row per discovered table/file, FK to data_sources

## Error Handling
| Error | Behaviour |
|---|---|
| MySQL connection refused | `POST /catalog/test-connection` returns 400 with message |
| MySQL user has write grants | `POST /catalog/test-connection` returns 400, source not saved |
| MySQL timeout during scan | Table marked with `error: "timeout"` in column_metadata, scan continues |
| File not found at scan time | Table soft-deleted, user notified in scan result |
| Credential decryption failure | 500 error with "credential configuration error" — no sensitive detail exposed |
| Unsupported file extension | Skipped silently, counted in `ScanResult.errors` |

## Security Rules
- Connection credentials MUST NOT appear in API responses
- Connection credentials MUST NOT appear in logs
- [LOCKED] MySQL user used for scanning MUST be read-only — enforced at
  `POST /catalog/test-connection` via grant inspection (see above), not just documented
- File scanner MUST NOT follow symlinks outside the registered directory

## Test Scenarios

### Unit
- MySQL scanner produces correct CatalogTable with column names and types
- File scanner correctly parses CSV headers and sample values
- Large file (>500MB) stores headers only with null row_count
- Upsert: existing table → column_metadata updated, not duplicated
- Upsert: removed table → soft-deleted, not hard-deleted
- Encrypted password is not returned in DataSource API response

### Integration (real MySQL + Docker)
- Full scan of test MySQL fixture produces correct schema
- Test connection returns 400 for wrong credentials
- Re-scan after adding a column to test fixture → column_metadata updated
- File scan of test directory correctly lists CSV and Excel files with headers
