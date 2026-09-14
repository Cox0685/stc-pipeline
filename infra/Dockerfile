# STC Pipeline - Container App Job image
#
# This intentionally does NOT rewrite the pipeline into a different
# architecture: it packages the same 23 scripts and the same
# STC Pipeline Runner.py entry point that already run locally, so this image
# is the same code you've been testing, just running somewhere with a
# scheduler attached instead of a person's laptop.

FROM python:3.12-slim

# pandas/lxml-adjacent packages sometimes need these build tools even for
# wheels; keeping the image slim but not so slim that pip install breaks
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY infra/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Scripts/ /app/Scripts/

WORKDIR /app/Scripts

# Container App Jobs run to completion and exit - no long-running server here,
# just the same runner script, same as running it locally.
ENTRYPOINT ["python", "STC Pipeline Runner.py"]
