# Viewer — CI-Korrektur 081

## Auftrag und Basis

Der Nutzer beauftragt die Korrektur der verbleibenden CI-Fehler und ihre
Übernahme im Apply. Ein FIX-Commit:
`Fix: wait for published watcher targets [VIEW-03.W-FIX2]`.
Der Viewer-Planstand bleibt unverändert.

Ausgangscommit auf `dev`: `11586df722dd34c242ee43236bb40bc2785a285c`.
Frisches Result: `patchharbor-apply_Result_062623_1110_e8a8ab.zip`.
Result-SHA-256: `007125e60445a14072cdce764ad18ff759993977a38fd261cb2774adcfaaee10`.
Repository-ID: `e7a93d72-62dc-4759-97e8-6bf6cdf10e90`.
Fingerprint: `7c9d2a24e397e0e5` mit `patchharbor-state-v1`, sauber.
Alle 479 effektiven Dateien wurden nativ geprüft und vor Änderungen byte-
und modusgenau mit dem isolierten Development-Worktree verglichen.

## CI-Befund und Korrektur

Der [manuelle Lauf 42760853300](https://github.com/cdoehn/patch-harbor/actions/runs/42760853300)
auf dem Ausgangscommit enthält elf erfolgreiche und zwei fehlgeschlagene
Acceptance-Jobs. Alle Windows-Jobs bestehen einschließlich der Korrektur 080.
Ubuntu 24.04 mit Python 3.10 scheitert im Test
`test_watcher_instances_have_independent_files_and_shutdown` mit
`KeyError: 'targets'`.

Der Publisher darf bereits einen gültigen Startdatensatz ohne Ziele schreiben.
`update()` veröffentlicht die Zieländerung asynchron. Der bisherige Test wartete
nur auf das Vorhandensein irgendeines Datensatzes und las anschließend ungeprüft
das noch nicht veröffentlichte Feld. Der Fehler lässt sich zuverlässig
reproduzieren, indem beide ersten Startdatensätze vor den Updates gelesen werden.
Diese Reihenfolge ist jetzt ausdrücklich Bestandteil des bestehenden Tests.

Die Korrektur wartet pro Instanz auf die genaue erwartete Phase und Zielliste
und prüft die zurückgegebene Momentaufnahme. Sie bestätigt unterschiedliche
Instanz-IDs und zwei tatsächlich laufende, unvollständige Beobachtungen. Nach
dem Schließen der ersten Instanz müssen deren Abschluss und unveränderte Ziele
sichtbar sein, während die zweite ihre eigenen Ziele weiterhin aktiv meldet.
Produktcode, Wartefristen, Skips und CI-Matrix bleiben unverändert.

## Docker-Abbruch eingeordnet

Der zweite Fehler liegt vor den Produkttests: `apt-get install` im
Ubuntu-24.04-Image konnte drei Perl-Pakete von `security.ubuntu.com` wegen
Verbindungsfehlern nicht herunterladen und endete mit Exitcode 100.

Am 10. November 2026 wurden im unveränderten offiziellen `ubuntu:24.04`-Container
`apt-get update` und anschließend der Download von `perl-modules-5.38`,
`libperl5.38t64` und `perl` über die ursprünglichen Paketquellen erneut geprüft.
Dieser gezielte Infrastrukturcheck bestand mit Exitcode 0; einschließlich
Abhängigkeiten wurden 10,1 MB in fünf Sekunden heruntergeladen. Alle drei
ursprünglich fehlgeschlagenen Pakete hatten dieselbe Version
`5.38.2-3.2ubuntu0.7` wie im CI-Fehler.

Damit ist aktuell kein Fehler im Docker-Baurezept belegt. Es wird keine
unbegründete Mirror-Umstellung oder Wiederholung von Testläufen eingebaut.
Der Downloadcheck ist keine vollständige Docker-Abnahme. Die neue native CI
muss auch diesen Job erneut bestätigen.

## Prüfungen und Apply

Development prüft gezielt parallel mit vier Workern:
`tests/test_monitor_live.py`, `tests/test_monitor.py`, `tests/test_execution.py`
und `tests/test_output.py`. Berichte liegen außerhalb der getesteten Quellen.
Die Reproduktion vor der Korrektur scheitert am selben `targets`-Zugriff wie CI.

Die ZIP enthält ausschließlich den korrigierten Test und diese Dokumentation.
Der Entrypoint prüft Dateihashes und Git-Scope, führt vor dem einzelnen Commit
die vollständige parallele Suite mit vier Workern und Controller-Bericht aus
und pusht anschließend genau einmal normal nach `dev`. Fehler stoppen die
Ausführung ohne Rollback oder Erfolgsmarker.

Diese Datei beschreibt die vorbereitete Lieferung; erst das Result bestätigt
den Apply. Der bestehende Watcher übernimmt das atomar veröffentlichte Paket.
CI startet weiterhin ausschließlich Christian; weder Dienste noch installierte
Laufzeiten oder andere Projekte werden durch dieses Paket verändert.

Verträge: `planning/viewer/specification.md`, `docs/test-parallelism.md` und
`spec/SPECIFICATION.md`.
