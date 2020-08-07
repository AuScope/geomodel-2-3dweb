#!/usr/bin/env python3

from fastapi.testclient import TestClient

from webapi.webapi import app

client = TestClient(app)


def test_read_item():
    response = client.get("/api/foo")
    assert response.status_code == 200
    assert response.json() == {
        "id": "foo",
        "title": "Foo",
        "description": "There goes my hero",
    }


