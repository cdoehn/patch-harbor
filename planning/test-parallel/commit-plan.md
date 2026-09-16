# PatchHarbor – pytest-xdist W/R/C-Plan

Ziel: Testinfrastruktur der bestehenden Version **1.2.0**, keine Versionsanhebung.
Spec: `planning/test-parallel/specification.md`.
Basis: `0c439b1c6400bdb12921ebaa5216620c9a122cd0`.
Dieser eigenständige Aufgabenplan verändert den abgeschlossenen
`planning/1.2.0/commit-plan.md` (4/4) nicht.

**Fortschritt nach erfolgreichem Commit dieses Zwischenstands: 4 / 15.**
Bei einem Abbruch sind nur die tatsächlich entstandenen Git-Commits erledigt.
Nicht committierte Fortschrittsangaben sind kein Erfolgsnachweis.

## Paketgrenzen

Bundle 1: a.W–b.C (Grundlage, expliziter Parallelbetrieb und Isolation).
Bundle 2: c.W–e.C (Ergebnisabnahme, paralleler Standard, CI und finale Dokumentation).
Die zweite Grenze und nicht benötigte C-Commits dürfen nach realem Befund
angepasst werden; keine leeren oder künstlich nachträglich zerlegten Commits.

Jeder W/R/C-Zustand entsteht einzeln: Dateien ändern, Gate ausführen,
Datei-/Indexumfang prüfen, Commit erstellen. Erst danach folgt der nächste.
Keine Installation des Endzustands vor dem ersten Commit, keine pauschalen
Rollbacks, kein Push zwischen Schritten. Dieses Bundle pusht nicht und führt
keine automatische Aktualisierung der produktiven pipx-Installation aus.
Ein abschließender Push/CI-Nachweis bleibt ein expliziter nachfolgender Vorgang.

## Schritte

1. **TEST-PARALLEL.a.W** – `test(runner): establish the serial pytest reference launcher`
   Status: implementiert, Commit nur nach Gate.
   Pytest ist bereits vorhanden. Ein zentraler Launcher und der vorhandene Bash-Einstieg verwenden den seriellen Referenzweg ohne künstliche Test-/Suitefrist. Vollständiger serieller Gate-Lauf.

2. **TEST-PARALLEL.a.R** – `test(runner): harden invocation and failure propagation`
   Status: implementiert, Commit nur nach Gate.
   Umgebung, Argumente, fremdes CWD, echte Exitcodes und Setup-/Teardown-Fehler absichern. Kein stiller grüner Ersatzlauf.

3. **TEST-PARALLEL.a.C** – `refactor(tests): separate launcher policy from process execution`
   Status: implementiert, Commit nur nach Gate.
   Launcher und wiederverwendbare Aufrufpolicy trennen; unverändertes Verhalten separat prüfen.

4. **TEST-PARALLEL.b.W** – `test(parallel): add opt-in pytest-xdist workers`
   Status: implementiert, Commit nur nach Gate.
   pytest-xdist ausschließlich als dev-Abhängigkeit; --workers 2/4/auto und --serial (-n 0), Standard vorläufig seriell. Vollständiger Zwei-Worker-Lauf.

5. **TEST-PARALLEL.b.R** – `test(parallel): isolate filesystem and worker process state`
   Status: offen.
   Lokale Benutzer-/Git-/Tempdaten und Prozesszustand isolieren; Importzustand kontrollieren; Paketquellenkopien vor flüchtigen Dateien schützen. Vollständiger Vier-Worker-Lauf.

6. **TEST-PARALLEL.b.C** – `refactor(tests): consolidate isolation and subprocess helpers`
   Status: offen.
   Gemeinsame Isolation und subprocess-Testhilfen zusammenführen, ohne fachliche Änderungen. Abschließend vollständige Läufe seriell, -n 2 und -n 4.

7. **TEST-PARALLEL.c.W** – `test(evidence): establish controller-owned result comparison`
   Status: offen.
   Vorhandene pytest-Berichte nutzen; nur Controller schreibt gemeinsame Ergebnisse. Keine Evidence-Infrastruktur auf Vorrat.

8. **TEST-PARALLEL.c.R** – `test(evidence): reject incomplete and crashed worker runs`
   Status: offen.
   Absichtliche Worker-Abstürze, fehlende Ergebnisse, unterschiedliche Sammlung, Setup/Teardown/Untertestfehler und unerwartete Skips prüfen.

9. **TEST-PARALLEL.c.C** – `refactor(evidence): separate result checks from pytest transport`
   Status: offen.
   Nur tatsächlich benötigte Ergebnisaggregation von pytest-Hooks trennen.

10. **TEST-PARALLEL.d.W** – `test(runner): enable parallel development runs by default`
   Status: offen.
   Erst nach Parallelabnahme standardmäßig auto, explizit seriell weiterhin möglich.

11. **TEST-PARALLEL.d.R** – `test(parallel): verify serial and worker-count equivalence`
   Status: offen.
   Komplette Serien für 0/2/4/auto mit mehreren Hash-Seeds; fachliche Inputs/IDs/Resultate vergleichen, keine Laufzeitversprechen.

12. **TEST-PARALLEL.d.C** – `refactor(tests): finalize shared parallel test policy`
   Status: offen.
   Policy konsolidieren: xdist verteilt; PatchHarbor entwickelt keinen Scheduler.

13. **TEST-PARALLEL.e.W** – `ci(tests): use pytest-xdist in existing acceptance lanes`
   Status: offen.
   Bestehende Betriebssystem-/Python-/PowerShell-Gates beibehalten; CI und Docker auf zentralen Teststart umstellen.

14. **TEST-PARALLEL.e.R** – `ci(tests): retain a blocking serial reference lane`
   Status: offen.
   Mindestens ein blockierender serieller CI-Referenzlauf; Fehler niemals durch retries/grüne Teilabnahmen verdecken.

15. **TEST-PARALLEL.e.C** – `docs(tests): finalize parallel test workflow and CI contracts`
   Status: offen.
   README, Spezifikation, Chat-Anweisungen, CI und Testdokumentation konsistent abschließen. Keine Dokumentations- oder Darstellungstests.
