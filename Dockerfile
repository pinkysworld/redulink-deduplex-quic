FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /artifact

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates rsync \
    && rsync --version | head -n 1 | grep -q "version 3.2.7" \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements-lock.txt

COPY . .

CMD ["python3", "scripts/run_smoke_validation.py"]
