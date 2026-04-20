# ADR 003: Metadata & Core Storage Engine Selection

## Status
Accepted

## Context
When managing distributed text fragments spanning thousands of source files, relying on raw JSON metadata coupled natively within Vector Stores induces severe overhead during transactional querying (e.g. document deletions, hash tracking). DeepVault requires a relational mapping to enforce ACID compliance for indexing states (hashes, chunk ranges), without compromising execution velocities.

## Decision
We elected to utilize **SQLite** directly orchestrated by standard PyDantic mappings via local `.db` files during Phase 1 deployment, effectively deferring PostgreSQL integration to Phase 4.

## Rationale
1. **Low Configuration Overhead**: SQLite provides ACID guarantees with absolutely zero configuration networks dynamically requiring `100%` container uptime. This drastically elevates local developer capability workflows mathematically.
2. **Hash-Based Duplicate Deduplication**: Using a standard relational index across `.hash` attributes allows lightning-fast `SELECT` sweeps to prevent duplicating ingestions across large static datasets mechanically. 
3. **Graceful Degration**: SQLite safely interfaces via asynchronous queues mapping localized environments seamlessly while scaling.

## Consequences
- **Positive**: We natively isolated semantic document ingestion logic tracking mechanically on a 1:N relational graph.
- **Negative (Mitigated)**: Concurrent asynchronous write operations naturally induce file-locks across SQLite. We natively circumvented this by pushing heavy pipeline jobs to HTTP async pools instead of local command-line CLI sweeps. 
- **Future Implication**: In scaling Phase 4, the architecture logically swaps SQLite for Dockerized `PostgreSQL` instances mechanically utilizing `psycopg2` via the established `BaseDocumentStore` interfaces.
