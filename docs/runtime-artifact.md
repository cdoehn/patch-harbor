# Kanonische Runtime, Rezeptformat 1

Stand 1.c.W: interner Provider und Buildverfahren. Neue Results bleiben Format 1;
Reader-/Writer-Integration folgt in 1.d/1.e. `RuntimeProvider().capture()` ist
ein expliziter interner Aufruf, kein neuer CLI-Befehl oder öffentlicher API-Export.
Source-/Editable-Betrieb liefert `unavailable/source_not_prepared`; normale
nicht-editierbare Wheel-, Source- und sdist-Installationen liefern vorbereitete
Ressourcen. Fehlt die Runtime oder funktioniert sie nicht, bleibt der bisherige
Entwicklungs-/Übergabeweg verpflichtend (Spec 40.3).

`build_backend.py` delegiert die PEP-517-Standardaufgaben an setuptools. Beim
Wheel-Build ergänzt er Ressourcen unter `patchharbor/_runtime/`, ohne den
Quellbaum zu verändern. `MANIFEST.in` nimmt den Backend-Code in die sdist auf.
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

Archivprofil: ZIP_STORED, kein ZIP64, keine Verzeichniseinträge, Kommentare oder
Extras; ASCII-Namen, Unix-Erzeugersystem, ZIP-Version 20, Modus 100644,
Zeitpunkt 1980-01-01 00:00:00. Lexikalische Reihenfolge, `.dist-info` zuletzt.
RECORD enthält sortierte UTF-8-CSV-Zeilen mit LF, URL-safe Base64-SHA-256 ohne
Padding und dezimaler Größe; seine letzte eigene Zeile hat leeren Hash/Größe.
WHEEL deklarierte Tags: `py3-none-any`, Purelib, Generator
`patchharbor-canonical-v1`. Requires-Python kommt aus gebauten Core-Metadaten.
Dev-Extras bleiben passive Metadaten; unbedingte Runtime-Dependencies und
zusätzliche Entry-Points sind verboten.

Grenzen: Rezept 1 MiB, Wheel 16 MiB, maximal 1.000 Einträge und 32 MiB
eingelesene innere Nutzdaten; Vorlage und API-Dokument je 128 KiB. Dateien werden
begrenzt, regulär und mit Vorher-/Nachher-Identität gelesen. Keine `.pth`, nativen
Erweiterungen, fremden Top-Level-Module, pyc oder eingefangenen Launcher.
Diese Prüfung belegt Integrität und Profil, keine Absenderauthentizität.

Ein Provider besitzt einen unveränderlichen request-lokalen Antwortwert und
materialisiert höchstens einmal. Die Antwort bindet Wheel und statische Vorlage
aus derselben Aufnahme. Der nächste Request erzeugt einen neuen Provider und
prüft erneut. Es gibt keinen persistenten Cache und keine Installation-/Temp-
Writes; ein leerer oder unbeschreibbarer Cache ist ohne Einfluss. Fehler ergeben
`unavailable` mit `source_not_prepared`, `resources_missing`, `resources_invalid`
oder `resource_limit`; unerwartete Programmierfehler und Abbruchsignale bleiben
sichtbar. Die spätere Resultschicht behandelt diesen Befund gemäß Spec 39.4.

`tests/test_runtime_packaging.py` installiert über alle drei Wege und danach
über kanonische Wheels in isolierte Umgebungen. Build-/Downloadquellen und
Installer-Caches werden entfernt, Aufrufe laufen außerhalb des Checkouts mit
isoliertem Interpreter. Drei Generationen müssen identische Wheel-Bytes liefern.
Das ist der Linux-Mindestdurchstich von 1.c.W; Windows, weitere Fehler-/Racefälle
und die umfassende GATE-RUNTIME-Abnahme bleiben Teil von 1.c.R/C.

Normative Grundlagen: [Wheel-Format](https://packaging.python.org/en/latest/specifications/binary-distribution-format/)
und [setuptools-Erweiterungen](https://setuptools.pypa.io/en/latest/userguide/extension.html).
Das kanonische Profil und der Content-ID-Algorithmus sind PatchHarbor-Verträge.
