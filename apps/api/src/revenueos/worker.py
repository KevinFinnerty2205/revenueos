from __future__ import annotations

import asyncio
import logging
import signal
import uuid

from revenueos.ai_worker_services import AIWorkerService
from revenueos.campaign_worker import CampaignWorkerService
from revenueos.config import Settings, get_settings
from revenueos.create_worker import CreateWorkerService
from revenueos.database import create_engine, create_session_factory
from revenueos.integration_worker import ActionExecutionWorkerService
from revenueos.observability import configure_logging
from revenueos.prospect_worker import ProspectWorkerService
from revenueos.recording_worker import RecordingWorkerService

logger = logging.getLogger("revenueos.ai_worker")


class AIWorker:
    def __init__(
        self,
        service: AIWorkerService,
        settings: Settings,
        *,
        recording_service: RecordingWorkerService | None = None,
        execution_service: ActionExecutionWorkerService | None = None,
        prospect_service: ProspectWorkerService | None = None,
        campaign_service: CampaignWorkerService | None = None,
        create_service: CreateWorkerService | None = None,
        worker_id: str | None = None,
    ) -> None:
        self._service = service
        self._settings = settings
        self._recording_service = recording_service
        self._execution_service = execution_service
        self._prospect_service = prospect_service
        self._campaign_service = campaign_service
        self._create_service = create_service
        resolved_worker_id = (worker_id or f"worker-{uuid.uuid4().hex}").strip()
        if not resolved_worker_id or len(resolved_worker_id) > 200:
            raise ValueError("Worker identity must contain 1 to 200 characters.")
        self.worker_id = resolved_worker_id

    async def run(self, stop: asyncio.Event) -> None:
        logger.info("worker_started", extra={"worker_id": self.worker_id})
        try:
            while not stop.is_set():
                processed = await self.run_once()
                if processed:
                    continue
                try:
                    await asyncio.wait_for(
                        stop.wait(),
                        timeout=self._settings.worker_poll_interval_seconds,
                    )
                except TimeoutError:
                    pass
        finally:
            logger.info("worker_stopped", extra={"worker_id": self.worker_id})

    async def run_once(self) -> bool:
        prospect_processed = (
            await self._prospect_service.run_once(self.worker_id) if self._prospect_service is not None else False
        )
        recording_processed = await self._recording_service.run_once() if self._recording_service is not None else False
        campaign_prepared = (
            await self._campaign_service.run_once(self.worker_id) if self._campaign_service is not None else False
        )
        execution_processed = (
            await self._execution_service.run_once(self.worker_id) if self._execution_service is not None else False
        )
        campaign_reconciled = (
            await self._campaign_service.run_once(self.worker_id) if self._campaign_service is not None else False
        )
        create_processed = (
            await self._create_service.run_once(self.worker_id) if self._create_service is not None else False
        )
        organisations = await self._service.discover_eligible_organisations()
        processed = (
            prospect_processed
            or recording_processed
            or campaign_prepared
            or execution_processed
            or campaign_reconciled
            or create_processed
        )
        for organisation_id in organisations:
            cancelled = await self._service.cancel_pending_jobs(organisation_id)
            recovered = await self._service.recover_abandoned_jobs(organisation_id)
            claim = await self._service.claim_next_job(organisation_id, self.worker_id)
            processed = processed or bool(cancelled or recovered or claim)
            if claim is not None:
                await self._service.execute_claimed_job(claim)
        return processed


async def run_worker(settings: Settings | None = None) -> None:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    engine = create_engine(resolved_settings)
    session_factory = create_session_factory(engine)
    if engine is None or session_factory is None:
        raise RuntimeError("The AI worker requires API_DATABASE_URL to be configured.")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for shutdown_signal in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(shutdown_signal, stop.set)
        except NotImplementedError:
            pass

    worker = AIWorker(
        AIWorkerService(session_factory, resolved_settings),
        resolved_settings,
        recording_service=RecordingWorkerService(session_factory, resolved_settings),
        execution_service=ActionExecutionWorkerService(session_factory, resolved_settings),
        prospect_service=ProspectWorkerService(session_factory, resolved_settings),
        campaign_service=CampaignWorkerService(session_factory, resolved_settings),
        create_service=CreateWorkerService(session_factory, resolved_settings),
    )
    try:
        await worker.run(stop)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
