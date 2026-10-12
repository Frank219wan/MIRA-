import os
os.environ['MIRA_DATABASE_URL'] = 'sqlite:///:memory:'
from fastapi.testclient import TestClient
from integration.app import app

def test_special_area_http():
    client = TestClient(app)
    profile = {'schema_version':'0.1','image_sample_id':'test','areas':[{
        'area_id':'one','source':'user_selected','user_label':'','label_source':'user_provided',
        'location':'other','preference':'KEEP','polygon':[{'x_norm':.1,'y_norm':.1},{'x_norm':.2,'y_norm':.1},{'x_norm':.2,'y_norm':.2}]}]}
    response = client.post('/special-area-guidance',json={'profile':profile})
    assert response.status_code == 200
    assert response.json()['guidance_blocks'][0]['decision_source'] == 'user_preference'
    profile['areas'][0]['preference']='BAD'
    assert client.post('/special-area-guidance',json={'profile':profile}).status_code == 400

def test_compatibility_routes():
    paths = TestClient(app).get('/openapi.json').json()['paths']
    assert {'/face-scan','/personalization','/special-area-guidance','/tutorials/parse'} <= paths.keys()
