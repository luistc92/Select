import asyncio
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional

from loguru import logger
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError

# Placeholder selectors - to be replaced with actual ones after access to QA mirror
TODO_SELECTOR_LOGIN_URL = "https://placeholder-portal.example.com/login"
TODO_SELECTOR_USERNAME = "input[name='username']"
TODO_SELECTOR_PASSWORD = "input[name='password']"
TODO_SELECTOR_SIGNIN_BUTTON = "button:has-text('Sign in')"
TODO_SELECTOR_DASHBOARD = "text=Dashboard"
TODO_SELECTOR_SERVICE_ID = "input[name='service_id']"
TODO_SELECTOR_PRICE = "input[name='price']"
TODO_SELECTOR_INVOICE_FILE = "input[type='file']"
TODO_SELECTOR_DESCRIPTION = "textarea[name='description']" 
TODO_SELECTOR_INVOICE_DATE = "input[name='invoice_date']"
TODO_SELECTOR_SUBMIT_BUTTON = "button:has-text('Submit')"
TODO_SELECTOR_SUCCESS = "text=Success"
TODO_SELECTOR_PORTAL_ID = "[data-portal-id]"
TODO_SELECTOR_SERVICE_TABLE = "table"

# Rate limit detection
TODO_SELECTOR_RATE_LIMIT = "text=Rate Limit"

# Base URL (from environment or default)
BASE_URL = os.getenv("PORTAL_BASE_URL", "https://placeholder-portal.example.com")
AUTH_FILE = "auth.json"


class PortalUploader:
    """Manages a Playwright browser session for uploading invoices to the portal."""

    def __init__(self, headless: bool = True):
        """Initialize the uploader with browser settings.
        
        Args:
            headless: Whether to run the browser in headless mode
        """
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self._auth_file = Path(AUTH_FILE)

    async def __aenter__(self) -> "PortalUploader":
        """Set up Playwright and browser for async context manager."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        
        # Check for existing auth
        if self._auth_file.exists():
            logger.info("[AUTH] Using saved cookies from previous session")
            self.context = await self.browser.new_context(storage_state=str(self._auth_file))
        else:
            logger.info("[AUTH] No saved session found, performing fresh login")
            self.context = await self.browser.new_context()
            await self._login()
            
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting the context manager."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def _login(self) -> None:
        """Perform login and save auth state."""
        # Get credentials from environment
        username = os.getenv("PORTAL_USERNAME")
        password = os.getenv("PORTAL_PASSWORD")
        
        if not username or not password:
            raise ValueError("Missing login credentials. Set PORTAL_USERNAME and PORTAL_PASSWORD environment variables.")
        
        # Create page and navigate to login
        page = await self.context.new_page()
        try:
            await page.goto(TODO_SELECTOR_LOGIN_URL)
            
            # Fill login form
            await page.fill(TODO_SELECTOR_USERNAME, username)
            await page.fill(TODO_SELECTOR_PASSWORD, password)
            await page.click(TODO_SELECTOR_SIGNIN_BUTTON)
            
            # Wait for successful login
            await page.wait_for_selector(TODO_SELECTOR_DASHBOARD, timeout=8000)
            logger.info("[AUTH] Login successful")
            
            # Save auth state for future runs
            await self.context.storage_state(path=str(self._auth_file))
            logger.info(f"[AUTH] Saved authentication state to {self._auth_file}")
        finally:
            await page.close()

    async def _retry_with_backoff(self, func, max_retries=3) -> Any:
        """Execute a function with exponential backoff retry on failure.
        
        Args:
            func: Async function to execute
            max_retries: Maximum number of retry attempts
            
        Returns:
            The result of the function if successful
            
        Raises:
            The last exception if all retries fail
        """
        retries = 0
        last_exception = None
        
        while retries <= max_retries:
            try:
                if retries > 0:
                    logger.warning(f"Retry attempt {retries}/{max_retries}")
                    
                return await func()
                
            except Exception as e:
                last_exception = e
                
                # Check if it's a rate limit error
                if isinstance(e, TimeoutError) or "429" in str(e) or "Rate Limit" in str(e):
                    retries += 1
                    if retries <= max_retries:
                        # Exponential backoff: 2^retries * 1000ms
                        wait_time = (2 ** retries) * 1000
                        logger.warning(f"Rate limit detected, backing off for {wait_time/1000}s")
                        await asyncio.sleep(wait_time / 1000)
                    else:
                        logger.error(f"Max retries ({max_retries}) exceeded")
                        raise
                else:
                    # Not a rate limit error, don't retry
                    raise
                
        raise last_exception

    async def upload_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Upload a single invoice row to the portal.
        
        Args:
            row: Dictionary containing the row data from the CSV
            
        Returns:
            Dict with status, portal_id (if successful), and error message (if failed)
        """
        page = await self.context.new_page()
        start_time = time.time()
        
        try:
            # Define the actual upload process as a nested function for retry
            async def do_upload():
                # Navigate to new service page
                await page.goto(f"{BASE_URL}/new-service")
                
                # Check for duplicate (if service_id already exists)
                service_id = str(row["service_id"])
                duplicate_check = await page.locator(f"{TODO_SELECTOR_SERVICE_TABLE} >> text={service_id}").count()
                
                if duplicate_check > 0:
                    # Get the existing portal ID if possible
                    try:
                        existing_id = await page.locator(f"{TODO_SELECTOR_SERVICE_TABLE} >> text={service_id}")
                        existing_id = await existing_id.evaluate("el => el.closest('tr').querySelector('[data-portal-id]').textContent")
                    except:
                        existing_id = "unknown"
                        
                    logger.info(f"[ROW_SKIP] service_id={service_id} (duplicate found, portal_id={existing_id})")
                    return {
                        "status": "SKIP", 
                        "portal_id": existing_id, 
                        "error_msg": None,
                        "processed_ts": datetime.now().isoformat()
                    }
                
                # Log the upload attempt
                logger.info(f"[ROW_START] service_id={service_id}, invoice_path={row['invoice_path']}")
                
                # Fill the form
                await page.fill(TODO_SELECTOR_SERVICE_ID, service_id)
                await page.fill(TODO_SELECTOR_PRICE, format(float(row["price"]), '.2f'))
                
                # Set file input (invoice)
                invoice_path = Path(row["invoice_path"]).resolve()
                await page.set_input_files(TODO_SELECTOR_INVOICE_FILE, str(invoice_path))
                
                # Fill optional fields if present
                if "description" in row and row["description"]:
                    await page.fill(TODO_SELECTOR_DESCRIPTION, str(row["description"]))
                
                if "invoice_date" in row and row["invoice_date"]:
                    await page.fill(TODO_SELECTOR_INVOICE_DATE, str(row["invoice_date"]))
                
                # Submit form
                await page.click(TODO_SELECTOR_SUBMIT_BUTTON)
                
                # Wait for success message
                await page.wait_for_selector(TODO_SELECTOR_SUCCESS, timeout=5000)
                
                # Extract portal ID
                portal_id = await page.locator(TODO_SELECTOR_PORTAL_ID).inner_text()
                
                return {
                    "status": "OK",
                    "portal_id": portal_id,
                    "error_msg": None,
                    "processed_ts": datetime.now().isoformat()
                }
            
            # Execute with retry
            result = await self._retry_with_backoff(do_upload)
            
            # If successful, log the timing
            if result["status"] == "OK":
                elapsed_ms = int((time.time() - start_time) * 1000)
                logger.info(f"[ROW_SUCCESS] service_id={row['service_id']}, portal_id={result['portal_id']}, time={elapsed_ms}ms")
            
            return result
            
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"[ROW_ERROR] service_id={row['service_id']}, error={error_msg}, time={elapsed_ms}ms")
            
            return {
                "status": "ERROR",
                "portal_id": None,
                "error_msg": error_msg,
                "processed_ts": datetime.now().isoformat()
            }
            
        finally:
            await page.close()