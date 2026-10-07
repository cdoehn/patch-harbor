# Pack-Grundlagen – interner Implementierungsstand PP-02A

Normativ gelten [die Hauptspezifikation](../spec/SPECIFICATION.md) und
[die PYZ/PACK-Erweiterung, Revision 2](../spec/SPECIFICATION_EXTENSION_PYZ_PACK.md)
gemeinsam. Der aktive [Implementierungsplan](../planning/pyz-pack/commit-plan.md)
ordnet Referenzerfassung und Inhaltsaufnahme als PP-01 und PP-02A ein.

**Noch kein öffentlicher `patchharbor pack`-Befehl und keine `api.pack_patch`.**
Diese Seite beschreibt die interne Grundlage für die späteren Pack-Schritte.
Result-Writer, Runtime-Wheel, Installationsweg und Patchformat sind unverändert.

## Eine erfasste Referenz, ein Datenstand

`result_reader.capture_result_reference(path, resource_policy=...,
expected_identity=...)` verwendet die bestehende stabile Dateierfassung und
den vollständigen formatabhängigen Result-Parser. Ein frozen/slots-Wert
`CapturedResultReference` hält danach nur die benötigten unveränderlichen Daten:

- `facts`: bestehende `ResultFacts` einschließlich des tatsächlichen Kontexts;
- `sha256`: Hash aller erfassten Resultbytes, nicht eine spätere Hash-Dateilesung;
- `bundle_suffix`: geprüftes Suffix, bei alten Results ohne Angabe der vorhandene
  leere Default;
- `handoff`: vorhandenes `BundleHandoff` mit exakten UTF-8-Bytes der Anleitung und
  der Umgebung, beziehungsweise `None` für gültige Legacy-Results ohne das Paar.

Das vollständige Archiv bleibt nicht im Rückgabewert gespeichert. Die kleinen
passiven Bytes dürfen mit dem bestehenden strikten JSON-Parser bei Bedarf neu
dekodiert werden; es entsteht dabei ein eigenes veränderliches Objekt, kein
geteilt veränderlicher Cache. Quelle ist immer die bereits vollständig geprüfte
Erfassung, nie ein zweites Öffnen des Referenzpfads. Ein Leser fügt keine lokalen
Hostinformationen zu unbekannten Zielumgebungsfeldern hinzu. Ein Hash ist kein
Authentizitätsnachweis und ein erfasster Wert kein allgemeines Vertrauenstoken.

Dirty-, Fehler- und Dry-Run-Results bleiben gültige Referenzen gemäß Bestandsvertrag.
`expected_*` eines vorherigen Apply wird nicht als tatsächliche Bindung verwendet.
Eine deklarierte defekte Runtime bleibt ein Fehler; ein gültiges `unavailable`
ist erlaubt. Der schwächere Repository-only-Diagnosepfad darf hierfür nicht
verwendet werden. Zielrechnerpfade werden nicht lokal aufgelöst. Weder Git noch
Registry, Shell, Netzwerk, Installation oder fachliche Schreibzugriffe sind nötig.

## Gemeinsame Validierung ohne erneuten Referenzzugriff

Der bestehende `read_result_reference(...)` ist ein kompatibler Adapter und
liefert unverändert `(ResultFacts, sha256)` mit den bisherigen Parametern und
Fehlerkategorien. Bestehende öffentliche API-/CLI-Signaturen und Ergebnisschemata
bleiben erhalten. Die neuen Namen sind interne Bausteine, keine zusätzlichen
öffentlichen APIs aus `patchharbor.api`.

`patch_inspection.validate_patch_against_reference(path, captured, ...)` ist der
interne Anschluss für den späteren Packer. Er liest und inspiziert die
**tatsächlichen Patch-ZIP-Bytes** erneut vollständig, verwendet aber für die
Bindung den innerhalb desselben Auftrags erfassten Referenzwert. Die gemeinsame
Ergebnisbildung prüft dieselbe vollständige Bindung und liefert dieselben
`scope`-/`not_checked`-Fakten wie die pfadbasierte öffentliche Validierung.
Fehlercodes aus Entrypoint, Paketprüfung und Bindung bleiben unverändert.

Der Aufrufer muss `captured` über die vollständige Erfassung erzeugen. Der
interne Anschluss akzeptiert weder eine Diagnosebewertung als Ersatz noch
führt er einen manuellen Konstruktoraufruf als neuen öffentlichen Vertrag ein.
Die späteren Pack-Schritte bleiben für Quellinventar, sichere temporäre Ausgabe,
Identität und unveränderte Bytes bis zur Veröffentlichung verantwortlich.

## Bereits vorhandene Regeln wiederverwenden

Für weitere Schritte dienen `bundle_paths`/`patch_manifest`/`patch_package`,
`payload_modes`, `resource_policy` und die Interpreter-/Markerprüfung weiterhin
als gemeinsame Regelquellen. Das vorhandene `BundleHandoff` und
`render_chat_handoff(document, template=...)` bieten unveränderliche Daten und
reines Rendering mit ausdrücklich übergebener Vorlage. Kein zweiter Satz von
Pfad-, JSON-, Handoff- oder Bindungsregeln wird hier eingeführt.

Result-Publikation bleibt in `result_bundle_publication` mit dem begrenzten
CIFS-Stabilisierungsvertrag aus `result_verification`: eigene Besitz-/Sync-Checks,
Replace und kontrollierte Wiederholungen. Die Weitergabe von `expected_identity`
und der `FileChangedDuringRead`-Ursachenkette bleibt erhalten. Dieser gemeinsame
Referenzreader selbst wiederholt nichts. Der spätere Packer bekommt ausdrücklich
No-replace **ohne** Stabilitäts-Retries. Eine gemeinsame Lesefunktion verschmilzt
nicht diese unterschiedlichen Publikationsregeln.

## Expliziter Inhaltsordner und unveränderte Dateien

Der interne Baustein `pack_sources.capture_sources` erfasst einen ausdrücklich
gewählten Inhaltsordner vollständig. Die Wurzel darf einmal kontrolliert
aufgelöst werden. Darunter werden Symlinks, Reparse-Punkte, erkennbare Hardlinks
und Sonderdateien abgelehnt. POSIX-Zugriffe sind an offene Verzeichnisdeskriptoren
gebunden; Windows hält die Vorfahren über nicht verschiebbare Verzeichnishandles.
Die vorhandenen Datei-, Pfad-, Modus- und statischen Skriptprüfer bleiben die
gemeinsame Regelquelle. Eine installierte Bash oder PowerShell ist dafür unnötig.

Dotfiles und eine enthaltene Repository-`CHAT_INSTRUCTIONS.md` sind Nutzdateien.
Es gibt keine `.gitignore`-Filterung und keine Auswahl angrenzender Dateien.
Die generierten Wurzelpfade `patch.json` und `PATCHHARBOR_META` sind reserviert;
interne `.git`-/`.patchharbor`-Pfade bleiben verboten. Leere Verzeichnisse zählen
zum Scanbudget und erzeugen eine zusammengefasste Warnung.

Alle Nutzbytes einschließlich Binärdaten und Zeilenenden bleiben erhalten.
Der voreingestellte Paketmodus ist `0644`, unabhängig von den Quellrechten.
Explizite Modi wie `0755` werden geprüft; ihre Schlüssel müssen tatsächlich
enthaltene reguläre Dateien bezeichnen. Dies ändert keine Apply-Regel für bereits
vorhandene POSIX-Zielrechte und ergänzt keine fehlenden Skriptmarker.

Die Aufnahme prüft höchstens 10.000 Dateisystemknoten einschließlich Wurzel und
Verzeichnissen. Von den 1.000 ZIP-Einträgen bleiben drei für Manifest und passive
Handoff-Dateien reserviert. Die gemeinsamen Grenzen von 256 MiB pro Inhalt und
512 MiB insgesamt werden vor und während der Byteaufnahme durchgesetzt. Die
später erzeugten Metadaten werden im Kandidatenbau zusätzlich geprüft.

Erkannte Änderungen beim Öffnen, Lesen oder bei der abschließenden erneuten
Inventur führen zu einem Fehler ohne Stabilitäts-Retry. Dies ist kein atomarer
Snapshot eines beliebig gleichzeitig manipulierten Verzeichnisbaums. Eine
spätere Veröffentlichung muss die erfassten Eingaben nochmals revalidieren.
Die Ausgabepfadprüfung akzeptiert nur ein neues Ziel außerhalb des Inhaltsbaums
in einem vorhandenen Verzeichnis. PP-02A erzeugt keine Ausgabe und schreibt
weder Eingaben noch Repository-/Registrydaten.

`tests/test_pack_sources.py` deckt die Eingabe-, Modus-, Budget- und Fehlergrenzen
sowie kontrollierte Datei-/Verzeichnisaustausche ab. Native Windows-Nachweise
werden durch Linux-Tests nicht ersetzt. Der interne Scanner ist bis PP-02B ein
ausdrücklich vorbereiteter Architektur-Einstieg ohne öffentliche Pack-API.

## Nachweise und Grenzen

`tests/test_captured_reference.py` ergänzt 52 funktionale Fälle für stabile
Bindung und Handoff-Bytes, Legacy-/Fehler-/Dirty-Referenzen, unveränderliche
Ergebnisdaten, Dateiaustausch, Fehlerkategorien, Ressourcenlimits, Weitergabe der
Publikationsidentität und fachlich lesende API-Parität. Die vorhandenen
Inspektions-, Referenz-, Runtime- und Publikationstests bleiben ebenfalls Pflicht.

Gesammelte Tests oder manuelle API-Gegenproben sind keine bestandene Vollsuite.
Die Nachweislage des konkreten Bundles steht im aktiven Plan; dessen verpflichtende
Apply-Gates bleiben bestehen. Vollständige Pack- und PYZ-Abnahme folgt erst in
ihren späteren Umsetzungsschritten. Auch dann ersetzt Paketvalidität weder
fachliche Tests noch Ausführung, Authentizität, Replay- oder Releasefreigabe.
