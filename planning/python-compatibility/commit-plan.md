# PatchHarbor – Implementierungsplan CPython 3.10/3.11

**Plan-ID:** `CPYTHON-310-311`
**Revision:** 1 · 13. Oktober 2026
**Status:** CP-00 vorbereitet; sechs Schritte, noch kein Apply dieses Plans bestätigt.
**Aktueller Auftrag:** ausschließlich ein Startcommit für Norm- und Planerweiterung.
**Zielversion:** gesondert festzulegen; veröffentlichte Basis bleibt 1.3.0.
**Normen gemeinsam:** [Hauptspec](../../spec/SPECIFICATION.md),
[PYZ/PACK](../../spec/SPECIFICATION_EXTENSION_PYZ_PACK.md) und
[CPython-Ergänzung Revision 1](../../spec/SPECIFICATION_EXTENSION_CPYTHON_310_311.md).

## 1. Auftrag, Basis und Arbeitsgrenze

Die vollständige API, Core-PYZ, CLI und separat installierte Watcher-Anwendung
werden nachweislich für CPython 3.10 und 3.11 erweitert. Der bisherige
PYZ/PACK-Plan ist abgeschlossen und wird nicht erneut begonnen. Die neue
Ergänzung ändert gezielt die Python-Untergrenze; alle anderen Sicherheits-,
Fehler-, Paket-, Ressourcen- und Übergabeverträge gelten weiter.

| Grundlage für CP-00 | Vollständiger Wert |
| --- | --- |
| Repository-ID | `e7a93d72-62dc-4759-97e8-6bf6cdf10e90` |
| Apply-Commit | `30e5de1d67a2d725ff192a0b97e50c2b0336bfcb` |
| Result | `patchharbor-apply_Result_093541_1008_cf92ce.zip` |
| Result-SHA-256 | `0fa06af4bd8d49b9a2c731fd80585db47a43b912f768c94e723c7e35d279411f` |
| Fingerprint / Algorithmus | `7c9d2a24e397e0e5` / `patchharbor-state-v1` |
| Inventar | 335 Dateien, tatsächlicher erfolgreicher Apply, sauberer Baum |
| Abgeschlossene Basisabnahme | manuelle CI [37802304850](https://github.com/cdoehn/patch-harbor/actions/runs/37802304850), sechs erfolgreiche Jobs auf obigem Commit |
| Lokaler letzter Nachweis | Development 3075 passed / 9 skipped; Apply 3052 passed / 8 skipped |

Diese Werte dokumentieren die gelesene Ausgangsbasis. Jedes Folgebundle bindet
sich neu an sein tatsächliches maßgebliches Result, nicht an kopierte Planwerte.
Resultalter allein ist kein Ausschluss: CP-00 hat Inhalt und Binding gegen das
unveränderte Apply-Repository erneut geprüft. Der Dev-Root besitzt historische
uncommittete Änderungen; gearbeitet wird in einem isolierten, aus dem Result
rekonstruierten Verzeichnis unter `patchharbor-codex/build/`.

CP-00 verändert nur die acht Norm-/Plan-/Verweisdateien dieses Startbundles.
Produktquellen, Paketversion, `Requires-Python`, Bootstrap-Programmbytes,
Tests, Abhängigkeiten und Workflow-YAML bleiben unverändert. Ein Plan ist kein
Kompatibilitätsnachweis. Der tatsächliche Commit entsteht ausschließlich durch
den bestehenden Watcher/Entrypoint im Apply-Repository.

## 2. Bestandsbefund und technische Leitentscheidungen

| Befund im geprüften 1.3.0-Stand | Bearbeitung |
| --- | --- |
| `pyproject.toml` verlangt `>=3.12`; Build-Metadaten werden in das Runtime-Rezept übernommen. | Untergrenze erst zusammen mit funktionsfähigen Datenlesern, Startcode, Writer und eigener Anleitung umstellen. |
| `platform/lifecycle.py` importiert `typing.Self`. | Stdlib-kompatible Annotationen; keine externe Runtime-Typing-Abhängigkeit. |
| `patch_pack.py` und `platform/pack_output.py` verwenden `add_note` auch in Fehlerpfaden. | Gemeinsamer enger Diagnoseadapter; ursprüngliche Ausnahme, Kategorie, Ursache und Cleanup-Information erhalten. |
| `platform/filesystem.py` und `scripts/pyz_bootstrap.py` setzen unter Windows `st_birthtime_ns` voraus. | Tatsächliche ältere Pfad-/Handle-Semantik und native Identitäts-/Zeitdaten untersuchen; kein permissives Weglassen. |
| Junction-/Reparse-Prüfungen und Windows-Testhilfen verwenden teils neue pathlib-Funktionen. | Sicherheitsgleichwertiger bestehender/native Adapter; Tests selbst auf 3.10/3.11 ausführbar machen. |
| `runtime_pyz.py`, `result_pyz.py`, `result_resources.py` und Bootstrap enthalten feste 3.12-Annahmen. | Zwei explizite geschlossene Varianten, alte kanonische Startbytes erhalten; erst Leser, dann Writer. |
| Release-/Dockerwerkzeuge und Packaging-Tests importieren `tomllib`. | Bedingter kompatibler Build-/Test-Reader für 3.10; kein neuer Runtime-Dependency oder eigener TOML-Parser. |
| Eigene Ressourcen enthalten die ausführbare Root-Chat-Anleitung. | Eigenes Bootstrapprogramm und eingebetteter Code bleiben gleich; erste neue Produktion startet aus ihrer eigenen Anleitung. |
| Die bestehende CI prüft native 3.12/3.14 und Docker, nicht beide neuen Interpreter. | Tatsächliche 3.10-/3.11-Jobs ergänzen; Simulationen belegen keine Interpreterunterstützung. |

Dieser Befund ist ein Startinventar, keine Behauptung vollständiger statischer
Analyse. CP-01 prüft zusätzlich die gesamte Syntax, Standardbibliotheksnutzung,
Lazy-Imports, Build-/Testhilfen und Plattformgrenzen auf 3.10-Inkompatibilitäten.
Abweichungen werden mit konkreten Dateien und Verhalten ergänzt. Keine
flächendeckenden Such-/Ersetzungsaktionen über eingefrorene historische Fixtures.

## 3. Sichere Commitfolge

| Schritt | Abhängigkeit | Vorgesehener Commit | Ergebnis und Gate |
| --- | --- | --- | --- |
| **CP-00** | bestätigte 1.3.0-Basis | `docs(spec): plan CPython 3.10 and 3.11 support [CP-00]` | Normsatz, sechs Schritte, Test-/CI-Matrix und aktive Verweise; vollständige parallele Gates und realer Apply. |
| **CP-01** | CP-00 | `refactor(compat): preserve core and filesystem behavior on Python 3.10 [CP-01]` | Sprach-/API-/Fehler-/Dateisystemkompatibilität mit Verhaltenstests; produktive Untergrenze bleibt 3.12. |
| **CP-02** | CP-01 | `feat(runtime): read legacy and Python 3.10 PYZ variants [CP-02]` | Vollständige Datenleser und Bootstrap akzeptieren beide konsistenten Varianten; Writer bleibt 3.12, eingefrorene Altartefakte unverändert. |
| **CP-03** | CP-02 | `feat(compat): enable Python 3.10 for distribution and Core PYZ [CP-03]` | Metadaten, Build/Test-Dependencies, Writer, Startcode, CLI/API und eigene Anleitung gemeinsam umgestellt; erste echte neue Resultgeneration. |
| **CP-04** | CP-03 | `test(compat): extend manual native Python acceptance matrix [CP-04]` | Vollständige Regressionen und konkrete 3.10-/3.11-CI-Lanes einschließlich Watcher/PowerShell; Workflow bleibt ausschließlich manuell. |
| **CP-05** | CP-04 und externe Nachweise | `chore(release): bind Python compatibility acceptance [CP-05]` | Tatsächliche Apply-/CI-/Artefakt-/Praxisnachweise schließen den Plan; nur nötige Dateien ändern, sonst null-Commit-Abnahmebericht. |

Sechs Planpositionen sind keine Pflicht zu sechs Bundles: fachlich abgrenzbare
aufeinanderfolgende Zustände dürfen gemeinsam übergeben werden. Jeder Commit
braucht sein vollständiges paralleles Gate. Korrekturen erhalten eigene
FIX-Kennungen und belegte Ausgangszustände; keine künstliche Fehleranzahlgrenze.
Der Auftrag für dieses Bundle endet nach CP-00. CP-01 bis CP-05 sind Planung,
keine Erlaubnis zur sofortigen automatischen Weiterarbeit in diesem Turn.

### CP-00 – Startvertrag übernehmen

- Neue CPython-Norm und dieser Plan; gezielte Vorrang-/Untergrenzenhinweise in
  den beiden bisherigen Normdateien und Änderungsprotokoll.
- README und projektbezogene Chat-Planauswahl zeigen auf den neuen Auftrag.
  Der ausführbare Bootstrap in der Chatvorlage bleibt bytegleich.
- Den abgeschlossenen PYZ/PACK-Status mit tatsächlichem 046-Apply und grüner CI
  einordnen; kein historischer Test-/CI-Fehler wird gelöscht.
- Genau ein Dokumentationscommit im Apply, vollständige parallele Tests in
  Development und Apply, ein normaler abschließender Push, kein CI-Start.

### CP-01 – Laufzeit und Dateisystemgrenzen kompatibel machen

Betroffen: importierte Core-/Watcher-Module, `platform/lifecycle.py`,
`platform/filesystem.py`, vorhandene Windows-Adapter, Pack-Cleanup und Testhilfen.
Insbesondere private Verzeichnisse/DACLs, Junctions, Reparse-Punkte, Creation-/
ChangeTime, Dateiaustausch und Handle-Schließreihenfolge konkret belegen.

Erforderliche Fälle CT-01–04 und CT-11/15 im selben Schritt ergänzen. Auf
vorhandenem 3.12/3.14 volle parallele Gates. Reale ältere Interpreter dürfen
bereits kompatible Quellpfade prüfen, ohne daraus eine freigegebene Installation
oder PYZ zu behaupten. Fehlende Interpreter werden als offen protokolliert;
keine Systeminstallation, Registryänderung oder Host-Watcher-Steuerung durch Codex.

### CP-02 – Datenleser und Bootstrap zuerst erweitern

Betroffen: `runtime_pyz.py`, `result_pyz.py`, gemeinsamer Result-Reader,
`runtime_sources.py`, Builder-Datenhelfer und `scripts/pyz_bootstrap.py` samt
identischem eingebettetem Programm. Vollständige native Referenzvalidierung
bleibt strenger als der Bootstrap-Vorcheck.

Historische 1.3.0-PYZ und Results werden mit Herkunft, vollen Hashes und
unveränderten kanonischen Bytes eingefroren. Keine Misch-Fixture aus altem
Reader und neuem abhängigen Modul. CT-05/06/08 prüfen alte/neue Varianten,
unbekannte Anforderungen, Startbyte-/Metadatenwidersprüche, beschädigte IDs,
Zähler und ZIP64-Budgets. Der neue Writer wird hier ausdrücklich noch nicht
aktiviert; ältere Artefakte erhalten keine geänderten Python-Anforderungen.

### CP-03 – Distribution, Producer und eigene Anleitung gemeinsam aktivieren

Betroffen: `pyproject.toml`, Buildbackend, Releaseaudits, Runtime-Provider,
`unavailable`-Dokumente, Startcode, installierte Ressourcen und Dokumentation.
Wheel/sdist sollen sich unter 3.10/3.11 regulär installieren lassen. Das
Deployment-/Buildwerkzeug darf passende Buildabhängigkeiten installieren;
der laufende Core, pack und der Bootstrap tun dies weiterhin nicht.

CT-07–14 werden mit real gebauten Artefakten außerhalb des Checkouts ausgeführt.
Die erste neue Result-PYZ muss ausschließlich anhand ihrer eigenen Anleitung
über API/CLI packen, vollständig validieren und einen regulären Apply ermöglichen.
Erst dann ist der Writerstand ein sinnvoller Übergabestand. Das ist noch keine
native Gesamtfreigabe ohne die neuen externen Lanes. Produktversion und Hashes
bleiben getrennt; eine Folgeversion wird spätestens vor CP-05 mit Christian
festgelegt, vorhandene Tags/Artefakte werden nicht verändert.

### CP-04 – Native Matrix und vollständige Abdeckung

Tests entstehen bereits bei CP-01–03. Dieser Schritt schließt Auswahl-/Fixture-
und Integrationslücken, statt Sicherheitsprüfungen bis zum Ende aufzuschieben.
Bestehende Core-/E2E-/Plattform-/Packaging-Gruppen und der xdist-Controller
bleiben der einzige Testscheduler. Versionsabhängige Testvoraussetzungen und
TOML-/ACL-Helfer dürfen die 3.10-/3.11-Sammlung nicht zum Scheitern bringen.

Die manuelle Workflowdatei und Artefaktnamen erhalten eindeutige Python- und
Plattformzuordnung. Historische CI-Reportauswertung darf keine fest verdrahtete
Vier-Artefaktliste als vollständigen neuen Nachweis behandeln. Einen automatischen
CI-Handoff wieder einzuschalten ist ausdrücklich verboten.

### CP-05 – Nachweise bewerten und beenden

Nach Christians manuellem CI-Lauf alle vorgeschriebenen Jobs, Testsammlungen,
Worker-Enden, Skips, Interpreter, Artefakthashes und vollständigen Commit prüfen.
Linux-Simulation, erfolgreiche Einrichtung, Dry-Run oder nur `--version` ersetzen
keinen nativen Durchstich. Neue CIFS-Praxis ist erforderlich, soweit geänderte
Metadaten-/Publikationsadapter diese Kombination berühren; frühere Nutzerbestätigung
nicht zu einem neuen 3.10-/3.11-Nachweis umetikettieren.

Ein externer Abschlussbericht neben dem Result genügt, wenn kein Dateidelta
notwendig ist. Kein leerer Commit und kein Bundle nur zum Eintragen einer CI-ID.
Bei fehlenden Nachweisen bleibt der konkrete Abnahmepunkt offen; keine erneuten
CI-Starts, spekulativen Patches oder Warteschleifen ohne Auftrag. Nach Abschluss
Zustand atomar speichern und Entwicklungsschleife beenden.

## 4. Geplante manuelle CI-Matrix

Die folgende Matrix wird erst in CP-04 umgesetzt. CP-00 verändert keinen Workflow.
Alle Tests laufen parallel; CI wird ausschließlich von Christian gestartet.

| Lane / bestehender Runner | CPython | Prüfung | Jobs |
| --- | --- | --- | ---: |
| Native Ubuntu 24.04 | 3.10, 3.11, 3.12 | vollständige Core-, E2E-, Plattform- und Packaging-Gruppen, jeweils parallel | 3 |
| Native Ubuntu 26.04 | 3.14 | bisheriger voller Umfang einschließlich repräsentativem uv-Weg | 1 |
| Native Windows 2025 / Windows PowerShell | 3.10, 3.11, 3.12 | vollständige vier Gruppen einschließlich echter Handles, CLI und Watcher | 3 |
| Native Windows 2025 / PowerShell 7 | 3.10, 3.11, 3.12 | bestehende native Windows-Auswahl, um alle neuen einschlägigen Fälle ergänzt, parallel | 3 |
| Docker Ubuntu 24.04 und 26.04 | bisherige 3.12-Basis | bestehende vollständige Integrationsgruppen, parallel | 2 |

Damit sind zwölf explizite Jobs geplant, kein unbeschränktes kartesisches
Kreuzprodukt. Docker bewahrt seine beiden vorhandenen Nachweise; neue 3.10/3.11
werden nativ unter Linux und Windows mit tatsächlichen Installationen geprüft.
Jeder Job dokumentiert den konkret verwendeten Patchstand. Nicht verfügbare
Runner/Interpreter werden nicht still durch andere Versionen ersetzt.
Timeouts der bestehenden Lanes bleiben erhalten, keine automatische Wiederholung.

Für 3.10/3.11 sind mindestens normale Wheel-/sdist-Installation, CLI und direkte
öffentliche API, stdlib-only PYZ und In-Process-API, tatsächliches Result/Apply
und installierter Watcher belegt. Die ergänzende PS7-Auswahl ersetzt nicht die
vollen nativen Windows-Suites. Ein versionierter Skip braucht einen sachlichen
Plattformgrund; Kernfunktionalität darf nicht wegen des älteren Interpreters
übersprungen und anschließend als unterstützt gemeldet werden.

## 5. Anforderungs- und Testzuordnung

| Anforderung | Umsetzung / Abnahme | Verhaltenstests |
| --- | --- | --- |
| CPY-01 | CP-00, CP-05 | Norm-/Quellenreview; keine Prosa-Assertions |
| CPY-02 | CP-01, CP-03–05 | CT-01, CT-09, CT-10 |
| CPY-03 | CP-01, CP-04/05 | CT-15, CT-16 |
| CPY-04 | CP-01–05 | CT-07, CT-09–11, CT-13 |
| CPY-05 | CP-01 | CT-01, CT-02 |
| CPY-06 | CP-03/04 | CT-13, CT-16 |
| CPY-07 | CP-01/02 | CT-03, CT-04, CT-11 |
| CPY-08 | CP-01/02/05 | CT-03, CT-04, CT-08, CT-16 |
| CPY-09 | CP-01–05 | CT-11, CT-12, CT-16 |
| CPY-10 | CP-02 | CT-05, CT-08 |
| CPY-11 | CP-02/03 | CT-06, CT-12, CT-14 |
| CPY-12 | CP-02/03 | CT-05–08, CT-14 |
| CPY-13 | CP-02/03 | CT-07, CT-08, CT-10 |
| CPY-14 | jeder Implementierungsschritt | CT-01–16, vollständige parallele Gates |
| CPY-15 | CP-04/05 | CT-15, CT-16 |
| CPY-16 | CP-03–05 | CT-13, CT-14, CT-16 |

Die Zuordnung konkreter neuer Node-IDs wird jeweils nach Implementierung ergänzt.
Wiederverwendet werden insbesondere `test_api_contract`, `test_pack_api`,
`test_pyz_bootstrap`, `test_runtime_pyz`, `test_result_format3`,
`test_result_robustness`, `test_runtime_packaging`, `test_packaging_e2e`,
`test_pyz_result_e2e`, `test_runtime_permissions`, `test_result_file_handles`,
`test_result_file_limits`, `test_watcher_events_native`,
`test_watcher_event_loop_e2e` und die Windows-Acceptance-Tests.
Keine separate Parallel-Implementierung des Testcontrollers.

## 6. Übergabe, Status und Abnahmecheckliste

Development verändert ausschließlich die eigene Arbeitskopie. Das Apply-Repository
bleibt für Codex lesend. Ein vollständiges Result liefert repo_id, base_commit,
state_fingerprint und fingerprint_algorithm ohne Kürzung. Echte fehlgeschlagene
Applies werden einschließlich Teilfortschritten ausgewertet; ein Result wird
erst durch bestätigte Folgebundle-Auslieferung verbraucht.

Der Entrypoint prüft jeden echten Commitstand mit der vollständigen parallelen
Suite vor dem Commit und führt erst nach allen erfolgreichen Phasen genau einen
normalen Push auf den bestätigten Branch aus. Keine seriellen Tests, automatischen
Tags oder CI-Dispatches. Die finale ZIP wird außerhalb des Exchange fertiggestellt,
geöffnet, einschließlich aller Inhalte/Hashes/Bindungen geprüft und genau einmal
atomar veröffentlicht. Der vorhandene Watcher übernimmt das tatsächliche Apply.

Tests laufen als eigene Prozesse mit Log und vollständigem Ergebnisnachweis.
Geplante KI-Kontrollen frühestens nach 300 Sekunden; zuverlässiges Prozessende
darf sofort ausgewertet werden. Kein zweiter Watcher, keine kurzen Modell-Polls.
CP-00 startet keine dauerhafte S-Schleife. Tokenmeter bleibt gestoppt.

- [ ] CP-00 tatsächlich angewendet; neueste Resultbindung und Planposition erfasst.
- [ ] CP-01/02 erhalten Fehler- und Dateisicherheit sowie originale Altartefakte.
- [ ] CP-03 weist erste neue Result-/PYZ-Produktion mit eigener Anleitung nach.
- [ ] Öffentliche API, CLI, PYZ und Watcher auf echtem 3.10 und 3.11 bestätigt.
- [ ] Vollständige parallele lokale/Apply-Gates und alle zwölf manuellen CI-Jobs grün.
- [ ] Erforderliche neue CIFS-/Plattformpraxis und sämtliche Skips ehrlich eingeordnet.
- [ ] Produktversion, vollständiger Endcommit und konkrete Artefakthashes festgelegt.
- [ ] Abschluss gespeichert; keine weiteren Bundles oder automatische Fortsetzung.

CP-00 wird erst durch seinen tatsächlichen Apply bestätigt. Änderungen nach einer
Abnahme erfordern neue passende Nachweise; die frühere 1.3.0-CI wird nicht als
Test dieses geänderten Dokumentations- oder zukünftigen Laufzeitstands ausgegeben.
