# Sicherer Referenzexport – 1.7.0

Plan SAFE-REFERENCE, 31. Oktober 2026. Nutzerauftrag:
`AUFTRAG_PATCHHARBOR_DEV.md`, ausdrücklich hier zur Ausführung übernommen.
Gemeinsame Norm: Hauptspec §43, PYZ/PACK- und CPython-Ergänzung.
Version 1.7.0 ist vom Nutzer gewählt, keine automatische Tag-/Releasefreigabe.

## Bestätigte Basis

Bundle 072 ist tatsächlich erfolgreich angewendet und normal nach dev gepusht:
`a5e2cf68067084f962190217a8cc7af138c896cf`, 3.416 passed / 15 skips,
12 Worker, vollständiges Gate, sauber. Result
`patchharbor-apply_Result_184246_1031_03684a.zip`, SHA-256
`47f22686863246004d28612e8d1fb84387131b459f89c919fc86024f795834b6`.
Die Entwicklung rekonstruiert seine 426 Dateien in einem isolierten Buildbereich;
der ältere dirty Development-Checkout bleibt erhalten. Keine direkte Apply-Mutation.

## Fünf fachliche Arbeitsschritte

| Nr. | Umfang / Ergebnis | Abnahme | Abhängigkeit / Art |
| --- | --- | --- | --- |
| 1 | Basis, Anforderungen, Norm und Plan | Tatsächliche Resultprüfung; eindeutiger öffentlicher Vertrag | 072; Bestandsprüfung plus neue Norm |
| 2 | Sichere Rohzustands-/Deltaerfassung | Null Helfer; keine Quellmutation; korrekte Schichten/Bindungen | 1; vorhandene Parser wiederverwenden, sichere Produktion ergänzen |
| 3 | Öffentlicher Modus und gebundene Betriebsgrenzen | Capability, Preflight, Fehler, Frische, exklusive Veröffentlichung | 2; neue Integration bestehender Core-Bausteine |
| 4 | Verhalten, Build und Referenzen | PH-SAFE-01–15; echte Wheel/PYZ-Prozesse, synthetische native Results | 3; neue Tests/Artefakte, vorhandene Build-/Lesekette |
| 5 | Apply und belegte Übergabe | Drei tatsächliche Gates/Commits, Quell-/Artefaktbindung, offene externe Nachweise | 4; bestehender Watcher-Workflow |

Ursprünglich geplant: **3 Commits, 1 Bundle (073)**; der bestätigte Teilabschluss und Bundle 074 sind unten dokumentiert. Keine künstlichen W/R/C-Teilzustände.
Jeder Zustand entsteht tatsächlich vor seinem Gate; nur der geprüfte Zustand
wird committed. Ein normaler Push nach dem letzten Gate. Development ausgewählt
parallel, Apply vollständig parallel vor jedem Commit. CI ausschließlich Christian.

| Commit | Fachlicher Zustand | Status |
| --- | --- | --- |
| SAFE-01 `docs(spec): define source-safe reference export` | §43, diese Schrittfolge und Abnahmematrix; keine Runtimebehauptung | tatsächlich committed, `3d8a7aa9ea0323093dd5dc067781cb7fe9afb77b`; vollständiges Gate grün |
| SAFE-02 `feat(api): add bound source-safe reference export` | Version 1.7.0, Erfassung, sichere Deltas, API/Capability, Grenzen und Fehler samt Verhaltenstests | vorbereitet |
| SAFE-03 `test(integration): deliver verified safe reference runtimes` | Gebaute Modul/PYZ-Durchstiche, Beispiel, manuelle Linux-3.10–3.14-Matrix und Lieferdokumentation | vorbereitet |

## Entscheidungen und Kompatibilität

`context` und `bundle` erhalten einen expliziten sicheren Modus. Ein kleiner
öffentlicher `prepare_reference_export` liefert die zusätzliche notwendige
Betriebs- UND Zustandsbindung. `configuration` allein bindet keine Quelle,
Registry oder physischen Ausgabepfade. Planvorbereitung schreibt nichts.
Sicherer Export unterdrückt Wartung vollständig; keine neue allgemeine Planengine.

Git-Worktree-Diff wird vollständig vermieden. Bereits sichere Index-/Rohbyte-
Vergleiche und die vorhandene state-v1-Kodierung bleiben maßgeblich. Native
Full-index-Literalpatches stammen ausschließlich aus erfassten Bytes und werden
gegen ein unabhängiges Git-Oracle geprüft. Aktive Filter/Encoding/ident und
mehrdeutige EOL-Fälle werden vor Helferausführung verweigert. Kein Git-Config-
Override beim Verbraucher, kein Abschalten mit falscher Fingerprintbehauptung.

Der neue Hostvertrag ist ausdrücklich Linux x86-64 / CPython 3.10–3.14.
Deskriptorverankerte Pfade und exklusive Hardlinks sichern den schreibenden Teil;
fehlende Voraussetzungen verweigern. Alte Plattformpfade und APIs bleiben
unverändert. Originale 1.4.0-/1.6.0-Artefakte werden nicht neu etikettiert.

## Pflichtabnahmen und konkrete Testzuordnung

| ID | Verhalten / vorgesehener Testbereich | Status |
| --- | --- | --- |
| PH-SAFE-01 | `test_safe_reference`: aktiver Clean-Filter, Quell-/Git-Hashes, null Aufrufe | implementiert; gebundene lokale Nachweise unten, Apply extern |
| PH-SAFE-02 | `test_safe_reference`: context/prepare/bundle, racy index und gleiche Statwerte | implementiert; gebundene lokale Nachweise unten, Apply extern |
| PH-SAFE-03 | `test_safe_reference`: clean/smudge/process/textconv/extdiff/fsmonitor/hooks mit Helfermarkern | implementiert; gebundene lokale Nachweise unten, Apply extern |
| PH-SAFE-04 | `test_safe_reference`: lokale/globale/Indexattribute, CRLF/encoding/ident, Ablehnung | implementiert; gebundene lokale Nachweise unten, Apply extern |
| PH-SAFE-05 | `test_safe_reference_roundtrip`: echte Dirty-/Clean-Schichten, Git-Oracle, Modi/SHA-256 | implementiert; gebundene lokale Nachweise unten, Apply extern |
| PH-SAFE-06 | `test_safe_reference_failures`: Änderungen während Erfassung/Veröffentlichung, kein Rebind | implementiert; gebundene lokale Nachweise unten, Apply extern |
| PH-SAFE-07 | `test_safe_reference_failures`: Registry/HEAD/Config/Pfadfehler ohne Reparatur | implementiert; gebundene lokale Nachweise unten, Apply extern |
| PH-SAFE-08 | `test_safe_reference_failures`: Preflight, explizites/Exchange-Ziel, keine Wartung, stale Grenzen | implementiert; gebundene lokale Nachweise unten, Apply extern |
| PH-SAFE-09 | `test_safe_reference_failures`: Kollisionen, Links/Sonderdateien, Pfadtausch, Fremdschutz | implementiert; gebundene lokale Nachweise unten, Apply extern |
| PH-SAFE-10 | `test_safe_reference_failures`: echte I/O-Fehler und Prozessabbrüche, Cleanupdiagnosen | implementiert; gebundene lokale Nachweise unten, Apply extern |
| PH-SAFE-11 | Vorhandene API-/Snapshot-/Pack-/Guarded-/frozen1.4-Suites plus sichere Roundtrips | implementiert; gebundene lokale Nachweise unten, Apply extern |
| PH-SAFE-12 | `test_safe_reference`: Capability/Typ-/Modus-/Altruntimegrenzen | implementiert; gebundene lokale Nachweise unten, Apply extern |
| PH-SAFE-13 | `test_safe_reference_distribution`: neue Wheel/PYZ in frischen Prozessen | implementiert; gebundene lokale Nachweise unten, Apply extern |
| PH-SAFE-14 | `test_safe_reference_distribution`: vollständige native Results, Python-only-Snapshotreader | implementiert; gebundene lokale Nachweise unten, Apply extern |
| PH-SAFE-15 | Buildnachweise, Quellinventar, Nutzer-CI; Linux 3.10–3.14 | lokal nur CPython 3.14.4 vorhanden; übrige Läufe offen |

Die Zuordnung wird nach tatsächlichen Ergebnissen fortgeschrieben. Keine Prosa-
oder Darstellungstests. Quellen/Budgets/Sicherheitsverträge bleiben bindend.
Eine technische Änderung der Schrittzahl wird mit gefundenem Grund und komplettem
Restumfang dokumentiert, nicht mit Kontext-/Zeitbedarf begründet.

## Lieferung und Abschluss

Extern gebundene Wheel-/sdist-/Core-PYZ-Builds, saubere und Dirty-Resultreferenzen
sowie ein öffentliches Integrationsbeispiel und SHA-256-Manifest gehören zur
Lieferung. Referenzen enthalten ausschließlich isolierte synthetische Daten.
Quelldigest vor Apply und danach der tatsächlich bestätigte Commit werden
abgeglichen. Vorbereitete Lieferungen sind kein Apply-Erfolg. Native CI und die
eigenständige SpecRoad-Abnahme werden nicht erfunden oder automatisch gestartet.
Keine Änderung an SpecRoad; 15.n.W bleibt dort bis zur eigenen Abnahme offen.

## Historischer Vorbereitungsnachweis für Bundle 073: SAFE-02

Der Modus und seine API sind implementiert. Eindeutiges `-text` muss in beiden
Attributsichten gelten; widersprüchliche Index-/Worktree-EOL-Regeln werden verweigert.
Bestehende Ablehnung von assume-unchanged/skip-worktree bleibt bestehen; racy
Indexstatwerte werden unabhängig mit Rohbytes geprüft. Neue Dateien sind privat;
Pfadtausch bei Diagnosestart/Publikation und bestehende Locklinks werden geprüft.
Die Zwischenläufe dienten Fehlerfindung und sind keine Commit-Gates. Das gebundene
ausgewählte SAFE-02-Gate liegt im Exchange-Bericht `patchharbor-safe-reference-073-SAFE-02-final.json`.
Sein Ergebnis ist vor Übergabe zu prüfen; tatsächliche Apply-Gates folgen erst
im Watcher. CI und SpecRoad-Abnahme bleiben getrennt offen.

## Historischer Vorbereitungsnachweis für Bundle 073: SAFE-03

Die drei Zustände sind vorbereitet. SAFE-01-final: 143 ausgewählte Tests;
SAFE-02-final: 637 ausgewählte Tests, jeweils 12 Worker und Exit 0 auf lokalem
CPython 3.14.4 / Linux x86-64. Der erste tatsächliche Distributionstest samt
CI-Katalog-/Versionsprüfungen bestand 91 Tests. Danach ergänzt SAFE-03 explizite
Teilwirkungsnachweise für Abbrüche unmittelbar nach dem atomaren Link sowie
korrekte Root-Skips für POSIX-Berechtigungszeugen. Vor Übergabe muss der gebundene
abschließende Bericht `patchharbor-safe-reference-073-SAFE-03-delivery.json` grün sein.
Alle Berichte, Befehle, Exitcodes und Eingangsdigests liegen in Exchange/reports;
fehlgeschlagene Zwischenläufe werden nicht zu erfolgreichen Gates umetikettiert.

PH-SAFE-01–12 sind durch die sicheren Verhaltens-, Fehler-, unabhängigen
Git-Roundtrip- und bestehenden Kompatibilitätstests abgedeckt. PH-SAFE-13/14
verwenden tatsächlich gebaute Wheel-/PYZ-Prozesse, getrennte Imports und native
Results; der abschließende Lauf bindet diese Nachweise an den Lieferstand.
PH-SAFE-15 bleibt für native CI außerhalb des lokalen 3.14.4-Hosts offen.
Linux 3.13 wurde zur rein manuellen Matrix hinzugefügt; die sechs benannten
Clean-/Dirty-/Filter-Distributionbeweise sind in allen Linux-Lanes verpflichtend.
Windows und Docker behalten ihre bestehenden Verträge. CI startet nur Christian.

Der [Integrationsleitfaden](../../docs/safe-reference-integration.md) nennt echte
öffentliche Aufrufe und reproduzierbare synthetische Fixtures. Neue native
Clean-/Dirty-Results, Wheel, sdist und Core-PYZ werden extern voll gehasht und
an das vollständige Quellinventar gebunden. Erst
`patchharbor-safe-reference-074-result-review.json` bestätigt die verbleibenden
Apply-Commits und Gates; `patchharbor-safe-reference-074-integration-delivery.json`
verknüpft sie mit den exakten Artefakten und PH-SAFE-01–15. Diese externen
Ergebnisnachweise schließen den Status fort, ohne künftigen Apply-Erfolg in
einem noch anzuwendenden Commit vorzutäuschen.

Geplante und bisher tatsächlich benötigte fachliche Schritte: **5**.
Drei Commits; ursprünglich ein Bundle, nach dem belegten Fehlversuch zwei. Kein neuer Folgeplan. SpecRoads eigene Abnahme,
Produktfreigabe, Tag und Installation bleiben separate Entscheidungen.

Der erste SAFE-03-Lauf hatte einen veralteten CI-Jobzähler (7 statt 8 native
Lanes); 423 andere Tests bestanden. Die betroffenen Katalog-/Review-Tests
werden auf die zusätzliche Linux-3.13-Lane aktualisiert und erneut gebunden.

Die synthetischen CI-Review-Fixtures führen nun ebenfalls die sechs neuen
Pflichtnachweise. Die echte Nachweisprüfung bleibt streng: fehlende sichere
Distributionbeweise werden weiterhin zurückgewiesen.

## Tatsächlicher Teilabschluss und Korrekturbundle 074

Bundle 073 wurde tatsächlich angewendet, brach aber im vollständigen SAFE-02-
Gate ab: 3 failed, 3.503 passed, 15 skips. Alle drei Fehler gehören zu
`tests/test_packaging_e2e.py`: feste Releaseversion noch 1.6.0 und sechs fehlende
Module in der expliziten Runtime-Allowlist. Die ursprüngliche lokale Auswahl
hatte diese Packaging-Prüfungen ausgelassen. Es wird keine Prüfung abgeschwächt:
Version und einzeln aufgeführtes Modulinventar werden auf 1.7.0 fortgeschrieben.

SAFE-01 ist durch 3.416 passed / 15 skips und Commit
`3d8a7aa9ea0323093dd5dc067781cb7fe9afb77b` bestätigt. Origin/dev steht noch auf
`a5e2cf68067084f962190217a8cc7af138c896cf`; ein Push fand nicht statt.
SAFE-02 liegt vollständig uncommitted vor, sein Index ist unverändert.
Result `patchharbor-apply_Result_195805_1031_ff651a.zip`, SHA-256
`7bbe684557ccadda01e037b55439b686b8012474c6c0b2071710e68abf9a7dc8`,
Fingerprint `eb7b69344c090c50`, ist die alleinige Basis von Bundle 074.

Es bleiben zwei echte Commitzustände: korrigiertes SAFE-02, danach SAFE-03.
Die vorhandenen Änderungen werden erhalten und vollständig geprüft; kein Reset,
kein erneuter SAFE-01-Commit. Jedes Commit erhält sein vollständiges paralleles
Apply-Gate, danach genau ein normaler Push. Lokal laufen ausgewählte Tests
einschließlich des kompletten Packaging-E2E-Moduls parallel. CI startet Christian.
Fachliche Arbeitsschritte bleiben fünf; wegen dieses nachgewiesenen Testfehlers
sind jetzt insgesamt zwei Übergabebundles statt eines erforderlich.

Der Endstand von Bundle 074 ergänzt den weiterhin offenen SAFE-03-Zustand,
behält die Packaging-Korrektur aus SAFE-02 und bindet die erneute Auslieferung
an das fehlgeschlagene tatsächliche Result. Zu verwenden sind die Nachweise
`patchharbor-safe-reference-074-SAFE-02.json`,
`patchharbor-safe-reference-074-SAFE-03.json` und später
`patchharbor-safe-reference-074-result-review.json` sowie
`patchharbor-safe-reference-074-integration-delivery.json` in Exchange/reports.
Die vorherigen Zwischenberichte und ursprünglichen 1.6.0-Artefakte bleiben erhalten.

The corrected packaging gate also exposed the unchanged 384 KiB wheel budget:
the default-compressed SAFE-02 wheel was 394,080 bytes. Build wheel members with
DEFLATE level 9; member bytes, RECORD contents and the budget remain unchanged.
The final original candidate recompresses from 394,272 to 393,146 bytes with
identical members. Installation and runtime behavior are rechecked on rebuilt
artifacts, not inferred from this compression-only diagnostic.

## Aktueller Liefernachweis für Bundle 074

SAFE-01 ist abgeschlossen; SAFE-02 und SAFE-03 bleiben bis zum tatsächlichen
Erfolg ihrer vollständigen parallelen Apply-Gates offen. Maßgeblich für die
Korrektur sind die gebundenen ausgewählten lokalen Berichte
`patchharbor-safe-reference-074-SAFE-02-final.json`,
`patchharbor-safe-reference-074-SAFE-03-final.json` und
`patchharbor-safe-reference-074-handoff-final.json`. Die alten 073-Berichte
bleiben historische Nachweise und bestätigen keinen korrigierten Dateistand.
Die exakten neuen Wheel-/sdist-/PYZ-Bytes und synthetischen nativen
Clean-/Dirty-Results stehen im 074-Liefermanifest mit externen SHA-256-Werten;
der tatsächliche Apply-Commit wird erst nach Resultprüfung zugeordnet.
