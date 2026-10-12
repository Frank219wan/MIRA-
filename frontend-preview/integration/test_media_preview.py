import os
os.environ['MIRA_DATABASE_URL'] = 'sqlite:///:memory:'
from fastapi.testclient import TestClient
from integration.app import app
from integration import media_preview

def test_upload_preview(tmp_path, monkeypatch):
    monkeypatch.setattr(media_preview, 'DIRECTORY', tmp_path)
    client = TestClient(app)
    response = client.post('/media/preview', files={'file': ('photo.png', b'preview-bytes', 'image/png')})
    assert response.status_code == 200
    preview = client.get(response.json()['preview_path'])
    assert preview.content == b'preview-bytes'
    assert preview.headers['content-type'] == 'image/png'
    assert client.post('/media/preview', files={'file': ('x.html', b'x', 'text/html')}).status_code == 415
    assert client.post('/media/preview', files={'file': ('x.png', b'', 'image/png')}).status_code == 400
    monkeypatch.setattr(media_preview, 'MAX_BYTES', 2)
    assert client.post('/media/preview', files={'file': ('x.png', b'large', 'image/png')}).status_code == 413
    assert len(list(tmp_path.iterdir())) == 1
    path = next(tmp_path.iterdir())
    os.utime(path, (0, 0))
    assert client.get(response.json()['preview_path']).status_code == 404
