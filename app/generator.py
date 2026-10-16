import uuid
import random
import argparse
from datetime import datetime, timedelta

import pandas as pd
from faker import Faker
from sqlalchemy import text

from .db import engine

fake = Faker()

# Every request passes through these services in order
CHAIN = ["api-gateway", "auth-service", "order-service", "db-service"]

COLUMNS = ["ts", "service", "level", "request_id",
           "message", "error_type", "latency_ms"]


def ms(t, n):
    return t + timedelta(milliseconds=n)


def normal_request(t):
    """A healthy request. A tiny fraction gets a harmless background warning."""
    rid = str(uuid.uuid4())
    rows = []
    for i, svc in enumerate(CHAIN):
        rows.append((ms(t, i * 20), svc, "INFO", rid,
                     f"{svc} handled request for user {fake.user_name()}",
                     None, random.randint(5, 80)))
    # background noise so the baseline is not exactly zero
    if random.random() < 0.005:
        rows.append((ms(t, 30), "auth-service", "WARN", rid,
                     f"Invalid password attempt for user {fake.user_name()}",
                     "BAD_PASSWORD", 20))
    return rows


def incident_request(t, kind):
    rid = str(uuid.uuid4())
    if kind == "db_failure":
        return [
            (t, "api-gateway", "INFO", rid, "request received", None, 10),
            (ms(t, 20), "auth-service", "INFO", rid, "token ok", None, 15),
            (ms(t, 40), "order-service", "INFO", rid, "creating order", None, 20),
            (ms(t, 60), "db-service", "ERROR", rid,
             f"Connection refused: could not connect to mysql primary after {random.randint(3, 5)} retries",
             "DB_CONNECTION_FAILED", 3000),
            (ms(t, 3100), "order-service", "ERROR", rid,
             "Order creation failed: database unavailable",
             "DEPENDENCY_FAILURE", 3100),
            (ms(t, 3150), "api-gateway", "ERROR", rid,
             "Upstream timeout while calling order-service",
             "TIMEOUT", 3200),
        ]
    if kind == "auth_failure":
        return [
            (t, "api-gateway", "INFO", rid, "request received", None, 10),
            (ms(t, 20), "auth-service", "ERROR", rid,
             "JWT signature verification failed", "AUTH_FAILED", 25),
            (ms(t, 30), "api-gateway", "WARN", rid,
             "401 returned to client", "AUTH_FAILED", 35),
        ]
    if kind == "high_latency":
        rows = []
        for i, svc in enumerate(CHAIN):
            slow = svc == "db-service"
            rows.append((ms(t, i * 20), svc,
                         "WARN" if slow else "INFO", rid,
                         "slow query detected" if slow else f"{svc} handled request",
                         "SLOW_QUERY" if slow else None,
                         random.randint(2000, 5000) if slow else random.randint(5, 80)))
        return rows
    raise ValueError(f"unknown incident kind: {kind}")


def flush(rows):
    if not rows:
        return
    df = pd.DataFrame(rows, columns=COLUMNS)
    df.to_sql("logs", engine, if_exists="append", index=False,
              chunksize=5000, method="multi")


def generate(n_requests, day_start, kind, inc_start_min, inc_len_min):
    inc_start = day_start + timedelta(minutes=inc_start_min)
    inc_end = inc_start + timedelta(minutes=inc_len_min)
    buffer = []
    for i in range(n_requests):
        t = day_start + timedelta(seconds=random.uniform(0, 24 * 3600))
        if inc_start <= t < inc_end and random.random() < 0.6:
            buffer += incident_request(t, kind)
        else:
            buffer += normal_request(t)
        if len(buffer) >= 50_000:
            flush(buffer)
            buffer = []
            print(f"  ...{i + 1}/{n_requests} requests done")
    flush(buffer)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=20000, help="number of requests")
    p.add_argument("--kind", default="db_failure",
                   choices=["db_failure", "auth_failure", "high_latency"])
    p.add_argument("--truncate", action="store_true",
                   help="empty the logs table first")
    a = p.parse_args()

    if a.truncate:
        with engine.begin() as c:
            c.execute(text("TRUNCATE TABLE logs"))
        print("logs table emptied")

    day = datetime(2026, 10, 1, 0, 0, 0)
    # incident from 14:05 to 14:17
    generate(a.n, day, a.kind, inc_start_min=14 * 60 + 5, inc_len_min=12)
    print("done")
