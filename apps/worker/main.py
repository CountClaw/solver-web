import asyncio
import logging

from core.config import load_config
from core.db import init_db
from core.queue import RedisTaskQueue
from core.repositories import (
    ensure_seed_data,
    get_task,
    mark_task_failed,
    mark_task_processing,
    mark_task_ready,
    mark_task_retry,
    upsert_solver_node_status,
)
from core.settings_service import NetworkSettingsManager
from core.solver_client import SolverClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("solver-worker")
cfg = load_config()


class WorkerApp:
    def __init__(self):
        self.queue = RedisTaskQueue(cfg)
        self.network_settings = NetworkSettingsManager(self.queue)
        self.solver = SolverClient(cfg)
        self._running = True

    async def startup(self) -> None:
        init_db()
        ensure_seed_data()
        await self.queue.ensure_group()
        await self.network_settings.load_initial()
        await self.network_settings.start_listener()
        logger.info("Worker 启动完成，consumer=%s", cfg.task_consumer_name)

    async def shutdown(self) -> None:
        self._running = False
        await self.network_settings.close()
        await self.queue.close()

    async def _handle_message(self, message_id: str, payload: dict) -> None:
        task_id = str(payload.get("task_id") or "").strip()
        if not task_id:
            await self.queue.ack_task(message_id)
            return

        task = get_task(task_id)
        if not task:
            await self.queue.ack_task(message_id)
            return

        status = str(task.get("status") or "")
        if status in {"ready", "failed", "timeout"}:
            await self.queue.ack_task(message_id)
            return

        current = mark_task_processing(task_id)
        if not current:
            await self.queue.ack_task(message_id)
            return

        network = await self.network_settings.get_current()
        result = self.solver.solve_turnstile(current, network)
        if result.ok and result.token:
            mark_task_ready(task_id, result.token, result.node_url)
            if result.node_url:
                upsert_solver_node_status(result.node_url, "healthy", 0, None)
            await self.queue.ack_task(message_id)
            return

        attempts = int(current.get("attempts") or 0) + 1
        max_attempts = int(current.get("maxAttempts") or cfg.worker_max_attempts)
        error_code = str(result.error_code or "SOLVER_FAILED")
        error_desc = str(result.error_description or "solver 处理失败")

        if result.node_url:
            upsert_solver_node_status(result.node_url, "degraded", 0, error_desc)

        if result.retryable and attempts < max_attempts:
            mark_task_retry(task_id, attempts, error_code, error_desc)
            await asyncio.sleep(cfg.worker_retry_delay_ms / 1000.0)
            await self.queue.enqueue_task(
                {
                    "task_id": task_id,
                    "website_url": str(current.get("websiteURL") or ""),
                    "website_key": str(current.get("websiteKey") or ""),
                    "action": str(current.get("action") or ""),
                    "cdata": str(current.get("cdata") or ""),
                }
            )
            await self.queue.ack_task(message_id)
            return

        final_status = "timeout" if error_code == "SOLVER_TIMEOUT" else "failed"
        mark_task_failed(task_id, error_code, error_desc, solver_node=result.node_url, status=final_status)
        await self.queue.ack_task(message_id)

    async def run(self) -> None:
        await self.startup()
        try:
            while self._running:
                batches = await self.queue.read_tasks(cfg.task_consumer_name)
                if not batches:
                    continue
                for _, messages in batches:
                    for message_id, payload in messages:
                        try:
                            await self._handle_message(message_id, payload)
                        except Exception as exc:
                            logger.exception("处理消息失败: %s", exc)
        finally:
            await self.shutdown()


async def main() -> None:
    app = WorkerApp()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())

