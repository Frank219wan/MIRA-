import os
os.environ['MIRA_DATABASE_URL'] = 'sqlite:///:memory:'
import json
from pathlib import Path
from fastapi.testclient import TestClient
from integration.app import app


def test_static_guidance_and_reference():
    client = TestClient(app)
    ref = client.get('/references/cat-eye').json()
    assert [s['action_id'] for s in ref['steps']] == ['A02','A04']
    assert ref['source'] == 'curated-reference'
    points = [{'x':.5,'y':.5} for _ in range(468)]
    for ids, xs in [([263,373,374,380,382,362],[.8,.76,.72,.68,.64,.6]),([33,144,145,153,155,133],[.2,.24,.28,.32,.36,.4])]:
        for i,x in zip(ids,xs): points[i]={'x':x,'y':.5 + (.02 if i not in [263,362,33,133] else 0)}
    profile = json.loads((Path(__file__).parents[1]/'tests/fixtures/face_profile_v0_3.json').read_text())
    body={'image_id':'photo-1','reference_id':'cat_eye_main_demo','action_id':'A04','landmarks':points,'face_profile':profile}
    for action,kind in [('A04','direction_line'),('A02','target_region')]:
        body['action_id']=action
        response=client.post('/guidance/static',json=body)
        assert response.status_code == 200, response.text
        assert response.json()['image_id']=='photo-1'
        assert {s['side'] for s in response.json()['shapes']} == {'left','right'}
        assert all(s['guidance_type']==kind for s in response.json()['shapes'])
    body['reference_id']='invented'
    assert client.post('/guidance/static',json=body).status_code in (400,422)
    body['reference_id']='cat_eye_main_demo';body['landmarks']=[]
    assert client.post('/guidance/static',json=body).status_code in (400,422)
