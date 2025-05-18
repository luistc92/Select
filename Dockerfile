# Stage 1: Build environment
FROM python:3.11-slim as builder

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Install Playwright and only Chromium browser
RUN pip install playwright==1.52.0 && \
    playwright install --with-deps chromium

# Stage 2: Runtime environment
FROM python:3.11-slim as runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy Playwright browser binaries
COPY --from=builder /ms-playwright /ms-playwright

# Install system dependencies for Playwright
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libcups2 \
    libxss1 \
    libxrandr2 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libpango-1.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Create directories for logs and auth
RUN mkdir -p logs

# Copy application code
COPY invoice_bot/ /app/invoice_bot/

# Create the directory for sample files/tests
COPY sample.csv /app/

# Default ENV variables
ENV PYTHONUNBUFFERED=1

# Entrypoint
ENTRYPOINT ["python", "-m", "invoice_bot.main"]

# Default command (overridable)
CMD ["--csv", "sample.csv"]