from __future__ import annotations

import asyncio
import logging
import signal
import time
import uuid
from collections.abc import Callable

from revenueos.ai_worker_services import AIWorkerService
from revenueos.campaign_worker import CampaignWorkerService
from revenueos.config import Settings, get_settings
from revenueos.create_worker import CreateWorkerService
from revenueos.crm_connector_worker import CRMConnectorWorkerService
from revenueos.database import create_engine, create_session_factory
from revenueos.google_worker import GoogleSyncWorkerService
from revenueos.integration_worker import ActionExecutionWorkerService
from revenueos.microsoft_worker import MicrosoftSyncWorkerService
from revenueos.observability import configure_logging
from revenueos.prospect_worker import ProspectWorkerService
from revenueos.recording_worker import RecordingWorkerService

logger = logging.getLogger("revenueos.ai_worker")


class WorkerHealthServer:
    """Private liveness listener for the managed worker component."""

    def __init__(
        self,
        port: int,
        max_staleness_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._port = port
        self._max_staleness_seconds = max_staleness_seconds
        self._clock = clock
        self._last_tick = clock()
        self._server: asyncio.Server | None = None

    def tick(self) -> None:
        self._last_tick = self._clock()

    @property
    def healthy(self) -> bool:
        return self._clock() - self._last_tick <= self._max_staleness_seconds

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, "0.0.0.0", self._port)

    async def close(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=2.0)
            status = "200 OK" if self.healthy and request_line.startswith(b"GET /health ") else "503 Unavailable"
            body = b'{"status":"healthy"}' if status.startswith("200") else b'{"status":"unhealthy"}'
            writer.write(
                f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\nCache-Control: no-store\r\n"
                f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                + body
            )
            await writer.drain()
        except (ConnectionError, TimeoutError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()


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
        microsoft_service: MicrosoftSyncWorkerService | None = None,
        google_service: GoogleSyncWorkerService | None = None,
        crm_connector_service: CRMConnectorWorkerService | None = None,
        health_tick: Callable[[], None] | None = None,
        worker_id: str | None = None,
    ) -> None:
        self._service = service
        self._settings = settings
        self._recording_service = recording_service
        self._execution_service = execution_service
        self._prospect_service = prospect_service
        self._campaign_service = campaign_service
        self._create_service = create_service
        self._microsoft_service = microsoft_service
        self._google_service = google_service
        self._crm_connector_service = crm_connector_service
        self._health_tick = health_tick
        resolved_worker_id = (worker_id or f"worker-{uuid.uuid4().hex}").strip()
        if not resolved_worker_id or len(resolved_worker_id) > 200:
            raise ValueError("Worker identity must contain 1 to 200 characters.")
        self.worker_id = resolved_worker_id

    async def run(self, stop: asyncio.Event) -> None:
        logger.info("worker_started", extra={"worker_id": self.worker_id})
        try:
            while not stop.is_set():
                if self._health_tick is not None:
                    self._health_tick()
                processed = await self.run_once()
                if self._health_tick is not None:
                    self._health_tick()
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
        microsoft_processed = await self._microsoft_service.run_once() if self._microsoft_service is not None else False
        google_processed = await self._google_service.run_once() if self._google_service is not None else False
        crm_connector_processed = (
            await self._crm_connector_service.run_once(self.worker_id)
            if self._crm_connector_service is not None
            else False
        )
        organisations = await self._service.discover_eligible_organisations()
        processed = (
            prospect_processed
            or recording_processed
            or campaign_prepared
            or execution_processed
            or campaign_reconciled
            or create_processed
            or microsoft_processed
            or google_processed
            or crm_connector_processed
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

    prospect_service = ProspectWorkerService(session_factory, resolved_settings)
    health_server = (
        WorkerHealthServer(
            resolved_settings.worker_health_port,
            resolved_settings.worker_health_max_staleness_seconds,
        )
        if resolved_settings.worker_health_port is not None
        else None
    )
    worker = AIWorker(
        AIWorkerService(session_factory, resolved_settings),
        resolved_settings,
        recording_service=RecordingWorkerService(session_factory, resolved_settings),
        execution_service=ActionExecutionWorkerService(session_factory, resolved_settings),
        prospect_service=prospect_service,
        campaign_service=CampaignWorkerService(session_factory, resolved_settings),
        create_service=CreateWorkerService(session_factory, resolved_settings),
        microsoft_service=MicrosoftSyncWorkerService(session_factory, resolved_settings),
        google_service=GoogleSyncWorkerService(session_factory, resolved_settings),
        crm_connector_service=CRMConnectorWorkerService(session_factory, resolved_settings),
        health_tick=health_server.tick if health_server is not None else None,
    )
    try:
        if health_server is not None:
            await health_server.start()
        await worker.run(stop)
    finally:
        try:
            if health_server is not None:
                await health_server.close()
        finally:
            try:
                await prospect_service.aclose()
            finally:
                await engine.dispose()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
