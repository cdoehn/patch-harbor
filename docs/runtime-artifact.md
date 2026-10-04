# Kanonische Runtime, Rezeptformat 1

Stand 1.c.R: interner Provider, Herkunftsprüfung und Buildverfahren. Neue Results bleiben Format 1;
Reader-/Writer-Integration folgt in 1.d/1.e. `RuntimeProvider().capture()` ist
ein expliziter interner Aufruf, kein neuer CLI-Befehl oder öffentlicher API-Export.
Source-/Editable-Betrieb liefert `unavailable/source_not_prepared`; normale
nicht-editierbare Wheel-, Source- und sdist-Installationen liefern vorbereitete
Ressourcen. Fehlt die Runtime oder funktioniert sie nicht, bleibt der bisherige
Entwicklungs-/Übergabeweg verpflichtend (Spec 40.3).

`build_backend.py` delegiert die PEP-517-Standardaufgaben an setuptools. Beim
Wheel-Build ergänzt er Ressourcen unter `patchharbor/_runtime/`, ohne den
Quellbaum zu verändern. Der Wheel-Build verwendet eine frische private Kopie
der definierten Build-Eingaben; `build/lib`, egg-info, Bytecode und zuvor
generierte Runtime-Ressourcen werden nicht übernommen. Frontend-Metadaten werden
über ihren absoluten Pfad an setuptools weitergegeben. `MANIFEST.in` nimmt den Backend-Code in die sdist auf.
Git, Installer-Caches und ein ursprüngliches Download-Wheel sind keine
Build-Eingaben. `source_commit` ist deshalb ehrlich `null`.

Der Transport behält die bisherigen `share/patchharbor`-Dokumente. Das kanonische
Wheel enthält ausschließlich Code in `patchharbor`/`patchharbor_watcher`, Typing,
Paketressourcen und die eigene `.dist-info`-Struktur. Der Vorlagenloader bevorzugt
die Ressourcen beim verankerten Produzentencode; alte Installationen behalten
ihren share-Fallback. Ein defekter vorbereiteter Satz wird nicht durch die
Vorlage einer anderen Installation ersetzt.

Das geschlossene Rezept enthält `marker=patch-harbor-runtime-recipe`,
`format_version=1`, `distribution=patchharbor`, `version`, `requires_python`,
`content_id_algorithm=patchharbor-runtime-content-v1`, `content_id`,
`source_commit` und `entries`. Jeder sortierte Eintrag besitzt genau `path`,
`source`, `size` und `sha256`. Pfade sind ASCII, relativ und kollisionsfrei;
Typen, Gerätepfade, Traversierung und die erlaubten Namensräume werden geprüft.
Metadatenziele beziehen Bytes aus passiven, ebenfalls inventarisierten Kopien
unter `_runtime/metadata/`; andere Ziele beziehen ihre eigenen Paketdateien.

`content_id` ist SHA-256 der JSON-Fassung ohne das Feld `content_id`:
Schlüssel sortiert, ASCII-Escapes, Separatoren Komma/Doppelpunkt ohne Leerzeichen,
abschließendes LF. Das finale Rezept hat dieselbe Kodierung einschließlich ID.
Code, Watcher, Typing, Vorlage, API-Dokumentation, Lizenz und funktionale
Metadaten gehen über ihre Größe und SHA-256 in diese Identität ein. Rezept und
RECORD stehen außerhalb dieses Hashinventars und sind daraus deterministisch
abgeleitet. Weder das Rezept noch das Wheel enthält seinen eigenen Archivhash
oder ein früheres Wheel. Der Provider liefert den vollständigen Archivhash
separat. Gleiche Versionsnummer bedeutet daher nicht gleichen Inhalt.

Zusätzlich bindet eine beim Wheel-Build erzeugte Datei
`patchharbor/_runtime_identity.py` den geladenen Prozess an seinen Produzenten.
Sie enthält ausschließlich einen Kommentar und das Literal `RESOURCE_ID`.
Der Algorithmus `patchharbor-runtime-producer-v1` hasht dieselbe kanonische
JSON-Kodierung eines Objekts mit `algorithm`, `version`, `requires_python`,
`source_commit` und der sortierten `entries`-Liste; nur der Eintrag dieser
Identitätsdatei wird ausgeschlossen. Danach wird ihr Literal erzeugt und die
Datei in das endgültige Inhaltsinventar aufgenommen. `content_id` umfasst somit
auch diese Datei; der Algorithmus `patchharbor-runtime-content-v1` bleibt gleich.
Beide Ableitungen sind endlich und enthalten keinen Selbsthash.

Der normale Paketimport übernimmt dieses eigene Literal einmalig, ohne Rezept,
Runtime-Provider oder Archiv zu laden. Source/editable enthält diese generierte
Datei nicht. Ein Provider vergleicht den aus dem geprüften Rezept abgeleiteten
Produzenten mit dem geladenen Literal und prüft die exakten Identitätsbytes als
Daten, ohne den beschriebenen Code zu importieren. Bei kohärenter Neuinstallation
derselben Version liefert ein alter Prozess `source_changed`; ein neuer Prozess
übernimmt den neuen Produzenten. Bereits erfasste Antworten bleiben unverändert.
Das erkennt widersprüchliche Herkunft, ist keine Signatur und keine Abwehr
beliebiger Manipulation des laufenden Python-Prozesses.

Archivprofil: ZIP_STORED, kein ZIP64, keine Verzeichniseinträge, Kommentare oder
Extras; ASCII-Namen, Unix-Erzeugersystem, ZIP-Version 20, Modus 100644,
Zeitpunkt 1980-01-01 00:00:00. Lexikalische Reihenfolge, `.dist-info` zuletzt.
RECORD enthält sortierte UTF-8-CSV-Zeilen mit LF, URL-safe Base64-SHA-256 ohne
Padding und dezimaler Größe; seine letzte eigene Zeile hat leeren Hash/Größe.
WHEEL deklarierte Tags: `py3-none-any`, Purelib, Generator
`patchharbor-canonical-v1`. Requires-Python kommt aus gebauten Core-Metadaten.
Dev-Extras bleiben passive Metadaten; unbedingte Runtime-Dependencies und
zusätzliche Entry-Points sind verboten.
Das endliche Requires-Python-Profil erlaubt kommaseparierte Vergleiche
`~=`, `==`, `!=`, `<=`, `>=`, `<`, `>` mit numerischen Versionen und den
unterstützten a/b/rc/post/dev-Suffixen; `.*` nur für numerische `==`/`!=`-Präfixe,
`~=` ab zwei numerischen Komponenten. Kein freier Text oder Epoch-/Local-Suffix.

Grenzen: Rezept 1 MiB, Wheel 16 MiB, maximal 1.000 Einträge und 32 MiB
eingelesene innere Nutzdaten; Vorlage und API-Dokument je 128 KiB. Dateien werden
begrenzt, regulär und mit Vorher-/Nachher-Identität gelesen. Keine `.pth`, nativen
Erweiterungen, fremden Top-Level-Module, pyc oder eingefangenen Launcher.
RECORD und die exakte gespeicherte ZIP-Größe werden vor den Nutzdatenreads
berechnet und vollständig mitbudgetiert. Auch konstruierte Rezeptobjekte müssen
zu ihren validierten Bytes passen. Abweichende Groß-/Kleinschreibung in
Elternverzeichnissen sowie ausgetauschte oder verlinkte Ressourcenverzeichnisse
werden abgewiesen; Verzeichnis-Mtime zählt nicht zur Dateiidentität.
Diese Prüfung belegt Integrität und Profil, keine Absenderauthentizität.

Ein Provider besitzt einen unveränderlichen request-lokalen Antwortwert und
materialisiert höchstens einmal. Die Antwort bindet Wheel und statische Vorlage
aus derselben Aufnahme. Der nächste Request erzeugt einen neuen Provider und
prüft erneut. Es gibt keinen persistenten Cache und keine Installation-/Temp-
Writes; ein leerer oder unbeschreibbarer Cache ist ohne Einfluss. Fehler ergeben
`unavailable` mit `source_not_prepared`, `source_changed`, `resources_missing`, `resources_invalid`
oder `resource_limit`; unerwartete Programmierfehler und Abbruchsignale bleiben
sichtbar. Die spätere Resultschicht behandelt diesen Befund gemäß Spec 39.4.

`tests/test_runtime_packaging.py` installiert über alle drei Wege und danach
über kanonische Wheels in isolierte Umgebungen. Build-/Downloadquellen und
Installer-Caches werden entfernt, Aufrufe laufen außerhalb des Checkouts mit
isoliertem Interpreter. Drei Generationen müssen identische Wheel-Bytes liefern.
1.c.R prüft zusätzlich zwei echte Neuinstallationen gleicher Version im laufenden
Prozess, editierbare Installation, veraltete Build-Ausgaben, API/CLI-Aufrufe und
Roundtrips bei schreibgeschützter Installation. Unter Linux ohne Root-Rechte
wird die fehlende Schreibberechtigung tatsächlich geprüft; Windows-chmod ist
kein ACL-Nachweis. Ein Threadtest prüft geteilte und unabhängige Provider,
Bytegleichheit und unveränderte Dateien bei fehlendem oder korruptem Cache.
Der Provider besitzt keine temporären Dateien; entsprechend entfällt deren Cleanup.

Die lokale Abnahme erfolgt ausschließlich parallel unter Linux/Python 3.14.
Ein echter Windows-Lauf und die native Rechteprüfung stehen noch aus.
GATE-RUNTIME ist deshalb nicht vollständig erfüllt; vor 1.c.C/1.d/1.e ist
dieser Nachweis über die vorhandenen manuell gestarteten Plattform-Lanes nötig.
Die Verschiebung dieses Abnahmenachweises ist im Plan ausdrücklich dokumentiert.

Normative Grundlagen: [Wheel-Format](https://packaging.python.org/en/latest/specifications/binary-distribution-format/)
und [setuptools-Erweiterungen](https://setuptools.pypa.io/en/latest/userguide/extension.html).
[PEP 517](https://peps.python.org/pep-0517/) beschreibt die Metadatenübergabe
und Build-Caches; [PEP 660](https://peps.python.org/pep-0660/) den getrennten Editable-Weg.
Das kanonische Profil und der Content-ID-Algorithmus sind PatchHarbor-Verträge.
