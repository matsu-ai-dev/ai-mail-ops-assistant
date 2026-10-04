import json

from lambda_handler import handler


def test_lambda_health():
    event = {
        "version": "2.0",
        "routeKey": "GET /health",
        "rawPath": "/health",
        "rawQueryString": "",
        "headers": {
            "host": "example.execute-api.local",
            "x-forwarded-proto": "https",
        },
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/health",
                "sourceIp": "127.0.0.1",
                "protocol": "HTTP/1.1",
            }
        },
        "isBase64Encoded": False,
    }

    response = handler(event, None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"status": "ok"}
