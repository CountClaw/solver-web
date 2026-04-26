from core.errors import error_response, processing_response, ready_response


def test_error_response_shape():
    data = error_response("ERROR_TEST", "desc")
    assert data["errorId"] == 1
    assert data["errorCode"] == "ERROR_TEST"
    assert data["errorDescription"] == "desc"


def test_processing_response_shape():
    data = processing_response()
    assert data == {"errorId": 0, "status": "processing"}


def test_ready_response_shape():
    data = ready_response("token-value")
    assert data["errorId"] == 0
    assert data["status"] == "ready"
    assert data["solution"]["token"] == "token-value"

