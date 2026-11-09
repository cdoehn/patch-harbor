# Viewer — Fortsetzung 079

Bundle 078 endete mit Exitcode 1 beim Vollsuite-Gate von VIEW-01.W.
Der Plan-Commit VIEW-00 ist erfolgreich übernommen:
`26b3bf4bf9b17c825b604cad1a180e3d6c64fe1d`.
Die erste Implementierungsstufe liegt uncommitted im Apply. Es gibt keinen Reset
und keine erneute Ausführung des bereits bestätigten Plan-Commits.

## Verifizierte Basis

Result: `patchharbor-apply_Result_141123_1109_9e8b5a.zip`

SHA-256: `88c7efa78be275cafdc121d471bcc73a3d5b57279f5f63e230efa3c600534ac2`

Repository-ID: `e7a93d72-62dc-4759-97e8-6bf6cdf10e90`

HEAD: `26b3bf4bf9b17c825b604cad1a180e3d6c64fe1d`

Fingerprint: `6f7bcf41cc02aa3c` (`patchharbor-state-v1`, dirty).

Alle 463 effektiven Dateien wurden über die native Result-Schnittstelle
validiert und mit dem vorbereiteten Wiederaufnahmestand byte- und modusgenau
verglichen. Eine native Sperrprobe bestätigte zum Prüfzeitpunkt frei; das ist
keine Reservierung. Vor Veröffentlichung wird die aktuelle Bindung erneut geprüft.

## Korrektur und Reihenfolge

Die zwei ursprünglichen Fehler waren die explizite Runtime-Dateiliste und deren
Prüfung am gebauten Wheel. Die Liste enthält jetzt je Commit genau die dort
vorhandenen, ausdrücklich aufgeführten Viewer-Module. Der Test leitet die
zulässigen Wheel-Inhalte weiterhin nicht aus einem beliebigen Build ab.

Die zusätzliche Distributionsprüfung des vollständigen Endstands fand außerdem
die bisherige Wheel-Grenze von 425984 Bytes. Gemessen wurden 429657 Bytes mit
allen Viewer-Funktionen. Das begrenzte Releasebudget beträgt deshalb jetzt
432 KiB (442368 Bytes); die exakte Dateiliste bleibt verbindlich. Allgemeine
Runtime-, ZIP-, Result- und Eingabegrenzen bleiben unverändert.

Enthalten sind neun Commit-Stufen, in dieser Reihenfolge:
VIEW-01.W, VIEW-01.R, VIEW-01.C, VIEW-02.W, VIEW-02.R, VIEW-02.C,
VIEW-03.W, VIEW-03.R, VIEW-03.C.

Die anfängliche reguläre Payload korrigiert nur den Packaging-Vertrag. Der erste
Commit umfasst anschließend auch die bereits vorhandenen, exakt verifizierten
VIEW-01.W-Dateien. Weitere Stände werden erst danach einzeln hergestellt.
Vor jedem Commit läuft die vollständige parallele Apply-Suite mit zwölf Workern;
bei Fehler stoppt die Folge. Ein normaler Push erfolgt erst nach allen Stufen.

## Nachweise und Grenzen

Gezielte parallele Development-Prüfung mit vier Workern: die erste reparierte
Stufe bestand 28 Packaging-/Viewer-/Architekturtests einschließlich echtem
Build und isolierter Installation. Am Endstand bestanden zunächst 44 weitere
Prüfungen für Distributionen, exportierte Runtimes, Live-Beobachtung und
Architektur; der dort gefundene Größenfehler wurde anschließend korrigiert.
Der korrigierte Endstand bestand anschließend 100 ausgewählte Tests mit vier
Workern in 67,95 Sekunden, einschließlich Wheel-/Quellpaketbau, isolierter
Installation, Viewer, Artefakten, Live-Beobachtung, Architektur und CLI.
Die Dateilisten aller neun Zwischenstände sind geprüft.

Dies ist PREPARED, kein behaupteter erfolgreicher Wiederaufnahme-Apply.
Die Native-Windows-TUI-Abnahme bleibt offen. Es erfolgt weder eine Installation
noch ein Dienstneustart oder CI-Start durch diese Entwicklungslieferung.
