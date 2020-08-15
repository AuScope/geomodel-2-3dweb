#!/usr/bin/env python3

from fastapi.testclient import TestClient
import sys, os
import pytest

# Add in path to local library files
sys.path.append(os.path.join('..', '..', '..', 'scripts'))

from webapi.webapi import app

client = TestClient(app)


def test_basic_error():
    response = client.get("/api/foo")
    assert response.status_code == 422 
    assert response.json() == {"detail":[
                                      {
                                "loc":["query","service"],
                                "msg":"field required",
                                "type":"value_error.missing"
                                      },
                                      {
                                "loc":["query","version"],
                                "msg":"field required",
                                "type":"value_error.missing"
                                      },
                                      {
                                "loc":["query","request"],
                                "msg":"field required",
                                "type":"value_error.missing"}
                                      ]}


@pytest.mark.parametrize("url,retcode,msg", [
    # Unknown service name
    ("/api/model?service=BLAH&request=GetCapabilities&version=1.0", 200,
     {"message":"Unknown service name, should be one of: 'WFS', '3DPS'"}),

    # Unknown model name
    ("/api/model?service=3DPS&request=GetCapabilities&version=1.0", 200,
     {'message': {'exceptions': [{'code': 'OperationNotSupported', 'locator': 'noLocator', 'text': 'Unknown model name'}], 'version': '1.0'}})
    ])

def test_service_errors(url, retcode, msg):
    response = client.get(url)
    assert response.status_code == retcode
    assert response.json() == msg
