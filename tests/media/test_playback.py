from __future__ import annotations

from pathlib import Path


class FakeSignal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback

    def emit(self, value: int) -> None:
        assert self.callback is not None
        self.callback(value)


class FakePlayer:
    def __init__(self) -> None:
        self.positionChanged = FakeSignal()
        self.source = None
        self.position = None
        self.play_count = 0
        self.stop_count = 0

    def setSource(self, source) -> None:
        self.source = source

    def setPosition(self, position: int) -> None:
        self.position = position

    def play(self) -> None:
        self.play_count += 1

    def stop(self) -> None:
        self.stop_count += 1


def test_local_playback_service_plays_local_cue_range_with_player_adapter(tmp_path: Path):
    from audiotran.media.playback import LocalPlaybackService

    audio_path = tmp_path / "voice.mp3"
    player = FakePlayer()
    service = LocalPlaybackService(player=player)

    service.play(audio_path, start=1.25, end=2.75)

    assert Path(player.source.toLocalFile()) == audio_path.resolve()
    assert player.position == 1250
    assert player.play_count == 1

    player.positionChanged.emit(2749)
    assert player.stop_count == 0

    player.positionChanged.emit(2750)
    assert player.stop_count == 1
