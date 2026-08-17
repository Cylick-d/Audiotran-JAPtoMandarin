from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QUrl, Slot


class PlaybackError(RuntimeError):
    pass


class LocalPlaybackService(QObject):
    def __init__(self, parent: QObject | None = None, *, player: Any | None = None) -> None:
        super().__init__(parent)
        self._player = player
        self._audio_output: Any | None = None
        self._cue_end_ms: int | None = None
        if player is not None:
            self._connect_player(player)

    def play(self, audio_path: Path, start: float, end: float) -> None:
        if start < 0 or end <= start:
            raise ValueError("cue playback requires a positive time range")

        player = self._ensure_player()
        self._cue_end_ms = round(end * 1000)
        player.setSource(QUrl.fromLocalFile(str(Path(audio_path).resolve())))
        player.setPosition(round(start * 1000))
        player.play()

    def _ensure_player(self):
        if self._player is not None:
            return self._player

        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        except ImportError as exc:
            raise PlaybackError("PySide6 Qt Multimedia support is unavailable") from exc

        self._audio_output = QAudioOutput(self)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio_output)
        self._connect_player(self._player)
        return self._player

    def _connect_player(self, player) -> None:
        player.positionChanged.connect(self._stop_at_cue_end)

    @Slot(int)
    def _stop_at_cue_end(self, position: int) -> None:
        if self._cue_end_ms is None or position < self._cue_end_ms:
            return
        self._player.stop()
        self._cue_end_ms = None
