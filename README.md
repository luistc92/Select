# Invoice Bot

A headless CLI automation tool for uploading invoices to customer web portals.

## Features

- Automatic CSV processing of service invoices
- Browser automation with Playwright for web portal interaction
- Parallel processing with concurrency controls
- Session persistence to avoid repeated logins
- Comprehensive logging and error handling
- Result CSV with status and portal IDs for each upload
- Docker containerization for easy deployment

## Quick Start

### Environment Setup

1. Create a `.env` file with credentials:

```
PORTAL_USERNAME=your_username
PORTAL_PASSWORD=your_password
PORTAL_BASE_URL=https://customer-portal.example.com
```

### Local Development

1. Clone the repository
2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
```

4. Install Playwright browsers:
```bash
playwright install --with-deps chromium
```

5. Run the bot:
```bash
python -m invoice_bot.main --csv services.csv
```

### Using Docker

1. Build the container:
```bash
docker build -t invoice-bot .
```

2. Run with your CSV file:
```bash
docker run --rm -v $(pwd)/services.csv:/app/services.csv \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/invoices:/app/invoices \
  --env-file .env \
  invoice-bot --csv services.csv
```

## Command Line Options

```
python -m invoice_bot.main [--csv PATH] [--headed] [--concurrency N]
```

- `--csv PATH`: Path to the CSV file (default: services.csv)
- `--headed`: Run in headed mode (visible browser)
- `--concurrency N`: Maximum concurrent uploads (default: 4)

## CSV Format

The tool requires a CSV file with the following columns:

- `service_id`: Unique identifier for the service (required)
- `price`: Service price, decimal number (required)
- `invoice_path`: Path to invoice PDF/XML file (required)
- `description`: Service description (optional)
- `invoice_date`: Invoice date in YYYY-MM-DD format (optional)

Additional columns will be preserved in the output file.

## Exit Codes

- `0`: All rows processed successfully
- `1`: Startup error (missing CSV, auth failure, etc.)
- `2`: Completed with one or more row processing errors

## Troubleshooting

### Authentication Issues

1. Delete the `auth.json` file to force a fresh login.
2. Verify credentials in the `.env` file.
3. Check that the portal URL is correct.

### Browser Automation Failures

1. Run with `--headed` flag to visually observe browser behavior.
2. Check logs for exact error messages.
3. Verify that the portal's HTML structure hasn't changed.

### Concurrency Problems

If you encounter rate limiting:
1. Reduce the `--concurrency` value.
2. Add delay between requests.

### Docker Issues

1. Ensure volume mounts are correct.
2. Check container logs with `docker logs`.
3. Verify environment variables are properly passed.