"""Tests for the Sleep Engine idle lifecycle."""

from collections.abc import Callable

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

    def _tasks(self):
        return [self._task_one, self._task_two]

    def _task_one(self) -> None:
        self.task_runs.append("one")

    def _task_two(self) -> None:
        self.task_runs.append("two")


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
