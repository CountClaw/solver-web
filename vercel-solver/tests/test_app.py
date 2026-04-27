import asyncio

from src.app_factory import create_app
from src.config import Settings
from src.solver_client import SolverResult


class FakeSolverClient:
    def __init__(self, result: SolverResult):
        self.result = result
        self.received_task = None

    def solve_turnstile(self, task):
        self.received_task = task
        return self.result


def build_settings() -> Settings:
    return Settings(
        client_keys=("swk_demo_key",),
        solver_node_urls=("http://solver-1.example",),
        solver_poll_interval_ms=250,
        solver_max_wait_seconds=40,
        solver_connect_timeout_ms=2500,
        solver_read_timeout_ms=5000,
        outbound_proxy_url="",
        outbound_no_proxy="localhost,127.0.0.1,::1",
    )


def test_health_endpoint():
    async def scenario():
        app = create_app(settings=build_settings(), solver_client=FakeSolverClient(SolverResult(True, "token", None, None, None)))
        client = app.test_client()
        response = await client.get("/health")
        data = await response.get_json()

        assert response.status_code == 200
        assert data["ok"] is True
        assert data["service"] == "vercel-solver"

    asyncio.run(scenario())


def test_solve_success_and_cdata_normalization():
    async def scenario():
        fake_solver = FakeSolverClient(
            SolverResult(
                ok=True,
                token="token-value",
                node_url="http://solver-1.example",
                error_code=None,
                error_description=None,
            )
        )
        app = create_app(settings=build_settings(), solver_client=fake_solver)
        client = app.test_client()

        response = await client.post(
            "/solve",
            json={
                "clientKey": "swk_demo_key",
                "task": {
                    "type": "TurnstileTaskProxyless",
                    "websiteURL": "https://example.com",
                    "websiteKey": "0x4AAAAAAA",
                    "action": "login",
                    "cData": "custom-data",
                },
            },
        )
        data = await response.get_json()

        assert response.status_code == 200
        assert data["errorId"] == 0
        assert data["status"] == "ready"
        assert data["solution"]["token"] == "token-value"
        assert fake_solver.received_task["action"] == "login"
        assert fake_solver.received_task["cdata"] == "custom-data"

    asyncio.run(scenario())


def test_solve_invalid_client_key():
    async def scenario():
        app = create_app(
            settings=build_settings(),
            solver_client=FakeSolverClient(SolverResult(True, "token", None, None, None)),
        )
        client = app.test_client()
        response = await client.post(
            "/solve",
            json={
                "clientKey": "bad-key",
                "task": {
                    "type": "TurnstileTaskProxyless",
                    "websiteURL": "https://example.com",
                    "websiteKey": "0x4AAAAAAA",
                },
            },
        )
        data = await response.get_json()

        assert response.status_code == 200
        assert data["errorCode"] == "ERROR_KEY_DOES_NOT_EXIST"

    asyncio.run(scenario())


def test_solve_bad_payload():
    async def scenario():
        app = create_app(
            settings=build_settings(),
            solver_client=FakeSolverClient(SolverResult(True, "token", None, None, None)),
        )
        client = app.test_client()
        response = await client.post(
            "/solve",
            json={
                "clientKey": "swk_demo_key",
                "task": {
                    "type": "TurnstileTaskProxyless",
                    "websiteURL": "https://example.com",
                },
            },
        )
        data = await response.get_json()

        assert response.status_code == 200
        assert data["errorCode"] == "ERROR_BAD_TASK_DATA"

    asyncio.run(scenario())


def test_solve_returns_solver_error():
    async def scenario():
        app = create_app(
            settings=build_settings(),
            solver_client=FakeSolverClient(
                SolverResult(
                    ok=False,
                    token=None,
                    node_url=None,
                    error_code="SOLVER_TIMEOUT",
                    error_description="等待 solver 结果超时",
                    retryable=True,
                )
            ),
        )
        client = app.test_client()
        response = await client.post(
            "/solve",
            json={
                "clientKey": "swk_demo_key",
                "task": {
                    "type": "TurnstileTaskProxyless",
                    "websiteURL": "https://example.com",
                    "websiteKey": "0x4AAAAAAA",
                },
            },
        )
        data = await response.get_json()

        assert response.status_code == 200
        assert data["errorCode"] == "SOLVER_TIMEOUT"

    asyncio.run(scenario())


def test_deprecated_endpoints():
    async def scenario():
        app = create_app(
            settings=build_settings(),
            solver_client=FakeSolverClient(SolverResult(True, "token", None, None, None)),
        )
        client = app.test_client()

        for path in ("/createTask", "/getTaskResult", "/admin/keys"):
            response = await client.post(path)
            data = await response.get_json()
            assert response.status_code == 410
            assert data["errorCode"] == "ERROR_UNSUPPORTED_ENDPOINT"

    asyncio.run(scenario())
