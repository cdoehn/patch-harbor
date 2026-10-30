# PatchHarbor – CPython 3.10 und 3.11

**Dokument-ID:** `CPYTHON-310-311`
**Revision:** 3
**Stand:** 30. Oktober 2026
**Status:** Fortgeltender CPython-Vertrag; RF-01 begrenzt die Artefakt-Kompatibilität auf die Basis ab 1.4.0. Implementierungs- und offene Abnahmenachweise bleiben im CPython-Plan erhalten.
**Produktbasis:** 1.4.0; Refactoring-Ziel 1.5.0. CPython-Untergrenze unverändert 3.10.
**Historischer Umsetzungsplan:** [CP-00 bis CP-05](../planning/python-compatibility/commit-plan.md)
**Aktiver Plan:** [REFACTOR-1.5.0](../planning/1.5.0/commit-plan.md)

## 1. Geltung und gezielte Vertragsänderung

**CPY-01.** Der Auftrag erweitert den tatsächlich unterstützten Bereich um
CPython 3.10 und 3.11. Gemeinsam normativ sind:

1. [SPECIFICATION.md](SPECIFICATION.md),
2. [SPECIFICATION_EXTENSION_PYZ_PACK.md](SPECIFICATION_EXTENSION_PYZ_PACK.md),
3. diese Ergänzung.

Dieser ausdrücklich erklärte Satz erweitert die Auswahlregeln der Hauptspec
§26.3/35 und PYZ/PACK GOV-01/03 ausschließlich für diesen Auftrag. Die Dateien
sind keine konkurrierenden Kandidaten. Spätere ausdrückliche Nutzerentscheidungen
gehen vor; danach gelten die hier ausdrücklich bezeichneten Abweichungen,
danach die fortgeltenden Regeln der beiden bisherigen Normdateien. Ein Plan
oder ein Implementierungsdetail darf die Sicherheitsverträge nicht absenken.

Gezielt ersetzt werden die Python-Untergrenze und der Ausschluss älterer
Interpreter in Hauptspec §4.2/38.2/41 sowie PYZ/PACK §2.2, PYZ-02 und TEST-04.
Die in 1.3.0 veröffentlichten Artefakte, Metadaten, IDs und Hashes bleiben
unverändert historische Tatsachen, ohne fortgesetzte Supportpflicht für diese
Altartefakte. Die ursprüngliche CP-00-Planübernahme änderte noch keine Laufzeit.
RF-01 präzisiert CPY-10–12 nach Hauptspec §1.1; Sicherheitsregeln bleiben erhalten.

## 2. Unterstützter Funktionsumfang

**CPY-02.** Zieluntergrenze für die neue Distribution und ihre Core-PYZ ist
CPython 3.10. Unter 3.10 und 3.11 funktionieren die vollständige öffentliche
synchrone API sowie sämtliche Core-CLI-Operationen mit ihren bisherigen
Voraussetzungen. Dazu gehören `pack`, `inspect`, `validate`, Registrierung,
Konfiguration, Kontext, `bundle`, tatsächliches/fehlgeschlagenes/Dry-Run-Apply
und `fs run`. Ein erfolgreicher Import oder `--version` genügt nicht.

**CPY-03.** Die normal installierte Watcher-Anwendung einschließlich API,
CLI, Worker-Grenze und vorhandener Dienstintegration funktioniert ebenfalls
unter beiden Interpretern. Linux-inotify, Windows-Ereignisse, fünf Sekunden
Quiet-Time, deduplizierte Beobachtung, Replay/Recovery, kontrolliertes Ende und
unterdrückte identische `no_candidate`-Meldungen bleiben erhalten. Kein
Ein-Sekunden-Poller, kein zweiter Apply-Runner und kein Watcher in der PYZ.
Die Unterstützung erzeugt keine zusätzliche Android-/Termux-Dienstzusage.

**CPY-04.** Core und PYZ bleiben ohne externe Laufzeitabhängigkeiten und ohne
mitgelieferten Interpreter. CLI und API verwenden dieselbe Implementierung.
`pack`/`inspect`/referenzgebundenes `validate` benötigen weiterhin weder Git,
Shell, Netzwerk noch eine Installation. Andere Operationen behalten ihre
Git-, Registry-, Dateisystem- und Interpretervoraussetzungen. Für 3.12 und 3.14
bleiben die vorhandenen Nachweise und Regression-Gates verpflichtend; daraus
folgt keine Zusage für beliebige zukünftige Interpreter oder PyPy.

## 3. Sprach-, Bibliotheks- und Sicherheitskompatibilität

**CPY-05.** Syntax, Importe, Typannotation-Auswertung, Paketressourcen und
Fehlerpfade müssen unter echtem 3.10 und 3.11 funktionieren. Neuere Funktionen
wie `typing.Self` oder `BaseException.add_note` dürfen nicht erst in seltenen
Abbruch-/Cleanup-Pfaden einen Import- oder Attributfehler verursachen.
Ein schmaler interner Kompatibilitätsadapter ist erlaubt; keine zweite Core-API
oder öffentliche Alternativimplementierung. Primärfehler, Fehlerkategorien,
Exitcodes, Warnungen, Ausnahmeverkettung und relevante Cleanup-Diagnosen bleiben
erhalten. Eine fehlende Komfortfunktion darf den Primärfehler nicht verdecken.

**CPY-06.** TOML wird nur dort bereitgestellt, wo Build-/Entwicklungswerkzeuge
es benötigen. Für 3.10 darf ein kompatibler TOML-Reader als ausdrücklich
bedingte Build-/Testabhängigkeit dienen. Kein eigener unvollständiger Parser,
kein nachträgliches `pip` im Produktaufruf, kein externer Runtime-Import und
keine zusätzliche Fremdbibliothek in der Core-PYZ. Installation aus Wheel und
sdist sowie die vollständige Testumgebung müssen mit kompatiblen tatsächlich
aufgelösten Werkzeugversionen unter beiden Interpretern möglich sein.

**CPY-07.** Dateisicherheit wird semantisch erhalten: reguläre Dateien,
No-follow, Symlink-/Junction-/Reparse-Ablehnung, sichere Elternverzeichnisse,
vollständige Identität, stabile Lesevorgänge, begrenzte Erfassung, Hashbindung,
Dateirechte und geordnete Handle-Freigabe. Das Fehlen von `Path.is_junction`
oder `st_birthtime_ns` ist keine Erlaubnis, die Prüfung wegzulassen oder nur
Größe/mtime zu vergleichen. Bestehende native Adapter sind zu nutzen bzw.
gezielt zu vervollständigen. Kann ein konkretes Dateisystem die erforderliche
Primitive nicht bieten, bleibt es explizit nicht unterstützt.

**CPY-08.** Windows-Pfad- und Handle-Beobachtungen müssen auch vor 3.12
vergleichbare Zeit-/Identitätsinformationen verwenden. Erstellungszeit und
Änderungszeit sind getrennt zu behandeln; keine pauschale Gleichsetzung von
`ctime` und `birthtime`. Reale Änderungen, Austausch und gleiche Größe/mtime
bei verändertem Inhalt müssen weiter erkannt werden. Private temporäre
Verzeichnisse und DACLs sind unter den tatsächlich eingesetzten Patchständen
zu prüfen; die Minorversionsnummer allein beweist kein Betriebssystemverhalten.
Der stdlib-Bootstrap erhält dieselben Sicherheitsinvarianten, ohne einen
vorinstallierten Core zu benötigen.

**CPY-09.** Pack-No-replace und Result-Publikation bleiben getrennte Verträge:
kein Überschreiben vorhandener Pack-Ziele; für Results unveränderte
Replace-/Sync-/CIFS-Retry-/Budget-/Diagnoseregeln. Beibehalten werden außerdem
Repository-ID, voller Base-Commit, Fingerprint/Algorithmus, Locks, Replay,
Recovery, Fehler-Teilfortschritte, ZIP64 sowie sämtliche Datei-/Bytebudgets.
Insbesondere bleiben 250.000 Snapshot-Dateien, 250.010 äußere ZIP-Einträge
und das separate innere Runtime-Limit erhalten. Keine automatische
Konfigurationsmigration, kein Cache als Vertrauensquelle und kein Retry um
semantisch ungültige Referenzen herum.

## 4. Kompatibilitätsbasis ab 1.4.0 und geschlossene PYZ-Verträge

**CPY-10.** Neue Leser verarbeiten unveränderte gültige 1.4.0-Results und
später unterstützte Vertragsstände. Result 1/2, Legacy-Wheel-Metadaten und die
originale 1.3.0-PYZ sind keine Supportpflicht mehr. Statische Resultprüfung
bleibt von der Ausführbarkeit der eingebetteten Runtime getrennt; unbekannte
oder nicht unterstützte Daten sind keine Erfolgs-/Archiv-/Recovery-Belege und
lösen keine Ersatz-Ausführung aus. Historische Bytes werden nicht verändert.

**CPY-11.** Patchformat 1, Resultformat 3, Runtime-Metadatenformat 2,
PYZ-Rezeptformat 1, Profil `patchharbor-core-no-watcher-v1` sowie bestehende
Inhalts-/Produzenten-ID-Algorithmen bleiben erhalten. Die unterstützte Basis
verwendet `requires_python: ">=3.10"` und die dazu festgelegten Startbytes.
Die ursprüngliche 1.3.0-Variante `>=3.12` bleibt historische Dokumentation,
keine Pflicht für neue Leser. Keine beliebigen Versionsausdrücke.

Rezept, Deskriptor, Build-Metadaten, Identitätsbytes und beide Startdateien
müssen denselben Vertrag beschreiben. Unbekannte Profile/Felder, gemischte
Startbytes und neu gehashte Widersprüche bleiben ungültig. FMT-03 erlaubt
genau die Capability-Varianten `[1, 2, 3]` (unveränderte Basis) und `[3]`
(bereinigter Produzent). Dies sind Result-Lesefähigkeiten des Produzenten,
keine unterschiedlichen Python-Mindestversionen oder neue Profilidentitäten.

**CPY-12.** Die damalige Umstellung auf `>=3.10` bereitete Leser und Bootstrap
vor dem Writerwechsel vor. Dieser historische Übergang muss nicht wiederholt
werden. Vor der Altpfadbereinigung werden unveränderte 1.4.0-Fixtures gesichert;
neue Leser und Bootstrap erhalten deren geschlossenen Vertrag. Writer,
`unavailable`-Metadaten, Programmeinstieg und eingebettete Anleitung bleiben
konsistent. Neue Results enthalten genau eine passende PYZ oder begründetes
`unavailable`. Bereits veröffentlichte 1.4.0-Leser dürfen unbekannte zukünftige
Verträge konservativ ablehnen; Abwärts- ist keine Vorwärtskompatibilität.

**CPY-13.** Bootstrap und In-Process-API funktionieren offline mit der
Standardbibliothek unter beiden neuen Interpretern. Sie prüfen vor Import
Herkunft, Pfade, Inventare, Budgets, Deskriptoren, Variante, Größen und Hashes.
Der minimale Vorcheck bleibt von vollständiger nativer Referenzvalidierung
unterschieden. Fremdimport-Konflikte werden nicht durch `sys.modules`-Löschen
verdeckt. Zu alte Interpreter werden vor Core-Import verständlich abgewiesen.
Bei technisch unbenutzbarer Runtime bleibt der bisherige dokumentierte
Fallback erhalten; falsche Bindung oder beschädigte Pflichtdaten bleiben Fehler.

## 5. Nachweis und Freigabe

**CPY-14.** Neue Verhaltenstests ergänzen die bestehenden vollständigen
parallelen Suites. Für jede Änderung entstehen ihre Fehler-/Sicherheitsprüfungen
im selben Implementierungsschritt. Keine Tests auf Konsolenlayout, Farben,
README-Prosa oder Markdown. Versionssimulationen sind ergänzende Grenztests,
kein Ersatz für tatsächliche CPython-Prozesse, native Windows-Handles oder
reale Result-/Pack-/Apply-Durchstiche mit gebauten Artefakten außerhalb des
Checkouts. Ein Skip ist kein positiver Unterstützungsnachweis.

**CPY-15.** Die manuelle CI-Matrix erhält reale 3.10- und 3.11-Lanes für
Linux und Windows einschließlich PowerShell-Integration und Watcher. Bestehende
3.12-/3.14-, Docker- und native Windows-Gates bleiben erhalten. Nur Christian
startet `workflow_dispatch`; keine Push-/PR-/Zeitplan-Trigger, kein automatischer
Dispatch oder Retry durch Codex, Watcher oder Entrypoint. Gemäß Nutzerentscheidung
vom 29. Oktober 2026 prüft Development nur eine dokumentierte änderungsbezogene
Auswahl parallel. Apply prüft jeden Commit mit der vollständigen parallelen
Suite, auch vor dem letzten Commit am Bundle-Ende; keine seriellen Gates.

**CPY-16.** Abnahme erfordert vollständigen Commit, tatsächlich geprüfte
Python-Patchstände, gebaute Wheel-/sdist-/PYZ-Hashes, echte lokale/Apply-Results
und passende erfolgreiche manuelle CI. Derselbe kanonische PYZ-Inhalt muss aus
Installation und PYZ selbst einschließlich drei isolierter Resultgenerationen
reproduzierbar sein. Messungen und fehlende native/Praxisnachweise bleiben
sichtbar. Die bisherige Nutzerbestätigung zu CIFS ist historische Evidenz;
berührte CIFS-/Metadatenpfade benötigen einen gezielten neuen Praxisnachweis
für die geänderte Kombination. Tags, Releases und Hostupdates sind eigene Aufträge.

## 6. Verbindliche Verhaltenstestfälle

| ID | Nachweis |
| --- | --- |
| CT-01 | Öffentliche API und alle CLI-Einstiege unter echtem 3.10/3.11 importieren/starten; Typen, Fehler und Rückgaben bleiben kompatibel. |
| CT-02 | Hauptfehler plus fehlschlagendes Cleanup erhalten Kategorie, Exitstatus, Verkettung und Diagnosen ohne `add_note`-Attributfehler. |
| CT-03 | Native Windows-Identität, Pfad-/Handle-Zeiten, Inhaltsänderung bei gleicher Größe/mtime und Dateiaustausch bleiben sicher erkannt. |
| CT-04 | Symlink, Junction, Reparse-Punkt, umgelenkte Eltern, Dateirechte und private Arbeitsverzeichnisse/DACLs werden unter alten und neuen Interpretern geprüft. |
| CT-05 | Neue Leser validieren unveränderte eingefrorene 1.4.0-Results und deren PYZ; statische Lesbarkeit hängt nicht von ihrer Ausführbarkeit ab. |
| CT-06 | Unterstützte PYZ mit >=3.10 und beide Capability-Varianten bestehen; unbekannte Anforderungen, gemischte Deskriptoren/Startbytes und neu gehashte Widersprüche scheitern. |
| CT-07 | Frischer stdlib-Prozess startet die neue PYZ unter 3.10/3.11 offline; kein fremdes Paket, Installer oder Checkout wird verwendet. |
| CT-08 | Eigene Result-Anleitung bootstrapped ihre tatsächliche PYZ; In-Process-API, Herkunft, Importkonflikt und zu alter Interpreter werden korrekt behandelt. |
| CT-09 | Vollständige Core-API/CLI-Parität: Konfiguration, Registrierung, bundle, tatsächliches Apply, Dry-Run, fehlgeschlagenes Apply und fs-run mit denselben Verträgen. |
| CT-10 | API-/CLI-/PYZ-pack mit vollständigen/diff/gemischten/Diagnose-Inhalten erzeugt dieselben gültigen Verträge; inspect/validate prüfen exakt die Referenz. |
| CT-11 | Pack-Nebenwirkungsfreiheit, No-replace, konkurrierende Publikation, Inputwechsel, Abbruch und Cleanup erhalten Erfolg/Fehlerkategorien. |
| CT-12 | Resultproduktion, Replay/Recovery/Archivierung, ZIP64, Datei-/Bytegrenzen und Runtime-unavailable/Fallback bleiben korrekt. |
| CT-13 | Normale Wheel-/sdist-Installation unter 3.10/3.11 bereitet Ressourcen vor; PYZ bleibt ohne Watcher/Runtime-Dependencies und ohne Cache materialisierbar. |
| CT-14 | Gebaute PYZ führt drei isolierte Generationen, Eigenressourcen/Pinning/Selbstupdate und Byte-Reproduktion unter beiden Interpretern durch. |
| CT-15 | Tatsächlich installierter Watcher: native Ereignisse, fünf Sekunden Ruhe, Änderungen während Apply, Duplikate, Neustart/Ende und beide Windows-Shells. |
| CT-16 | Dokumentierte parallele Development-Auswahl und vollständige parallele Apply-Gates, eindeutige manuelle CI-IDs/Commitbindungen und getrennte neue CIFS-Praxis bei betroffenen Pfaden. |

## 7. Primärquellen und Abgrenzung

Die Sprach-/Standardbibliotheksunterschiede wurden für CP-00 anhand der
offiziellen CPython-Dokumentation geprüft. Die obigen Produkt- und
Sicherheitsentscheidungen sind PatchHarbor-Verträge, keine Garantie der Quellen.

- [Python 3.11: Neuerungen](https://docs.python.org/3.11/whatsnew/3.11.html):
  `Self`, `tomllib` und Exception-Notizen sind neu gegenüber 3.10.
- [Python 3.12: Neuerungen](https://docs.python.org/3.12/whatsnew/3.12.html):
  Junction-Erkennung und Windows-stat-Felder wurden erweitert; Patchstände
  unterscheiden sich auch beim Verhalten privater Verzeichnisse.
- [Python 3.10: os](https://docs.python.org/3.10/library/os.html) und
  [Python 3.12: os](https://docs.python.org/3.12/library/os.html):
  Dateizeiten und Feldverfügbarkeit sind plattformabhängig. Der konkrete
  Pfad-/Handle-Vertrag ist zusätzlich im betroffenen Interpreter zu prüfen.

| Revision | Datum | Änderung |
| --- | --- | --- |
| 3 | 2026-10-30 | RF-12: CPY-15/CT-16 an die geltende ausgewählte parallele Development-Prüfung und vollständige parallele Apply-Gates angeglichen; Interpreter- und Sicherheitsverträge unverändert. |
| 2 | 2026-10-29 | RF-01: Supportbasis ab 1.4.0 statt Pflicht für Results 1/2 und originale 1.3.0-PYZ; historische Bytes bleiben unverändert, Untergrenze und Sicherheitsverträge erhalten. |
| 1 | 2026-10-13 | Beauftragtes Ziel CPython 3.10/3.11, Vertragsabgrenzung, geschlossene Legacy-/Ziel-PYZ-Varianten und Abnahmematrix; noch keine Runtime-Änderung. |
