import os
import pytest
os.environ['MIRA_DATABASE_URL'] = 'sqlite:///:memory:'
from fastapi.testclient import TestClient
from integration.app import app
from integration import media_preview
from src.services.tutorial_parser import MockTutorialVisionProvider


@pytest.mark.parametrize("filename,mime,kind", [("x.png","image/png","frame_directory"),("x.mp4","video/mp4","video")])
def test_uploaded_media_reaches_provider_and_is_saved(tmp_path, monkeypatch, filename, mime, kind):
    monkeypatch.setattr(media_preview, 'DIRECTORY', tmp_path)
    from src.db.session import create_week1_engine, bootstrap_database, create_session_factory
    engine = create_week1_engine('sqlite:///' + str(tmp_path / 'test.db'))
    bootstrap_database(engine)
    monkeypatch.setattr(app.state, 'session_factory', create_session_factory(engine))
    monkeypatch.setattr(media_preview, 'DIRECTORY', tmp_path / 'uploads')
    client = TestClient(app)
    expected = b'uploaded image bytes'
    upload = client.post('/media/preview', files={'file': (filename, expected, mime)}).json()
    monkeypatch.setattr(app.state.tutorial_parser, 'provider', MockTutorialVisionProvider())
    body = {'upload_id': upload['upload_id'], 'title': 'uploaded tutorial'}
    assert client.post('/tutorials/parse-upload', json=body).status_code == 503
    class TestProvider:
        provider_name = 'test-provider'
        def extract_action_units(self, media, prompt):
            assert media.media_kind == kind
            path = media.media_path if kind == 'video' else next(media.media_path.iterdir())
            assert path.read_bytes() == expected
            return {'action_units':[{'step_index':1,'area':'眼皮','goal':'打底',
                'product_requirement':'浅紫色眼影','tool':'眼影刷','motion':'轻扫',
                'intensity':'轻','target_result':'均匀底色'}]}
    monkeypatch.setattr(app.state.tutorial_parser, 'provider', TestProvider())
    response = client.post('/tutorials/parse-upload', json=body)
    assert response.status_code == 200
    assert len(response.json()['action_units']) == 1
    assert client.get('/recipes/' + response.json()['recipe_id']).json() == response.json()
    assert client.post('/tutorials/parse-upload', json={**body,'upload_id':'../../etc/passwd'}).status_code == 404
