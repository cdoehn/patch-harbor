# Entwicklungstests – erster Parallelisierungsschritt

Aufgabenplan: `planning/test-parallel/commit-plan.md` (W/R/C).
Vertrag: `planning/test-parallel/specification.md`.

Nach Installation der Entwicklungsabhängigkeiten (`python -m pip install -e
'.[dev]'` in der Entwicklungs-venv) sind diese Aufrufe verfügbar:

```sh
python tools/run_tests.py --serial
python tools/run_tests.py --workers 2
python tools/run_tests.py --workers 4
python tools/run_tests.py --workers auto
python tools/run_tests.py --workers 2 -- tests/test_configuration.py
```

`scripts/test.sh` richtet wie bisher die lokale `.venv` ein und delegiert an
denselben Launcher, einschließlich übergebener Argumente. Der Launcher ist
auch unter Windows per Python aufrufbar. Das produktive PatchHarbor wird
nicht neu installiert. Ohne Argument bleibt der Standard bis Bundle 2 seriell.
Direktes `python -m pytest -n 0` oder `-n 2/4/auto` bleibt möglich; anders als
der Launcher übernimmt dieser direkte Aufruf geerbte `PYTEST_ADDOPTS`.

Keine neue Runtime-Abhängigkeit und kein eigener Scheduler. `auto` wird
unverändert an xdist übergeben; keine eigene CPU-Erkennung oder Workersteuerung.
Der Launcher verwendet keine Test-/Suitefrist und deaktiviert pytest-timeout.
Das äußere Apply-Limit bleibt separat und muss bei langen Gates ausdrücklich
mit `patchharbor apply --timeout 28800 ...` gesetzt werden.

## Isolationsprüfung

Bestandsaufnahme: vorhandene Tests verwenden bereits überwiegend tmp_path,
MonkeyPatch und private Git-/Registry-/Exchange-Umgebungen. Testhilfen und
Subprozesse sind Teil der Isolation, nicht nur Testfunktionen.

Zusätzlich gelten pro Test eigene Home-/Config-/State-/Temp-/Git-Umgebungen.
Die Prozesswache prüft nach dem Fixture-Teardown cwd, Umgebungsvariablen,
sys.path, globalen Zufallszustand und SIGINT/SIGTERM-Handler. Gefundene Leaks
machen den Test rot; Zustand wird danach zurückgesetzt, damit nachfolgende
Tests nicht nur Folgefehler melden. PYTEST_CURRENT_TEST wird von pytest selbst
verändert und ist von diesem Vergleich ausgenommen.

Die konkrete ungesicherte sys.modules-Entfernung im systemd-Test wird durch
MonkeyPatch zurückgesetzt. Keine pauschale Entladung normaler Lazy-Imports.
Die inspizierten Testhilfen verwenden keine zusätzlichen globalen lru_cache-
oder random.seed-Zustände; ein neu hinzukommender Cache braucht eigene
Rücksetz-/Isolationsprüfung. Dynamische Hilfsimporte sind gesondert zu prüfen.
Die vorhandenen Prozess-/Lock-Lifecycle-Tests bleiben erhalten; es wird kein
realer systemd-Dienst gestartet. Packaging arbeitet auf privaten Kopien,
ignoriert lokale .patchharbor-Daten und flüchtige pytest-/Tool-Caches.

Reale Zwei-/Vier-Worker-Regressionen erzeugen getrennte Repositories,
Benutzerpfade, Registry- und Lockdateien. Jeder Fall schreibt seine eigene
Beobachtungsdatei, pytest erzeugt den gemeinsamen JUnit-Bericht im Controller.
Das ist ein funktionaler Test, kein Test von Konsolenausgaben oder Laufzeiten.

## Noch nicht abgeschlossen

Die umfassenden Fehlernachweise für Worker-Abstürze, fehlende Ergebnisse,
abweichende Sammlung, unerwartete Skips, Hash-Seed-Vergleiche und auto-
Vollabnahme folgen in Bundle 2. Ebenso paralleler Standard, CI/Docker und
finale Anpassung der bestehenden README-/Chat-/Spezifikationspassagen.
Ein grüner Teiltest ist keine Aussage über den erfolgreichen lokalen Apply.
