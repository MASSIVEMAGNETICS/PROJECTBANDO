# PROJECTBANDO

## VictorVault

VictorVault is a local-first ingestion and observer system for TabTimeMachine. It processes browser session snapshots with atomic writes, deduplication, and semantic analysis.

### Features

- **Local-First Ingestion**: Process `*_session.json` files (and optional `*_tabs.pdf`) from an inbox directory
- **Atomic Storage**: Copy files to `vault/YYYY/MM/DD/stamp/` with atomic temp->rename pattern
- **Smart Handling**: 
  - Quarantine malformed JSON files
  - Deduplicate by SHA256 hash
- **SQLite Index**: Fast metadata search across all sessions
- **Semantic Observer**: Uses portable_asi PortableShard with:
  - `text_to_vec`: Convert text to vector representations
  - `rank_sim`: Rank documents by similarity
  - Mission prototypes for categorization
  - NPZ checkpoint persistence
  - Feedback-driven learning

### Installation

Requires Python 3.11+

```bash
# No additional dependencies required - uses only Python stdlib and numpy
pip install numpy
```

### Usage

#### Configuration

The system uses `config.json` for configuration:

```json
{
  "base_path": ".",
  "inbox_dir": "inbox",
  "vault_dir": "vault",
  "quarantine_dir": "quarantine",
  "db_file": "victorvault.db",
  "checkpoint_file": "shard_checkpoint.npz",
  "watch_interval": 5
}
```

#### CLI Commands

**Ingest files from inbox:**
```bash
python victorvault_cli.py ingest
```

**Watch inbox continuously:**
```bash
python victorvault_cli.py watch --interval 5
```

**Search indexed sessions:**
```bash
python victorvault_cli.py search "github"
python victorvault_cli.py search "machine learning" --limit 20
```

**Export co-occurrence graph:**
```bash
python victorvault_cli.py export-graph --output graph.json
```

**Add feedback for learning:**
```bash
python victorvault_cli.py feedback 123 --score 0.9 --terms "python,github,api"
```

**Add mission prototype:**
```bash
python victorvault_cli.py add-mission "research" "academic papers and research documentation"
```

### Architecture

- **victorvault/ingestion.py**: File ingestion with atomic writes and deduplication
- **victorvault/index.py**: SQLite-based metadata index
- **victorvault/portable_asi.py**: Adaptive Semantic Index with text vectorization
- **victorvault/observer.py**: Semantic analysis and co-occurrence computation
- **victorvault/cli.py**: Command-line interface

### Data Flow

1. **Ingest**: `*_session.json` files placed in `inbox/`
2. **Validate**: JSON parsing and validation
3. **Deduplicate**: SHA256 hash checking
4. **Store**: Atomic copy to `vault/YYYY/MM/DD/stamp/`
5. **Index**: Extract metadata and tabs to SQLite
6. **Observe**: Semantic analysis with PortableShard
7. **Query**: Search and analyze stored sessions

### Session File Format

Expected JSON structure:
```json
{
  "tabs": [
    {
      "title": "Page Title",
      "url": "https://example.com"
    }
  ]
}
```

### Testing

Run the smoke test:
```bash
python test_victorvault.py
```
