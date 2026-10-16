from datetime import datetime

from app.investigator.pipeline import investigate
from app.investigator.report import to_markdown

result = investigate(
    "Users reported checkout failures and slow responses around 2 PM.",
    datetime(2026, 10, 1, 0, 0, 0),
    datetime(2026, 10, 1, 23, 59, 59),
)

md = to_markdown(result)
with open("report.md", "w") as f:
    f.write(md)
print(md)
print("\nSaved to report.md")
