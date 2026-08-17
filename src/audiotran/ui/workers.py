from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QObject, Signal, Slot


@dataclass(slots=True)
class WorkerResult:
    stage: str
    payload: object | None = None
    error_message: str | None = None


class ProjectWorker(QObject):
    progress = Signal(int, str)
    result = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(
        self,
        stage: str,
        task: Callable[[ProjectWorker], object | None],
    ) -> None:
        super().__init__()
        self._stage = stage
        self._task = task

    def report_progress(self, percent: int, message: str) -> None:
        self.progress.emit(percent, message)

    @Slot()
    def run(self) -> WorkerResult:
        try:
            payload = self._task(self)
            outcome = WorkerResult(stage=self._stage, payload=payload)
            self.result.emit(outcome)
            return outcome
        except Exception as exc:  # pragma: no cover - exercised via signal path
            outcome = WorkerResult(stage=self._stage, error_message=str(exc) or exc.__class__.__name__)
            self.error.emit(outcome.error_message or "worker failed")
            return outcome
        finally:
            self.finished.emit()
