"""Opt-in full migration test using a new loopback-only PostgreSQL cluster.

Run with PROGRAMME_POSTGRES_TEST=1. Never connects to the application's database.
"""
import os
from pathlib import Path
import socket
import subprocess

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


@pytest.mark.skipif(os.environ.get("PROGRAMME_POSTGRES_TEST") != "1", reason="Disposable PostgreSQL integration is opt-in")
def test_full_postgres_migration_chain_and_programme_audit(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config

    binaries = Path(os.environ.get("PROGRAMME_POSTGRES_BIN", r"C:\Program Files\PostgreSQL\17\bin"))
    if not (binaries / "initdb.exe").exists():
        pytest.skip("PostgreSQL test binaries unavailable")
    cluster = tmp_path / "programme_cluster"
    log = tmp_path / "postgres.log"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def run(*args):
        # Windows server grandchildren can keep captured PIPE handles open after
        # pg_ctl exits. Files avoid a false hang while retaining failure evidence.
        output_path = tmp_path / "command.log"
        with output_path.open("w", encoding="utf-8") as output:
            result = subprocess.run([str(arg) for arg in args], stdout=output, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, timeout=60, creationflags=flags)
        assert result.returncode == 0, output_path.read_text(encoding="utf-8", errors="replace")

    run(binaries / "initdb.exe", "-D", cluster, "-U", "programme_test", "-A", "trust", "--no-locale", "--encoding=UTF8")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    engine = None
    try:
        run(binaries / "pg_ctl.exe", "-D", cluster, "-l", log, "-o", f"-h 127.0.0.1 -p {port}", "-w", "start")
        url = f"postgresql+psycopg2://programme_test@127.0.0.1:{port}/postgres"
        monkeypatch.setenv("DATABASE_URL", url)
        backend = Path(__file__).parents[1]
        config = Config(str(backend / "alembic.ini"))
        config.set_main_option("script_location", str(backend / "alembic"))
        command.upgrade(config, "019_vaisala_defect_evidence")
        engine = create_engine(url)
        with engine.begin() as conn:
            authority = conn.execute(text("INSERT INTO authorities(name) VALUES ('Disposable test') RETURNING id")).scalar_one()
            user = conn.execute(text("INSERT INTO users(authority_id,email,hashed_password,role) VALUES (:a,'test@invalid','unused','manager') RETURNING id"), {"a": authority}).scalar_one()
            survey = conn.execute(text("INSERT INTO vaisala_surveys(authority_id,source_filename,source_format,network_key) VALUES (:a,'legacy.csv','csv','test') RETURNING id"), {"a": authority}).scalar_one()
        command.upgrade(config, "020_vaisala_programme")
        assert "vaisala_programme_review_events" in inspect(engine).get_table_names()
        with engine.begin() as conn:
            programme = conn.execute(text("""INSERT INTO vaisala_programmes
                (authority_id,survey_id,created_by,idempotency_key,request_fingerprint,model_version,policy_version,merge_scale,split,generated_at,metadata_json)
                VALUES (:a,:s,:u,'test','fingerprint','v1','v1','section','combined',CURRENT_TIMESTAMP,'{}') RETURNING id"""),
                {"a": authority, "s": survey, "u": user}).scalar_one()
            item = conn.execute(text("INSERT INTO vaisala_programme_items(programme_id,item_key,assessment) VALUES (:p,'item','{}') RETURNING id"), {"p": programme}).scalar_one()
            conn.execute(text("INSERT INTO vaisala_programme_review_events(item_id,sequence,author_id,decision) VALUES (:i,1,:u,'{}')"), {"i": item, "u": user})
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM vaisala_surveys WHERE id=:s"), {"s": survey})
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO vaisala_programme_review_events(item_id,sequence,author_id,decision) VALUES (:i,1,:u,'{}')"), {"i": item, "u": user})
        command.downgrade(config, "019_vaisala_defect_evidence")
        assert "vaisala_programmes" not in inspect(engine).get_table_names()
        with engine.connect() as conn:
            assert conn.execute(text("SELECT source_filename FROM vaisala_surveys WHERE id=:s"), {"s": survey}).scalar_one() == "legacy.csv"
        command.upgrade(config, "020_vaisala_programme")
    finally:
        if engine is not None:
            engine.dispose()
        if (cluster / "postmaster.pid").exists():
            run(binaries / "pg_ctl.exe", "-D", cluster, "-m", "fast", "-w", "stop")
