import pytest
from sample_repo.src.metrics.report import MetricsReportService

def test_metrics_json():
    service = MetricsReportService()
    data = service.get_metrics_json()
    assert len(data) == 3
    assert data[0]["prs_merged"] == 14

def test_metrics_csv_export():
    service = MetricsReportService()
    csv_text = service.export_metrics_csv()
    assert "date,prs_merged,bugs_fixed,test_coverage" in csv_text
    assert "2026-10-01,14,8,89.5" in csv_text
