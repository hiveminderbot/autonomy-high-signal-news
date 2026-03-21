# High-Signal News Deployment Guide

This document covers deploying the High-Signal News aggregation pipeline as a scheduled daily service.

## Overview

The aggregation pipeline can be run in two modes:
1. **Manual execution** - Run on-demand for testing or debugging
2. **Scheduled execution** - Run automatically via systemd timer (recommended)

## Prerequisites

- Python 3.11+
- SQLite 3.35+ (for FTS5 support)
- systemd (for scheduled execution)
- Network access to RSS feeds

## Installation

### 1. Clone and Setup

```bash
cd /home/autonomy/labs/high-signal-news
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Create Required Directories

```bash
mkdir -p state output logs
```

### 3. Initialize Databases

The databases are created automatically on first run, but you can verify connectivity:

```bash
python3 -c "from scripts.aggregator.storage import ArticleStorage; s = ArticleStorage('state/aggregation.db'); print('Database OK')"
```

## Manual Execution

### Basic Run (AI domain only)

```bash
cd /home/autonomy/labs/high-signal-news
source .venv/bin/activate

python scripts/run_daily_aggregation.py \
    --db state/aggregation.db \
    --newsletter-db state/newsletters.db \
    --catalog sources/sources-ai.json \
    --newsletter-catalog sources/newsletter_catalog.json \
    --output-dir output \
    --log-dir logs
```

### With Limits (for testing)

```bash
# Process only 5 feeds and 3 newsletters
python scripts/run_daily_aggregation.py \
    --catalog sources/sources-ai.json \
    --limit-feeds 5 \
    --limit-newsletters 3 \
    --domain ai
```

### Skip Content Extraction (faster)

```bash
python scripts/run_daily_aggregation.py \
    --catalog sources/sources-ai.json \
    --no-extract
```

## Scheduled Execution (systemd)

### 1. Install Service Files

```bash
# Copy systemd files to system directory
sudo cp systemd/high-signal-news.service /etc/systemd/system/
sudo cp systemd/high-signal-news.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload
```

### 2. Configure User and Paths

Edit `/etc/systemd/system/high-signal-news.service` to match your setup:

```ini
[Service]
User=your-username
Group=your-group
WorkingDirectory=/path/to/high-signal-news
ExecStart=/path/to/high-signal-news/.venv/bin/python \
    scripts/run_daily_aggregation.py \
    --db state/aggregation.db \
    --newsletter-db state/newsletters.db \
    --catalog sources/sources-ai.json \
    --newsletter-catalog sources/newsletter_catalog.json \
    --output-dir output \
    --log-dir logs
ReadWritePaths=/path/to/high-signal-news/state \
               /path/to/high-signal-news/output \
               /path/to/high-signal-news/logs
```

### 3. Enable and Start Timer

```bash
# Enable the timer (starts on boot)
sudo systemctl enable high-signal-news.timer

# Start the timer now
sudo systemctl start high-signal-news.timer

# Check status
sudo systemctl status high-signal-news.timer
```

### 4. Verify Timer is Active

```bash
# List all timers
systemctl list-timers --all

# Check next scheduled run
systemctl status high-signal-news.timer
```

### 5. View Logs

```bash
# View service logs
sudo journalctl -u high-signal-news.service

# Follow live logs
sudo journalctl -u high-signal-news.service -f

# View today's run
sudo journalctl -u high-signal-news.service --since today
```

## Monitoring

### Check Last Run Status

```bash
# Check if timer triggered successfully
systemctl status high-signal-news.service

# Check for errors in recent runs
sudo journalctl -u high-signal-news.service --since "24 hours ago" | grep -i error
```

### Manual Trigger (for testing)

```bash
# Run the service manually without waiting for timer
sudo systemctl start high-signal-news.service
```

## Troubleshooting

### Service Fails to Start

```bash
# Check for syntax errors in service file
sudo systemd-analyze verify /etc/systemd/system/high-signal-news.service

# Check detailed logs
sudo journalctl -u high-signal-news.service --no-pager -n 50
```

### Permission Denied Errors

Ensure the service user has read/write access to:
- `state/` - Database files
- `output/` - Aggregation results
- `logs/` - Log files

```bash
sudo chown -R autonomy:autonomy /home/autonomy/labs/high-signal-news/state
sudo chown -R autonomy:autonomy /home/autonomy/labs/high-signal-news/output
sudo chown -R autonomy:autonomy /home/autonomy/labs/high-signal-news/logs
```

### Database Locked Errors

SQLite doesn't handle concurrent writes well. Ensure only one aggregation runs at a time (the systemd service type is `oneshot` for this reason).

## Backup and Recovery

### Database Backup

```bash
# Backup databases before major changes
cp state/aggregation.db state/aggregation.db.backup.$(date +%Y%m%d)
cp state/newsletters.db state/newsletters.db.backup.$(date +%Y%m%d)
```

### Restore from Backup

```bash
# Stop the service
sudo systemctl stop high-signal-news.timer

# Restore database
cp state/aggregation.db.backup.20260321 state/aggregation.db

# Restart service
sudo systemctl start high-signal-news.timer
```

## Source Catalogs

Available source catalogs:

| Catalog | Domain | Sources |
|---------|--------|---------|
| `sources/sources-ai.json` | AI/ML | ~15 feeds |
| `sources/sources-dev.json` | Software Development | ~12 feeds |
| `sources/sources-investment.json` | Investment | ~15 feeds |
| `sources/newsletter_catalog.json` | Newsletters | ~8 sources |

To use multiple domains, run separate service instances or create a combined catalog.

## Performance Tuning

### For Large-Scale Aggregation

If processing 50+ sources:

1. Increase SQLite cache:
```python
# In storage.py, modify connection string
self.conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
```

2. Use `--no-extract` for faster runs (skips content extraction)

3. Consider running separate timers for each domain:
   - `high-signal-news-ai.timer` - 6:00 AM
   - `high-signal-news-dev.timer` - 6:30 AM
   - `high-signal-news-invest.timer` - 7:00 AM

## Security Considerations

- The systemd service runs with limited privileges (`NoNewPrivileges=true`)
- Network access is required for RSS feed fetching
- Consider firewall rules if running in restricted environment
- API keys (if used for premium sources) should be in environment files with restricted permissions

## Uninstallation

```bash
# Stop and disable timer
sudo systemctl stop high-signal-news.timer
sudo systemctl disable high-signal-news.timer

# Remove service files
sudo rm /etc/systemd/system/high-signal-news.service
sudo rm /etc/systemd/system/high-signal-news.timer

# Reload systemd
sudo systemctl daemon-reload
```
