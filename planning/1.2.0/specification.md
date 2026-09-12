# PatchHarbor 1.2.0 – öffentliche Python-Schnittstelle

Basis: sauberer Snapshot `62020dab617d54925c8dd0ac192aaff685cda0f3`.
Dieser additive Vertrag ergänzt `spec/SPECIFICATION.md`. Alle bestehenden
Paket-, SHA-, Fingerprint-, Replay-, Recovery-, Archiv-, CLI- und JSON-Verträge
bleiben erhalten. Die Versionsanhebung erfolgt erst im Release-Schritt.

## API-1: Bibliotheksgrenze

`patchharbor.api` ist der öffentliche Import-Namensraum. Er delegiert fachliche
Operationen ausschließlich an Application; keine zweite Implementierung von
Scans, Registrierung, Paketprüfung, Ausführung oder Result-Erzeugung. Keine
CLI-Subprozesse, kein globales chdir, keine neuen Runtime-Abhängigkeiten.

Konfiguration, Registry, Kontext, manuelle Bundles, Apply, Dry-Run, automatischer
Einzelpoll und fs-run sind erreichbar. Rückgaben und Fehler sind typisiert;
identische Repository- und Run-Werte werden wiederverwendet. Apply liefert den
vollständigen RunReport auch für bekannte Fehler, die übrigen Operationen werfen
für Toolfehler PatchHarborError. Eigene Prozess-Exitcodes bleiben unverfälscht.

Standardmäßig still, explizite Streams und request-lokale Beobachter. Keine
implizite Terminalauswahl oder stdin-Lektüre. Pfade als str/PathLike[str], Timeout
endlich und positiv. Ein discovery-repository ersetzt niemals die Manifest-ID
eines expliziten Pakets. Beobachterfehler dürfen keine Sicherheitsentscheidung
verändern. Result-Rohlogs bleiben auch bei fehlerhaften optionalen Ausgabesenken
vollständig, soweit deren obligatorisches Speichern selbst möglich ist.

Der detaillierte API-Vertrag samt Rückgabefeldern und Einschränkungen steht in
`docs/python-api.md`; API-Tests prüfen fachliches Verhalten und Bibliotheks-I/O,
nicht Farben, Texte, Symbole oder Konsolendarstellung.

## API-2: CLI wird API-Consumer

Alle Haupt-CLI-Kommandos nutzen die öffentliche API. Argumente, JSON-Serializer,
Konsolengestaltung, interaktive Auswahl, fs-run --log und Exit-Code-Mapping
bleiben Adapteraufgaben. Keine direkten Application-Aufrufe mehr aus cli.py.
Die kompakte/verbose Konsole, Punkte frühestens alle 0,8 Sekunden ohne Carriage
Return, vollständige MESSAGE-Blöcke und bisherige JSON-Schemata bleiben erhalten.

## API-3: Watcher

Separater Schritt: öffentliche API für automatische Verarbeitung und geteilte
Konfiguration verwenden. Den heutigen Subprozess-/Signal-/Abbruchvertrag vorher
explizit abgleichen und funktional prüfen. Failed-Retry, Replay, globaler Scope,
Betriebsprotokolle und Linux-Serviceverhalten bleiben erhalten. Keine eigene
Scan- oder Apply-Logik im Watcher.

## API-4: Release

Öffentliche API-Kompatibilität abschließend auditieren, Beispiele/Dokumentation
und Releasespezifikation konsistent abschließen, Version 1.2.0 anheben und alle
Release-Gates prüfen. Keine vorzeitigen Tags oder Veröffentlichungen.
