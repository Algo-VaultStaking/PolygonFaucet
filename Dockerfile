# syntax=docker/dockerfile:1

FROM python:3.13-slim AS build

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libmariadb-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

FROM python:3.13-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends libmariadb3 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=build /usr/local /usr/local

WORKDIR /app

COPY . .

CMD ["python3", "main.py"]
