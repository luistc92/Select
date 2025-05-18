import os
import pytest
import asyncio
from pathlib import Path

from invoice_bot.portal_uploader import PortalUploader


@pytest.mark.asyncio
async def test_uploader_initialization():
    """Smoke test to verify PortalUploader can be initialized."""
    # Skip if running in CI without credentials
    if os.environ.get("CI") and not os.environ.get("PORTAL_USERNAME"):
        pytest.skip("Skipping smoke test in CI without credentials")
    
    # Create dummy auth file to skip actual login
    auth_file = Path("auth.json")
    if not auth_file.exists():
        auth_file.write_text('{"cookies": [], "origins": []}')
    
    # Initialize uploader with headed mode for visual verification
    async with PortalUploader(headless=False) as uploader:
        # Just verify that initialization completed
        assert uploader.browser is not None
        assert uploader.context is not None


@pytest.mark.asyncio
async def test_csv_read():
    """Test that the sample CSV can be read correctly."""
    import pandas as pd
    
    # Ensure sample CSV exists
    sample_path = Path("sample.csv")
    assert sample_path.exists(), "Sample CSV file not found"
    
    # Read the CSV
    df = pd.read_csv(sample_path)
    
    # Verify required columns
    required_cols = ["service_id", "price", "invoice_path"]
    for col in required_cols:
        assert col in df.columns, f"Missing required column: {col}"