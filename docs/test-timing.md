# Getrennte Testlaufzeiten

Der vorhandene Launcher `python tools/run_tests.py --workers auto --report
build/tests.json` schreibt normale Phasenmessungen als additive `telemetry`
(Format 1) in den vorhandenen Report (Format 2). Der Ablauf, die Worker-Nachweise,
Beweissignaturen und Erfolgsgates bleiben unverändert.

`setup` ist Vorbereitung, `call` die Ausführung innerhalb der Pytest-call-Phase,
`teardown` das Aufräumen. Die call-Phase enthält dort gestartete Prozesse,
dynamisch angeforderte Fixtures und einen kleinen Frameworkanteil. Fehlende
Phasen sind unbekannt; nach fehlgeschlagenem/übersprungenem Setup ist call
`not_run`. Nur tatsächlich gemessene Null ist eine Nullzeit.

`tools.timing_model.case_timings(report)` liefert die drei Phasen und eine Testgesamtzeit, soweit
alle benötigten Beobachtungen vorliegen. `rank(report)` sortiert standardmäßig
nach call; `phase='setup'` und `phase='teardown'` liefern getrennte Ranglisten.
Subtests bleiben zusätzliche Beobachtungen und werden nicht noch einmal zur
übergeordneten call-Phase addiert.

Jede Fixtureinstanz hat Scope, Parameterindex, Worker, inklusive Setup-Spanne,
Finalisierungszeitpunkt und tatsächliche Verbraucher. Der Parameterwert wird
nicht serialisiert. Verbraucher werden aus dem bereits aufgelösten Pytest-Cache
gelesen, ohne Fixtures anzufordern. Die Finalisierungsdauer bleibt unbekannt:
der öffentliche Post-Finalizer-Hook hat keine Startgrenze. Die teardown-Phase
misst trotzdem das gesamte beobachtete Aufräumen. Fixturezeiten sind enthaltene
Spannen, keine zusätzlichen Kosten pro Verbraucher.

Alle Intervalle beziehen sich auf die monotone Uhr ihres Prozesses. UTC dient
der Einordnung. Workerstart/-ende werden zusätzlich an der Controller-Uhr
beobachtet. Überlappende Workerzeiten werden nie als Job-Walltime summiert.
Imports vor Registrierung, übrige Session-End-Hooks, Reportpublikation und
CPU-Zeit sind ausdrücklich nicht vollständig instrumentiert.

Messfehler und fehlende Worker ergeben partielle Telemetrie. Der gesonderte
Reader prüft Run-/Quellbindung und Messwerte, kann aber auch rote Testreports
lesen. Er bestätigt keine erfolgreiche Abnahme. Die strenge Abnahme bleibt
ausschließlich Aufgabe von `test_results.validate()`.

`tools/timing_capture.py` enthält ausschließlich den Pytest-Messadapter und
seine Fehlergrenze. `tools/timing_model.py` liest und bewertet die Messdaten
ohne Pytest-/Core-Import oder Dateizugriff. `tools/test_evidence.py` übernimmt
nur das additive Feld in seinen bestehenden atomaren Report-Schreibpfad.

Das ist normale Zeitbeobachtung, kein Profiling: cProfile, tracemalloc, strace
und die lokale Datenbank gehören zum folgenden, ausdrücklich gestarteten
Profiling-Werkzeug. Keine zusätzlichen Prozesse oder Uploads entstehen hier.

Hookverträge: [Pytest-Referenz](https://docs.pytest.org/en/stable/reference/reference.html#pytest.hookspec.pytest_fixture_setup)
und [Hook-Wrapper](https://docs.pytest.org/en/stable/how-to/writing_hook_functions.html#hook-wrappers-executing-around-other-hooks).
