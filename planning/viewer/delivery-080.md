# Viewer — CI-Korrektur 080

## Auftrag und geprüfte Basis

Der Nutzer beauftragt die Korrektur der GitHub-CI auf `dev` und die Lieferung
als PatchHarbor-Paket im konfigurierten Exchange. Ein fachlicher FIX-Commit:
`Fix: synchronize live Apply observation test [VIEW-03.W-FIX1]`.
Der Implementierungsplan wird nicht erweitert.

GitHub- und lokaler Ausgangscommit:
`725c1ed8825909e92be31b874d88c2da6644f55c`.

Frisch erzeugtes Result: `patchharbor-apply_Result_215929_1109_5a8328.zip`.
SHA-256: `90e02644a551fdf06df084338dfc285a8ccf220d8c5819787ec5b0b39430e1a8`.
Repository-ID: `e7a93d72-62dc-4759-97e8-6bf6cdf10e90`.
Fingerprint: `7c9d2a24e397e0e5`, Algorithmus `patchharbor-state-v1`, sauber.
Alle 478 effektiven Dateien wurden nativ aus dem Result validiert und vor
Änderungen byte- und modusgenau mit dem isolierten Development-Worktree verglichen.

## Befund und Korrektur

Im [manuellen CI-Lauf 42686105237](https://github.com/cdoehn/patch-harbor/actions/runs/42686105237)
scheitert ausschließlich die Windows-2025-/Python-3.12-Lane. Der Core-Test
`test_actual_apply_publishes_effective_timeout_output_and_result` wartet acht
Sekunden ab Apply-Start auf den effektiven Entrypoint-Timeout. Die Lane meldet
einen Fehler, 2597 bestandene Tests und 166 Skips; ihre nachfolgenden Suites
liefen nicht. Die übrigen zwölf Acceptance-Lanes sind erfolgreich.

Eine zusätzliche native Testvariante verzögert die Prozesserzeugung um
8,5 Sekunden. Mit dem bisherigen Test reproduziert sie auf Linux denselben
Fehler an derselben Wartefrist; der unverzögerte Fall besteht. Dies belegt die
Startzeitabhängigkeit, ersetzt aber keinen neuen Windows-Nachweis.

Der Test wartet jetzt auf eine Bereitschaftsdatei des echten Entrypoints
außerhalb des Zielrepositorys. Erst danach beginnt das unveränderte begrenzte
Warten auf die Live-Publikation. Der Entrypoint schreibt weiterhin zuerst
Ausgabe ohne Zeilenumbruch und wartet auf eine explizite Freigabe des Tests.
Damit kann er nicht allein durch Ablauf der bisherigen einsekündigen Pause
enden, bevor die laufende Beobachtung geprüft ist. Die Freigabe erfolgt auch
bei fehlgeschlagenen Assertions im `finally`-Block.

Die reale Entrypoint-Ausführung hat einen expliziten Test-Timeout von 30 Sekunden.
Eine vorzeitige Apply-Beendigung während des Startwartens meldet das tatsächliche
Primärergebnis. Result-Publikation erhält keine zusätzliche künstliche
Zehnsekundenfrist. Die Prüfung von effektivem Timeout, laufendem Zustand,
unvollständiger Ausgabe, anschließendem Exit 0, Result-Status sowie vollständiger
Run- und Repository-Identität bleibt erhalten. Produktcode, Produktionslimits,
Test-Skips und CI-Matrix ändern sich nicht.

## Prüfungen und Übergabe

Development führt ausschließlich die parallele Auswahl mit vier Workern aus:
`tests/test_monitor_live.py`, `tests/test_monitor.py`, `tests/test_execution.py`
und `tests/test_output.py`. Der zusätzliche verzögerte Start bleibt Bestandteil
der regulären Tests. Berichte liegen außerhalb der getesteten Quellen.

Der Patch enthält nur den korrigierten Test und diese Lieferdokumentation.
Vor seinem einzelnen Commit führt der Entrypoint die vollständige parallele
Apply-Suite mit vier Workern und Controller-Bericht aus. Er prüft die erwarteten
Dateihashes und den Git-Scope vor und nach dem Gate, committet ausschließlich
diese zwei Dateien und führt genau einen normalen Push auf `dev` aus.
Bei einem Fehler stoppt die Ausführung ohne Erfolgsmarker oder Rollback.

Diese Dokumentation beschreibt die vorbereitete Lieferung; ein erfolgreicher
Apply wird erst durch sein Result bestätigt. Die neue native Windows-CI bleibt
bis zu Christians manuellem Start offen. Der Entrypoint startet weder CI noch
Dienste, installiert keine Laufzeit und greift nicht in andere Projekte ein.

Verträge: `planning/viewer/specification.md`, `docs/test-parallelism.md` und
die bestehenden Apply-/Result-Regeln in `spec/SPECIFICATION.md`.
