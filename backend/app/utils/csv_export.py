import csv
import io
from collections.abc import Iterable

CSV_FIELDS = ["id", "title", "snippet", "date", "type", "source", "url", "thumbnail"]


def items_to_csv_bytes(items: Iterable[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for it in items:
        writer.writerow(it)
    return buf.getvalue().encode("utf-8")
