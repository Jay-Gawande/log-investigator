# Incident Investigation Report

**Incident description:** Users reported checkout failures and slow responses around 2 PM.

**Searched range:** 2026-10-01 00:00:00 to 2026-10-01 23:59:59

## 1. Anomalous period

- **Start:** 2026-10-01 14:05:00
- **End:** 2026-10-01 14:17:00
- **Error/warn lines in window:** 309
- **Peak per minute:** 36 (normal baseline: 0.0)

## 2. Affected services (ordered by first error)

| service | errors | warns | total_lines | first_error | avg_latency_ms |
|---|---|---|---|---|---|
| db-service | 103 | 0 | 169 | 2026-10-01 14:05:14.997000 | 1847.0 |
| order-service | 103 | 0 | 272 | 2026-10-01 14:05:18.037000 | 1192.0 |
| api-gateway | 103 | 0 | 272 | 2026-10-01 14:05:18.087000 | 1227.0 |
| auth-service | 0 | 0 | 169 | - | 27.0 |

## 3. Major error groups

| service | level | error_type | pattern | count | first_seen | last_seen |
|---|---|---|---|---|---|---|
| api-gateway | ERROR | TIMEOUT | Upstream timeout while calling order-service | 103 | 2026-10-01 14:05:18.087000 | 2026-10-01 14:16:54.840000 |
| db-service | ERROR | DB_CONNECTION_FAILED | Connection refused: could not connect to mysql primary after <n> retries | 103 | 2026-10-01 14:05:14.997000 | 2026-10-01 14:16:51.750000 |
| order-service | ERROR | DEPENDENCY_FAILURE | Order creation failed: database unavailable | 103 | 2026-10-01 14:05:18.037000 | 2026-10-01 14:16:54.790000 |

## 4. Request traces

Failing requests sampled: **103**

Most common request paths among failing requests:

| path | count |
|---|---|
| api-gateway:INFO > auth-service:INFO > order-service:INFO > db-service:ERROR > order-service:ERROR > api-gateway:ERROR | 103 |


Example trace (request `00b41248-010b-402e-94d0-adbf4cba5f4a`):

| ts | service | level | error_type | message |
|---|---|---|---|---|
| 2026-10-01 14:11:46.138000 | api-gateway | INFO | - | request received |
| 2026-10-01 14:11:46.158000 | auth-service | INFO | - | token ok |
| 2026-10-01 14:11:46.178000 | order-service | INFO | - | creating order |
| 2026-10-01 14:11:46.198000 | db-service | ERROR | DB_CONNECTION_FAILED | Connection refused: could not connect to mysql primary after 4 retries |
| 2026-10-01 14:11:49.238000 | order-service | ERROR | DEPENDENCY_FAILURE | Order creation failed: database unavailable |
| 2026-10-01 14:11:49.288000 | api-gateway | ERROR | TIMEOUT | Upstream timeout while calling order-service |


## 5. Timeline

| first_seen | service | level | error_type | occurrences | last_seen |
|---|---|---|---|---|---|
| 2026-10-01 14:05:14.997000 | db-service | ERROR | DB_CONNECTION_FAILED | 103 | 2026-10-01 14:16:51.750000 |
| 2026-10-01 14:05:18.037000 | order-service | ERROR | DEPENDENCY_FAILURE | 103 | 2026-10-01 14:16:54.790000 |
| 2026-10-01 14:05:18.087000 | api-gateway | ERROR | TIMEOUT | 103 | 2026-10-01 14:16:54.840000 |


## 6. Root-cause hypothesis

- **Root cause service:** db-service
- **Root cause error type:** DB_CONNECTION_FAILED
- **Propagation path:** db-service -> order-service -> api-gateway
- **Confidence:** 1.0
- **Produced by:** llm

The incident originated at 2026-10-01 14:05:14.997000 when db-service first threw DB_CONNECTION_FAILED errors with 103 total failures attempting to connect to the mysql primary. This failure drove db-service latency to an average of 1847.0 ms, causing order-service to fail with 103 DEPENDENCY_FAILURE errors starting at 14:05:18.037000. Finally, api-gateway timed out waiting on order-service across 103 requests starting at 14:05:18.087000.

## 7. Verification against logs

- Claimed error exists in window: **True**
- Appeared before all other significant errors: **True**
- Share of failing requests containing it: **1.0**
- **Verified: True**

## 8. Investigation attempts

- Attempt 1: verified = True
