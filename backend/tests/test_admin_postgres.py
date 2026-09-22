"""Opt-in local PostgreSQL checks; all records live in a disposable, isolated schema.

Run with ADMIN_TEST_POSTGRES=1. The URL is read from the project's .env and is
rejected unless its host is local. No existing schema or application data is changed.
"""
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

os.environ.setdefault('ANTHROPIC_API_KEY', 'test-key')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_permissions.db')
os.environ.setdefault('JWT_SECRET', 'test-secret')

from database import Base
from models.user import Authority, User
from models.asset import Asset, AnalysisRun, RiskScore, ScannerRawRecord, ReactiveJobRecord, ReactiveAggregate
from routers import analysis, admin
from schemas.admin import DatasetDelete
from services.reactive_aggregates import rebuild_reactive_aggregates


@pytest.fixture
def postgres_sessions():
    if os.getenv('ADMIN_TEST_POSTGRES') != '1':
        pytest.skip('Set ADMIN_TEST_POSTGRES=1 to use an isolated local PostgreSQL schema')
    values = dotenv_values(Path(__file__).resolve().parents[2] / '.env')
    url = make_url(values['DATABASE_URL'])
    assert url.get_backend_name() == 'postgresql' and url.host in ('localhost', '127.0.0.1', '::1'), 'Only local PostgreSQL is allowed'
    schema = 'admin_delete_test_' + uuid.uuid4().hex
    owner = create_engine(url)
    engine = None
    try:
        with owner.begin() as connection:
            connection.execute(CreateSchema(schema))
        engine = create_engine(url, connect_args={'options': '-csearch_path=' + schema})
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine)
        with sessions() as db:
            db.add(Authority(id=1, name='Isolated test authority')); db.flush()
            db.add(User(id=1, authority_id=1, email='test@example.com', role='admin', hashed_password='unused'))
            db.add(Asset(id=1, authority_id=1, nsg_ref='test', road_class='A'))
            db.flush()
            db.add(ScannerRawRecord(asset_id=1, source_file='remove.csv', avg_ci=50, rci_band='Amber', survey_year=2026))
            db.commit()
        yield sessions
    finally:
        if engine is not None:
            engine.dispose()
        with owner.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        owner.dispose()


def test_deletion_waits_for_analysis_and_removes_its_saved_results(postgres_sessions, monkeypatch):
    entered_llm, release_llm, delete_started = threading.Event(), threading.Event(), threading.Event()
    state = {}

    def generate(scored, stats):
        entered_llm.set()
        assert release_llm.wait(15), 'Test did not release the simulated LLM call'
        return 'Analysis based on source data being deleted'

    monkeypatch.setattr(analysis, 'generate_analysis', generate)

    def run_analysis():
        with postgres_sessions() as db:
            return analysis.run_analysis(db=db, current_user=db.get(User, 1))

    def delete_source():
        with postgres_sessions() as db:
            state['pid'] = db.execute(text('SELECT pg_backend_pid()')).scalar_one()
            delete_started.set()
            return admin.delete_dataset_upload(1, 'scanner', DatasetDelete(source_file='remove.csv'), db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        analysis_job = pool.submit(run_analysis)
        deletion_job = None
        try:
            assert entered_llm.wait(10)
            deletion_job = pool.submit(delete_source)
            assert delete_started.wait(5)
            deadline = time.monotonic() + 5
            blocked = False
            with postgres_sessions.kw['bind'].connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
                while time.monotonic() < deadline:
                    wait_type = observer.execute(text('SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid'), {'pid': state['pid']}).scalar()
                    if wait_type == 'Lock':
                        blocked = True
                        break
                    if deletion_job.done():
                        break
                    time.sleep(.05)
            assert blocked, 'Deletion must wait until analysis has persisted its results'
        finally:
            release_llm.set()
            analysis_job.result(timeout=10)
            if deletion_job is not None:
                deletion_job.result(timeout=10)
    with postgres_sessions() as db:
        assert db.query(ScannerRawRecord).count() == 0
        assert db.query(AnalysisRun).count() == 0
        assert db.query(RiskScore).count() == 0


def test_reactive_rebuild_uses_postgres_date_arithmetic_and_retained_jobs(postgres_sessions):
    with postgres_sessions() as db:
        db.add_all([
            ReactiveJobRecord(asset_id=1, job_number='1', source_file='remove.csv', job_entry_date=datetime(2026, 1, 1), priority_category=1),
            ReactiveJobRecord(asset_id=1, job_number='2', source_file='keep.csv', job_entry_date=datetime(2026, 1, 3), actual_comp_date=datetime(2026, 1, 5), priority_category=2, job_type_category='pothole'),
        ])
        db.flush()
        rebuild_reactive_aggregates(db, [1])
        db.commit()
        assert db.query(ReactiveAggregate).one().total_jobs_raised == 2
    with postgres_sessions() as db:
        assert admin.delete_dataset_upload(1, 'reactive', DatasetDelete(source_file='remove.csv'), db).status_code == 204
    with postgres_sessions() as db:
        aggregate = db.query(ReactiveAggregate).one()
        assert aggregate.total_jobs_raised == 1 and aggregate.urgent_jobs_24hr == 1
        assert aggregate.emergency_jobs_2hr == 0 and aggregate.pothole_count == 1
        assert aggregate.mean_days_to_completion == 2
        assert db.query(ReactiveJobRecord).one().source_file == 'keep.csv'
