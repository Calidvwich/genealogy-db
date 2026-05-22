"""Export the full PostgreSQL database to a SQL dump in the project root.

The generated file is named `genealogy_db_bck` by default, matching the request.
It is a plain-text SQL dump that can recreate a fresh database when restored
with psql.
导出直接执行此脚本即可
导入请执行psql -U postgres -d postgres -f genealogy_db_bck
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
import sys


DEFAULT_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:Xjz20041119@127.0.0.1:5432/genealogy_db",
)


def export_database(output_path: Path, db_url: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "pg_dump",
        "--dbname",
        db_url,
        "--file",
        str(output_path),
        "--create",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--format=plain",
        "--encoding=UTF8",
    ]

    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise SystemExit(
            "pg_dump was not found. Install the PostgreSQL client tools and make sure pg_dump is on PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Export failed. pg_dump exit code: {exc.returncode}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export the whole database to SQL.")
    parser.add_argument(
        "--output",
        default="genealogy_db_bck",
        help="Output file name, defaulting to genealogy_db_bck in the project root.",
    )
    parser.add_argument(
        "--db-url",
        default=DEFAULT_DB_URL,
        help="PostgreSQL connection string. Defaults to DATABASE_URL or the built-in fallback.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parent
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = root_dir / output_path

    export_database(output_path, args.db_url)
    print(f"数据库已导出到: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())