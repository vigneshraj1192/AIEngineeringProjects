"""Metrics reporting service for DevStream Labs."""

import io
import csv
from typing import List, Dict, Any

class MetricsReportService:
    """Generates weekly engineering productivity and quality metrics."""

    def __init__(self):
        self._sample_data = [
            {"date": "2026-10-01", "prs_merged": 14, "bugs_fixed": 8, "test_coverage": 89.5},
            {"date": "2026-10-02", "prs_merged": 18, "bugs_fixed": 12, "test_coverage": 91.2},
            {"date": "2026-10-03", "prs_merged": 15, "bugs_fixed": 9, "test_coverage": 90.8},
        ]

    def get_metrics_json(self) -> List[Dict[str, Any]]:
        """Return raw metrics as structured dictionary records."""
        return self._sample_data

    def export_metrics_csv(self) -> str:
        """Export metrics formatted as CSV text."""
        output = io.StringIO()
        fieldnames = ["date", "prs_merged", "bugs_fixed", "test_coverage"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(self._sample_data)
        return output.getvalue()
