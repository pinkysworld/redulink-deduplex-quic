FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /artifact

COPY requirements-lock.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements-lock.txt

COPY . .

CMD ["python3", "scripts/run_smoke_validation.py"]
