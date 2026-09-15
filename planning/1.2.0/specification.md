# PatchHarbor 1.2.0 – öffentliche Python-Schnittstelle

Basis: sauberer Snapshot `62020dab617d54925c8dd0ac192aaff685cda0f3`.
Dieser API-Vertrag ergänzt `spec/SPECIFICATION.md`. Paket-, SHA-, Fingerprint-,
Replay-, Recovery- und öffentliche Ergebnis-JSON-Verträge bleiben erhalten.
Die unten beschriebene OFF-PLAN-Konfigurationsrevision ersetzt ausdrücklich den
früheren globalen Konfigurationsvertrag; kein Kompatibilitäts-Fallback.
Version 1.2.0 und der abgeschlossene API-Plan mit 4/4 bleiben unverändert.

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

Der Watcher prüft beim Start `api.repositories()`. Pro Poll bleibt ein eigener
Prozess erhalten; `patchharbor_watcher.worker` ruft `api.apply_next()` direkt
auf und verwendet das bestehende Apply-JSON-Protokoll. Core lädt die lokalen
Konfigurationen aller registrierten Repositorys frisch und fasst physisch
identische Exchange-Verzeichnisse zusammen. Kein cwd-basiertes
`api.configuration()` im Watcher und keine eigene Scan-/Apply-Logik.
Failed-Retry, Replay, globaler Repository-Scope, Betriebsprotokolle und
Linux-Serviceverhalten bleiben erhalten. Signalhandler, Poll-Warteverhalten und
Prozessgruppen werden nicht umgebaut. Gültig unkonfigurierte Instanzen und
fehlende Repository-Pfade werden übersprungen; beschädigte Konfigurationen
vorhandener Repositorys führen zum Poll-Fehler ohne Reparatur.

## API-4: Release

Öffentliche API-Kompatibilität abschließend auditieren, Beispiele/Dokumentation
und Releasespezifikation konsistent abschließen, Version 1.2.0 anheben und alle
Release-Gates prüfen. Keine vorzeitigen Tags oder Veröffentlichungen.

Der öffentliche Import bleibt `from patchharbor import api`; keine parallele
Top-Level-Fassade. Dokumentierte Aufrufe, Ergebnisfelder und Fehlersemantik sind
ab 1.2.0 unterstützt. Private Implementierungsimporte und diagnostische Texte
sind keine Stabilitätszusage. Annotierte Pakete enthalten `py.typed`; Wheel/sdist
führen API-Dokumentation mit. API und Watcher müssen auch nach Installation eines
Wheels außerhalb des Checkouts funktionieren, einschließlich automatischem Apply,
korrektem Rohlog und Result-Bundle. CLI/JSON-Schemata und Python >=3.12 bleiben.

Vor dem Abschluss laufen alle funktionalen, Sicherheits-, Packaging- und
Plattform-Gates. Reine UI-Ausgaben werden nicht neu getestet. Der Planstatus sagt
nur aus, welche Änderungen implementiert sind; lokale Ausführung und CI bestätigen
erst danach den konkreten Release-Commit. Kein automatischer Release-Tag.


## Repositorylokale Konfiguration (OFF-PLAN REPO-CONFIG-1 / REPO-CONFIG-2)

Die technische Umstellung ist im Ausgangscommit `4f64362` enthalten.
REPO-CONFIG-2 schreibt den öffentlichen Vertrag fort und ergänzt abschließende
Verhaltensprüfungen. Beide Aufträge verändern den API-Planzähler nicht.

- Alle Einstellungen gehören in `.patchharbor/config.json`, gebunden durch die
  benachbarte `.patchharbor/id` und die globale Registry. Neues geschlossenes
  lokales Format 1 mit exakt `format_version`, `exchange_directory`,
  `bundle_suffix`, `archive_directory`; Exchange darf nach Erstregistrierung
  `null` sein. Kein Repository-Pfad und keine zweite ID im Config-Dokument.
- Alle CLI-Configure-Aufrufe verwenden das aktuelle registrierte Repository.
  `api.configuration(repository=".", *, revalidate=False)` und die drei Setter
  mit keyword-only `repository="."` erlauben explizite Auswahl ohne `chdir`.
  `ConfigurationResult.exchange_directory` ist `Path | None`.
- Reines Lesen prüft Identität und Schema; `revalidate=True` zusätzlich den
  verfügbaren Exchange und die Pfadpolitik. Setter sperren Registry vor
  Repository, erhalten andere Werte und schreiben atomar. Fehlende/ungültige
  lokale Dateien werden niemals automatisch angelegt oder repariert.
- Nur echte Erstregistrierung erzeugt Defaults. `unregister` erhält lokale
  Daten; erneute Registrierung und Verschieben verwenden sie. Git-Clone startet
  neu. `.patchharbor/` bleibt über den lokalen Git-Exclude ausgeschlossen.
- Austauschordner dürfen geteilt oder getrennt sein. Automatische Auswahl
  akzeptiert ein Paket nur im konfigurierten Exchange seines Manifest-Ziels.
  Expliziter Apply darf anderswo lesen; Result, Suffix und Archivierung verwenden
  dennoch ausschließlich das Zielrepository. Ein explizites Ausgabeziel
  übergeht nur unset/unavailable Exchange, nicht defekte lokale Konfiguration.
- Kein Migrationscode für globale Config-Dateien, keine Übernahme alter Formate,
  kein Fallback. Bestehende ältere Registrierungen werden manuell eingerichtet;
  globale Registry, Locks und Replay-State bleiben technische Benutzerzustände.
- Acceptance prüft echte CLI-/API-/Watcher-Workflows, getrennte/geteilte Ordner,
  Suffix-/Archivbesitz, explizite Ausgabe, Umregistrierung und Fehler ohne
  Reparatur. Keine neuen Text-/Darstellungs- oder Dokumentationstests.

Normativer Gesamtvertrag: `spec/SPECIFICATION.md`, insbesondere 4.3, 13, 16 und
32; Benutzerworkflow und manueller Versionswechsel: README; exakte API-Verwendung:
`docs/python-api.md`. Testergebnisse und externe CI bleiben getrennte Nachweise.
