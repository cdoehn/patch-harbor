from __future__ import annotations

from threading import Thread

from patchharbor.progress import ActivityEvent, activity, observe_activity


def test_nested_observers_restore_and_can_be_disabled() -> None:
    outer, inner = [], []
    with observe_activity(outer.append):
        activity("a", "first")
        with observe_activity(inner.append):
            activity("b", "inner")
        with observe_activity(None):
            activity("c", "unobserved")
        activity("d", "last")
    activity("e", "outside")
    assert [event.phase for event in outer] == ["a", "d"]
    assert [event.phase for event in inner] == ["b"]


def test_observer_failure_does_not_replace_the_operation() -> None:
    def failing(event: ActivityEvent) -> None:
        raise RuntimeError("optional observer failed")

    facts = []
    with observe_activity(facts.append):
        with observe_activity(failing):
            activity("a", "still safe")
        activity("b", "restored")
    assert len(facts) == 1
    assert facts[0].phase == "b"


def test_observation_is_request_local_and_identifiers_remain_complete() -> None:
    main, worker = [], []
    identifier = "a" * 40

    def run() -> None:
        activity("a", "not inherited")
        with observe_activity(worker.append):
            activity("b", identifier, identifiers=(identifier,))

    with observe_activity(main.append):
        thread = Thread(target=run)
        thread.start()
        thread.join()
        activity("c", "parent")
    assert [event.phase for event in main] == ["c"]
    assert worker == [ActivityEvent("b", identifier, "info", (identifier,))]
