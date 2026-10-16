CREATE TABLE IF NOT EXISTS logs (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  ts DATETIME(3) NOT NULL,
  service VARCHAR(50) NOT NULL,
  level VARCHAR(10) NOT NULL,
  request_id CHAR(36) NOT NULL,
  message TEXT NOT NULL,
  error_type VARCHAR(50) NULL,
  latency_ms INT NULL,
  INDEX idx_ts (ts),
  INDEX idx_req (request_id),
  INDEX idx_svc_ts (service, ts),
  INDEX idx_level_ts (level, ts)
);
