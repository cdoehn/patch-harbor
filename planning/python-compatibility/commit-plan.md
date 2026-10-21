# PatchHarbor – Implementierungsplan CPython 3.10/3.11

**Plan-ID:** `CPYTHON-310-311`
**Revision:** 9 · 14. Oktober 2026
**Status:** CP-00 bis CP-04 und FIX1–FIX3 angewendet; alle zwölf manuellen CI-Jobs und 39 Testreports auf dem Implementierungsstand bestätigt. CP-05-VERSION / Bundle 055 vorbereitet; vollständiger Planabschluss bleibt offen.
**Aktueller Auftrag:** automatische Fortsetzung CP-03 bis CP-05; CI startet weiterhin ausschließlich Christian.
**Zielversion:** 1.4.0. Christian beauftragt nach dem grünen Fix ausdrücklich das Tag v1.4.0; Bundle 055 stellt die Version vor dem Tagging konsistent um.
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

CP-00 änderte nur die acht Norm-/Plan-/Verweisdateien des Startbundles.
Produktquellen, Paketversion, `Requires-Python`, Bootstrap-Programmbytes,
Tests, Abhängigkeiten und Workflow-YAML blieben dabei unverändert. Ein Plan ist kein
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
Der ursprüngliche Bootstrap-Auftrag endete nach CP-00; Bundle 048 bestätigte CP-01.
Seit dem ausdrücklichen Auftrag vom 14. Oktober 2026 werden CP-03 bis CP-05
automatisch fortgesetzt. Fehlende externe Abnahmen werden benannt; kein
automatischer CI-Start und keine eigenmächtige Release-/Hostaktualisierung.

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

Die folgende Matrix wird in CP-04 / Bundle 051 umgesetzt. CP-00 veränderte keinen Workflow.
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

- [x] CP-00 tatsächlich angewendet; neueste Resultbindung und Planposition erfasst.
- [x] CP-01/02 erhalten Fehler- und Dateisicherheit sowie originale Altartefakte; native Zielplattform-Abnahme bleibt offen.
- [x] CP-03 weist erste neue Result-/PYZ-Produktion mit eigener Anleitung nach; tatsächlicher Apply 050 bestätigt.
- [ ] Öffentliche API, CLI, PYZ und Watcher auf echtem 3.10 und 3.11 bestätigt.
- [ ] Vollständige parallele lokale/Apply-Gates und alle zwölf manuellen CI-Jobs grün.
- [ ] Erforderliche neue CIFS-/Plattformpraxis und sämtliche Skips ehrlich eingeordnet.
- [ ] Produktversion, vollständiger Endcommit und konkrete Artefakthashes festgelegt.
- [ ] Abschluss gespeichert; keine weiteren Bundles oder automatische Fortsetzung.

CP-00 bis CP-03 sind durch die unten gebundenen tatsächlichen Applies bestätigt.
CP-04 benötigt seinen eigenen erfolgreichen Apply; der vorbereitete Quellstand genügt nicht. Änderungen nach einer
Abnahme erfordern neue passende Nachweise; die frühere 1.3.0-CI wird nicht als
Test dieses geänderten Dokumentations- oder zukünftigen Laufzeitstands ausgegeben.


## 7. CP-01 / Bundle 048: bestätigte Basis und vorbereitete Änderungen

Startcommit CP-00: `73d7317dbd7221576b4930c27eec44eb38a50bff`, tatsächlich
angewendet und normal auf dev gepusht. Result
`patchharbor-apply_Result_115235_1013_1c84df.zip`, SHA-256
`4ce49fc2d2f8d793eb9cc6ea1539f007aa72ac867f5eb4f2175ea1bf68233aee`:
337 Dateien, sauberer Baum, 3052 bestandene parallele Apply-Tests / 8 Skips.
Development: 3075 passed / 9 skipped einschließlich Übergabeprüfungen.
Repository-ID `e7a93d72-62dc-4759-97e8-6bf6cdf10e90`, Fingerprint
`7c9d2a24e397e0e5`, Algorithmus `patchharbor-state-v1`.

Der Nutzer hat danach das erste Implementierungsbundle beauftragt. CP-01 enthält:

- Stdlib-Typvariable statt des erst ab 3.11 importierbaren `typing.Self`.
- Gemeinsame interne Exception-Notizen mit erhaltenem Primärfehler, Ursache,
  Fehlerkategorie, Exitstatus und Cleanup-Diagnosen, auch ohne `add_note`.
- Für Windows vor 3.12: zwei native FILE_BASIC_INFO-Beobachtungen um fstat;
  CreationTime und ChangeTime bleiben getrennt. Änderungen während der Erfassung
  und nicht verfügbare Primitiven werden abgewiesen. Keine schwächere
  Identitäts-, Größen-, Änderungs-, Hash- oder CIFS-Fallback-Prüfung.
- Reparse-/Junction-Klassifikation aus lstat-Attributen und Reparse-Tag statt
  eines optionalen neuen pathlib-Aufrufs. Unbekannte Reparse-Dateien bleiben
  an der regulären Lesegrenze ausgeschlossen.
- Private Request-/Registrierungsverzeichnisse werden unter Windows mit einer
  geschützten, vererbbaren DACL bereits beim exklusiven CreateDirectoryW erzeugt.
  Zugriff für effektiven Benutzer und Administratoren; kein nachträgliches
  Reparieren fremder ACLs und kein offenes Zwischenfenster. POSIX-Modi bleiben.
- Versionskompatible native Berechtigungshilfen und Watcher-Fehlerdiagnostik
  für die vorhandenen Verhaltenstests.
- Die festen Packaging-/Release-Inventare enthalten explizit die drei neuen
  Core-Module; die Prüfung bleibt eine geschlossene Allowlist.

Die Untergrenze, Produktversion, alle drei Normdateien, PYZ-Profile, Rezept-/
Result-/Paketformate, Writer, Bootstrapprogramm und Workflowdatei bleiben in
CP-01 unverändert. Beide geschlossenen PYZ-Varianten folgen erst in CP-02;
Metadaten, Build-/Test-TOML-Abhängigkeiten und Writerumschaltung erst in CP-03.

### Konkrete Verhaltenstests dieses Schritts

| Normfall | Neue Prüfung / bestehende Regression | Nachweisgrenze |
| --- | --- | --- |
| CT-01 | `test_core_watcher_imports_and_type_hints_do_not_need_typing_self`, `test_runtime_sources_use_python_310_grammar`; bestehende API-/CLI-/Prozess-/Watcher-Suites | Importhindernis und Grammatik geprüft; keine Simulation als echter 3.10-Lauf ausgeben. |
| CT-02/11 | `test_notes_keep_primary_exception_identity_category_and_cause`, Pack-Publikations-/Interrupt-/Referenz-Cleanup-Fehler in `test_python_compat.py`; bestehende Pack-Fehlerinjektion | Vollständige Kategorien und Ursachen statt Konsolenwortlaut. |
| CT-03 | stabile native Zeiten, widersprüchliche Daten, fehlende Primitive, echter gleich großer Schreibvorgang mit wiederhergestellter mtime | Simulation auf Linux plus tatsächlicher Handle-Test in `test_python_compat_windows.py`. |
| CT-04 | Reparse-/Junction-Ablehnung, geschützte vererbte DACL, fehlgeschlagene Token-/SID-/Security-Descriptor-Erfassung und Ressourcenfreigabe | Native DACL-/Junction-Tests müssen auf Windows tatsächlich bestehen. |
| CT-15 | bestehende vollständige installierte Watcher-, Ereignis- und Prozessbaumtests; portable Fehlernotiz im Event-Testhelfer | Windows und alte Interpreter bleiben separate Zielplattformnachweise. |

Die Quellprüfung erfasst alle 116 Core-/Watcher-Module mit 3.10-Grammatik und
Standardbibliotheksimporten. Laufzeitabhängigkeiten wurden nicht hinzugefügt.
Auf diesem Laptop wurde nur CPython 3.14.4 gefunden. Keine neue Systeminstallation
oder Host-Watcher-Änderung; tatsächliche 3.10-/3.11-Läufe bleiben offen, ebenso
native Windows-Ergebnisse. CP-01 benötigt vollständige parallele Development-
und Apply-Gates. CI startet ausschließlich Christian; die neue Matrix kommt CP-04.

Der erste vollständige lokale Lauf fand drei fehlende Inventareinträge in den
beiden Release-Testdateien (3 failed, 3119 passed, 13 skipped). Diese Listen
wurden ergänzt; für den dadurch geänderten Stand ist erneut das vollständige
parallele Gate erforderlich. Dieser erste Lauf gilt nicht als Abnahme.

### Technische Primärquellen

- [CPython 3.10 fileutils](https://github.com/python/cpython/blob/3.10/Python/fileutils.c)
  und [3.11 fileutils](https://github.com/python/cpython/blob/3.11/Python/fileutils.c):
  st_ctime wird aus ftCreationTime gebildet, auch bei fstat.
- [CPython 3.12 fileutils](https://github.com/python/cpython/blob/3.12/Python/fileutils.c):
  getrennte CreationTime/ChangeTime aus FILE_BASIC_INFO; Grundlage des erhaltenen
  neueren Descriptor-Vertrags.
- [Windows FILE_BASIC_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_basic_info)
  und [CreateDirectoryW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createdirectoryw):
  native Zeitinformationen und Sicherheitsattribute bei der Verzeichniserzeugung.
- [Python 3.10 os.mkdir](https://docs.python.org/3.10/library/os.html#os.mkdir):
  0700-ACL-Unterstützung wurde erst in 3.10.15 nachgezogen. CP-01 verlässt sich
  dafür nicht auf eine Minorversionsannahme oder einen stillen chmod-Fallback.


## 8. CP-02 / Bundle 049: zwei geschlossene Datenvarianten vor Writerwechsel

CP-01 ist mit Commit `e60729187b34b4203fc2bd62d41b209022098cfc` tatsächlich
angewendet und auf dev gepusht. Result
`patchharbor-apply_Result_123625_1013_c5dc9e.zip`, SHA-256
`0f596a42c05ef795d9e15a8e38ffdae2bd5e31c08812e4c820b91e601510d7b1`:
342 Dateien, sauberer Baum, 3099 parallele Apply-Tests / 12 Skips mit zwölf Workern.
Development: 3122 passed / 13 skipped einschließlich 24 Übergabeprüfungen.
Repository-ID `e7a93d72-62dc-4759-97e8-6bf6cdf10e90`, Fingerprint
`7c9d2a24e397e0e5`, Algorithmus `patchharbor-state-v1`.

CP-02 erweitert den gemeinsamen PYZ-Datenleser und Runtime-2-Deskriptorleser auf
exakt `>=3.12` und `>=3.10`; die statische Lesbarkeit hängt nicht von der
Ausführbarkeit auf dem prüfenden Interpreter ab. Die historischen `MAIN_BYTES`
bleiben identisch. Beide Startdateien müssen jetzt nicht nur zueinander, sondern
auch bytegenau zur deklarierten Variante passen. Unbekannte Anforderungen,
neu gehashte Mischvarianten, fremde Profile, beschädigte Produzenten-/Inhalts-IDs
und abweichende Metadaten werden weiterhin abgewiesen.

Der Build-Datenhelfer wählt Startbytes anhand seiner ausdrücklichen Anforderung.
Die normale Distribution, der Writer einschließlich `unavailable` und alle
Produktmetadaten bleiben in diesem Schritt bei `>=3.12` / Version 1.3.0.
3.10-Artefakte in diesen Tests sind ausdrücklich zukünftige synthetische Varianten.
Gemeinsame Reader/Provider und ihre vorhandenen Ressourcenadapter verarbeiten die
geprüften Varianten; kein zweiter Core und keine parallele öffentliche API.

Der stdlib-Bootstrap und sein identischer ausführbarer Block in der Root-Anleitung
prüfen zusätzlich inneres Inventar, Rezept-/Produzenten-IDs, beide Startdateien
und die Übereinstimmung mit dem Runtime-Deskriptor vor dem Import. Das separate
innere 1000-Eintrags-/32-MiB-Budget und das gemeinsame äußere Budget bleiben
verbindlich; 250.010 äußere Einträge und ZIP64 werden nicht zurückgenommen.
`runtime_descriptor_precheck` bleibt ausdrücklich keine native Vollprüfung der
Repositoryreferenz. Versionssperren gelten pro ausgewähltem Artefakt, alte
3.12-Artefakte werden nicht umetikettiert. Importkonflikte bleiben Fehler.

Für Windows übernimmt der installationsfreie Bootstrap die in CP-01 eingeführte
Trennung von CreationTime und nativer ChangeTime vor 3.12, die atomare private
DACL-Erzeugung und native No-follow-Handle-Prüfung. Reparse-Dateien sowie
umgelenkte Eltern werden abgewiesen, Elternidentitäten erneut geprüft und
owned Handles auch bei fehlschlagender Stream-Erzeugung geschlossen. Die engen
stdlib-Primitiven stehen dort ohne Core-Import bereit; ihre Fehlerfälle und
nativen Verhaltensfälle werden für beide Aufrufwege geprüft.

### Eingefrorene Grundlage und Nachweisgrenzen

`tests/fixtures/python_variants/` enthält drei einmal erzeugte synthetische
Referenzen nach den unveränderten Datenhelfern des bestätigten 1.3.0-Stands
`30e5de1d67a2d725ff192a0b97e50c2b0336bfcb`. Sie sind keine behaupteten realen Applies.
Die Format-2-Referenz enthält das vorhandene unveränderte 1.2.1-Wheel; Format 3
enthält die vollständig archivierte 1.3.0-PYZ aus dem separaten Bundle-046-Build.
PYZ-SHA-256: `942b2161c46ae3d81e0faf097b649d58d61c9c0d493b934d11cc708a314bfe21`,
941575 Bytes. `provenance.json` bindet alle Archive, Helfer und Identitäten.
Das Artefakt ist kein behaupteter Download eines veröffentlichten Release-Assets.
Bestehende historische Fixtures werden nicht geändert. Für den alten PYZ-Leser
wird die vollständige historische Runtime ausgeführt, keine Modul-Mischversion.

| Fall | Konkrete neue Prüfungen |
| --- | --- |
| CT-05 | Bytegenaue eingefrorene Results 1/2/3, unveränderte originale Startbytes, ganze historische 1.3.0-Runtime liest alte und lehnt neue Variante konservativ ab. |
| CT-06 | Beide Varianten, unbekannte Anforderungstypen/-ausdrücke, neu gehashte widersprüchliche Startbytes, Metadaten, Profile und Identitäten. |
| CT-08 | Versionssperre vor Import, statische Lesbarkeit getrennt von Ausführung, keine gefälschte Absenkung über Assessment; frischer stdlib-Prozess packt/prüft mit beiden Varianten. |
| CT-03/04 | Native und simulierte ChangeTime-, Reparse-/Junction-, DACL- und Handle-Cleanup-Fälle im standalone Bootstrap. |
| CT-12 | Inneres Eintrags-/Bytebudget, falsche Zähler, CRC-/Hashfehler, äußeres ZIP64 und 250.000-Dateien-Regression; Writer bleibt 3.12. |

Die konkreten neuen Fälle stehen in `test_python_variants.py` und
`test_bootstrap_python_compat.py`; vorhandene Bootstrap-, PYZ-, Result-,
Watcher- und Packaging-Suites bleiben Teil des vollständigen parallelen Gates.
Native Windows-Fälle sind auf Linux Skips. Nur CPython 3.14.4 ist hier verfügbar;
Versionssimulationen und echte Prozesse auf 3.14 ersetzen keine 3.10-/3.11-Abnahme.
CI startet ausschließlich Christian. CP-03 (Writer/Installation) und die erweiterte
CI-Matrix aus CP-04 werden mit diesem Bundle nicht aktiviert.


## 9. CP-03 / Bundle 050: kompatible Distribution und Produktion

CP-02 wurde mit Commit `97d69cad66b2d2cee5633fb965a5970fc745eb1f` tatsächlich
angewendet und normal auf dev gepusht. Maßgebliches Result:
`patchharbor-apply_Result_155544_1013_44b6c3.zip`, SHA-256
`79633931146e82de1fdbdd4ccf1265adf836de2de2a9f9de761ca8b4320ece9b`.
Repository-ID `e7a93d72-62dc-4759-97e8-6bf6cdf10e90`, Fingerprint
`7c9d2a24e397e0e5`, Algorithmus `patchharbor-state-v1`; 350 Dateien,
sauberer Baum. Vollständige parallele Gates: Development 3226 passed / 16
skipped (einschließlich Übergabeprüfungen), Apply 3203 passed / 15 skipped.

CP-03 stellt Requires-Python, normale Writer-/unavailable-Metadaten,
kanonischen Build-Startcode und eigene Anleitung gemeinsam auf >=3.10 um.
Der vorhandene Backend wählt bereits anhand derselben Distribution-Metadaten
beide identischen Startdateien. Alte Startbytes, eingefrorene Fixtures und
Leserprofile bleiben unverändert; kein zusätzlicher Runtime-Dependency.
TOML-Hilfen der Release-/Testwerkzeuge verwenden unter 3.10 den ausdrücklich
bedingten Build-/Dev-Reader tomli; Installation und Tests lösen passende
Werkzeugversionen anhand deren Python-Metadaten auf. Offline-Installationsfixtures
stellen ihre deklarierten Buildabhängigkeiten ausdrücklich bereit.

CT-07–14: Die bestehende echte Erstproduktion in `test_pyz_result_e2e.py`
prüft jetzt neue Runtime-/Rezept-/Startbytes, bootstrapped aus ihrer eigenen
Result-Anleitung ohne Installation/Netzwerk, packt Full-/Diff-/Mischpayloads
und führt einen regulären PYZ-Apply aus. `test_runtime_packaging.py` prüft
Wheel, Source und sdist sowie drei isolierte tatsächliche Resultgenerationen
und identische PYZ-Bytes. `test_producer_compatibility.py` ergänzt die
maschinenlesbare Installationsgrenze und beweist fehlende Runtime-Abhängigkeiten.
Der Writer-Test heißt jetzt `test_writer_uses_python310_requirement_and_start_bytes`;
seine bisherige Zwischenstand-Annahme wurde durch die neue Produktionsgrenze ersetzt.
Historische >=3.12-Ausführung bleibt unter zu alten Interpretern ausdrücklich
ausgenommen, ihre statische Datenprüfung bleibt vollständig erhalten.

Development und Apply führen jeweils die gesamte Suite parallel aus.
Hier ist CPython 3.14.4 verfügbar; weder Metadaten noch Simulationen beweisen
native 3.10-/3.11-Unterstützung. CP-04 ergänzt die manuelle Matrix; CP-05
benötigt Christians CI, konkrete Artefakt-/Interpreterdaten und die berührte
CIFS-/Plattformpraxis. Produktversion bis zur gesonderten Entscheidung 1.3.0;
keine bestehenden Artefakte oder Tags werden geändert.

Primärquellen für die Build-/Testentscheidung:
[Tomli](https://pypi.org/project/tomli/2.0.1/),
[setuptools 77](https://pypi.org/project/setuptools/77.0.3/),
[pytest-Kompatibilität](https://pytest.org/en/latest/backwards-compatibility.html).

Der erste CP-03-Volltest fand 168 Setup-Fehler aus einem gemeinsamen
synthetischen Legacy-Wheel-Fixture (3063 passed / 16 skipped): die neue
bedingte tomli-Dev-Abhängigkeit passt nicht in dessen geschlossenes Altprofil.
Nur dieser explizite synthetische Fixture entfernt die neue Dev-Metadatenzeile;
Original-Wheels, neuer Writer und strikter Legacy-Reader bleiben unverändert.
Der korrigierte Stand benötigt ein neues vollständiges paralleles Gate.


## 10. CP-04 / Bundle 051: manuelle native Matrix und belastbare Nachweise

CP-03 ist mit Commit `ba29e0515af90733d415c73bf999b5ee583baf4f` tatsächlich
angewendet und normal auf dev gepusht. Basisresult:
`patchharbor-apply_Result_101142_1014_eff441.zip`, SHA-256
`8b5d79f020bbd962236c3b4d80f07bf26cd629be946abba814df0e65ec462bae`.
Repository-ID `e7a93d72-62dc-4759-97e8-6bf6cdf10e90`, Fingerprint
`7c9d2a24e397e0e5`, Algorithmus `patchharbor-state-v1`; sauberer Baum,
351 Dateien. Vollständige parallele Gates: Development 3231 passed / 16 skipped,
Apply 3208 passed / 15 skipped. Der erste lokale Fixture-Fehler wurde vor
Auslieferung korrigiert; Originalfixtures und strikter Altreader unverändert.

CP-04 aktiviert ausschließlich workflow_dispatch und die zwölf Lanes aus §4.
Native Artefaktnamen enthalten die Python-Version; PowerShell-7 prüft zusätzlich
Core-/Bootstrap-Zeiten, DACLs, Junctions, beide Varianten und den tatsächlich
installierten Watcher. Die bisherigen 3.12-/3.14- und Docker-Gates bleiben.
Docker exportiert nun ebenfalls vollständige JSON-Reports aller vier parallelen
Gruppen; seine temporären Container bleiben ohne Netzwerk. Der Berichtspfad
wird ausdrücklich in den Container eingebunden, nicht das Arbeitsrepository.

`scripts/capture_ci_build.py` erstellt Wheel/sdist/PYZ mit bestehenden
Releaseaudits und erfasst Hashes, Interpreter-Patchstand, aufgelöste Build-/
Testwerkzeuge, genaue Quellbindung und Commit. Normale CI-Reports liegen neben
dieser Bauquittung. Docker dokumentiert den vom Host belegten Buildkontext-Commit.
`scripts/run_handoff_ci.py` ist nun ausschließlich ein lesender Reviewer für
eine ausdrücklich angegebene Run-ID und volle Commit-SHA. Er besitzt keinen
Dispatch-/Retry-/Pollingpfad mehr; die historische CI-Kennung ist nicht nötig.
Alle zwölf Jobs und Reportartefakte müssen vollständig zum angefragten Stand
passen. Serielle Reports, fehlende Worker, übersprungene native Sicherheitsfälle,
alte Vier-Artefaktlisten und unvollständige Installations-/PYZ-/Watcher-Nachweise
können keine erfolgreiche Abnahme erzeugen. Ein laufender Run wird einmal als
pending gespeichert; er wird weder gestartet noch erneut gestartet.

Die Tests der historischen Wheel-Bootstrap-Installation prüfen unter 3.10/3.11
den tatsächlichen konservativen Fallback vor Installation. Historische komplette
Format-2-Runtime-Ausführung bleibt wegen deren eigener >=3.12-Anforderung
übersprungen; neue Datenleser prüfen dieselben Altresults weiterhin. Kein
unverändertes Altartefakt wird umetikettiert, keine neue Funktion wird dafür geskippt.
Die früheren Dispatch-Simulationen in `test_handoff_ci.py` wurden durch die
entsprechenden lesenden Bindungs-/Fehler-/Vollständigkeitsfälle ersetzt; kein
Dispatch ist mehr zulässiges Verhalten dieses Projektwerkzeugs.

CT-15/16: Tests in `test_handoff_ci.py`, `test_ci_build_evidence.py`, den
bestehenden Workflow-/Docker-Vertragstests sowie die vollständigen Native- und
Packaging-Suites belegen die neuen Nachweisgrenzen. Echter 3.10-/3.11-/Windows-
und Docker-Lauf bleibt Christians manuelle CI; lokale Simulationen zählen nicht
als deren Erfolg. CP-05 bleibt bis zu passenden externen Nachweisen offen.

Der erste vollständige CP-04-Lauf ergab 3245 passed / 16 skipped und zwei
Fehler in bestehenden Workflow-/Launcher-Erwartungen: die PowerShell-Zeile
verwendet jetzt YAML-Anführungszeichen und die Windows-Auswahl enthält acht
zusätzliche Testmodule. Beide Erwartungen wurden dem vorgesehenen Vertrag
angepasst. Der geänderte Stand erhält erneut das vollständige parallele Gate.


## 11. CP-04-FIX1 / Bundle 052: Fehler der ersten erweiterten CI

CP-04 wurde auf `db1167f3471a3f8db462363f611627e7894a6c83` tatsächlich
angewendet/gepusht. Basisresult `patchharbor-apply_Result_104037_1014_3a2194.zip`,
SHA-256 `ccce4805326bfe31a5ba6918eef17a3c593337ebc8784bf1e76fc39d01bbeacb`;
Repository-ID `e7a93d72-62dc-4759-97e8-6bf6cdf10e90`, Fingerprint
`7c9d2a24e397e0e5` / `patchharbor-state-v1`. 353 Dateien, sauberer Baum.
Development 3247 passed / 16 skipped, Apply 3224 passed / 15 skipped.

Christians [manueller Lauf 38551979998](https://github.com/cdoehn/patch-harbor/actions/runs/38551979998)
prüfte denselben vollständigen Commit. Das bereitgestellte Logarchiv hat SHA-256
`07a65a3c3b3302cfd36ee76870f33b789de9635afd719c4d04f8e84e8651013f`.
Vier Joblogs enden grün (Ubuntu 3.11/3.12/3.14 und Windows 3.12); acht enthalten
Fehler. Logs sind Diagnosen, keine vollständige maschinelle Matrixabnahme.

| Befund | Korrektur und Nachweisgrenze |
| --- | --- |
| Python 3.10 kann die ausgegebene UTC-Endung Z nicht direkt mit datetime.fromisoformat lesen. | Ausschließlich der Testparser normalisiert Z zu +00:00. UTC, Zeitzone und unverändertes öffentliches JSON bleiben geprüft. |
| Docker 3.12 installiert das bedingte tomli korrekt nicht; der Preflight verlangte dennoch alle Namen. | PEP-508-Marker mit vorhandenem packaging-Reader im Developmentwerkzeug auswerten. Tests für 3.10/3.11/3.12/3.14, Extras, Plattformen, ungültige Anforderungen und fehlende tatsächlich benötigte Distributionen. Keine Produktabhängigkeit. |
| Windows-Watcher-Test brach nach 35 Sekunden vor dem Drain ab; ein echtes Apply war bereits zurück. | Nur dieses Windows-Testbudget wird 120 Sekunden. Echte Core-Prozesse, zwei einmalige Versuche, Fehler-Replay-Schutz und fünf Sekunden Quiet-Time bleiben. Laufzeiten/Status pro Versuch dienen der Fehlerdiagnose. |
| Nativer Bootstrap-Mutationstest beobachtete teilweise keine erkennbare Änderung. | Private Fixture schreibt nach getrennten Zeittakten, flush/fsync und geschlossenem Writer. Native ChangeTime muss nachweislich verschieden sein; echte Ablehnung bleibt Pflicht. Kein Skip und keine Produktprüfung entfällt. Der native Wiederholungslauf bleibt erforderlich. |
| Ein 10.000-Knoten-Packtest auf Windows 3.12 wurde bei einer Verzeichnis-Metadatenabweichung abgewiesen. | Der Log enthält nicht das abweichende Feld. Unveränderte strenge Signatur wird nun mit allen konkreten Vorher-/Nachher-Abweichungen diagnostiziert; jeder Signaturbestandteil besitzt einen Ablehnungs-/Handle-Cleanup-Test. Die Ursache ist noch nicht nachgewiesen, daher kein Retry, ignoriertes Feld oder behaupteter Verzeichnisfix. |

Der nächste manuelle CI-Lauf muss die Korrekturen nativ bestätigen und, falls
die Verzeichnisabweichung wieder auftritt, ihre exakten Werte liefern.
Die Spezifikationen, Paketformate, Altfixtures, PYZ-/Bootstrapbytes, Workflow-
Auslöser und Sicherheitsentscheidungen bleiben unverändert. Vollständige
parallele Development-/Apply-Gates vor dem einzigen Korrekturcommit; CI startet
nur Christian. Der Produktversionswechsel zu 1.4.0 ist danach gesondert vorgesehen.

Primärquellen zur Einordnung:
[Python datetime](https://docs.python.org/3/library/datetime.html#datetime.datetime.fromisoformat),
[PEP-508-Marker](https://packaging.pypa.io/en/stable/markers.html),
[Windows-Dateizeiten](https://learn.microsoft.com/en-us/windows/win32/sysinfo/file-times).


## 12. CP-04-FIX2 / Bundle 053: Docker-Berichte und verbleibendes Windows-Fixture

CP-04-FIX1 ist mit `6b177eb46c735fe1c7ce673e716f6f95f5dcd4ab` tatsächlich
angewendet/gepusht. Basisresult `patchharbor-apply_Result_114551_1014_6f6831.zip`,
SHA-256 `be9afce4c8a88833a62a0414b7d8b70745536b098d73b730494755e161f2dfb0`;
Repository-ID `e7a93d72-62dc-4759-97e8-6bf6cdf10e90`, Fingerprint
`7c9d2a24e397e0e5` / `patchharbor-state-v1`; 353 Dateien, sauberer Baum.
Development 3263 passed / 16 skipped, Apply 3240 passed / 15 skipped.

Christians [manueller Lauf 38559897782](https://github.com/cdoehn/patch-harbor/actions/runs/38559897782)
prüfte diesen vollständigen Commit. Das bereitgestellte Logarchiv hat SHA-256
`9bee9f2a67a5899cdb499e6306dda6fd6a5e390dc20488ed60e0554ebcf7cf43`.
Neun Joblogs enden erfolgreich. Beide Docker-Jobs bestehen alle vier parallelen
Testgruppen, scheitern danach beim Upload an `EACCES` für den Core-JSON-Bericht.
Windows 3.12 besteht Core/E2E, scheitert an einem anderen nativen Mutationsfixture
im Plattform-Gate und führt Packaging daher nicht aus. Die vorherigen Fehler
kehren in diesem Lauf nicht wieder; für die frühere Verzeichnisabweichung gibt
es damit weiterhin keinen konkreten Metadatenbefund und keinen behaupteten Fix.

### Korrekturen

- Der atomare Testreport wird absichtlich mit 0600 erstellt. Im Docker-Container
  gehört er root; der Upload läuft als Host-Runner und kann ihn nicht öffnen.
  Ein enger Development-Wrapper übergibt nach genau einem Gate den ausdrücklich
  benannten fertigen Bericht an die Host-UID/GID, weiterhin mit 0600. Das gilt
  auch für fehlgeschlagene Gates und die Buildquittung. Keine rekursive Änderung,
  keine Freigabe für alle Benutzer, kein geänderter Produkt-/Report-Writer.
  Symlink, Hardlink, Verzeichnis und FIFO sind ausgeschlossen; Exportfehler
  machen einen erfolgreichen Gate-Aufruf erfolglos und erhalten einen bereits
  fehlgeschlagenen Exitcode. Native POSIX- und Prozess-Verhaltenstests prüfen
  Bytes, Rechte, einmaligen Aufruf, Fehler und Descriptor-Cleanup. Docker-Upload
  selbst bleibt durch die nächste manuelle CI nachzuweisen.
- `test_native_legacy_handle_adapter_detects_real_change_with_restored_mtime`
  belegte exakt gleiche native ChangeTime vor/nach der sofortigen Mutation.
  Das Fixture trennt wie der bereits grüne Bootstrap-Test die Zeittakte durch
  50 ms, schreibt mit flush/fsync, schließt den Writer und stellt mtime zurück.
  Native ChangeTime muss ausdrücklich verschieden sein; gleiche Größe, Identität,
  BirthTime und mtime sowie die echte Ablehnung bleiben verpflichtend. Kein Skip,
  kein Retry und keine tolerantere Produktprüfung. Neuer nativer Windows-Lauf nötig.

Alle Runtime-/Bootstrap-/Altfixture-Bytes, drei Normdateien, Paketverträge,
Workflow-Auslöser und Produktversion bleiben unverändert. Volle parallele
Development-/Apply-Gates vor genau einem Korrekturcommit. CI startet nur Christian;
CP-05 und die Version 1.4.0 folgen erst mit passenden Abnahmen.

Primärquellen: [Windows-Dateizeiten](https://learn.microsoft.com/en-us/windows/win32/sysinfo/file-times),
[Python-Dateieigentümer](https://docs.python.org/3/library/os.html#os.fchown).


## 13. CP-04-FIX3 / Bundle 054: belegter NTFS-Verzeichnisunterschied

CP-04-FIX2 wurde auf `77b38265d08b64b02d9b4e92a5c39eeb32083220` tatsächlich
angewendet/gepusht. Basisresult `patchharbor-apply_Result_131454_1014_6a9679.zip`,
SHA-256 `e092e99a3817246ae30da159a42c3504d04736c46ba22c6b512efbb571d6c138`;
Repository-ID `e7a93d72-62dc-4759-97e8-6bf6cdf10e90`, Fingerprint
`7c9d2a24e397e0e5` / `patchharbor-state-v1`; 354 Dateien, sauberer Baum.
Development 3276 passed / 16 skipped, Apply 3253 passed / 15 skipped.

Christians [manueller Lauf 38585784200](https://github.com/cdoehn/patch-harbor/actions/runs/38585784200)
prüfte denselben Commit. SHA-256 des bereitgestellten Logarchivs:
`5a4bc88269836bd2e2cb2545d6701998f8c67fff57f7cd0f1cc404aedde47bac`.
Elf Joblogs enden erfolgreich, einschließlich beider Docker-Uploads und aller
nativen Mutationsfixtures. Windows/PowerShell 7 mit Python 3.12.10 scheitert
allein am unveränderten Test mit 10.000 Dateisystemknoten.

Die neue genaue Diagnose zeigt `st_file_attributes` vor dem Öffnen 268435472
(0x10000010), danach 16 (0x10). Alle sieben übrigen Signaturfelder sind gleich.
Das entspricht dem in [CPython #126253](https://github.com/python/cpython/issues/126253)
belegten Unterschied: NTFS kann zusätzlich sein internes Verzeichnisbit liefern.
Dieses Bit ist kein öffentliches
[Windows-Dateiattribut](https://learn.microsoft.com/en-us/windows/win32/fileio/file-attribute-constants).
Der zuvor ungeklärte Fehler hat jetzt eine konkrete belegte Ursache; kein
allgemeiner Stabilitäts-Retry oder pauschales Weglassen der Attribute ist nötig.

### Enger Kompatibilitätsadapter und Nachweise

`source_tree.metadata_signature` normalisiert ausschließlich 0x10000000,
und ausschließlich auf Windows, bei Verzeichnistyp, gesetztem öffentlichem
DIRECTORY-Bit 0x10 und ohne REPARSE_POINT-Bit 0x400. Reguläre Dateien,
POSIX-Beobachtungen, Reparse-Punkte und inkonsistente Typangaben erhalten
keine Ausnahme. Alle anderen 31 Attributbits, auch sonstige unbekannte Bits,
werden unverändert verglichen. Identität, Modus, Linkzahl, Größe und beide
Zeitfelder bleiben vollständig erhalten. Rohbeobachtungen werden nicht verändert;
Fehlerdiagnosen behalten ihre konkreten Vorher-/Nachher-Werte. Derselbe Vergleich
gilt für Root, Kindöffnung, erneute Beobachtung und finale Inventarprüfung.

46 zusätzliche Verhaltensfälle prüfen beide Übergangsrichtungen mit vollständiger
Erfassung und Revalidierung eines realen Baums, sämtliche anderen Attributbits,
begrenzten Plattform-/Dateitypbereich sowie echte Metadatenabweichungen und
Handle-Cleanup trotz gleichzeitig wechselndem NTFS-Bit. Reparse-Punkte bleiben
abgewiesen. Die Windows-Stat-Beobachtungen sind dabei gezielt simuliert;
der vorhandene native 10.000-Knoten-Test bleibt unverändert und muss den Fix
im nächsten manuellen CI-Lauf bestätigen. Keine neuen Skips oder Retries für
bestehende Tests und keine reduzierte native Testauswahl.

Dies setzt CPY-07/08 und CT-03/11/16 um, ohne Paket-, Fehler- oder Ressourcen-
verträge zu ändern. Die drei Normdateien, alte Fixtures, Bootstrap-/Startbytes,
Workflow und Produktversion bleiben unverändert. Vollständige parallele lokale
und Apply-Gates vor genau einem Korrekturcommit; CI startet nur Christian.
CP-05 einschließlich Version 1.4.0 und finaler Artefaktbindung bleibt offen.


## 16. CP-05-VERSION / Bundle 055: Version und ausdrücklich beauftragtes Tag

CP-04-FIX3 ist tatsächlich angewendet und normal auf dev gepusht:
`f2e64c241f4e20a1b7e2c4c83faa45ba557f6d0b`.
Result `patchharbor-apply_Result_160614_1014_854693.zip`, SHA-256
`b669f8f6a8ad8876d6a25381dd2b1c26176d09c11901665eb8d7ccdbe636bff4`,
bestätigt 354 Dateien, sauberen Baum und 3299 passed / 15 skipped im vollständigen
parallelen Apply-Gate. Development: 3322 passed / 16 skipped einschließlich
Übergabeprüfungen. Repository-ID `e7a93d72-62dc-4759-97e8-6bf6cdf10e90`,
Fingerprint `7c9d2a24e397e0e5`, Algorithmus `patchharbor-state-v1`.

### Bestätigte native Implementierungsabnahme

Christian startete [CI 38596693717](https://github.com/cdoehn/patch-harbor/actions/runs/38596693717)
manuell auf diesem vollständigen Commit. Alle zwölf Jobs sind grün. Die zwölf
Artefakte wurden heruntergeladen und ihre 39 vollständigen Testreports mit
je vier Workern geprüft: Sammlungen, Worker-Enden, Pflichtfälle, Skips,
Build-/Testbindung sowie Wheel-/sdist-/PYZ-Identitäten und Hashbelege.
Die Original-ZIP-Digests wurden aus GitHub-Metadaten gegen Uploadlogs geprüft;
der Download lieferte entpackte Inhalte, keine lokal erneut gehashten Original-ZIPs.

Native Python-Patchstände: Linux 3.10.22 / 3.11.17 / 3.12.15 / 3.14.7;
Windows und PowerShell 7: 3.10.11 / 3.11.9 / 3.12.10; Docker: 3.12.14.
Die zusätzlichen Skips älterer Interpreter betreffen historische Laufzeiten,
deren eigene Python-3.12-Grenze erhalten bleibt. Neue API-/CLI-/Watcher-/PYZ-
Pflichtdurchstiche einschließlich drei Offline-Generationen bestehen tatsächlich.

### Autorisierter Versions- und Tagschritt

Auf Christians ausdrücklichen Tagauftrag folgt ein echter Versionscommit:
`chore(release): prepare PatchHarbor 1.4.0 [CP-05-VERSION]`.
Die Paketversion, aktuellen Installationsbeispiele, Chatvertragsversion und
bestehenden Release-Prüfwerte wechseln gemeinsam auf 1.4.0. Historische Fixtures,
Startbytes, Normverträge und Laufzeitverhalten bleiben unverändert.

Development und Apply führen die vollständigen parallelen Gates aus.
Der gebundene Entrypoint prüft vor dem Commit, dass lokal und auf origin noch
kein `v1.4.0` existiert. Nach erfolgreichem Gate und geprüftem Commit erzeugt er
genau dieses annotierte Tag auf dem vollständigen neuen Commit. Ein einziger
normaler atomarer Push veröffentlicht dev und Tag gemeinsam; keine Force-Option,
kein Verschieben/Löschen eines bestehenden Tags, keine weiteren Branches.
Lokales Tagobjekt, Zielcommit und beide Remote-Refs werden danach überprüft
und als maschinenlesbarer Nachweis im Result protokolliert. Bei Fehlern bleibt
der tatsächliche Teilfortschritt sichtbar; kein automatisches Aufräumen der Refs.

Diese explizite Einzelausnahme ersetzt nur für Bundle 055 das allgemeine Verbot
unbeauftragten Taggings. Development führt keine Git-Mutationen aus; der vorhandene
Watcher übernimmt den autorisierten Entrypoint. Kein CI-Dispatch, GitHub-Release,
Paketindex-Upload oder Hostupdate ist Bestandteil dieses Auftrags.

Ein Tag ersetzt keine fehlenden Abschlussnachweise. Die native CI ist an den
obigen Implementierungscommit vor der Versionsumschaltung gebunden. Der neue
Versionsstand erhält seine eigenen lokalen/Apply-Gates; eine native CI auf seinem
Endcommit startet weiterhin ausschließlich Christian. Erforderliche neue
CIFS-Praxis und die endgültige CP-05-Abnahme bleiben ausdrücklich offen.
