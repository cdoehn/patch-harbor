# Kanonische Runtimeprofile: PYZ und Legacy-Wheel


## PP-04A: vorbereiteter Core-PYZ-Kandidat

Das neue geschlossene Profil `patchharbor-core-no-watcher-v1` verwendet
`patchharbor/_runtime/pyz-recipe.json`, Marker `patch-harbor-pyz-recipe`,
Rezeptversion 1 und Content-ID-Verfahren `patchharbor-pyz-content-v1`.
`runtime_pyz.py` prüft Daten; es führt keine darin beschriebenen Module aus.

Das sortierte finite Inventar enthält Root-`__main__.py`, Core-Code, Typingmarker,
Chatvorlage, API-Dokumentation, Lizenz und das generierte `_pyz_identity.py`.
`__main__.py` stammt ausschließlich aus der inventarisierten Ressource
`patchharbor/_runtime/pyz-main.py` mit gleichen Bytes. Der Einstieg prüft
Python >=3.12 vor dem ersten Core-Import. Watcher, dist-info, alte generierte
Wheel-Identitäten/-Rezepte, fremde Pakete, Bytecode, Hooks und Runtime-Artefakte
sind ausgeschlossen. Legacy-Wheel-Lesecode bleibt im Core.

Die Ableitung ist endlich: Producer-ID aus versioniertem Inventar ohne eigene
Identitätsdatei; daraus feste Identitätsbytes; vollständiges Inventar samt
Identitätsdatei ergibt Content-ID; erst das fertige ZIP ergibt den Artefakthash.
Kanonisches JSON ist ASCII-kompatibles UTF-8 mit sortierten Schlüsseln, kompakten
Separatoren und genau einem LF. Rezept und Identität hashen sich nicht selbst.

Das ZIP verwendet STORED, v20, reguläre 0644-Dateien, Unix-Erzeuger, feste 1980-Zeit,
lexikografische Reihenfolge sowie leere Flags/Extra-/Kommentarfelder. Vor dem
ZipFile-Inventar wird das tatsächliche begrenzte Zentralverzeichnis durchlaufen;
gefälschte Zähler verbergen keine zusätzlichen Einträge. Lokale Header, Inventar,
CRC/Größen und sämtliche finalen kanonischen Bytes werden geprüft. Grenzen:
16 MiB Artefakt, 32 MiB Inhalte, 1.000 Einträge, 1 MiB Rezept; das übergeordnete
Resultbudget bleibt zusätzlich relevant.

Der normale Build liefert zwei bewusst unabhängige vorbereitete Profile.
Der kanonische Legacy-Wheel-Satz enthält keine erzeugten PYZ-Ressourcen; die PYZ
enthält keine erzeugten Wheel-Ressourcen. Dadurch entstehen weder Hashzyklen
noch rekursiv eingebettete Artefakte. Die Installation trägt beide Datensätze;
der produktive Writer bleibt vorerst Format 2 und bettet allein das Wheel ein.
Build-Helfer werden über einen privaten am Quellpfad verankerten Namensraum geladen,
niemals aus einem zufälligen gleichnamigen Paket in CWD oder Site-Packages.

`scripts/build_release.py --outdir dist` erzeugt Wheel, sdist und den kanonischen
PYZ-Kandidaten. Die bestehende Python-Rückgabe `(wheel, source_distribution)` bleibt
kompatibel. Kandidat und installierte Rezeptmaterialisierung müssen bytegleich sein.
Das ist in PP-04A noch keine Freigabe aller PYZ-Kommandos: ZIP-Ressourcenzugriff,
Python-only-Bootstrap und Result-3-Writer haben nachfolgende Gates.

## Fortgeführter Legacy-Wheel-Vertrag

Die folgende Beschreibung dokumentiert den historischen Wheel-Aufbau. Sein
Datenvertrag bleibt für alte Results erhalten; frühe 1.c-Statusangaben beschreiben
keinen neuen aktiven Plan. Der aktuelle Produktionswriter ist Format 2.

Stand 1.c.C mit nativ bestätigten Abnahmekorrekturen FIX1–FIX3:
interner Provider, Herkunftsprüfung und getrenntes Buildverfahren. Neue Results bleiben Format 1;
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
Die Rezept-Erzeugung und Vorbereitung des Transportinventars liegen nur in
`build_backend.py`; diese Buildfunktionen werden nicht im Runtime-Wheel installiert.
`runtime_wheel.py` besitzt den stdlib-basierten Rezeptvalidator und den reinen
Materializer. `runtime_artifact.py` übernimmt begrenzte Ressourcenreads und den
unveränderlichen Besitz pro Request. CLI, API und Watcher erhalten keine eigenen
Generatoren oder voneinander abweichenden Provider.

Das Backend lädt den gemeinsamen Validator über seinen eigenen absoluten
Quellpfad. Ein fremdes Arbeitsverzeichnis oder gleichnamiges Paket darf ihn
nicht ersetzen. Transportvorbereitung verändert ihr Eingabeinventar nicht;
veraltete erzeugte Ressourcen und Identitätsdaten werden vollständig neu
abgeleitet. Rezept-/Produzenten-JSON und RECORD haben jeweils genau einen
Serializer. Nur die Bytekodierung ist geteilt: Transport- und kanonisches
Inventar sowie deren Pfad-/Profilregeln bleiben verschieden. Andere vorhandene
Hash-/Pfadhelfer mit abweichenden Verträgen werden nicht zusammengezogen.

Git, Installer-Caches und ein ursprüngliches Download-Wheel sind keine
Build-Eingaben. `source_commit` ist deshalb ehrlich `null`.

Der Transport behält die bisherigen `share/patchharbor`-Dokumente. Das kanonische
Wheel enthält ausschließlich Code in `patchharbor`/`patchharbor_watcher`, Typing,
Paketressourcen und die eigene `.dist-info`-Struktur. Der Vorlagenloader bevorzugt
die Ressourcen beim verankerten Produzentencode; alte Installationen behalten
ihren share-Fallback. Reihenfolge: eigene vorbereitete Paketressource,
verankerte Quellvorlage, Legacy-share-Vorlage. Das gilt auch bei einer installierten
Paketwurzel namens `src` mit zufällig daneben liegender Quellvorlage.
Ein defekter vorbereiteter Satz wird nicht durch die
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
wird die fehlende Schreibberechtigung tatsächlich geprüft. Die Korrektur
1.c.R-FIX1 verwendet unter Windows DACLs für die aktuelle Prozessidentität;
Windows-chmod ist kein ACL-Nachweis. Ein Threadtest prüft geteilte und unabhängige Provider,
Bytegleichheit und unveränderte Dateien bei fehlendem oder korruptem Cache.
Der Provider besitzt keine temporären Dateien; entsprechend entfällt deren Cleanup.

Die Rechtefixture liegt ausschließlich in `tests/runtime_permissions.py` und
`tests/fixtures/runtime_readonly.ps1`. Vor der Änderung werden die DACLs aller
Fixturedateien/-verzeichnisse in einem privaten Journal außerhalb der geschützten
Installation gesichert. Explizite Deny-Einträge sperren Schreiben und Löschen;
Lesen, Ausführen und das Wiederherstellen der Rechte bleiben möglich. Echte
Schreib-, Verzeichniserzeugungs-, Umbenennungs- und Löschversuche müssen scheitern.
Der Prüfablauf ersetzt weder Rechtevergabe noch Benutzerverwaltung im Produkt.

Nach Erfolg und Ausnahmen werden die ursprünglichen DACLs zurückgeschrieben
und gegen einen vollständigen nativen Readback geprüft. Bei einem Fehler während der
Wiederherstellung bleibt ausschließlich das private Journal zur Diagnose erhalten.
Unverwandte Dateien, ACLs außerhalb der privaten Fixture, Owner und Audit-Regeln
werden nicht verändert. POSIX root kann Modebits umgehen: ein solcher Lauf
belegt keinen verweigerten Schreibzugriff, und der separate native Rechtetest
wird ausdrücklich übersprungen. Die Root-Roundtrip-Prüfung bleibt ausführbar.

Der erste native [CI-Lauf von 1.c.R-FIX1](https://github.com/cdoehn/patch-harbor/actions/runs/37188040469)
(Versuch 1, HEAD `5535d77fba44acd2232ebf51ca5be0205b0abc3a`) scheiterte unter
Windows und in beiden Docker-Lanes. 1.c.R-FIX2 korrigiert die Testvoraussetzungen:
Der Quellbetriebstest importiert eine saubere Quellkopie in einem neuen Prozess,
auch wenn sein Controller eine installierte Wheel-Runtime verwendet. Während
capture sind Datei-/Cachezugriffe, Prozessstarts und Netzwerk gesperrt.

Die ACL-Kindprozesse erhalten eine Kopie ihrer Umgebung ohne PSModulePath
(Groß-/Kleinschreibung unabhängig). So baut jede Engine ihre eigenen Modulpfade
auf. Die aufrufende Umgebung wird nicht verändert. Das beseitigt den bekannten
[Konflikt beim Start von Windows PowerShell über Python aus PowerShell 7](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_psmodulepath#starting-windows-powershell-from-powershell-7).
Der native Regressionstest gibt bewusst einen ungeeigneten geerbten Modulpfad vor.

Der Teilsetup-Test unterscheidet seine eigene injizierte Ausnahme von nativen
Fehlern. 1.c.R-FIX2 legte die zuvor verdeckten Wiederherstellungsdiagnosen offen.
Der zweite [CI-Lauf 37191971893, Versuch 1](https://github.com/cdoehn/patch-harbor/actions/runs/37191971893)
auf HEAD `31d8d2274facaac2b6590ab39ca9ac83b3ab6357` bestätigt erfolgreiche Linux-,
Docker- und PowerShell-7-Plattformjobs. Windows-Packaging meldet 8 Fehler,
23 bestandene Tests und 1 Skip. Sämtliche 6.302 im vollständigen Joblog enthaltenen
SDDL-Vergleichspaare (einschließlich Wiederholungen) gehören zu vier Formen:
Windows ergänzt `AI`, bei der Probe-Datei ändert sich zusätzlich die Reihenfolge
benachbarter einfacher Allow-Einträge mit gleichen Flags. Es gibt dort keine
gemeldeten Fehler der Set-Acl-Restoreoperation selbst.

1.c.R-FIX3 korrigiert deshalb den bisherigen Textgleichheitsvergleich, nicht die
gespeicherten Rechte. Set-Acl schreibt weiterhin den unveränderten Original-SDDL
jedes Objekts zurück. PowerShell liefert danach alle Pfade und ausgelesenen DACLs
als UTF-8-JSON. `tests/runtime_acl.py` prüft das vollständige Inventar gegen das
private Journal; Exit-Code 0 allein genügt nicht. Doppelte Felder/Pfade, fehlende
oder zusätzliche Objekte und ungültige Berichte scheitern mit erhaltenem Journal.

Der Vergleich lässt ausschließlich Folgendes zu:

- Gleichbleibende Kontrollflags oder ein von Windows ergänztes `AI`; Verlust von
  `AI` sowie jede Änderung von `P` oder `AR` bleiben Fehler.
- Umordnung benachbarter einfacher Allow-ACEs mit exakt gleichen ACE-Flags.
  Masken, SIDs, Flags, Eintragsanzahl und Duplikate müssen vollständig gleich sein.
  Deny-, Objekt-/Callback-ACEs und andere Flaggruppen bilden feste Reihenfolgegrenzen.

Das ist eine konservative Vergleichsregel für private Testfixtures, kein
allgemeiner ACL-Normalisierer. Unbekannte komplexe Darstellungen werden nur bei
exakter Gleichheit akzeptiert. Ein unabhängiges Zugriffsentscheidungsmodell prüft
die erlaubten Umordnungen; Gegenproben ändern Rechte, SIDs, Flags, Einträge und
Allow-/Deny-Reihenfolge. Echte Schreib-/Löschverweigerung, Setup-/Verbraucherfehler,
gleichzeitige Fixtures und beide Windows-Engines bleiben im nativen Testumfang.
Die [automatische Vererbung](https://learn.microsoft.com/en-us/windows/win32/secauthz/automatic-propagation-of-inheritable-aces)
und [Bedeutung der ACE-Reihenfolge](https://learn.microsoft.com/en-us/windows/win32/secauthz/order-of-aces-in-a-dacl)
begründen die begrenzte Ausnahme vom früheren Darstellungsvergleich.

Der manuelle [Acceptance-Lauf 37206108132, Versuch 1](https://github.com/cdoehn/patch-harbor/actions/runs/37206108132)
bestätigt FIX3 auf dem tatsächlichen Apply-Commit
`f4b0920cadac710cd48568fb16d517e9c92fe692` aus Bundle 009. Alle sechs Jobs sind
erfolgreich, einschließlich beider Ubuntu-/Docker-Lanes und Windows.
Windows-Packaging besteht unter Python 3.12 mit 65 bestandenen Tests und genau
einem POSIX-Skip. Die nativen DACL-Fälle beider Engines und der Standardinstallations-
Roundtrip sind damit bestätigt; GATE-RUNTIME ist für diese Basis erfüllt.
1.c.C ist durch Bundle 010 angewendet: Commit
`d31047b2feca049c2db5443bb61df2ce7ce5e7f6`, im Apply abschließend seriell und
parallel je 2.013 bestanden / 7 Skips. Development prüft ausschließlich parallel.
Der folgende Reader-Vertrag steht in [result-format-2.md](result-format-2.md).

Der Launcher aktiviert den Evidenz-Controller auch ohne Berichtdatei. Vor
Exit 0 prüft er `tools.test_results.validate`, alle Worker-/Phasenbelege und die
unveränderte Quellen-/Interpreterbindung. Der erfolgreiche CI-Schritt belegt
diese Prüfung im Windows-Controller. Run- und Jobdaten sowie das vollständige
Windows-Log sind im Exchange gesichert. Artefaktmetadaten einschließlich SHA-256
wurden abgeholt; der separate lokale Download der Artefaktbytes scheiterte an
der Netzsperre. Eine erneute lokale JSON-Prüfung wird deshalb nicht behauptet.

Die nativen Lanes laden `patchharbor-packaging-<runner>` mit
`patchharbor-packaging-tests.json` hoch (14 Tage); fehlende Dateien sind Fehler.
Für CI-Nachweise werden Run-HEAD, Versuch und tatsächliche Windows-/Linux-Jobs
zugeordnet. Ein vollständig abgeholter Bericht wird zusätzlich mit
`tools.test_results.validate` geprüft; seine Bindung muss die native Plattform,
den passenden Interpreter und `expected_workers > 0` bestätigen. Die CI-Prüfung
im Controller bleibt in jedem Lauf Pflicht. Insbesondere müssen folgende Fälle
bestanden sein, nicht übersprungen oder nur gesammelt:

- `test_standard_installation_and_three_offline_canonical_generations`: wheel/source/sdist.
- `test_native_permissions_deny_writes_and_restore`: beide Verbraucherfälle.
- `test_windows_dacl_restore_after_completed_setup_error`: powershell.exe und pwsh.
- Die vorhandenen gleichversionierten Neuinstallations- und Editable-Fälle.

GitHub-CI bleibt ausschließlich `workflow_dispatch`. Nach dem Lauf zu Bundle 009 erst nach
fünf weiteren Bundles wieder regulär CI: 014, 019 usw., nach deren Apply/Push.
Zwischenbundles benötigen keinen eigenen Lauf und bleiben nicht allein wegen
fehlender CI auf ihrem Einzelcommit stehen. Zusätzliche Läufe nur auf ausdrücklichen
Nutzerauftrag; bekannte Fehler weiter auswerten. Der grüne Lauf von Bundle 009
wird nicht als Windows-Ausführung von Bundle 010 ausgegeben. Lokale Gates und
GATE-RUNTIME-Verhaltensanforderungen bleiben verbindlich.
Das fällige Bundle beauftragt seinen Apply-Entrypoint mit Dispatch nach dem
erfolgreichen Push, Warten auf alle Jobs einschließlich Windows und Rückgabe
von Run-ID/URL, vollständigem Commit, Job-Ergebnissen und Testnachweisen bzw.
Fehlerdiagnosen im Result-Ausführungslog. Kein zusätzlicher Trigger oder Retry.

Die Testnamen beziehen sich auf `test_runtime_packaging.py` und
`test_runtime_permissions.py`. Der Quellhash bindet die tatsächlichen Checkout-
Bytes einschließlich Test-/Workflowdateien; eine lokale Development-Bindung mit
ignorierten Rollenregeln ist kein Ersatz für die CI-Bindung. Aus einem grünen
Linux-Result, einem bloßen Upload oder einem früheren Run darf kein Windows-
Gate abgeleitet werden. Es gibt weiterhin keine behauptete Releasefreigabe.

Die Fixture verwendet die dokumentierten
[Windows-Dateirechte](https://learn.microsoft.com/en-us/dotnet/api/system.security.accesscontrol.filesystemrights),
[DACL-Wiederherstellung](https://learn.microsoft.com/en-us/dotnet/api/system.security.accesscontrol.objectsecurity.setsecuritydescriptorsddlform)
und [Set-Acl](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/set-acl).
Die Berichtübergabe verwendet vorhandene
[Workflow-Artefakte](https://docs.github.com/en/actions/tutorials/store-and-share-data).

Normative Grundlagen: [Wheel-Format](https://packaging.python.org/en/latest/specifications/binary-distribution-format/)
und [setuptools-Erweiterungen](https://setuptools.pypa.io/en/latest/userguide/extension.html).
[PEP 517](https://peps.python.org/pep-0517/) beschreibt die Metadatenübergabe
und Build-Caches; [PEP 660](https://peps.python.org/pep-0660/) den getrennten Editable-Weg.
Das kanonische Profil und der Content-ID-Algorithmus sind PatchHarbor-Verträge.
