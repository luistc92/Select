import argparse
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import pandas as pd
from dotenv import load_dotenv
from loguru import logger

from invoice_bot.logging_setup import bootstrap
from invoice_bot.portal_uploader import PortalUploader


# Required CSV columns
REQUIRED_COLUMNS = ["service_id", "price", "invoice_path"]

# Default concurrency
DEFAULT_CONCURRENCY = 4


async def process_row(
    uploader: PortalUploader, row: Dict[str, Any], semaphore: asyncio.Semaphore
) -> Dict[str, Any]:
    """Process a single row with concurrency control via semaphore.
    
    Args:
        uploader: The portal uploader instance
        row: Dictionary containing row data
        semaphore: Semaphore to limit concurrency
        
    Returns:
        Dict with upload result (status, portal_id, error_msg)
    """
    async with semaphore:
        return await uploader.upload_row(dict(row))


async def main(csv_path: str, headless: bool = True, concurrency: int = DEFAULT_CONCURRENCY) -> int:
    """Main entry point for the invoice bot.
    
    Args:
        csv_path: Path to the CSV file containing invoice data
        headless: Whether to run in headless mode
        concurrency: Maximum number of concurrent uploads
        
    Returns:
        Exit code (0: success, 1: startup error, 2: some row errors)
    """
    start_time = time.time()
    
    # Load environment variables
    load_dotenv()
    
    # Set up logging
    bootstrap()
    
    # Parse CSV path
    csv_file = Path(csv_path)
    if not csv_file.exists():
        logger.error(f"[INIT] CSV file not found: {csv_file}")
        return 1
    
    # Read CSV with pandas
    try:
        df = pd.read_csv(csv_file)
        logger.info(f"[READ_CSV] Loaded {len(df)} rows from {csv_file}")
    except Exception as e:
        logger.error(f"[INIT] Failed to read CSV: {e}")
        return 1
    
    # Validate required columns
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        logger.error(f"[INIT] Missing required columns: {', '.join(missing_columns)}")
        return 1
    
    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(concurrency)
    
    # Create uploader and process rows
    results = []
    async with PortalUploader(headless=headless) as uploader:
        # Create tasks for each row
        tasks = [
            process_row(uploader, row, semaphore) 
            for _, row in df.iterrows()
        ]
        
        # Run all tasks and collect results
        results = await asyncio.gather(*tasks)
    
    # Process results
    status_counts = {"OK": 0, "SKIP": 0, "ERROR": 0}
    for result in results:
        status_counts[result["status"]] += 1
    
    # Add results to DataFrame
    result_df = df.copy()
    
    # Add result columns - we convert the list of dicts to a dict of lists
    result_dict = {
        "status": [],
        "portal_id": [],
        "error_msg": [],
        "processed_ts": []
    }
    
    for r in results:
        result_dict["status"].append(r["status"])
        result_dict["portal_id"].append(r["portal_id"])
        result_dict["error_msg"].append(r["error_msg"])
        result_dict["processed_ts"].append(r["processed_ts"])
    
    # Assign the new columns
    result_df = result_df.assign(**result_dict)
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_csv = f"run-{timestamp}.csv"
    
    # Save result CSV
    result_df.to_csv(output_csv, index=False)
    logger.info(f"[SUMMARY_WRITE] Results written to {output_csv}")
    
    # Log summary
    elapsed_sec = int(time.time() - start_time)
    logger.info(
        f"[SUMMARY] Completed: {status_counts['OK']} OK, {status_counts['SKIP']} SKIP, "
        f"{status_counts['ERROR']} ERROR, total runtime {elapsed_sec}s"
    )
    
    # Determine exit code
    if status_counts["ERROR"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Invoice upload automation tool")
    parser.add_argument("--csv", default="services.csv", help="Path to CSV file with invoice data")
    parser.add_argument("--headed", action="store_true", help="Run in headed mode (visible browser)")
    parser.add_argument(
        "--concurrency", type=int, default=DEFAULT_CONCURRENCY, 
        help=f"Maximum concurrent uploads (default: {DEFAULT_CONCURRENCY})"
    )
    
    args = parser.parse_args()
    
    # Run the async main function
    exit_code = asyncio.run(main(
        csv_path=args.csv,
        headless=not args.headed,
        concurrency=args.concurrency
    ))
    
    sys.exit(exit_code)