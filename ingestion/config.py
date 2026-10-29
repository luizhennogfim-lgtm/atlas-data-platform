"""Runtime settings, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from psycopg.conninfo import conninfo_to_dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DSN = "postgresql://atlas:atlas_dev_only@localhost:5432/atlas"


@dataclass(frozen=True)
class Settings:
    dsn: str
    source_dir: Path
    dbt_project_dir: Path
    dbt_bin: str
    reports_dir: Path
    sql_init_dir: Path
    warn_reject_rate: float
    critical_reject_rate: float

    def dbt_env(self) -> dict[str, str]:
        """Connection variables read by transformations/dbt_project/profiles.yml."""
        parts = conninfo_to_dict(self.dsn)
        return {
            "ATLAS_DB_HOST": str(parts.get("host", "localhost")),
            "ATLAS_DB_PORT": str(parts.get("port", "5432")),
            "ATLAS_DB_USER": str(parts.get("user", "atlas")),
            "ATLAS_DB_PASSWORD": str(parts.get("password", "")),
            "ATLAS_DB_NAME": str(parts.get("dbname", "atlas")),
        }


def get_settings() -> Settings:
    root = Path(os.environ.get("ATLAS_PROJECT_ROOT", PROJECT_ROOT))
    return Settings(
        dsn=os.environ.get("ATLAS_DB_DSN", DEFAULT_DSN),
        source_dir=Path(os.environ.get("ATLAS_SOURCE_DIR", root / "data" / "sample")),
        dbt_project_dir=root / "transformations" / "dbt_project",
        dbt_bin=os.environ.get("ATLAS_DBT_BIN", "dbt"),
        reports_dir=Path(os.environ.get("ATLAS_REPORTS_DIR", root / "reports")),
        sql_init_dir=root / "sql" / "init",
        warn_reject_rate=float(os.environ.get("ATLAS_WARN_REJECT_RATE", "0.01")),
        critical_reject_rate=float(os.environ.get("ATLAS_CRITICAL_REJECT_RATE", "0.20")),
    )
