from app import google_drive_storage


def test_drive_request_has_fresh_timed_transport(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "test-refresh-token")
    monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "test-folder-id")

    previous_service = getattr(google_drive_storage._SERVICE_LOCAL, "service", None)
    google_drive_storage._SERVICE_LOCAL.service = None
    try:
        service = google_drive_storage._service()
        first = service.files().get(fileId="sample-a", fields="id")
        second = service.files().get(fileId="sample-b", fields="id")

        assert first.http is not second.http
        assert first.http.http is not second.http.http
        assert first.http.http.timeout == google_drive_storage._DRIVE_HTTP_TIMEOUT_SECONDS
    finally:
        google_drive_storage._SERVICE_LOCAL.service = previous_service


def test_drive_api_call_uses_configured_retry_count():
    class Request:
        def __init__(self):
            self.retries = None

        def execute(self, num_retries):
            self.retries = num_retries
            return {"ok": True}

    request = Request()
    assert google_drive_storage._api_call(request) == {"ok": True}
    assert request.retries == google_drive_storage._DRIVE_API_RETRIES
