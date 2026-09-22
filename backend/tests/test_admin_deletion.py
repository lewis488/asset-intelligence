from datetime import datetime

import pytest
from test_admin import api
from models.user import Authority, User
from models.asset import (Asset, ScannerRecord, ScannerRawRecord, CviRecord, CviRawRecord,
                          ScrimRecord, ReactiveJob, ReactiveJobRecord, ReactiveAggregate,
                          NetworkAsset, RiskScore, AnalysisRun)
from models.vaisala import (VaisalaSurvey, VaisalaSection, VaisalaInterval, VaisalaRagDriftLog,
                            VaisalaNetworkGeometry, VaisalaNetworkFeature)


@pytest.mark.parametrize("role", ["manager", "viewer", None])
def test_deletion_and_upload_inventory_require_admin(api, role):
    client, headers, _ = api
    for method, path in [
        ("DELETE", "/admin/users/2"), ("DELETE", "/admin/authorities/2"),
        ("GET", "/admin/authorities/1/uploads"),
        ("DELETE", "/admin/authorities/1/datasets/scanner"),
    ]:
        response = client.request(method, path, headers=headers.get(role, {}), json={"source_file": "test.csv"})
        assert response.status_code == (401 if role is None else 403)


def test_user_deletion_revokes_token_and_preserves_authority_data(api):
    client, headers, sessions = api
    users = client.get('/admin/users', headers=headers['admin']).json()
    manager = next(user for user in users if user['role'] == 'manager')
    admin = next(user for user in users if user['role'] == 'admin')
    assert client.delete(f"/admin/users/{admin['id']}", headers=headers['admin']).status_code == 409
    assert client.delete(f"/admin/users/{manager['id']}", headers=headers['admin']).status_code == 204
    assert client.get('/assets/', headers=headers['manager']).status_code == 401
    assert client.delete(f"/admin/users/{manager['id']}", headers=headers['admin']).status_code == 404
    with sessions() as db:
        assert db.get(Authority, 1) is not None
        assert db.get(User, admin['id']) is not None


def test_authority_requires_users_and_source_data_removed_first(api):
    client, headers, sessions = api
    auth = headers['admin']
    assert client.delete('/admin/authorities/1', headers=auth).status_code == 409
    with sessions() as db:
        asset = Asset(authority_id=2, nsg_ref='shared')
        db.add(asset); db.flush()
        db.add(ScannerRecord(asset_id=asset.id, source_file='survey.csv'))
        db.add(RiskScore(asset_id=asset.id, composite_score=50))
        db.add(AnalysisRun(authority_id=2, summary_text='Obsolete analysis'))
        db.commit()
    assert client.delete('/admin/authorities/2', headers=auth).status_code == 409
    assert client.request('DELETE', '/admin/authorities/2/datasets/scanner', headers=auth, json={'source_file': 'survey.csv'}).status_code == 204
    assert client.delete('/admin/authorities/2', headers=auth).status_code == 204
    assert client.delete('/admin/authorities/2', headers=auth).status_code == 404
    with sessions() as db:
        assert db.query(Asset).filter_by(authority_id=2).count() == 0
        assert db.get(Authority, 1) is not None


@pytest.mark.parametrize('dataset,model', [
    ('scanner', ScannerRecord), ('scanner', ScannerRawRecord), ('cvi', CviRecord),
    ('cvi', CviRawRecord), ('scrim', ScrimRecord), ('reactive', ReactiveJob),
    ('reactive', ReactiveJobRecord), ('network', NetworkAsset),
])
def test_source_file_deletion_preserves_other_files_types_and_authorities(api, dataset, model):
    client, headers, sessions = api
    with sessions() as db:
        a = Asset(authority_id=1, nsg_ref='same-road')
        b = Asset(authority_id=2, nsg_ref='same-road')
        db.add_all([a, b]); db.flush()
        for index, (asset, filename) in enumerate([(a, 'remove.csv'), (a, 'keep.csv'), (b, 'remove.csv')]):
            fields = {'source_file': filename}
            if model is NetworkAsset: fields.update(authority_id=asset.authority_id, nsg_ref=str(index))
            else: fields.update(asset_id=asset.id)
            if model is ReactiveJobRecord: fields.update(job_number=str(index), job_entry_date=datetime(2026, 1, 1))
            if model in (ScannerRawRecord, CviRawRecord, ScrimRecord): fields.update(survey_year=2020 + index)
            db.add(model(**fields))
        # Derived values must no longer describe the deleted inputs.
        db.add_all([RiskScore(asset_id=a.id), RiskScore(asset_id=b.id),
                    AnalysisRun(authority_id=1, summary_text='old'), AnalysisRun(authority_id=2, summary_text='keep')])
        db.commit()
    listing = client.get('/admin/authorities/1/uploads', headers=headers['admin']).json()
    assert {(entry['dataset_type'], entry['source_file']) for entry in listing} == {(dataset, 'remove.csv'), (dataset, 'keep.csv')}
    response = client.request('DELETE', f'/admin/authorities/1/datasets/{dataset}', headers=headers['admin'], json={'source_file': 'remove.csv'})
    assert response.status_code == 204, response.text
    with sessions() as db:
        assert db.query(model).count() == 2
        assert db.query(model).filter_by(source_file='keep.csv').count() == 1
        assert db.query(AnalysisRun).filter_by(authority_id=1).count() == 0
        assert db.query(AnalysisRun).filter_by(authority_id=2).count() == 1
        assert db.query(RiskScore).count() == 1


def test_reactive_deletion_rebuilds_totals_from_retained_jobs(api):
    client, headers, sessions = api
    with sessions() as db:
        asset = Asset(authority_id=1, nsg_ref='1')
        db.add(asset); db.flush()
        asset_id = asset.id
        db.add_all([
            ReactiveJobRecord(asset_id=asset_id, job_number='remove', source_file='remove.csv', job_entry_date=datetime(2026, 1, 1), priority_category=1, job_type_category='pothole'),
            ReactiveJobRecord(asset_id=asset_id, job_number='keep', source_file='keep.csv', job_entry_date=datetime(2026, 2, 1), actual_comp_date=datetime(2026, 2, 3), priority_category=2, job_type_category='patching'),
            ReactiveAggregate(asset_id=asset_id, year=2026, total_jobs_raised=99),
        ])
        db.commit()
    assert client.request('DELETE', '/admin/authorities/1/datasets/reactive', headers=headers['admin'], json={'source_file': 'remove.csv'}).status_code == 204
    with sessions() as db:
        result = db.query(ReactiveAggregate).filter_by(asset_id=asset_id).one()
        assert result.total_jobs_raised == 1
        assert result.emergency_jobs_2hr == 0 and result.urgent_jobs_24hr == 1
        assert result.pothole_count == 0 and result.patching_count == 1
        assert result.jobs_completed == 1 and result.jobs_outstanding == 0
        assert result.mean_days_to_completion == 2


def test_individual_vaisala_deletion_uses_id_and_authority_even_for_same_filename(api):
    client, headers, sessions = api
    with sessions() as db:
        surveys = [VaisalaSurvey(authority_id=authority_id, source_filename='same.xlsx', source_format='xlsx', network_key='test') for authority_id in [1, 1, 2]]
        db.add_all(surveys); db.flush()
        ids = [survey.id for survey in surveys]
        for survey in surveys:
            db.add_all([VaisalaSection(survey_id=survey.id, section_ref='A', length_m=10),
                        VaisalaInterval(survey_id=survey.id, section_ref='A', length_m=10),
                        VaisalaRagDriftLog(survey_id=survey.id, defect_key='edge', validated_weight=1, actual_weight=2)])
        db.commit()
    listing = client.get('/admin/authorities/1/uploads', headers=headers['admin']).json()
    assert {entry['upload_id'] for entry in listing} == set(ids[:2])
    assert all(entry['record_count'] == 1 for entry in listing)
    assert client.request('DELETE', '/admin/authorities/1/datasets/vaisala', headers=headers['admin'], json={'upload_id': ids[2]}).status_code == 404
    assert client.request('DELETE', '/admin/authorities/1/datasets/vaisala', headers=headers['admin'], json={'upload_id': ids[0]}).status_code == 204
    with sessions() as db:
        for model in [VaisalaSurvey, VaisalaSection, VaisalaInterval, VaisalaRagDriftLog]:
            assert db.query(model).count() == 2


def test_zero_record_geometry_is_listed_and_blocks_authority_deletion(api):
    client, headers, sessions = api
    with sessions() as db:
        empty = VaisalaNetworkGeometry(authority_id=2, source_filename='empty.zip', section_field='ref')
        full = VaisalaNetworkGeometry(authority_id=2, source_filename='full.zip', section_field='ref')
        db.add_all([empty, full]); db.flush()
        ids = [empty.id, full.id]
        db.add(VaisalaNetworkFeature(geometry_id=full.id, section_key='a', geometry_geojson='{}'))
        db.commit()
    listing = client.get('/admin/authorities/2/uploads', headers=headers['admin']).json()
    assert len(listing) == 2
    assert client.delete('/admin/authorities/2', headers=headers['admin']).status_code == 409
    for upload_id in ids:
        assert client.request('DELETE', '/admin/authorities/2/datasets/vaisala_network', headers=headers['admin'], json={'upload_id': upload_id}).status_code == 204
    assert client.delete('/admin/authorities/2', headers=headers['admin']).status_code == 204
    with sessions() as db:
        assert db.query(VaisalaNetworkFeature).count() == 0


def test_delete_requires_explicit_target_and_rejects_unknown_dataset(api):
    client, headers, _ = api
    for key, payload in [('scanner', {}), ('scanner', {'upload_id': 1}), ('vaisala', {'source_file': 'x'}), ('vaisala', {'upload_id': 1, 'source_file': 'x'})]:
        assert client.request('DELETE', f'/admin/authorities/1/datasets/{key}', headers=headers['admin'], json=payload).status_code == 422
    assert client.request('DELETE', '/admin/authorities/1/datasets/unknown', headers=headers['admin'], json={'source_file': 'x'}).status_code == 422


def test_public_registration_cannot_create_users_or_authorities(api):
    client, _, sessions = api
    for role in ['admin', 'manager', 'viewer']:
        assert client.post('/auth/register', json={'email': 'public@example.com', 'password': 'test-password', 'authority_name': 'Public', 'role': role}).status_code == 403
    with sessions() as db:
        assert db.query(Authority).count() == 2
        assert db.query(User).count() == 3


def test_source_groups_combine_legacy_raw_but_preserve_other_datasets(api):
    client, headers, sessions = api
    with sessions() as db:
        asset = Asset(authority_id=1, nsg_ref='1')
        db.add(asset); db.flush()
        db.add_all([ScannerRecord(asset_id=asset.id, source_file='same.csv'),
                    ScannerRawRecord(asset_id=asset.id, source_file='same.csv'),
                    ScannerRecord(asset_id=asset.id, source_file=None),
                    CviRecord(asset_id=asset.id, source_file='same.csv')])
        db.commit()
    rows = client.get('/admin/authorities/1/uploads', headers=headers['admin']).json()
    assert next(row for row in rows if row['dataset_type'] == 'scanner' and row['source_file'] == 'same.csv')['record_count'] == 2
    assert client.request('DELETE', '/admin/authorities/1/datasets/scanner', headers=headers['admin'], json={'source_file': 'same.csv'}).status_code == 204
    with sessions() as db:
        assert db.query(CviRecord).count() == 1
        assert db.query(ScannerRecord).count() == 1
    assert client.request('DELETE', '/admin/authorities/1/datasets/scanner', headers=headers['admin'], json={'source_file': None}).status_code == 204
    with sessions() as db:
        assert db.query(ScannerRecord).count() == 0


def test_cached_narrative_refreshes_after_source_deletion(api, monkeypatch):
    client, headers, sessions = api
    from routers import analysis
    from services import llm
    analysis._narrative_cache.clear()
    monkeypatch.setattr(llm, 'generate_asset_narrative', lambda context: context)
    with sessions() as db:
        asset = Asset(authority_id=1, nsg_ref='cache-test')
        db.add(asset); db.flush()
        db.add(ScannerRawRecord(asset_id=asset.id, source_file='scanner.csv', survey_year=2026, avg_ci=50, rci_band='Amber'))
        db.commit()
    first = client.post('/analysis/asset/cache-test', headers=headers['manager'])
    assert first.status_code == 200, first.text
    assert first.json()['data_used'] == ['SCANNER']
    assert client.post('/analysis/asset/cache-test', headers=headers['manager']).json()['cached'] is True
    assert client.request('DELETE', '/admin/authorities/1/datasets/scanner', headers=headers['admin'], json={'source_file': 'scanner.csv'}).status_code == 204
    after = client.post('/analysis/asset/cache-test', headers=headers['manager']).json()
    assert after['cached'] is False and after['data_used'] == []
    assert after['narrative'] != first.json()['narrative']
    analysis._narrative_cache.clear()


def test_deleted_vaisala_section_cannot_be_read_from_narrative_cache(api, monkeypatch):
    client, headers, sessions = api
    from routers import analysis
    analysis._narrative_cache.clear()
    monkeypatch.setattr(analysis, 'generate_vaisala_section_narrative', lambda context: 'Narrative')
    with sessions() as db:
        survey = VaisalaSurvey(authority_id=1, source_filename='cache.xlsx', source_format='xlsx', network_key='test')
        db.add(survey); db.flush()
        section = VaisalaSection(survey_id=survey.id, section_ref='A', length_m=10)
        db.add(section); db.flush()
        survey_id, section_id = survey.id, section.id
        db.commit()
    assert client.post(f'/analysis/vaisala/{section_id}', headers=headers['manager']).status_code == 200
    assert client.post(f'/analysis/vaisala/{section_id}', headers=headers['manager']).json()['cached'] is True
    assert client.request('DELETE', '/admin/authorities/1/datasets/vaisala', headers=headers['admin'], json={'upload_id': survey_id}).status_code == 204
    assert client.post(f'/analysis/vaisala/{section_id}', headers=headers['manager']).status_code == 404
    analysis._narrative_cache.clear()
