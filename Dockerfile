# Use a stable Debian bookworm-based image instead of slim/trixie to avoid
# unreliable apt mirrors that cause "Tried to start delayed item … but failed".
FROM python:3.12-bookworm

WORKDIR /app

# Install system dependencies in a single layer so that apt-get update is
# always executed immediately before apt-get install, preventing stale index
# errors.  Clean the apt lists afterwards to keep the image small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies before copying the rest of the source so that
# Docker can cache this layer when only application code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source.
COPY . .

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
