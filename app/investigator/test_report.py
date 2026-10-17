from datetime import datetime

from .pipeline import investigate
from .report import to_markdown

result = investigate(
    "Users reported checkout failures and slow responses around 2 PM.",
    datetime(2026, 10, 1, 0, 0, 0),
    datetime(2026, 10, 1, 23, 59, 59),
)

md = to_markdown(result)
with open("output/report.md", "w") as f:
    f.write(md)
print(md)
print("\nSaved to report.md")
