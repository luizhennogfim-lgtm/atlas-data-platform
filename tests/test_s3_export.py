from pathlib import Path

from pipeline.s3_export import export_report


class StubS3:
    def __init__(self):
        self.calls = []

    def upload_file(self, filename, bucket, key):
        self.calls.append((filename, bucket, key))


def test_disabled_without_bucket(monkeypatch, tmp_path):
    monkeypatch.delenv("ATLAS_S3_BUCKET", raising=False)
    assert export_report(tmp_path / "r.md") is None


def test_uploads_with_stub_client(tmp_path):
    stub = StubS3()
    target = export_report(Path("reports/quality_report.md"), client=stub, bucket="demo-bucket")
    assert target == "s3://demo-bucket/atlas/reports/quality_report.md"
    assert stub.calls[0][1:] == ("demo-bucket", "atlas/reports/quality_report.md")
