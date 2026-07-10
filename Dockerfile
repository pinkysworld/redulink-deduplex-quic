FROM python:3.13-slim AS zstd-builder

ARG ZSTD_VERSION=1.5.7
ARG ZSTD_SHA256=eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl build-essential \
    && curl -fsSL "https://github.com/facebook/zstd/releases/download/v${ZSTD_VERSION}/zstd-${ZSTD_VERSION}.tar.gz" -o /tmp/zstd.tar.gz \
    && echo "${ZSTD_SHA256}  /tmp/zstd.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/zstd.tar.gz -C /tmp \
    && make -C "/tmp/zstd-${ZSTD_VERSION}" -j2 zstd-release

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /artifact

# GNU rsync for the file-tree comparator, iproute2/tc for Linux netem, and
# util-linux/taskset for optional CPU-affinity runs. zstd is source-pinned.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates rsync iproute2 util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY --from=zstd-builder /tmp/zstd-1.5.7/programs/zstd /usr/local/bin/zstd

COPY requirements-lock.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements-lock.txt

COPY . .

CMD ["python3", "scripts/run_smoke_validation.py"]
