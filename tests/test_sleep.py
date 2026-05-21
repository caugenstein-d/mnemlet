"""Tests for the Sleep Engine idle lifecycle."""

from collections.abc import Callable
from threading import Event

from mnemlet.engine.sleep import SleepEngine


class FakeClock:
    """Controllable monotonic-style clock for sleep tests."""

    def __init__(self, now: float = 1_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FastSleepEngine(SleepEngine):
    """SleepEngine with deterministic no-op tasks for fast tests."""

    def __init__(self, clock: Callable[[], float], threshold: int = 10) -> None:
        super().__init__(
            db=None,
            chroma=None,
            embedder=None,
            vault=None,
            decay_engine=None,
            inactivity_threshold_seconds=threshold,
            clock=clock,
            task_cooldown_seconds=0,
        )
        self.task_runs: list[str] = []

    def _tasks(self) -> list[Callable[[], None]]:
        return [self._task_one, self._task_two]

    def _task_one(self) -> None:
        self.task_runs.append("one")

    def _task_two(self) -> None:
        self.task_runs.append("two")


class FailingSleepEngine(FastSleepEngine):
    """SleepEngine with a task that fails deterministically."""

    def _tasks(self) -> list[Callable[[], None]]:
        return [self._task_one, self._task_fails]

    def _task_fails(self) -> None:
        self.task_runs.append("fails")
        raise RuntimeError("boom")


class BlockingSleepEngine(FastSleepEngine):
    """SleepEngine with a task that blocks until stop is requested."""

    def __init__(self, clock: Callable[[], float], threshold: int = 10) -> None:
        super().__init__(clock=clock, threshold=threshold)
        self.entered = Event()

    def _tasks(self) -> list[Callable[[], None]]:
        return [self._task_blocking, self._task_two]

    def _task_blocking(self) -> None:
        self.task_runs.append("blocking")
        self.entered.set()
        while self._running:
            self.entered.wait(timeout=0.001)


class IgnoringStopSleepEngine(SleepEngine):
    """SleepEngine with a task that ignores stop until released."""

    def __init__(self, clock: Callable[[], float], threshold: int = 10) -> None:
        super().__init__(
            db=None,
            chroma=None,
            embedder=None,
            vault=None,
            decay_engine=None,
            inactivity_threshold_seconds=threshold,
            clock=clock,
            task_cooldown_seconds=0,
            stop_join_timeout_seconds=0.01,
        )
        self.entered = Event()
        self.release = Event()
        self.task_runs: list[str] = []

    def _tasks(self) -> list[Callable[[], None]]:
        return [self._task_blocking]

    def _task_blocking(self) -> None:
        self.task_runs.append("blocking")
        self.entered.set()
        self.release.wait(timeout=2)


def wait_for_engine(engine: SleepEngine) -> None:
    """Wait for the engine's background thread to finish."""
    assert engine._thread is not None
    engine._thread.join(timeout=2)
    assert not engine._thread.is_alive()


def test_should_sleep_after_inactivity_threshold() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)

    assert engine.should_sleep() is False
    clock.advance(11)

    assert engine.should_sleep() is True


def test_completed_run_does_not_immediately_sleep_again() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)
    clock.advance(11)

    assert engine.start() == {"status": "started"}
    wait_for_engine(engine)

    assert engine.state == "completed"
    assert engine.should_sleep() is False
    assert engine.task_runs == ["one", "two"]


def test_completed_run_cannot_restart_in_same_epoch_after_threshold() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)
    clock.advance(11)

    assert engine.start() == {"status": "started"}
    wait_for_engine(engine)
    first_thread = engine._thread

    clock.advance(11)

    assert engine.should_sleep() is False
    assert engine.start() == {"status": "not_ready", "state": "completed"}
    assert engine._thread is first_thread
    assert engine.task_runs == ["one", "two"]


def test_task_failure_does_not_complete_epoch_and_allows_retry() -> None:
    clock = FakeClock()
    engine = FailingSleepEngine(clock=clock, threshold=10)
    clock.advance(11)

    assert engine.start() == {"status": "started"}
    wait_for_engine(engine)

    assert engine.state != "completed"
    assert engine.status()["completed_activity_epoch"] is None
    assert engine.status()["last_completed"] is None
    assert engine.should_sleep() is True
    assert engine.start() == {"status": "started"}
    wait_for_engine(engine)
    assert engine.task_runs == ["one", "fails", "one", "fails"]


def test_stopped_run_does_not_complete_epoch_and_allows_retry() -> None:
    clock = FakeClock()
    engine = BlockingSleepEngine(clock=clock, threshold=10)
    clock.advance(11)

    assert engine.start() == {"status": "started"}
    assert engine.entered.wait(timeout=2)
    assert engine.stop()["status"] == "stopped"

    assert engine.state != "completed"
    assert engine.status()["completed_activity_epoch"] is None
    assert engine.status()["last_completed"] is None
    assert engine.should_sleep() is True
    assert engine.start() == {"status": "started"}
    assert engine.entered.wait(timeout=2)
    assert engine.stop()["status"] == "stopped"
    assert engine.task_runs == ["blocking", "blocking"]


def test_live_worker_prevents_restart_after_stop_timeout() -> None:
    clock = FakeClock()
    engine = IgnoringStopSleepEngine(clock=clock, threshold=10)

    assert engine.start(force=True) == {"status": "started"}
    assert engine.entered.wait(timeout=2)
    first_thread = engine._thread

    assert engine.stop()["status"] == "stopped"
    assert first_thread is not None
    assert first_thread.is_alive()
    assert engine.start(force=True) == {"status": "already_running"}
    assert engine._thread is first_thread
    assert engine.task_runs == ["blocking"]

    engine.release.set()
    wait_for_engine(engine)

    assert engine.start(force=True) == {"status": "started"}
    wait_for_engine(engine)
    assert engine.task_runs == ["blocking", "blocking"]


def test_checkpoint_accessors_return_copies() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)
    clock.advance(11)

    assert engine.start() == {"status": "started"}
    wait_for_engine(engine)

    checkpoint = engine.checkpoint
    checkpoint["_task_one"] = False
    status = engine.status()
    status["checkpoint"]["_task_two"] = False

    assert engine.checkpoint == {"_task_one": True, "_task_two": True}
    assert engine.status()["checkpoint"] == {"_task_one": True, "_task_two": True}


def test_new_activity_allows_future_sleep_cycle() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)
    clock.advance(11)
    engine.start()
    wait_for_engine(engine)

    engine.bump_activity()
    assert engine.state == "idle"
    assert engine.should_sleep() is False

    clock.advance(11)
    assert engine.should_sleep() is True


def test_checkpoints_are_scoped_to_each_run() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)
    clock.advance(11)
    engine.start()
    wait_for_engine(engine)

    engine.bump_activity()
    clock.advance(11)
    engine.start()
    wait_for_engine(engine)

    assert engine.task_runs == ["one", "two", "one", "two"]


def test_parallel_runs_are_prevented_even_when_force_is_true() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)
    clock.advance(11)

    assert engine.start() == {"status": "started"}
    assert engine.start(force=True) == {"status": "already_running"}

    wait_for_engine(engine)


def test_start_reports_not_ready_before_threshold() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)

    assert engine.start() == {"status": "not_ready", "state": "idle"}
    assert engine._thread is None


def test_force_start_runs_before_threshold() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)

    assert engine.start(force=True) == {"status": "started"}
    wait_for_engine(engine)

    assert engine.task_runs == ["one", "two"]
