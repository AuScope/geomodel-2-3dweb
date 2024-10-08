#!/usr/bin/env python3

import sys, os, shutil
import pytest
from fastapi.testclient import TestClient

from pathlib import Path
file_path = Path( __file__ ).absolute()

# Repo root path
root_path = file_path.parents[3]

# Add in path to local library files
sys.path.append(str(root_path / "scripts"))

# Copy in model files to support web interface
WEBAPI_INPUT = str(root_path / "scripts" / "webapi" / "input")
if not os.path.exists(WEBAPI_INPUT):
    os.mkdir(WEBAPI_INPUT)
    shutil.copy(str(root_path / "web_build" / "input" / "TasConvParam.json"), WEBAPI_INPUT)
    shutil.copy(str(file_path.parents[0] / "data" / "ProviderModelInfo.json"), WEBAPI_INPUT)

from webapi.webapi import app

client = TestClient(app)

# All tests marked with xfail because they make live HTTPS calls which may fail

@pytest.mark.xfail
def test_basic_error():
    response = client.get("/api/foo")
    assert response.status_code == 422 
    assert response.json() == {"detail":[
                                      {
                                "input": None,
                                "loc":["query","service"],
                                "msg":"Field required",
                                "type":"missing",
                                      },
                                      {
                                "input": None,
                                "loc":["query","version"],
                                "msg":"Field required",
                                "type":"missing",
                                      },
                                      {
                                "input": None,
                                "loc":["query","request"],
                                "msg":"Field required",
                                "type":"missing",
                                      }
                                ]
                              }


@pytest.mark.xfail
@pytest.mark.parametrize("service, version", [ ("3DPS", "1.0") ])
def test_getcap(service, version):
    # Test getCapabilities
    print("/api/tas?service={0}&request=GetCapabilities&version={1}".format(service, version))
    response = client.get("/api/tas?service={0}&request=GetCapabilities&version={1}".format(service, version))
    assert response.status_code == 200
    print(response.json())
    assert response.json()[:53] ==  '<?xml version="1.0" encoding="UTF-8"?>\n<Capabilities '
    


@pytest.mark.xfail
@pytest.mark.parametrize("url,retcode,msg", [
    # Unknown service name
    ("/api/model?service=BLAH&request=GetCapabilities&version=1.0", 200,
     "Unknown service name, should be one of: 'WFS', '3DPS'"),

    # 3DPS GetCapabilities: Unknown model name
    ("/api/model?service=3DPS&request=GetCapabilities&version=1.0", 200,
     {'exceptions': [{'code': 'OperationNotSupported', 'locator': 'noLocator', 'text': 'Unknown model name'}], 'version': '1.0'}),

    # 3DPS GetResourceById wrong version
    ("/api/tas?service=3DPS&request=GetResourceById&version=5.0", 200,
     {'exceptions': [{'code': 'OperationProcessingFailed', 'locator': 'noLocator', 'text': 'Incorrect version, try "1.0"'}], 'version': 'Unknown'}),

    # 3DPS unsupported request type
    ("/api/model?service=3DPS&request=GetScene&version=1.0", 200,
     {'exceptions': [{'code': 'OperationNotSupported', 'locator': 'getscene', 'text': 'Request type is not implemented'}], 'version': '1.0'}),

    # 3DPS GetResourceById unknown request
    ("/api/model?service=3DPS&request=GetResourceByIdd&version=1.0", 200,
     {'exceptions': [{'code': 'OperationNotSupported', 'locator': 'noLocator', 'text': 'Unknown request type'}], 'version': '1.0'}),

    # WFS wrong version
    ("/api/model?service=WFS&request=GetPropertyValue&version=1.0", 200,
     {'exceptions': [{'code': 'OperationProcessingFailed', 'locator': 'noLocator', 'text': 'Incorrect version, try "2.0"'}], 'version': 'Unknown'}),

    # WFS unknown request name
    ("/api/model?service=WFS&request=GetPropertyValuee&version=2.0", 200,
     {'exceptions': [{'code': 'OperationNotSupported', 'locator': 'noLocator', 'text': 'Unknown request name'}], 'version': '2.0'}),



    ])
def test_service_errors(url, retcode, msg):
    response = client.get(url)
    assert response.status_code == retcode
    assert response.json() == msg
