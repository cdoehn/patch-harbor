# Pack-Grundlagen – Implementierungsstand PP-01

Normativ gelten [die Hauptspezifikation](../spec/SPECIFICATION.md) und
[die PYZ/PACK-Erweiterung, Revision 2](../spec/SPECIFICATION_EXTENSION_PYZ_PACK.md)
gemeinsam. Der aktive [Implementierungsplan](../planning/pyz-pack/commit-plan.md)
ordnet diesen vorbereitenden Schritt als PP-01 (2/16) ein.

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
