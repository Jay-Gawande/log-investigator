from .db import query_df

print(query_df("SELECT COUNT(*) AS rows_in_logs FROM logs"))
print("OK: Python -> MariaDB works")

