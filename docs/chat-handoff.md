# Kompakte Chat-Anleitung und separater Starthelfer

Der aktive Vertrag ergänzt Task 2 / Result 4 um Begleitdatenformat 3.
Produktversion und Formatnummern sind unabhängig. Vor-2.0-Kompatibilität ist keine
Anforderung; bestehende 2.0-Begleitdaten bleiben als Format-2-Paar lesbar.
Leser, die Format 3 nicht kennen, lehnen es ab. Es gibt kein stilles Entfernen
der Zusatzdatei, keinen Konverter und keine Lockerung von Bindung oder Replay.

## Ablage und Validierung

| Ressource | Result-ZIP | Task-ZIP |
| --- | --- | --- |
| Anleitung | `CHAT_INSTRUCTIONS.md` | `PATCHHARBOR_META/CHAT_INSTRUCTIONS.md` |
| Umgebung | `environment.json` | `PATCHHARBOR_META/environment.json` |
| Starthelfer | `tools/pyz_bootstrap.py` | `PATCHHARBOR_META/tools/pyz_bootstrap.py` |

Environment 3 verlangt genau diesen relativen Helferdeskriptor:
`bootstrap: {path: "tools/pyz_bootstrap.py", size: <integer>, sha256: <full hash>}`.
Die Größe ist die Bytezahl, kein Boolean; der Hash ist SHA-256 über die exakten
Helferbytes. Zusätzliche/fehlende reservierte Dateien, falsche Großschreibung,
abweichende Pfade, ungültige UTF-8-/BOM-/Größenwerte oder falsche Hashes sind Fehler.
Je Begleitdatei gelten höchstens 128 KiB. Version 2 hat exakt das bisherige Paar
und keinen Helferdeskriptor. Task-Metadaten dürfen vollständig fehlen.

Die Dateien sind passive Metadaten, keine Entrypoints und keine Repository-Payloads.
Normale Root-Dateien eines Tasks sind Payloads; deshalb den Helfer dort niemals
unter `tools/` ablegen. Im Result ist `base/tools/` separat und unverändert.
Öffnen, Inspizieren, Validieren und Packen importieren oder starten den Helfer nicht.

## Produzent und Distribution

Einzige gepflegte Quelle: `tools/pyz_bootstrap.py`. Der Build prüft dessen Syntax
und Capability-Literale statisch. `scripts/render_chat_bootstrap.py --write`
aktualisiert nur diese Literale; `--check` und Buildhooks schreiben nichts.
Die Vorlage verweist auf die Datei und enthält keine ausführbare Kopie.

Wheel und sdist tragen die Quelldatei. Das Wheel enthält zusätzlich normalisierte
LF-Bytes unter `patchharbor/_runtime/tools/pyz_bootstrap.py`; dieselben Bytes gehören
zum geschlossenen PYZ-Inventar, zu Recipe-Hashes und Producer-ID. Unvorbereiteter
Source-Modus liest nur den Helfer seines eigenen geladenen Modulbaums. Keine
Auswahl aus CWD, fremden Repositories, fremden Installationen oder dem Internet.

Execute erfasst Anleitung, Helfer und Runtime vor möglichen Selbständerungen.
Der Result-Writer verwendet diese erfassten Bytes. Scheitert nur die optionale
Runtime, müssen erforderliche Ressourcen weiter gegen dieselbe Producer-ID und
Recipe-Einträge nachgewiesen werden. Kein späteres Nachladen beliebiger neuer
Bytes. Fehlende Pflichtressourcen verhindern eine unvollständige Veröffentlichung.

Die bestehende PYZ-Rezeptversion lässt den Helfer als benannte Ressource zu;
alte 2.0-PYZ ohne separate Ressource bleiben als Daten lesbar. Neue Erzeuger und
Releaseprüfungen verlangen sie. Ein alter Produzent kann keinen Helfer erfinden.
Die neue äußere ZIP-Grenze von 250.011 erhält 250.000 Snapshotdateien plus elf
maximale Begleiteinträge; alle übrigen Budgets und Sicherheitsprüfungen bleiben.

## Inhalt und Vertrauensgrenze

Der erzeugte Kopf enthält nur Repositoryname, Bundleart/-name, einen Verweis auf
die vollständige `environment.json` und passend zitierte lokale Befehle. Vollständige
Zielinformationen bleiben ohne Verlust in JSON. Pfade gelten für den Zielrechner,
`null` bleibt unbekannt, die verbindliche Bindung kommt aus `context.json`.
Unbekannte erlaubte Zusatzwerte werden erhalten. Markdown-Daten werden escaped;
Kontrollzeichen in Pfaden erzeugen keine ausführbaren Beispiele.

Die Vertrauensprüfung vor dem expliziten Start bleibt erforderlich. Ein Hash im
selben unbekannten Paket authentifiziert niemanden. Der Standardbibliothek-Helfer
prüft nur Runtime-Beschreibung/Artefakt; seine positive Vorprüfung ist keine native
Vollprüfung des Results. Erst `pack`/`validate` prüfen die vollständige Referenz.
`unavailable` und technische Startfehler bleiben aktuelle Fälle mit dokumentiertem
sicherem Fallback, nicht eine Erlaubnis zum Umgehen ungültiger Repositorydaten.

## Zuordnung der bisherigen Regeln

Basis: `CHAT_INSTRUCTIONS.md` in Commit
`32804cc6c0b1e58c9fd9c1122237d089b574cdee`. Die nachfolgende Zuordnung dient der
inhaltlichen Prüfung; ihr Archiv wird nicht automatisch in den Prompt geladen.

| Bisheriger Abschnitt | Aktuelle Stelle / Behandlung |
| --- | --- |
| Einleitung, Formate | Einleitung; Task 2 / Result 4 erhalten, Environment 3 ausdrücklich ergänzt |
| 1 Aufgaben, Core-Nutzung, keine Sandbox | §1; keine erfundenen APIs, keine rekursive Ausführung, kein zweiter Writer |
| 1 POSIX-Modi/Selbstupgrade | §4 Modi; §1 privater Schritt-Core; 0600, Sonderbits, ACL-Grenzen erhalten |
| 1 Repositorykonfiguration | §6; lokaler geschlossener Vertrag, kein globaler Fallback/Metadatenersatz |
| 1 Exchange-/Watcher-Auswahl | §6; lokaler manueller Scope, globaler automatischer Scope, Replay und Auswahlordnung |
| 1 Archivierung | §6; konservative Beweise, keine Löschung, frische Abschlussprüfung |
| 1 Attempt-Recovery | §6; Beweiskette und echter Lock, Replay-Formatangabe auf aktuellen Wert 5 korrigiert |
| 2 Eingaben | §1/§2; aktuelles vollständiges Result und vollständige Maschinenwerte |
| 3 Snapshotprüfung | §2; Base + staged + unstaged + untracked, tatsächlicher Fehlerzustand |
| 3 Umgebung | §2 und JSON; keine erfundenen Werte, Hostdaten-Minimierung, Shell-/Kernelgrenzen |
| 3 eingebettetes Python | `tools/pyz_bootstrap.py`; tatsächliche Datei in Bundle und Distribution |
| 3 Vorcheck/Python-only/Herkunft | §2 Starthelfer; unveränderte Trennung von Datenprüfung, Vertrauen und Import |
| 3 Runtime-Ausfall | §2 Fallback; ein Versuch, Originalbytes, kein Formatwechsel/falscher Vollnachweis |
| 4 aktive Pläne/Suchfolge | §3; expliziter Auftrag, gemeinsame Normsätze, eindeutige Suchfolge und STOP-Codes |
| 4 PatchHarbor-spezifische Versionen/alte Arbeitsphasen | Historisches Archiv; keine operative Vorgabe für fremde Projekte |
| 5 Scope/Projektregeln/Diagnosebundle | §3; Nutzervorrang, keine Scope-Ausweitung, null Commits weiterhin zulässig |
| 6 PLAN/FIX/OFF-PLAN/WRC | §3; Kennungen, Messages, Zähler und echte Zwischenstände erhalten |
| 7 Pack/ZIP/Dateiname/Suffix | §4; falsches Wort Patch im Task-Namensschema korrigiert |
| 7 Manifest/Entrypoint/Pfade/Modi | §4; sieben geschlossene Felder, volle Bindung, private Ausführung, Pfadgrenzen |
| 7 Begleitpaar/Umgebung | §4; `bundle_type: Task`, explizites Format 3; bisheriges Format 2 weiter lesbar |
| 7 erstmaliger Vor-2.0-Runner-Workaround | Nur Archiv; nicht mehr Bestandteil des aktiven Vertrags |
| 7 Ressourcen | §4; unzutreffenden Format-1-Titel entfernt, genau ein Begleitplatz ergänzt |
| 8 Testpolicy/Gates/Sequenz | §5; nach Zielprojekt, echte Reihenfolge, rotes Gate stoppt Folge, fremde Änderungen erhalten |
| 8 Bündelnummer/Erfolgszeile | §5/§7; nur vollständiger belegter Erfolg, keine nominellen Zwischencommits |
| 9 Ergebnisauswertung | §5; Gesamterfolg, Teilerfolg und Fehlerarten getrennt belegen |
| 10 WARNUNG/STOP | §7; Codes, Anfang/Abschluss und keine ZIP/Nummer bei STOP erhalten |
| 11 Anzeige/Nummer/Backup/Versand | §7; eine Datei, genaue SHA, Nutzungsautorisierung, kein Doppelversand, letzte Linkzeile |
| 12 Komponentenrollen | §1; generische Verantwortungsgrenzen, kein automatischer Projektauftrag |

Alle früheren Prosaangaben stehen im ausdrücklich inaktiven
[Archiv](history/chat-instructions-before-standalone-helper.md). Der damalige
Code bleibt außerdem an den genannten Git-Commit gebunden. Zusammengeführte
Regeln stehen einmal an ihrer fachlichen Stelle; zeitgebundene Erfolge werden
nicht als aktueller Stand fortgeschrieben. Fehlende ignorierte Projektregeln
werden weder erfunden noch aus historischen Projektabschnitten abgeleitet.

## Nachweise

Apply führt die bestehende vollständige parallele Suite vor jedem Commit aus.
Die ergänzten Fälle prüfen passive Task-/Result-Helfer, ungültige Deskriptoren und
Inventare, fehlende Ressourcen, Einfrieren vor Selbständerung, Build-Gates,
Wheel/sdist/PYZ, echte Python-only-Nutzung aus einem Result und drei Generationen
nach Entfernen der ursprünglichen Buildquellen. Testausführung findet nicht im
Development statt. Vor einem Result sind diese Prüfungen geplant, nicht bestanden.
