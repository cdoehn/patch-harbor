# PatchHarbor – Spezifikations-Changelog

## 2026-10-08 – PP-02A bestätigt; Pack-Core/API als Bundle 032

- Bundle 031 mit Commit `d487a84c55857ea0f64914f1cd636e5fc796a3fb`,
  vollem parallelem Apply-Gate und normalem Push bestätigt.
- Planrevision 9 fasst PP-02B/C vor Übergabe zu einem Commit zusammen:
  unveränderte Inhalte, gebundene Manifest-/Handoff-Erzeugung, gemeinsame
  Prüfung der realen ZIP und No-replace-Veröffentlichung über die öffentliche API.
- Fachliche Fehler behalten ihre Kategorien; Cleanup nach Publikation liefert
  vollständigen Erfolg mit Warnung. Die CI bleibt ausschließlich nutzergestartet.
  Beide normativen Spezifikationen, Resultformat 2 und Wheel-Writer bleiben erhalten.

## 2026-10-07 – PP-01 bestätigt; PP-02A / Bundle 031 vorbereitet

- Bundle 030 bestätigt die Fixture-Reparatur, volles paralleles Apply-Gate,
  Commit `e34a81c517d66c079f85cc43033b233f8c9f90a8`, normalen Push und sauberen Baum.
  Der Handoff prüft den tatsächlichen lokalen Testkontext einschließlich lokaler
  ignorierter Anleitungen zusätzlich zur vollständigen Projektinventur.
- Plan Revision 8 und Statushinweise führen den nächsten Schritt PP-02A:
  begrenzter vollständiger Quellscan, unveränderte Bytes, explizite Modi,
  gemeinsame sichere Handles und abschließende Inventur ohne Stabilitäts-Retry.
- Keine öffentliche Pack-Funktion, kein Formatwechsel und keine Änderung an
  den beiden normativen Spezifikationen. Neue Verhaltenstests und Pack-Dokumentation;
  volle parallele Gates, tatsächlicher neuer Apply und native Nachweise getrennt.


## 2026-10-07 – PP-01-FIX3 / Bundle 029: Whitespace-Abbruch und neue Testpolicy

- Result von 028 vollständig geprüft: Exit 1 vor Tests, Commit und Push;
  alle acht Payload-Dateien erhalten, HEAD unverändert, tatsächlicher Fingerprint
  `5b93b0f9950d5100`. Korrektur bindet genau diesen dirty Teilzustand.
- Problematische Leerzeichen im Plan bereinigt; vollständige finale Unterschiede
  vor Auslieferung mit Git lesend geprüft. Git-Fehlerdiagnosen gehen in das Log.
- Spätere ausdrückliche Nutzerentscheidung: Development und Apply ausschließlich
  volle parallele Tests, CI nur vom Nutzer manuell gestartet, Schleife ohne feste
  Korrekturgrenze. Plan Revision 7 und aktuelle Hinweise führen diese Policy.
- Historische Fixture-Reparatur erhalten; Produktquellen und beide Normdateien
  bytegleich. Tatsächlicher Reparaturerfolg bleibt bis zum Watcher-Result offen.

## 2026-10-07 – PP-01-FIX2 / Bundle 028: konsistente Legacy-Fixture auf dem Laptop

- Frisches clean Result bindet den vorhandenen PP-01-Commit
  `e6ed2895c6922c1bf0f8f13ec6af58bb70fd7c3d`; vier E2E-Importfehler auf
  unverändertem Snapshot parallel reproduziert.
- Historische `patch_inspection.py` aus demselben Commit wie die eingefrorenen
  Reader ergänzen, Provenienz hashen und alle historischen Importe im echten
  Kindprozess prüfen. Keine optionalen Produktimports, Skips oder gelockerten
  Exit-/Archivierungsprüfungen; Produktquellen und beide Normdateien unverändert.
- Plan Revision 6 und aktuelle Statushinweise ordnen den ausdrücklich bestätigten
  Laptop-Wechsel ein: Development parallel, Apply-Endstand seriell/parallel vor
  Commit/Push, kein Hook-Bypass. Reguläre nächste CI 029; kein Zusatzlauf für 028.
- Auslieferung nur nach bestandenem vollständigem lokalen Gate; tatsächlicher
  Reparatur-Apply und dessen Nachweise bleiben bis zum neuen Result offen.


## 2026-10-07 – PP-01-FIX1 / Bundle 027: Tests nur in CI während der Pixel-Phase

- Spätere ausdrückliche Nutzerentscheidung: Bis Christian ausdrücklich auf den
  Laptop wechselt, keine lokalen Produkttests oder Testinstallationen auf dem
  Pixel. Die frühere Beschränkung auf PP-00 und die Fünferregel sind während
  dieser Phase ersetzt, nicht nur für das nächste Bundle.
- Das Result `patch-harbor_Result_160403_1007_ee4cb0.zip` belegt den Abbruch von
  026 im seriellen Testlauf (Exit 130), vor neuem Commit/Push/CI. Tatsächlicher
  Fingerprint `44ec92f72a0fd9dd`, HEAD weiterhin
  `7a28bbc2189cdb2a78590e62a45e4d96b0ff893d`. Die PP-01-Dateien sind erhalten.
- Fortsetzungsbundle 027 / PP-01-FIX1 bleibt Position 2/16. Plan Revision 5,
  README, Chat-Anweisungen und Testdokumentation verankern den Vorrang. Kein
  erneutes Ausbringen oder Ändern der PP-01-Core-/Testdateien; beide normativen
  Spezifikationen bleiben bytegleich. Ältere Einträge unten sind Historie.
- Ein fachlicher PP-01-Commit, normaler Push und automatisch einmal vorhandene
  parallele Acceptance-CI. Alle sechs nativen/Docker-Jobs und die zugeordneten
  Nachweise bleiben Pflicht; keine zusätzliche serielle CI-Suite. Derselbe
  Ablauf gilt für folgende änderungsführende Pixel-Bundles, kein Warten auf 029.
- Ausschließlich kommando-lokales Abschalten der Commit-/Push-Hooks verhindert
  indirekte lokale Tests. Keine Änderung an Remote, Registry, persistenter
  Git-Konfiguration, Workflow, CI-Helfer oder Testwerkzeugen. Keine Installation,
  kein Watcher-Neustart und keine neue PYZ-/Pack-Funktion durch diese Reparatur.
- Der Pixel wartet auf die CI und prüft deren Berichte. Keine lokale Ersatzsuite
  und kein Erfolgsmarker bei fehlender/roter CI. Kein automatischer Retry oder
  Rollback; vorhandene Testberichte und Commits bleiben erhalten. Die endgültige
  Abnahme von PP-01 wird erst anhand des tatsächlichen neuen Results bestätigt.

## 2026-10-07 – PP-00 bestätigt, PP-01 / Bundle 026 vorbereitet

- Result `patch-harbor_Result_141601_1007_ef9735.zip` bestätigt PP-00/FIX1:
  Commit `7a28bbc2189cdb2a78590e62a45e4d96b0ff893d`, normaler Push und
  CI-Run `37635401106` mit sechs grünen Jobs. Ältere offene PP-00-Passagen
  unten sind historische Vorbereitung, nicht der aktuelle Abschlussstatus.
- Plan Revision 4: PP-00 abgeschlossen, PP-01 vorbereitet (2/16), keine
  vorweggenommene Ausführung des neuen Codes. Beide Spezifikationen unverändert.
- PP-01 führt intern eine einzige vollständig geprüfte Result-Erfassung mit
  Fakten, Hash, Suffix und unveränderlichem Handoff zusammen. Der bisherige
  Reader-Vertrag bleibt erhalten. Der interne Pack-Anschluss prüft tatsächliche
  Paketbytes mit derselben Bindungs-/Ergebnisfunktion wie die öffentliche API.
- 52 neue funktionale Prüffälle; Sammlung und Syntax geprüft. Elf manuelle
  API-Gegenproben in zwei parallelen Prozessen erfolgreich, aber reguläre
  Development-Vollsuite mangels installierbarer Testabhängigkeiten hier nicht
  gestartet (`REDUCED_TEST_SCOPE`). Keine fingierte Vollsuite-/CI-Freigabe.
- Lokaler Apply führt vor dem einzelnen Commit beide regulären Vollsuite-
  Endgates seriell/parallel aus und prüft die Controller-Äquivalenz. Die einmalige
  Pixel-Ausnahme endet mit PP-00. Kein zusätzlicher CI-Lauf in 026; Termin 029
  bleibt unverändert. Kein Hook-Bypass, Tag, produktives Upgrade oder Watcherstart.
- Keine neue Pack-CLI/API, keine PYZ und kein Resultformat 3 in diesem Schritt.
  Result-Sync/Replace/CIFS-Retry und späteres Pack-No-replace bleiben getrennt.

## 2026-10-07 – PP-00-FIX1 vorbereitet: GitHub-SSH-Alias im Handoff

- Result `patch-harbor_Result_134816_1007_61119e.zip` belegt den Abbruch von
  Bundle 024 vor Staging/Commit/Push/CI. Sechs Dokumente liegen uncommitted vor;
  der Basiscommit ist unverändert. Kein Reset, keine Rücknahme der Dokumente.
- Bundle 025 repariert ausschließlich die Übergabe dieses ersten PP-00-Schritts:
  semantische Repository-/Transportprüfung statt sechs exakter URL-Strings,
  SSH-Hostauflösung über die vorhandene Konfiguration, unveränderte Remotes.
- Fetch- und Pushziel müssen weiterhin eindeutig `cdoehn/patch-harbor` sein.
  Git-Remote-Stand und GitHub-API-Ref werden an denselben vollständigen Commit
  gebunden. Keine Zugangsdaten, URLs mit Tokens oder SSH-Schlüsselpfade im Log.
- Plan Revision 3 hält Ursache, tatsächlichen schmutzigen Ausgangsstand und
  Fortsetzung derselben Pixel-Ausnahme fest. Ein Dokumentationscommit, normaler
  Push, automatische parallele CI über den unveränderten Handoff-Helfer.
  Tatsächlicher Reparatur-Apply, Commit, Push und CI-Erfolg stehen noch aus.
- Hauptspezifikation, Ergänzung Revision 2, Produktcode, CI-Workflow und
  CI-Helfer bleiben bytegleich. Keine Produkt- oder Releasefreigabe.

## 2026-10-07 – PYZ/PACK PP-00: Normsatz und aktiver Plan integriert

- Die unveränderte Ergänzung Revision 2 liegt neben der Hauptspezifikation
  unter `spec/SPECIFICATION_EXTENSION_PYZ_PACK.md`. Beide Dateien gelten für
  den Auftrag gemeinsam; GOV-01/GOV-03/GOV-04 grenzen Vorrang und Ausnahmen ab.
- Neuer aktiver Plan `planning/pyz-pack/commit-plan.md`, Revision 2: neun
  Arbeitspakete, 16 vorgeschlagene Commit-Schritte. PP-00 ist in Bundle 024
  vorbereitet; tatsächlicher Apply, Push und CI-Erfolg werden nicht vorweggenommen.
- Aktuelle Quelle ist `patch-harbor_Result_132210_1007_306573.zip`:
  289 überprüfte Base-Dateien, bytegleich mit der bisherigen Planungsgrundlage;
  keine neue fachliche Implementierung, keine Produktversionsänderung.
- README und Chat-Vorlage verankern den aktiven Plan und gemeinsamen Normsatz,
  ohne abgeschlossene Pläne zu reaktivieren oder offene CIFS-/Windows-Nachweise
  zu schließen. Die Hauptspezifikation selbst bleibt bytegleich.
- Explizite Nutzerentscheidung nur für das erste Feature-Bundle auf dem Pixel:
  keine Produkttests oder Testinstallation im Apply. Ein Commit und normaler
  Push, dann automatisch ein `workflow_dispatch` des bestehenden parallelen
  Acceptance-Workflows; sämtliche sechs Jobs und deren Nachweise bleiben Pflicht.
  Der Entrypoint wartet auf deren Ergebnis. Keine serielle Zusatzsuite, keine
  neuen Trigger, kein Retry und kein Gesamterfolg bei fehlender/roter CI.
  Kommando-lokales Abschalten von Commit-/Push-Hooks verhindert Teststarts
  durch vorhandene Hooks; persistente Git-Einstellungen bleiben unangetastet.
- Außerhalb von PP-00 bleibt die bisherige Test-/CI-Policy erhalten. Runtime
  bleibt im Result ein Wheel / Format 2; PYZ ohne Watcher und `pack` folgen erst
  in den geplanten Implementierungsschritten. Kein Release, Tag, Upgrade oder
  Watcher-Neustart durch PP-00.


## 2026-10-06 – CIFS-1: Eigene temporäre Results vor Verifikation stabilisieren

- Bundle 022 und sein vollständiger grüner CI-Lauf bestätigen den Abschluss
  des Watcher-Plans. Der ausdrücklich beauftragte CIFS-Fix erhält einen eigenen
  Plan und einen zusammengehörigen Commit in Bundle 023.
- Datei und Verzeichnis werden vor der ersten Verifikation und jedem weiteren
  Versuch synchronisiert. Nur ein typisierter `FileChangedDuringRead` darf
  die Prüfung derselben eigenen temporären Datei erneut auslösen.
- Sofortiger Erstversuch; Pausen 2, 3, 5, 10, 20, 20, 30, 30, 60, 60, 60 Sekunden.
  Gemeinsames Budget für vollständige Verifikation und abschließenden Hashread;
  ausdrücklich längere Linux-CIFS-Caches verlängern es begrenzt.
- Geöffnete Handles müssen zur reservierten regulären Datei gehören. Symlinks,
  fremde Dateien und Integritätsfehler bleiben terminal. Der finale Hash muss
  zum tatsächlich vollständig geprüften ZIP passen. Apply wird nie wiederholt.
- Sichere Metadaten, Versuche und Synchronisationsstatus stehen bei erschöpfter
  Verifikation zusätzlich in `verification.json` der Notfalldiagnose.
  Result-/Run-Schemaversionen und Wheel-Fallback bleiben erhalten.
- Tatsächlicher Apply und Prüfung auf echter Windows-CIFS-Freigabe stehen für
  den Fix aus. Keine zusätzliche CI in 023; nächster regulärer Termin ist 024.

## 2026-10-06 – WE-4: Native Windows-Umbenennungssperre berücksichtigt

- Bundle 021 ist tatsächlich angewendet; die anschließende manuelle CI bestätigt
  alle Windows-E2E-Fälle einschließlich der vorherigen drei Fehler.
- Ein Plattformtest scheitert vor seiner Ereignisprüfung: Windows verweigert
  das Umbenennen eines Vorfahren mit geöffnetem Unterordner.
- Bundle 022 berücksichtigt diesen eng begrenzten Sperrfall und verlangt
  unveränderte Identitäten, weiter funktionierende Ereigniserkennung und einen
  erfolgreichen Rename nach der Handle-Freigabe. Kein zusätzlicher Skip.
- Betriebsdokumentation und Plan sind abgeglichen. Produktiver Watcher-Code,
  Core-Grenzen und Testgates bleiben erhalten. Tatsächlicher Apply sowie native
  Windows-Plattform-/Packaging-Abnahme von 022 sind offen; reguläre CI bleibt 024.

## 2026-10-06 – WE-4: Windows-Abschlussbehandlung korrigiert

- Bundle 020 ist tatsächlich angewendet; die folgende manuelle CI bestätigt die
  Testsetup-Korrektur, meldet aber drei Windows-Watcher-Integrationsfehler.
- Bundle 021 verarbeitet ausstehende Abbruch- und Abschlussmeldungen über den
  Completion Port, bevor Puffer und Handles freigegeben werden. Ein gleichzeitig
  schließender Reader verliert keinen bereits empfangenen Abschluss.
- Zusätzliche Abbruchrennen und begrenzte native Kindprozesse prüfen die
  Freigabe. Der Download-Test erzeugt beobachtbare Schreibereignisse und prüft
  die volle anschließende Ruhefrist. Bei Hängern bleibt die erste Ausnahme sichtbar.
- Verzögerte Windows-Dateicache-Meldungen und atomare Bundle-Bereitstellung sind
  dokumentiert. Apply-/Integritätsprüfungen und ereignisloser Leerlauf bleiben.
- Tatsächlicher Apply und native Windows-Abnahme von 021 stehen aus. Keine
  zusätzliche CI; nächste reguläre CI bleibt 024.

## 2026-10-06 – WE-4: Windows-Testsetup korrigiert, Abschluss offen

- Alle fünf Plancommits sind angewendet und gepusht; die lokalen Abschlussgates
  von Bundle 019 bestanden. Die anschließende CI ist fehlgeschlagen.
- Der pytest-Node-ID der übergroßen Worker-Anfrage überschritt unter Windows die
  Grenze für `PYTEST_CURRENT_TEST`. Eine kurze explizite Kennung erhält denselben
  Prüfwert und dieselbe Ablehnung vor dem Core-Aufruf.
- Bundle 020 bereitet einen Korrekturcommit vor. Die fehlenden Windows- und
  Docker-Nachweise sind im Plan offen vermerkt; nächste reguläre CI bleibt 024.

## 2026-10-05 – WE-4: Integration und Abschlussprüfung vorbereitet

- WE-3 separat nach vollständiger paralleler Prüfung festgehalten; WE-4 ist der
  tatsächliche zweite Dateizustand von Bundle 019, kein rückwirkliches Phasenlabel.
- Reale Ereignissteuerung während Apply, mehrere Bundles, fehlgeschlagene
  Identität ohne Retry, unabhängiger Download und Signalstop im Leerlauf geprüft.
- Installierter Wheel führt außerhalb des Checkouts eine native Fünfsekunden-
  Warteoperation mit anschließendem tatsächlichem Worker-Apply aus.
- CI-Rückgabe umfasst die Watcher-Nachweise einschließlich Windows; Abschluss
  bleibt bis zur Auswertung des tatsächlichen Apply-/CI-Result offen.

## 2026-10-05 – WE-3: Ereignissteuerung und begrenzte Worker-Scope

- WE-2 durch tatsächliches Bundle-018-Result bestätigt (3/5 Planschritte).
- Fünf Sekunden monotone Ruhe je Exchange, einmalige Startprüfung, keine
  periodische Discovery im Leerlauf; Ereigniserfassung während eines Workers.
- Versionierter privater Scope-/Fortschrittsvertrag, Generationserhalt und
  technische Sperrbereitschaft mit Backoff bis 300 Sekunden.
- Gefilterte Konfigurationsereignisse und Beobachtung der Wiederkehr fehlender
  Wurzeln über unverbindliche Core-Pfade; sämtliche Apply-Prüfungen bleiben aktiv.
- CLI-Pollintervall entfernt. Bundle 019 führt nach dem einzigen Push die fällige
  CI einschließlich Windows aus; tatsächliches Apply und native Abnahme offen.

## 2026-10-05 – WE-2: Native Ereignisadapter vorbereitet

- WE-1 durch tatsächliches Bundle-017-Result bestätigt (2/5 Planschritte).
- Getrennte inotify-/ReadDirectoryChangesW-Adapter, flache und gefilterte
  Vorfahrenbeobachtung, kontrolliertes Aufwecken/Schließen ohne neue Abhängigkeiten.
- Strukturierte Hinweise für Änderungen, Root-Verlust und Queue-Überlauf;
  begrenzte Ereignismengen und explizite Backend-Fehler ohne Polling-Fallback.
- Deterministische Decoder-/Ressourcenprüfungen sowie echte native Ereignistests.
  Lokale Linux-Nachweise ersetzen keine Windows-CI; diese bleibt bis 019 offen.
- Bundle 018 bereitet WE-2 vor. Die CLI-Aktivierung und Ruhefrist folgen in WE-3;
  keine Versionsänderung oder zusätzliche CI durch diesen Zwischenstand.

## 2026-10-05 – WE-1: Core-Grenzen für den Ereignis-Watcher vorbereitet

- WE-0 durch tatsächliches Bundle-016-Result bestätigt (1/5 Planschritte).
- Öffentliche Abfragen für geprüfte physische Exchange-Wurzeln und Kontrollpfade;
  keine Bundle-Scans bei Beobachtungsabfrage oder technischer Sperrprüfung.
- Optional eingeschränkte automatische Discovery: leere/fremde/veraltete Scopes
  erweitern die Auswahl nicht; andere Exchanges bleiben von Scans und Wartung frei.
- Strukturierte Zustände für leere Auswahl, verbrauchten Versuch, Sperrkonflikt,
  Dry-Run und Fehler. Root-Identität wird auch vor Mutationsbeginn erneut geprüft.
- WE-1 für Bundle 017 vorbereitet; Apply offen. Watcher-Aktivierung folgt in WE-3,
  native Abschlussnachweise bleiben offen. Keine zusätzliche CI vor Bundle 019.

## 2026-10-05 – WE-0: Planungsbootstrap für Exchange-Ereignisse

- Neuer aktiver Plan `planning/watcher-events/commit-plan.md` mit eigenständiger
  Spezifikation; fünf Commitschritte einschließlich des Dokumentationsbootstraps.
- Ziel: flache native Ereignisüberwachung, pro Exchange fünf Sekunden Ruhe nach
  letzter relevanter Änderung, kein periodischer Scan/Worker im Leerlauf.
- Startbestand, laufende Applies, mehrere Exchanges/Bundles, Konfigurationswechsel,
  Sperrwiederaufnahme, Ereignisverlust und Plattformgrenzen sind ausdrücklich geregelt.
- RIV-Abschluss anhand Bundle 015 samt sechs erfolgreichen CI-Jobs bestätigt.
  Diese historischen Nachweise bestätigen noch keine neue Watcher-Funktion.
- Bundle 016 übernimmt ausschließlich Planung. Bestehender Watcher, Produktversion
  und installierte Engine bleiben im bisherigen Zustand. Keine CI-Anforderung;
  nächste reguläre CI bleibt 019, vorgesehen auf dem vollständigen neuen Endstand.

## 2026-10-05 – RIV 1.f.C: gemeinsamer Handoff und Abschlussabgleich

- R mit 2.224 bestandenen Tests / 7 Skips parallel eingefroren; C behält Sammlung
  und Ergebnisse. Reale Apply-Gates und CI-Nachweise entstehen erst später.
- Ein gemeinsamer Testskript-Helfer transportiert native Python-Fixtures durch
  Bash/PowerShell; doppelte Quote-Logik in Self-update und Commitfolgen entfällt.
- Gemeinsame Bindungsprojektion und Quellenidentität ersetzen Bootstrap-Duplikate.
- Planstatus bereits angewendeter Schritte, API-/Format-/Bootstrap-Dokumentation
  und Abdeckungsnachweise sind abgeglichen. 18/18 vorbereitet, 15/18 angewendet.
- Bundle 014 liefert drei echte Zustände. Der Entrypoint prüft W/R parallel,
  C seriell und danach parallel, erzeugt drei Commits und pusht genau einmal;
  anschließend fällige CI einschließlich Windows mit zugeordneten Result-Logs.
- Bei bestätigtem finalem Apply und CI endet der Plan ohne weiteres Bundle.
  Keine neue Version, kein Tag und kein vorweggenommener Release.

## 2026-10-05 – RIV 1.f.R: Fehlergrenzen und fällige CI

- W mit 2.174 bestandenen Tests / 7 Skips vollständig parallel eingefroren.
- Fehlende Werkzeuge, inkompatible Python-Konjunktionen, Hashwechsel,
  Schattenmodule und technische Nutzungsfehler sind vom fachlichen Ablehnen getrennt.
  Geänderte finale Patch-/Referenzbytes erhalten keinen alten Erfolgsnachweis.
- Reale Gatefehler bewahren Teilcommits und den nicht committeden Dateistand;
  ohne erfolgreiche Gesamtfolge gibt es keinen Push.
- Bestehende CI-Lanes liefern maschinenlesbare Gatebelege; Ubuntu 26.04 nutzt
  Python 3.14 und einen repräsentativen uv-Pfad, Grundmatrix bleibt Python 3.12.
- Projektbezogener Helfer dispatcht die fällige CI einmal, nach finalem Push,
  bindet volle SHA/Handoff-ID und liefert Windows-/Job-/Testnachweise im Apply-Log.
  Kein Core-Scheduler, keine automatische CI-Wiederholung und keine neuen Trigger.
- 17/18 vorbereitet, 15/18 angewendet; finaler Apply und CI weiterhin ausstehend.

## 2026-10-05 – RIV 1.f.W: geprüfter Bootstrap und bisherige Übergabe

- Bundle 013 mit drei echten Commits, lokalen Gates und finalem Push bestätigt;
  15/18 angewendet, 16/18 im Dateistand vorbereitet. Keine vorweggenommene CI-Freigabe.
- Kanonische Chat-Vorlage enthält Herkunfts-/Profilprüfung vor Wheel-Code,
  explizite Offlineinstallation und verpflichtenden bisherigen Übergabeweg bei Ausfall.
- Reviewed Repository-Helfer nutzt vorhandene vertrauenswürdige Parser;
  Runtime-only-Defekte bleiben getrennt von ungültigen Repositorydaten und
  werden nie als erfolgreiche native Vollvalidierung ausgegeben.
- Reale isolierte Bootstrap- und Null-/Ein-/Mehrcommit-Applies ergänzen die
  blockierenden Packaging-/E2E-Gates. Die Vorlagengröße richtet sich am bestehenden
  Handoff-Bytebudget aus, nicht an einer zusätzlichen Prosa-Längenvorgabe.
- Bundle 014 schließt nach den echten R/C-Zuständen mit fälliger CI einschließlich
  Windows. Deren tatsächliche Ergebnisse bleiben bis zum Apply offen.

## 2026-10-05 – RIV 1.e.C: gemeinsame Publikationsdaten

- R vollständig parallel geprüft: 2.165 bestanden / 7 Skips; vor C eingefroren.
- Ein typisierter interner Dokumentensatz verbindet Report, Handoff, Manifest,
  Kontext und Runtime. Manueller und Apply-Pfad publizieren ihn über denselben Helfer.
- Die Budgetentscheidung besitzt genau einen vorbereitenden Fallback ohne
  Publikationswiederholung; doppelte Argumentübergaben entfallen.
- Die Result-Roundtrip-Fixture führt jede Generation ohne redundante Fallunterscheidung aus.
- 15/18 vorbereitet, 12/18 durch Apply bestätigt. C muss dieselbe vollständige
  Testsammlung mit gleichen Ergebnissen bestehen. Apply: W/R parallel, C seriell
  und danach parallel, drei Commits, ein abschließender Push; CI erst wieder 014.

## 2026-10-05 – RIV 1.e.R: Self-update, Result-Roundtrip und Fehlerdiagnose

- W vollständig parallel geprüft: 2.145 bestanden / 7 Skips; Dateistand vor R eingefroren.
- Notfallberichte behalten nach erfolgreicher Snapshotaufnahme den neuen geprüften
  Kontext, wenn die spätere Publikation scheitert.
- Reale isolierte Self-updates prüfen alte Runtime/Vorlage zusammen mit neuem
  Repository-Commit, auch bei fehlgeschlagenem Entrypoint nach dem Commit.
- Alle drei Installationswege erzeugen drei echte Result-Generationen und verwenden
  jeweils das daraus entnommene Wheel; Python-Allokation und ZIP-Mehrbedarf werden gemessen.
- Dirty/Untracked und explizite Ziele bleiben vollständig; Schreib-, Verifikations-
  und Publikationsfehler werden nicht in Runtime-Erfolge umgedeutet.
- 14/18 vorbereitet, 12/18 durch Apply bestätigt; eigener vollständiger R-Gate erforderlich.

## 2026-10-05 – RIV 1.e.W: gemeinsame Runtime-Einbettung

- Bundle 012 tatsächlich angewendet: zwölf Planschritte und GATE-READERS bestätigt.
  Der nachfolgende Watcher-Diagnoselauf enthält null Commits und denselben sauberen Stand.
- Manueller Bundle-, Apply-, Dry-Run- und Watcher-Pfad verwenden Format 2.
  Runtime und statische Chat-Vorlage werden vor Apply-Mutationen zusammen fixiert.
- Runtime-only-Ausfall und Zusatzbudgetüberschreitung erzeugen eine begründete
  Warnung und `unavailable`; Snapshot, Logs und ursprüngliches Primärergebnis bleiben.
- Fehlende bisherige Pflichtdateien bleiben echte Result-Fehler. Prüfung der
  tatsächlichen ZIP-Inhalte erfolgt vor atomarer Veröffentlichung über den Reader.
- 13/18 vorbereitet; Freigabe nur nach vollständiger paralleler W-Prüfung.
  R/C folgen als echte getrennte Zustände.
  Development nur parallel, CI weiter im Fünf-Bundle-Takt, nächste reguläre 014.

## 2026-10-04 – RIV 1.d.C: gemeinsamer Leservertrag ohne doppelten Vollread

- R vollständig parallel bestanden: 2.132 Tests / 7 Skips. Erst nach dessen
  eingefrorenem Dateistand folgt C als zweiter echter Schritt in Bundle 012.
- Gemeinsame Marker-/JSON-Prüfung für Result-Klassifikation und Pfadprofilwahl;
  keine parallelen ad-hoc Parser derselben Result-Daten.
- Der gemeinsame Reader liefert geprüfte Handoff-Fakten. Veröffentlichung nutzt
  seine vollständige CRC-/Inventarprüfung und prüft nur eigene Pflichten zusätzlich.
- CRC-Regression beschädigt tatsächliche Archivbytes; Sicherheitsnachweis bleibt
  unabhängig von der Wahl eines internen Lesehelfers.
- Vorhandenen Marker-Test von Quelltextfundstelle auf tatsächliche Erkennung
  umgestellt; keine neue Darstellungs- oder Prosaprüfung.
- 12/18 vorbereitet, 10/18 durch Apply bestätigt. R parallel vor Commit 1,
  C seriell und parallel vor Commit 2, genau ein abschließender Push.
  Development nur parallel; Writer 1, Paketversion und CI-Takt unverändert.

## 2026-10-04 – RIV 1.d.R: begrenzte Verzeichnisse und Altleser-Nachweis

- Bundle 011 tatsächlich angewendet als
  `164987080b64d364feac477afa6a7b541ec8d852`: abschließend seriell und parallel
  je 2.103 bestanden / 7 Skips, ein normaler Push, sauberer Baum.
- R als 11/18 vorbereitet; zehn Schritte durch Apply bestätigt. Bundle 012 plant
  R und C als getrennte echte Dateistände, eigene Tests und zwei Apply-Commits.
- Inneres zentrales ZIP-Verzeichnis vor ZipInfo-Allokation begrenzt und geprüft;
  gefälschte Zähler, Pfadlängen, Zusatzdaten und Grenzen scheitern früh.
- Rekursionstiefe im Result-Marker beendet die Exchange-Erkennung kontrolliert.
- Unveränderte historische Lesermodule mit Herkunft/Hashes eingefroren.
  Echte gemischte Exchanges belegen konservatives Behalten neuer Results und
  fortgesetzte Format-1-Archivierung; Wheels werden nicht als Patch ausgewählt.
- Writer bleibt Format 1. Lokale Tests ausschließlich parallel; Apply vor R
  parallel, am endgültigen C-Stand seriell und parallel vor letztem Commit/Push.
  Keine zusätzliche CI oder Releasefreigabe; nächste reguläre CI Bundle 014.

## 2026-10-04 – RIV 1.d.W: Format-2-Leser vor Writer-Aktivierung

- Bundle 010 tatsächlich angewendet als
  `d31047b2feca049c2db5443bb61df2ce7ce5e7f6`: abschließend seriell und parallel
  je 2.013 bestanden / 7 Skips, ein normaler Push, sauberer Baum.
- `1.d.W` als 10/18 vorbereitet, 9 Feature-Schritte durch Apply bestätigt.
  Gemeinsamer Reader für Result 1/2; produktive Writer bleiben bei Format 1.
- Geschlossenes Runtime-Schema in `docs/result-format-2.md`, vollständige
  Deskriptor-/Hash-/Inventarprüfung, kanonisches inneres Wheel und gemeinsames
  Bytebudget. Keine Installation, Extraktion oder Ausführung von Wheel-Code.
- Referenzprüfung, Veröffentlichungsprüfung und Archiv-/Recovery-Fakten nutzen
  denselben Reader. Diagnosegültigkeit bleibt von Erfolgsevidence getrennt.
  Results mit Unicode-Repositorypfaden bleiben lesbar; Patchpfade bleiben streng.
- Regressionen für embedded/unavailable, Dirty/Fehler/Dry-Run, korrupte Metadaten
  und Archive, Limits, öffentliche API/CLI sowie tatsächliche Recovery.
- Bestehende Reader-Lücke für kategorisierte Werkzeugfehler geschlossen:
  Zustandskonflikte bleiben gültige Diagnosen, auch wenn das abgelehnte Paket
  ein anderes Git-Objektformat erwartete. Maßgeblich bleibt der tatsächliche Kontext.
- Ergänzte Nutzerregel: fälliges Bundle dispatcht nach Apply/Push die vorhandene
  CI einschließlich Windows und wartet; Run-/Commit-/Job-/Testnachweise kommen
  im Result zurück. Unverändert Basis 009, nächste 014/019; keine Extra-CI für 011.
- Development nur parallel; Apply-Endstand seriell und danach parallel vor
  einem Commit und einem normalen Push. Null-/Mehrcommit-Bundles und sicherer
  bisheriger Übergabeweg bei Wheel-Ausfall bleiben erhalten. Keine Releasefreigabe.


## 2026-10-04 – RIV 1.c.C: Build-/Runtime-Trennung und CI-Takt

- Bundle 009 tatsächlich angewendet als
  `f4b0920cadac710cd48568fb16d517e9c92fe692`, abschließend seriell und parallel
  je 2.008 bestanden / 7 Skips, ein normaler Push, sauberer Baum.
- Manueller Acceptance-Lauf 37206108132, Versuch 1 auf genau diesem HEAD:
  alle sechs Jobs erfolgreich, Windows-Packaging 65 bestanden / 1 POSIX-Skip.
  GATE-RUNTIME bestätigt; vollständiges Joblog und Metadaten gesichert.
  Maschinenbericht im CI-Controller geprüft; separater lokaler Artefakt-Download
  netzbedingt nicht möglich, keine behauptete lokale JSON-Nachprüfung.
- `1.c.C` als 9/18 vorbereitet; 8 Feature-Schritte durch Apply bestätigt.
  Build-Rezept und Transportvorbereitung ins Backend begrenzt, Materializer
  und unveränderlicher request-lokaler Provider bleiben installiert nutzbar.
- Gemeinsame Rezeptkodierung und RECORD-Serialisierung bei getrennten Inventaren;
  vorbereitete eigene Vorlage vor Source-/share-Fallback, auch unter `src`.
- Funktionale Regressionen für unveränderte Eingabeinventare, veraltete Ressourcen,
  Generatorherkunft und Vorlagenbesitz. Keine neuen Darstellungs-/Prosatests.
- Nutzerregel vom 4. Oktober: CI ausschließlich manuell alle fünf weiteren
  Bundles, nach Basis 009 nächste 014 und 019. Zwischencommits benötigen keinen
  eigenen CI-Lauf. Bekannte Fehler auswerten; Zusatzläufe nur auf Nutzerauftrag.
- Development nur parallel; Apply-Endstand seriell, danach parallel, ein Commit
  und ein normaler Push. Null-/Mehrcommit-Bundles bleiben erlaubt. Wheel-Ausfall
  verwendet weiterhin den bisherigen sicheren Übergabeweg. Kein Format-2-Writer,
  keine Versionserhöhung und keine neue Releasefreigabe.

## 2026-10-04 – RIV 1.c.R-FIX3: Windows-DACL-Readback

- Bundle 008 durch echten Apply auf `31d8d2274facaac2b6590ab39ca9ac83b3ab6357`
  bestätigt; abschließend seriell und parallel je 1.974 bestanden / 7 Skips,
  genau ein Push, sauberer Baum. Feature-Zähler bleibt 8/18.
- Manueller CI-Lauf 37191971893, Versuch 1: fünf Jobs erfolgreich; Windows-
  Packaging 8 Fehler / 23 bestanden / 1 Skip. Fehlerdiagnosen zeigen ergänztes
  `AI` und umgeordnete benachbarte gleichartige Allow-ACEs nach Set-Acl.
- Original-DACLs weiter zurückschreiben; vollständigen UTF-8-JSON-Readback gegen
  das Journal prüfen. Ausschließlich Hinzufügen von `AI` und Umordnung unmittelbar
  benachbarter einfacher Allow-ACEs mit identischen Flags akzeptieren.
- Rechte, SIDs, übrige Kontroll-/ACE-Flags, Anzahl und Duplikate bleiben exakt;
  Deny-/Objekt-/Callback-ACEs und Flaggruppen bilden feste Reihenfolgegrenzen.
  Ungültige Berichte und echte Unterschiede scheitern mit erhaltenem Journal.
- Regressionen mit den vier echten CI-SDDL-Paaren, unabhängigen Zugriffsentscheidungen
  und fehlerhaften Readbacks. Keine Text-/Layouttests und keine Produkt-ACL-Änderung.
- Development nur parallel; Apply am einzigen Endstand vollständig seriell und
  danach parallel vor einem Commit und einem Push. Native Windows-Abnahme bleibt
  offen (REDUCED_TEST_SCOPE); kein automatischer CI-Start und kein vorgezogener C-Schritt.

## 2026-10-04 – RIV 1.c.R-FIX2: CI-Testvoraussetzungen und Fehlerdiagnose

**FIX:** unverändert 8/18. FIX1 angewendet als
`5535d77fba44acd2232ebf51ca5be0205b0abc3a`; der erste manuelle Acceptance-Lauf
37188040469 (Versuch 1) scheiterte in Windows-Packaging und beiden Docker-Jobs.

- Quellbetrieb aus einer echten isolierten Quellkopie prüfen, auch bei installiertem
  Wheel im Testcontroller; keine Änderung am produktiven Runtime-Provider.
- Geerbten PSModulePath nur für ACL-Kindprozesse entfernen, sodass deren Engine
  passende Module lädt; keine globale Umgebungs-/Registryänderung.
- Erwarteten injizierten Fehler von echten Setup-/Wiederherstellungsfehlern trennen;
  Originalfehler und genaue DACL-Abweichungen im nächsten CI-Lauf sichtbar machen.
- Strikte Rechteprüfung und privates Wiederherstellungsjournal erhalten.
- Die zusätzliche pwsh-Wiederherstellungsursache bleibt offen. Linux-Abnahme und
  installierte Wheel-Regression ersetzen den neuen Windows-/Docker-Lauf nicht.
- Ein geplanter Apply-Commit, lokale Tests nur parallel; finales Apply seriell
  und danach parallel vor Commit/Push. Keine Versionsanhebung, kein CI-Start.


## 2026-10-04 – RIV 1.c.R-FIX1: native Rechteabnahme und CI-Nachweise

**FIX:** Planposition bleibt 8/18; 1.c.R ist über Result
`patchharbor-apply_Result_064126_1004_5de6a7.zip` angewendet/gepusht,
Commit `5e27c78d190a642d60eac55f767bc69dc086ac48`.

- Windows-Rechtefixture verwendet native DACLs statt chmod als Ersatznachweis.
- Tatsächliche Datei-/Verzeichnis-Schreib-, Umbenennungs- und Löschversuche müssen
  verweigert werden; Lesen und installierte Offline-Materialisierung funktionieren.
- Gespeicherte DACLs nach Erfolg, Teilsetup-/Verbraucherfehlern wiederherstellen;
  bei fehlgeschlagener Wiederherstellung das private Journal erhalten.
- Neue Verhaltenstests für Rechte, Isolation, Pfadgrenzen und Cleanup;
  native Windows-Pfade unter Linux ausdrücklich nicht als ausgeführt zählen.
- Manueller CI-Workflow veröffentlicht Packaging-JSON je nativer Lane.
- Kein neuer Planpunkt, keine Laufzeit-/Resultformatänderung und kein CI-Start.
  GATE-RUNTIME bleibt bis zur echten Windows-Abnahme offen; danach erst 1.c.C.

## 2026-10-03 – RIV 1.c.R: Herkunft, Ressourcenbudgets und parallele Provider

**Dateistand:** 1.c.R; 8/18 vorbereitet, sieben Feature-Schritte durch echte
Apply-Results bestätigt. Neue Basis: `616d232c7ac1dc37c602e3e33a750ae09599a9b5`
aus `patchharbor-apply_Result_194435_1003_3dbbba.zip`.

- Geladene Produzentenidentität erkennt kohärente Neuinstallation gleicher Version;
  bestehende Antwort bindet weiterhin unveränderlich Artefakt und statische Vorlage.
- Endliche zusätzliche ID ohne Selbsthash, endgültiger Inhaltsalgorithmus unverändert.
- Vollständige Archiv-/RECORD-Budgets vor Reads, portables Pfadprofil und
  Ressourcenverzeichnisse geprüft; Fehler/Abbruch bleiben eindeutig.
- Frisch gestagter Wheel-Build verhindert Übernahme veralteter Build-Ausgaben.
- Verhaltenstests für Parallelität, Rechte, Cache-Unabhängigkeit, drei Generationen,
  echte gleichversionierte Reinstallation, Source/sdist und verändertes Editable.
- Bundle 006 plant einen Apply-Commit; Development prüft nur parallel, Apply
  abschließend seriell und parallel vor Commit und einzigem Push.
- REDUCED_TEST_SCOPE / PLAN_SPEC_MINOR_DEVIATION: Windows- und nativer Rechtebeleg
  aus dem R-Vorcommit-Gate verschoben; weiterhin vor 1.c.C/GATE-RUNTIME erforderlich.
  Keine Releasefreigabe, kein Tag/CI-Start, Result-Format 1 und Version 1.2.1 bleiben.

## 2026-10-03 – RIV 1.c.W: vorbereitete kanonische Wheel-Runtime

**Dateistand:** 1.c.W; 7/18 vorbereitet, 1.a/1.b durch tatsächliche Apply-Results
bestätigt. Neue Apply-Basis: `c04ed7ad7907ad20c8a2c05fabc7cfe50bd76094` aus
`patchharbor-apply_Result_171842_1003_c2008e.zip`. Neuer Commit erst im Apply.

- PEP-517-Backend ergänzt vorbereitete Paketressourcen auch für Source/sdist.
- Interner Provider prüft Inventar, Profil, Grenzen und Inhalts-SHA, erzeugt
  zyklusfreie kanonische ZIP_STORED-Bytes und bindet die statische Vorlage.
- Paketressourcen bevorzugt; Legacy-share-Fallback für bisherige Installationen.
- Funktionale Installationstests mit entfernten Quellen/Caches und drei
  bytegleichen kanonischen Generationen; keine Prosa-/Darstellungstests.
- Neue Nutzer-Testregel dauerhaft in Plan, Spec und Testdokumentation:
  Development nur parallel; Apply-Zwischenstände parallel; allein am Bundle-Ende
  seriell und parallel vor letztem Commit und einzigem Push.
- Ein Commit in Bundle 005; 1.c.R/C und GATE-RUNTIME-Gesamtfreigabe folgen.
  Result-Format bleibt 1, Paketversion 1.2.1. Kein Tag oder CI-Start.

## 2026-10-03 – RIV 1.b: explizite Referenz- und Repositorybindung

**Dateistand:** 1.b.W, 1.b.R, 1.b.C; 6/18 vorbereitet.
**Apply-Basis:** `67215b1a425d7bff8c685934e60104d7b86f1323` aus `patchharbor-apply_Result_145837_1003_112aa3.zip`.
Bundle 003 mit drei Commits, sechs Vollsuiten und finalem Push bestätigt.
Neue Commit-SHAs und Apply-Erfolg stehen erst im nächsten Result.

- `validate_patch` und CLI prüfen wahlweise eine Result-Referenz oder ein registriertes Repository.
- Format-1-Leser prüft Inventar, Blob-/Dateihashes, Metadaten und tatsächlichen Kontext;
  konsistente Dirty-, Fehler- und Dry-Run-Results bleiben gültige Referenzen.
- Paket-/Referenzmodus ohne Git und Registry; Repositorymodus mit bestehenden Locks/lesenden Git-Abfragen.
- Referenzpfade sind fremde Metadaten, keine lokale Zielwahl. UTF-8-Snapshotpfade bleiben unterstützt.
- Fehlende Legacy-Delta-/Loghashes, Live-Zustand und Authentizität werden nicht als geprüft behauptet.
- Eingabe-, Race-, Lock- und Integritätsfehler sowie unveränderter fachlicher Zustand funktional abgesichert.
- Allgemeine Resultintegrität und strengere Archiv-/Recovery-Policy verwenden gemeinsame geprüfte Fakten.
- Results bleiben Format 1; Runtime/Wheel-Fallback und Format 2 folgen separat.

## 2026-10-03 – RIV 1.a: eigenständige lesende Paketprüfung

**Dateistand:** 1.a.W, 1.a.R, 1.a.C; 3/18 vorbereitet. Basis des nächsten Apply:
`289fa32b8a295c91e456abe0f61c2ae232966719` aus `patchharbor-apply_Result_122057_1003_77a6b0.zip`.
P0 ist über dessen tatsächliche Tests, Commit und Push bestätigt. Neue Apply-Commits
stehen erst im späteren Result; keine erfundene eigene SHA oder CI-Freigabe.

- Öffentliche `inspect_patch`-/`validate_patch`-API und CLI-Kommandos für package-Scope.
- Unveränderliche Paketfakten, vollständige SHA/Größe, Rollen, Modi und MESSAGE-Daten
  aus derselben stabil gelesenen ZIP; gemeinsame bestehende Sicherheitsprüfer.
- JSON-Ausgabe 2 nur für die neuen Kommandos; bestehende Ausgabeversion 1 bleibt.
- Kein Git/Registry-/Apply-/Result-/Runtime-Lebenszyklus im Paketmodus.
- Funktionale Tests für API/CLI, Fehlercodes, Nebenwirkungen und Datenverträge.
- P1 in Paketprüfung (P1a) und spätere Bindungsprüfung (P1b) getrennt.
- Fehlerprioritäten, Dateiaustausch, Observerisolation und fehlerhafte Archiv-/JSON-Eingaben abgesichert.
- Gemeinsame statische Entrypointprüfung von Apply und Inspect konsolidiert; Ausgabeprojektion getrennt.
- Runtime, Wheel-Fallback-Ausführung und Format 2 bleiben spätere Schritte;
  kein Versionswechsel, Tag oder automatischer CI-Start.

## 2026-10-03 – RIV-DOCS-1: Spezifikation und aktiven Entwicklungsplan integrieren

**Status:** Dokumentationsvorbereitung; RIV-Featurefortschritt 0/18.
Paketversion bleibt 1.2.1; keine Feature-, Runtime-, Apply- oder Releasefreigabe
durch diesen Eintrag. Tatsächliche Apply-Commits und Tests belegt das Result.

- Exchange-Revision 2 auf dem aktuellen sauberen Result-Stand
  `68dba9216b72dc0b6441df83f49c9047b8b038b9` integriert. Vollständige Bindung,
  Result-SHA und ursprüngliche Dokumenthashes stehen im neuen Plan.
- `spec/SPECIFICATION.md` bleibt die einzige normative Gesamtspezifikation.
  Bestehende Kapitel 33/34 bleiben erhalten; RIV belegt 35–41. Geplante
  API-/CLI-Prüfungen, Runtime und Result-Format 2 sind als unimplementiert markiert.
- Aktiver Plan: `planning/runtime-inspect-validate/commit-plan.md`; sechs
  echte W/R/C-Gruppen, zunächst 18 Schritte in vier flexiblen Feature-Paketen.
  Diese Dokumentübernahme ist P0 / OFF-PLAN außerhalb der 18 Schritte.
- Verpflichtender bisheriger Entwicklungs-/Übergabeweg bei fehlendem oder
  nicht funktionsfähigem Wheel. Ausfallgrund und Prüfumfang sichtbar; keine
  erfundene native Prüfung. Runtime-only-Defekt und ungültige Repositorybasis
  bleiben unterscheidbar. Der Fallback ersetzt nicht die Runtime-Featureabnahme.
- Bundles unterstützen null, einen oder mehrere Commits. Diagnosebundles
  sammeln beauftragte Ergebnisse über Result/Logs ohne Commit, Push, Tag oder
  Implementierungsfortschritt. Mehrere echte Commitzustände sind normal erlaubt.
- Repositorylokale Konfiguration, generische 1.2.1-Chatregeln und POSIX-Vertrag
  erhalten. Überholte Test-/CI-Aussagen der Hauptspezifikation an CI-MANUAL-1
  angeglichen: vor jedem Apply-Commit Vollsuite parallel, danach seriell;
  Acceptance-CI ausschließlich manuell. Keine neuen Prosa-/Darstellungstests.
- Development bereitet geprüfte Zustände und genau eine Patch-ZIP vor.
  Ausschließlich der Apply-Entrypoint committet und pusht nach vollständigem
  Erfolg einmal normal auf den bestätigten Branch; Diagnosebundles pushen nicht.
  Keine automatische Versionsanhebung, kein Tag und kein automatischer CI-Start.

## [1.2.1] – 2026-10-02

**Status:** Entwicklungs-Chat-Vertrag bereinigt und Release 1.2.1 vorbereitet.

- Generische Chat-Instructions leiten Tests aus Zielprojekt und Nutzerauftrag ab;
  PatchHarbor Core definiert keine fachliche Teststrategie.
- Ein Bundle darf standardmäßig einen oder mehrere fachlich geschlossene Commits
  enthalten; W/R/C ist nur bei ausdrücklicher Projekt-/Auftragsvorgabe Pflicht.
- Zwischenstände werden real nacheinander hergestellt, geprüft und committed;
  Teilerfolg bleibt sichtbar und erzeugt keine Gesamt-Erfolgsmeldung.
- Paketformat, State-Bindung, Sicherheitsprüfungen, Bundle-Nummer und genau eine
  kanonische ZIP bleiben unverändert.
- Paket- und Vertragsversion werden auf 1.2.1 angehoben; Release-Tag `v1.2.1`.

## 2026-09-21 – HANDOFF-NR: nummerierter Abschlussblock

- Erfolgreiche Patch-Antworten wiederholen den grünen Statusbalken unten; der Patch-Link ist die letzte Antwortzeile.
- Repositorybezogene dreistellige Bundle-Nummern sind bewusst Best Effort ohne neue Infrastruktur oder Sicherheitsbindung.
- Dieselbe kanonische ZIP behält ihre Nummer bei erneutem Link/Backup/Versand; STOP vergibt keine Nummer.
- Der Entrypoint meldet dieselbe Nummer nur nach vollständigem Erfolg und sauberem Zielzustand.
- Warning-/STOP-Abschluss und bestehende Drive-/Gmail-Sicherungsregeln bleiben verbindlich.
- Drei W/R/C-Vertragscommits; kein neues Paketformat, keine Runtime-Abhängigkeit und keine Migration.

## 2026-09-18 – POSIX-MODE: Bestandsrechte erhalten, Paketmodi strikt prüfen

- Bestehende normale rwx-Rechte erhalten, einschließlich 0664/0666/0777; Sonderbits ablehnen.
- ZIP/API-Modi zusätzlich ohne Gruppen-/Andere-Schreibrechte; Modus vor Ersetzung setzen.
- Korrektur des vor Commit abgebrochenen 0664-Bootstraps; keine automatische Rechteänderung.
- Private Core-Zustandsdateien und native Windows-Rechtepolitik getrennt halten.
- Fehler-/Dry-Run-/Apply-Regressionen und verbindliche Core-vor-Entrypoint-Regel.
- Drei echte W/R/C-Commits; keine Versionsanhebung oder Migration.
- Lokale Vollsuite künftig parallel, serielle Referenz in CI; Ausnahme für dieses Bundle.

## 2026-09-16 – TEST-PARALLEL: pytest-xdist als Entwicklungsstandard

- Gemeinsamer pytest-Launcher für lokal, CI und Docker, standardmäßig xdist auto;
  explizite Workerzahlen und vollständige serielle Referenz bleiben erhalten.
- Controller-eigene Nachweise mit Inputbindung, Sammlungs-/Phasenprüfung und
  Worker-Abschlussbelegen; neutrales Modell getrennt vom pytest-Adapter.
- Vollvergleich 0/2/4/auto und zusätzlicher Hash-Seeds, einschließlich sichtbarer
  Skips und Fehlernachweisen für verlorene Ergebnisse und abgestürzte Worker.
- Bestehende Plattformmatrix unverändert; zusätzliche blockierende serielle CI.
- Keine Runtime-Abhängigkeit, kein Produktscheduler, keine neuen Darstellungs-
  oder Dokumentationstests und keine künstlichen Test-/Suitefristen.
- 15 echte W/R/C-Zustände gemäß Aufgabenplan. Keine Versionsanhebung oder
  automatische Veröffentlichung; erfolgreicher Apply und externe CI sind
  weiterhin anhand der tatsächlich entstandenen Ergebnisse nachzuweisen.


**Dateiname:** `SPECIFICATION_CHANGELOG.md`<br>
**Stand:** 2026-10-02

Dieses Dokument protokolliert Änderungen am verbindlichen Produktziel. Es ist kein Git-Commit-Log und ersetzt nicht die getrennten Umsetzungspläne unter `planning/`.

---

## [1.2.0 / repositorylokale Konfiguration] – 2026-09-15

**Status:** Bewusste OFF-PLAN-Vertragsänderung; technische Basis `4f64362`
(REPO-CONFIG-1), Dokumentations-/Acceptance-Fortschreibung REPO-CONFIG-2.
Version 1.2.0 und abgeschlossener API-Plan bleiben bei 4/4. Keine Release- oder
CI-Freigabe allein durch diese Dokumentation.

- Sämtliche Repository-Einstellungen ausschließlich in `.patchharbor/config.json`
  neben `.patchharbor/id`; lokaler Git-Exclude statt versionierter `.gitignore`.
- Neues geschlossenes lokales Format 1 mit vier Pflichtfeldern und erlaubtem
  `exchange_directory: null` nach echter Erstregistrierung. Kein globaler
  Konfigurationspfad, keine Übernahme alter Format-1/2/3-Dokumente.
- Configure bindet an das aktuelle registrierte Repository, einschließlich
  Unterverzeichnissen; API erlaubt ausdrückliche Auswahl per `repository`.
  Normales Lesen prüft Schema/Identität, explizite Revalidierung auch den Exchange.
- Keine Migration und keine automatische Reparatur. Bestehende Instanzen richten
  die lokale Datei von Hand ein. Registry, lokale ID, Exclude und Replay bleiben
  erhalten; kein Reset, kein Löschen von Locks oder Replay-Belegen.
- Getrennte und geteilte Exchange-Pfade sind erlaubt. Core scannt jeden physischen
  Ordner pro Poll einmal; Pakete müssen für automatische Auswahl im Exchange
  ihres Zielrepositorys liegen. Suffix/Archivregeln bleiben unabhängig.
- Watcher-Startup prüft Registry statt globaler Config, Worker lädt lokale Werte
  pro Poll frisch. Unset Exchange und fehlende Repository-Pfade werden übersprungen;
  beschädigte Config lebender Repositorys führt zum Fehler vor Ausführung.
- `unregister` erhält lokale Daten; erneute Anmeldung und echter Umzug nutzen sie.
  Git-Clone übernimmt keine ignorierten Metadaten und braucht Register/Configure.
- Explizites Ausgabeziel übergeht nur unset/unavailable Exchange, nie fehlende
  oder beschädigte Config. Result-/Chat-Begleitdaten gehören zum Zielrepository.
- Frühere globale Konfigurationsaussagen bleiben nur als Changelog-Historie;
  die Produktspezifikation verweist auf den aktuell verbindlichen lokalen Vertrag.
- Spezifikation, README, API-Vertrag, Planungsspezifikation und Chat-Vorlage sind
  abgeglichen. Abschließende Tests prüfen reale CLI-/API-/Watcher-/Archivabläufe;
  alte README-/Help-Wortlautprüfungen werden durch Verhaltenstests ersetzt.
- Paketmarker, Fingerprint, Replay-Format, Ergebnis-JSON, Produkt-Timeout,
  Prozess-/Signalsicherheit und externe Backup-Verantwortung bleiben erhalten.

Die folgenden Einträge dokumentieren historische Stände. Globale Konfiguration
und ältere Config-Formate darin sind kein aktuell unterstützter Fallback.

## [1.2.0] – 2026-09-13

**Status:** API-1 bis API-4 implementiert; Release-Freigabe des konkreten Commits
erfordert vollständige lokale Prüfungen und grüne externe CI.

- Unterstützte synchrone Python-API unter `patchharbor.api`: Konfiguration,
  Registry, Kontext, Bundles, Apply/Dry-Run, automatischer Poll und Skriptrunner.
- Haupt-CLI und Watcher verwenden dieselbe API. Der Watcher behält einen separaten
  Prozess pro Poll; keine neue Signal-, Retry- oder Prozessgruppenlogik.
- Standardmäßig stille Bibliothek, explizite Streams und neutrale Beobachter,
  vollständige IDs sowie unveränderte Result-, Fehler- und Wire-Semantik.
- API-Vertrags- und installierte Wheel-/Worker-Tests, mitgelieferte Dokumentation
  und `py.typed`; weiterhin keine Runtime-Abhängigkeiten und Python >=3.12.
- Version und Chat-Vertrag auf 1.2.0. Paketformat, SHA-/Fingerprint-, Replay-,
  Recovery-, Archiv- und CLI-Verträge bleiben kompatibel. Kein automatischer Tag.

### Abschließender Chat-Auslieferungsvertrag (OFF-PLAN) – 2026-09-13

- Genau eine finale Auslieferung mit einer kanonischen ZIP und nur einer grünen
  Bereitschaftszeile; die bisherige doppelte Kopf-/Fußzeile entfällt.
- Erst nach Paketvalidierung Dateiname, Größe und vollständige SHA-256 festlegen;
  Chat-Link sowie, soweit verfügbar, private byteidentische Drive- und
  Gmail-Sicherung. Anhängegrenzen führen zum bestätigten Drive-Link statt
  zu einer anderen Paketfassung. Keine erfundenen Links oder Erfolgsnachweise.
- Backup- und Versandfehler sind nicht blockierend; unbestätigte Vorgänge zuerst
  prüfen, nicht doppelt ausliefern. Generierte Bundle-Anleitungen übernehmen
  den Vertrag aus derselben kanonischen Vorlage.
- Nur Dokumentation und Dokumentprüfungen ändern sich. Core, API, Paketformat,
  Version 1.2.0 und Plan-Zähler bleiben unverändert; kein automatischer Tag.

## [1.1.1] – 2026-08-28

**Status:** Freigegeben und vollständig umgesetzt; der abgeschlossene Plan liegt unter `planning/1.1.1/commit-plan.md`.

### Post-release farbige Streaming-Konsole – 2026-09-11

- Feste Dashboard-Flächen und Refresh-Schleife entfallen zugunsten fortlaufender farbiger Meldungen ohne Kürzung der Textinhalte. Kurze technische IDs bleiben bestehen.
- Ausführliche Beobachtung bereits bei Exchange-Einträgen und Inhaltsklassifizierung; auch Ablehnungs-, Recovery- und Archivierungsgründe sowie Dateischreib- und Result-Schritte werden sichtbar. Keine zusätzlichen Dateioperationen oder veränderten Sicherheitsentscheidungen für die Anzeige.
- Vollständige MESSAGE-Blöcke vor dem Skript und unmittelbare Weitergabe verfügbarer Prozess-Chunks. Kein Warten auf einen Zeilenumbruch durch PatchHarbor.
- JSON und bytegenaue Ausführungslogs bleiben unverändert. Zusätzliche interne Meldungen sind Konsolenausgabe, kein neuer Result-ZIP-Eintrag. Bei Pipes/plain bleiben Skriptdaten und menschliche Diagnostik getrennt.
- Keine automatisierten Tests der Konsolendarstellung; bestehende betroffene Anzeigeprüfungen werden entfernt. Funktionale Sicherheits-, Parser-, Prozess-, Log- und Maschinenverträge bleiben geprüft.
- Acceptance-Matrix erhält 120 Minuten Job-Timeout. Separate PowerShell-/Docker-Grenzen und fachliche Prozess-Timeouts bleiben unverändert. Lokaler vollständiger Testlauf ohne künstliche Test-/Suite-Frist.

### Post-release SHA-gebundene Attempt-Recovery – 2026-09-11

- Vollständige Paket-SHA aus den tatsächlich validierten ZIP-Bytes; neue Apply-Resultate korrelieren `patch_sha256`, Run-ID, ursprüngliche vollständige Bindung und optionalen verifizierten Abschlusscommit. Keine Änderung von `patch.json`, Fingerprint oder Benennung.
- Bestehender Replay-State Format 4 ergänzt Attempt-Run-ID und vor Result-Veröffentlichung lokal gepinnte Result-SHA. Formate 1–3 bleiben strikt lesbar, ohne nachträglich erfundene Belege. Konfiguration bleibt Format 3.
- Result-Veröffentlichung vor terminalem Replay-Abschluss; ein Fehler beim letzten State-Schreiben überschreibt den Erfolgsbeleg nicht. Abbruch vor Veröffentlichung bleibt ohne Reparatur.
- Recovery vor Archivierung unter echtem Repository-Lock, mit vollständiger ZIP-/Snapshot-/Git-Prüfung, Scope-Erhalt, frischer Revalidierung und Compare-and-swap. Kein Erfolg bei aktivem Lock, Dirty-Zustand, fehlenden oder widersprüchlichen Beweisen. Kein automatisches Reset/Rollback und keine Screen-/PID-Heuristik.
- Pending-Result-Belege werden nicht vorzeitig archiviert. Recovery funktioniert auch ohne Archivierung; Dry-Run bleibt unverändert. Altfälle ohne lokal verankerte Beweise werden nicht rückwirkend als Erfolg ausgegeben.
- Regressionen mit echten Prozessabbrüchen vor/nach Commit und Veröffentlichung, frischen Folgeläufen, aktiven Locks, Manipulation, Migrations- und Revalidierungsrennen. 10.800-Sekunden-Timeout, CWD-/Watcher-/Retry-Semantik und Sicherheitsgrenzen bleiben erhalten.

### Post-release Windows-Zeilenumbruchkorrektur – 2026-09-10

- Der Loader der installierten Chat-Vorlage und der Renderer für explizite Vorlagen verwenden dieselbe zentrale CRLF-/CR-zu-LF-Normalisierung. Neu generierte Patch-/Result-Anleitungen erhalten damit kanonische LF-Zeilenenden auch unter Windows.
- Die Normalisierung betrifft ausschließlich Vorlagentext im Speicher. Quelldateien, Repository-Snapshots, empfangene Nutzdateien und exakte JSON-Feldwerte bleiben unverändert. UTF-8-, BOM- und Rohbyte-Größenprüfungen werden nicht gelockert.
- Plattformunabhängige Byte-Fixtures reproduzieren Windows-CRLF bereits unter Linux. Regressionen sichern LF, CRLF, CR, gemischte Endungen, Leerzeilen, Unicode, fehlenden Abschlussumbruch, installierte und explizite Vorlagen sowie die unveränderten Repository-Bytes im tatsächlichen Result Bundle.
- Kein weiterer Replay-/Crash-Recovery-Fix, keine Änderung an Archivierung, Sicherheitsbindungen, Paketformat oder Drei-Stunden-Standardtimeout.

### Post-release nachweisbasierte Exchange-Archivierung – 2026-09-09

- Korrektur des noch nicht erfolgreich angewendeten Archivierungs-Patches: gemeinsame funktionale CLI-Testhelfer ohne pauschalen 20-Sekunden-Subprozess-Timeout; ausdrücklich angeforderte Timeout-/Prozesstests bleiben erhalten.
- Validierte Kandidaten teilen je Repository und Scan genau eine anfängliche konsistente Zustandserfassung. Doppelte Vorab-Revalidierung entfällt; jeder tatsächliche Move erhält nach dem letzten Datei-Hash weiterhin eine frische vollständige State-/Git-/Registry-/Konfigurations-/Replay-Prüfung. Aktuelle Resultate und fehlende Abschlussbelege werden ohne Historienabfrage behalten.
- Zusätzliche Regressionen zählen Zustandsabfragen statt Laufzeiten und simulieren Änderungen nach dem Datei-Hash; keine veraltete Freigabe wird gecacht und kein fachlicher Drei-Stunden-Timeout geändert.

- `configure archive-dir NAME` verwendet die bestehende Konfiguration; Standard `PatchHarbor-Archive`, leerer Wert/`--clear` deaktiviert. Direkter Exchange-Unterordner, führender Punkt erlaubt, keine Windows-Hidden-Logik.
- Konfiguration Format 3 erhält Exchange-Pfad und Suffix; Formate 1/2 werden ohne Schreibzugriff mit sicherem Standard gelesen.
- Der bestehende Replay-State Format 3 speichert nach erfolgreichem Vorwärts-Commit optional `completed_commit`; alte attempted/succeeded-Daten erhalten keine erfundenen Commit-Belege.
- Nur exakt gebundene erfolgreiche Patches mit Abschlussbeleg und validierte saubere Result-Snapshots echter Git-Vorfahren werden archiviert. Fehlende/unklare Beweise, fremde oder beschädigte Dateien, Dirty-/Fehler-Bundles und unvollständige/ersetzte Historien bleiben liegen.
- Manueller Repository-Scope, explizite Paketauswahl und globaler Watcher bleiben getrennt; Dry-Run archiviert nichts. Alter/Dateiname beeinflussen die Entbehrlichkeit nicht.
- Gepinnte Verzeichnisse, wiederholte Hash-/State-Prüfung und No-Replace-Rename verhindern Zielumleitung und Überschreiben; Kollisionen erhalten eindeutige Namen, fehlgeschlagene Moves behalten die Quelle. Kein Löschen, keine rekursive Archivsuche.
- Regressionen decken Migration, Konfiguration, echte Git-Nachweise, Replay/Retry, Repository-Trennung, manipulierte Bundles, Symlinks, Kollisionen und Fehlerpfade ab. Paketformat, Fingerprint, Bundle-Benennung und 10.800-Sekunden-Timeout bleiben unverändert.

### Post-release selbstbeschreibende Bundle-Übergabe – 2026-09-08

- Jede Result-Bundle-Erzeugung rendert frisch die installierte statische Chat-Vorlage plus konkrete lokale Daten; `CHAT_INSTRUCTIONS.md` und `environment.json` werden atomar mitveröffentlicht, ohne Zusatzbefehl oder Sidecar.
- Repository-Pfad, konfigurierter Exchange-Pfad, tatsächliches Ausgabeziel, Suffix, Namensschema und vollständige Bindungswerte sind konsistent; Pfade bleiben reine Hilfen für lokale Befehle und niemals Sicherheitsbindung.
- Allowlist für Distribution, Kernel, Architektur, Python, uv, konfigurierte Shell und PatchHarbor-Version; fehlende optionale Daten sind `null`, uv-Probe begrenzt. Keine Netzwerkabfragen, Hostnamen, IPs oder Umgebungsdumps.
- Die statische Vorlage bleibt fachliche Quelle und wird bei installiertem Betrieb aus dem versionierten Datenartefakt geladen. Keine Zielrepository-Datei überschreibt den Vertrag, keine zurückgelieferten Instructions werden ausgeführt.
- Externe Patch-Pakete enthalten ein optionales, strikt geprüftes `PATCHHARBOR_META`-Paar, getrennt von Nutzdateien/Entrypoint; bestehende Pakete und `patch.json` bleiben kompatibel. Bootstrap-Regel für den ersten älteren Runner dokumentiert.
- Regressionen decken alle Result-Pfade, frische Konfiguration, Fremdrepository/Watcher, fehlende Systemdaten, Metadaten-Isolation, Paketierung, unveränderte Bindung und atomare Fehlerbehandlung ab.

### Post-release konfigurierbares Bundle-Suffix – 2026-09-08

- `configure bundle-suffix SUFFIX` und `configure bundle-suffix --clear` ergänzen die bestehende Configure-CLI; `configure show` zeigt den Wert.
- Die Konfiguration verwendet das geschlossene Format 2 mit `exchange_directory`, `format_version` und `bundle_suffix`. Format 1 bleibt ohne Suffix lesbar; erst ein expliziter Schreibvorgang migriert atomar. Beide Konfigurationsbefehle erhalten jeweils die andere Einstellung und nutzen denselben globalen Lock.
- Das Suffix wird nach `.zip` an alle neu erzeugten Result-Bundle-Namen angehängt, auch bei Fehler, Dry-Run, Watcher und explizitem Ausgabeziel. Der leere String erhält das bisherige Namensschema.
- Result-`context.json` trägt den bei der Ausgabe verwendeten Wert als optionale, nicht zustandsbindende Metadaten für die Patch-Dateinamen externer Chats. Alte Bundles ohne Feld gelten als suffixlos; `patch.json` und das geschlossene `context --json`-Schema bleiben unverändert.
- Ein zentraler reiner Helfer validiert portable Suffixe und fügt sie an. Temporäre Download-Endungen werden nicht als fertiges Suffix zugelassen. Ziel und Suffix werden vor Veröffentlichung revalidiert.
- Inhaltsbasierte Erkennung akzeptiert alte und suffigierte ZIPs weiterhin ohne Umbenennen. CWD-Bindung, Replay-/Retry-Regeln, Watcher-Schutz, `mtime_ns`, vollständige Kennungen, Fingerprint und 10.800-Sekunden-Timeout bleiben unverändert.
- README, CLI-Hilfe, Chat-Vertrag und Spezifikation dokumentieren Einrichtung, Abschalten, Migration und die Grenzen reiner Dateiumbenennung. Regressionen umfassen Konfiguration, atomare Persistenz, Suffix-Erkennung, automatische Resultate, manuellen Retry, Watcher und Änderungen während der Ausgabe.

### Post-release repository-scoped manual Apply – 2026-08-31

- Ein manueller parameterloser `patchharbor apply` löst zuerst das registrierte Repository des aktuellen Arbeitsverzeichnisses auf; Aufrufe aus Unterverzeichnissen werden der Repository-Wurzel zugeordnet.
- Pakete anderer registrierter Repositorys sind für diesen manuellen Aufruf keine Kandidaten. Ist das aktuelle Repository nicht eindeutig registriert, endet der Auftrag ohne globalen Fallback.
- Ein explizites `patchharbor apply PATCH_ZIP` bleibt eine bewusste paketgesteuerte Auswahl und darf weiterhin das über `repo_id` bestimmte andere registrierte Repository verwenden.
- Der Watcher bleibt mit seinem internen automatischen Ursprung repositoryübergreifend und verwendet weiterhin den Schutz gegen die sofortige Wiederholung fehlgeschlagener Pakete.
- Unter den nach Repository-, State- und Replay-Prüfung verbleibenden Kandidaten gewinnt der höchste `mtime_ns`; bei identischem Zeitstempel entscheidet der Unicode-NFC-normalisierte und anschließend der unveränderte Dateiname deterministisch.
- Ein neuerer fremder, state-inkompatibler oder replaygeschützter Kandidat blockiert keinen älteren zulässigen Kandidaten.
- Paketformat, Fingerprint-Algorithmus, Drei-Stunden-Standardtimeout und das bereits veröffentlichte Bundle-Namensschema bleiben unverändert.

### Post-release complete-identifier guidance – 2026-08-30

- Die Kurzansichten von `register`, `context` und `registry list` werden ausdrücklich als reine Präsentation dokumentiert und dürfen nicht als Chat- oder Maschineninput beziehungsweise für `patch.json` verwendet werden.
- Der Kontext-Hinweis nennt jetzt den tatsächlich unterstützten Befehl `patchharbor context --json`; `register` besitzt weiterhin bewusst keine `--json`-Option.
- README und CLI-Hilfe verweisen für vollständige Registry-UUIDs auf `patchharbor registry list --json` und stellen klar, dass gekürzte Präfixe keine gültigen `unregister`-Selektoren sind.
- Der normale Chat-Workflow verwendet weiterhin `CHAT_INSTRUCTIONS.md` und das aktuelle Result Bundle, dessen `context.json` alle Bindungswerte vollständig enthält.
- JSON-Schema, persistierte Identitäten und sämtliche Sicherheitsvergleiche bleiben unverändert.

### Post-release replay and presentation update – 2026-08-30

- Der persistente Replay-State unterscheidet `attempted`, `failed` und `succeeded`; erfolgreiche Pakete bleiben gesperrt, während ein bewusster manueller parameterloser Apply einen weiterhin exakt gebundenen fehlgeschlagenen Patch erneut versuchen darf.
- Der Watcher kennzeichnet seinen Core-Aufruf intern als automatisch und wiederholt eine fehlgeschlagene unveränderte Paketidentität bei späteren Polls nicht erneut.
- Bei mehreren vollständig passenden Kandidaten gewinnt erst nach allen Sicherheits- und State-Prüfungen der eindeutige höchste `mtime_ns`; ein exakter Höchstwert-Tie wird fail-safe abgelehnt.
- Patch- und Result-Dateinamen folgen `<Repository>_Patch_<HHMMSS>_<MMDD>_<ID6>.zip` beziehungsweise `<Repository>_Result_<HHMMSS>_<MMDD>_<ID6>.zip`; Uhrzeit ist UTC, das Jahr entfällt und ID6 enthält kein Auslassungszeichen.
- Menschenlesbare Terminalausgaben kürzen lange technische Kennungen zentral auf sechs Zeichen plus `…`; JSON, Manifeste, Logs, Persistenz und Sicherheitsvergleiche behalten vollständige Werte.
- Ein öffentlicher `--retry-failed`-Schalter wird nicht eingeführt, weil der normale manuelle parameterlose Apply bereits die bewusste Retry-Aktion ist.

### Post-release fix – 2026-08-29

- `2.b.R-FIX1` hält die automatische Exchange-Erkennung auf gemeinsamem Android-/Termux-Speicher funktionsfähig, wenn Pfad- und Deskriptoransicht keine vergleichbare Inode-Identität liefern.
- Der Fallback bleibt auf Exchange-Dateien begrenzt und verlangt weiterhin übereinstimmenden Dateityp, Größe und Änderungszeit sowie den vollständigen SHA-256; ausgewählte Pakete werden vor der Mutation erneut geöffnet und gehasht.
- Eine einzelne instabile, nicht lesbare oder gleichzeitig veränderte Fremddatei wird nur für den aktuellen Scan übersprungen und macht nicht mehr den gesamten Exchange-Ordner unbrauchbar.
- Der gemeinsame Standard-Timeout für `patchharbor apply` und `patchharbor fs run` steigt von 300 auf 10.800 Sekunden (drei Stunden); `--timeout` bleibt die explizite Überschreibung pro Aufruf. Der Watcher verwendet denselben Core-Default.

### Release – 2026-08-28

- Paketversion und Release-Artefakte verwenden verbindlich `1.1.1`.
- Der konsolidierte Plan ist mit 12 / 12 Plan-Commits vollständig abgeschlossen und enthält keine `NEXT`- oder `OPEN`-Zeile mehr.
- Der vollständige manuelle Exchange-Kreislauf, die Watcher-Delegation, persistente Dateiidentität, Linux- und Windows-Verträge sowie Wheel-, Source-Distribution- und pipx-Installation sind blockierend abgesichert.
- Spezifikation, README, Chat-Vertrag, CLI, Packaging und Release-Audits beschreiben denselben freigegebenen 1.1.1-Stand.

### Planning correction – 2026-08-26

- Der mechanische 33-Commit-Plan wurde ohne Änderung des Produktziels auf 12 fachlich eigenständige Plan-Commits konsolidiert.
- Die bereits umgesetzten Commits `1.a.W` und `1.a.R` ergeben den Planstand 2 / 12; die Konsolidierung selbst ist ein Off-Plan-Commit und verändert den Zähler nicht.
- W-R-C bleibt als Qualitätsprinzip erhalten, wird aber nicht mehr als zwingendes Dreiermuster für jeden Step verwendet.
- Die Fortschrittstabelle im Plan wird ab jetzt mit jedem Plan-Commit aktualisiert, damit ein neuer Chat den Stand aus dem Result-Bundle-Snapshot bestimmen kann.
- Das UI-Beispiel in der Spezifikation wurde hinsichtlich der neuen Gesamtzahl angepasst.
- Die Testausführungsregel wurde plattformgerecht präzisiert: Termux-Commit-Skripte auf Christians Pixel laufen ohne künstliche Einzeltest- oder Gesamtsuite-Timeouts; produktinterne Timeout-Verträge sowie CI- und Release-Grenzen bleiben bestehen.
- Alle fachlichen 1.1.1-Produktfunktionen bleiben unverändert.

### Added

- Allgemeine benutzerspezifische `config.json` mit geschlossenem Format-1-Schema und `exchange_directory`.
- Sichere CLI zum Setzen und Anzeigen des Exchange-Ordners.
- Gemeinsamer Exchange-Ordner als Standardziel für manuelle und automatische PatchHarbor Result Bundles.
- `patchharbor apply` ohne Dateipfad mit nicht rekursiver, inhaltsbasierter und repositoryzustandsgebundener Paketauswahl.
- Persistente Dateidentität aus kanonischem Pfad und SHA-256 zur Verhinderung ungeplanter automatischer Wiederverarbeitung.
- Gemeinsamer Konfigurations-, Klassifikations- und Dateidentitätsvertrag für Core und Watcher.
- Root-Datei `CHAT_INSTRUCTIONS.md` zur Initialisierung eines neuen Entwicklungs-Chats.
- Verbindliche Chat-Regeln für Plan- und Spezifikationssuche, Spec-vs.-Plan-Prüfung, Tests, Commit-Arten und Result-Bundle-Auswertung.
- Schmale deterministische Chat-UI mit `PLAN`, `FIX`, `OFF-PLAN`, `WARNING`, `STOP` und doppelter `PATCH BEREIT`-Zeile.
- README-Abläufe für neues und bestehendes Repository, neuen Chat, manuellen Modus und Watcher-Modus.

### Changed

- Der frühere Watcher-Eingangsordner und der frühere Standard-Result-Ordner werden durch eine gemeinsame Exchange-Grenze ersetzt.
- `patchharbor bundle` und Apply-Result-Bundles veröffentlichen ohne `--output-dir` im Exchange-Ordner.
- Der Watcher besitzt keine eigene Eingangsordner-Konfiguration mehr und liest ausschließlich `config.json`.
- Result Bundles dürfen bewusst neben Patch-Paketen im Exchange-Ordner liegen und werden zuverlässig nicht als Patch ausgeführt.
- PatchHarbor räumt Exchange-Dateien nicht auf; Archivierung, Sortierung und Journalisierung bleiben außerhalb des Core.
- Repo Assist wird als Werkzeug für Commit-Plan, Journal, Reproduzierbarkeit, Tests und Commits beschrieben, nicht als zwingend oberster Orchestrator.
- Exakte Chat-Statuszeilen sind als maschinenlesbarer UI-Vertrag von der sonstigen Regel gegen Human-Text-Snapshot-Tests ausgenommen.

### Clarified

- Der Chat benötigt weder den lokalen Repository-Pfad noch den Exchange-Pfad; `CHAT_INSTRUCTIONS.md` und ein aktuelles Result Bundle genügen zur Initialisierung.
- `patchharbor apply` erzeugt nach sicherer Repository-Auflösung selbst das Result Bundle; der Patch-Entrypoint ruft `patchharbor bundle` nicht rekursiv auf.
- Projekttests können und sollen durch den vertrauenswürdigen Patch-Entrypoint ausgeführt werden, bleiben aber außerhalb der fachlichen Verantwortung des Core.
- Testfehler oder andere Entrypoint-Fehler führen nicht zu einer globalen PatchHarbor-Rückabwicklung; das Result Bundle enthält soweit möglich den tatsächlich zurückgebliebenen Zustand und die vollständigen Logs.
- Fixes verwenden `<PLAN-ID>-FIX<n>` und erhöhen den Plan-Commit-Zähler nicht; Off-Plan-Kennungen und -Messages dürfen sinnvoll frei gewählt werden.

### Removed / No migration

- Keine 1.1.1-Laufzeitquelle `watcher.json`.
- Keine 1.1.1-Laufzeitquelle `paths.json`.
- Kein Migrations- oder Fallbackcode für frühere Entwicklungs-Konfigurationen, da keine produktiv verwalteten 1.1.0-Installationen übernommen werden müssen.

---

## [1.1.0] – 2026-08-04

**Status:** Verbindliche, implementierungsreife Spezifikationsfassung; Umsetzung gegenüber der vorhandenen 1.0.0-Codebasis erfolgt über den getrennten 1.1.0-Commit-Plan.

### Added

- Vollständige eigenständige Produktspezifikation, getrennt vom Commit-Plan.
- Vollständige Übernahme aller fortgeltenden 1.0.0-Produktverträge.
- Registrierung konkreter lokaler Git-Repository-Instanzen.
- UUID v4 als stabile `repo_id` pro lokalem Klon oder Worktree.
- Lokale ID-Datei `.patchharbor/id`, die nicht committet wird.
- Lokales Git-Exclude über `git rev-parse --git-path info/exclude`.
- Zentrale benutzerspezifische Zuordnung von Repository-ID zu kanonischem Pfad.
- Registry-Minimum mit `register`, `register --new-id`, `registry list` und `unregister`.
- Idempotente Registrierung und definierter Umgang mit verschobenen oder kopierten Repository-Instanzen.
- Befehl `patchharbor context` mit fertigem Copy-Paste-Block.
- Getrenntes Zustandsmodell aus vollständigem Base-Commit und Dirty-State-Fingerprint.
- Normativer Algorithmus `patchharbor-state-v1`.
- Kanonische byteweise Erfassung von staged, unstaged und untracked Zustand.
- SHA-256-Fingerprint, gekürzt auf 16 kleingeschriebene Hex-Zeichen.
- Feste Byte-Rahmung, exakte Payloadcodierung und vier verbindliche Testvektoren einschließlich staged und unstaged.
- Sicherer Mehr-Repository-Pfad `patchharbor apply PATCH_ZIP`.
- Verpflichtende Root-Datei `patch.json` mit Paketmarker, Formatversion, Repository-ID, Base-Commit, Fingerprint-Algorithmus, Fingerprint und Entrypoint.
- Genau ein automatisch gestarteter Entrypoint.
- Privates temporäres Entrypoint-Verzeichnis bei gleichzeitigem Repository-Wurzelverzeichnis als CWD.
- Verbot aller ZIP-Pfade mit `.git` oder `.patchharbor` als Pfadsegment.
- Exklusive betriebssystemübergreifende Sperre pro Repository-ID.
- Erkennung äußerer Zustandsänderungen während der Snapshot-Aufnahme.
- Dry-Run über `patchharbor apply --dry-run PATCH_ZIP`.
- Trennung von primärem Auftragsergebnis und Result-Bundle-Ergebnis.
- Verbindliche Fehlerpriorität bei gleichzeitigem Skript- und Bundle-Fehler.
- Exit-Code `11`, wenn ausschließlich die Result-Bundle-Erzeugung fehlschlägt.
- Strukturierter `logs/run.json`-Bericht.
- Vollständige versionierte `--json`-Abschlussverträge für `registry list`, `context`, `bundle` und `apply`.
- Atomare Veröffentlichung eines vollständig erzeugten Result Bundles.
- Best-effort-Notfallrettung von `execution.log` und `run.json` bei Bundle-Fehlern.
- Vollständiges PatchHarbor Result Bundle mit Base-Dateien, staged Patch, unstaged Patch, untracked Dateien, Kontext und Run-Logs.
- Separater PatchHarbor Watcher als dünne systemd-fähige Komponente.
- Verbindliche Abgrenzung gegenüber Repo Assist und PromptBridge.
- Expliziter Hinweis, dass PatchHarbor keine Sandbox und keine Absenderauthentifizierung ist.
- Aktualisierter Release-Audit-Vertrag für die neue Dokumentstruktur.

### Changed

- Die Hauptspezifikation ist jetzt vollständig selbständig und verweist für unverändertes 1.0.0-Verhalten nicht mehr nur auf eine verkürzte Zusammenfassung.
- Der sichere Mehr-Repository-Workflow verwendet ausschließlich echte Dateien in ZIP-Paketen.
- Im ZIP-Wurzelverzeichnis muss genau eine Datei `patch.json` heißen; weitere sichere Dateien und Verzeichnisse sind ausdrücklich zulässig.
- Der äußere Download-Dateiname und seine Endung sind keine Zuordnungs- oder Sicherheitsinformation.
- Repository-Name, Remote-URL, Branch und zuletzt verwendetes Repository dürfen nicht zur automatischen Auswahl dienen.
- Der Entrypoint wird nicht in das Repository geschrieben, sondern privat temporär ausgeführt.
- Alle übrigen sicheren Paketdateien sind bytegenaue Nutzdateien.
- Das Result Bundle ist immer vollständig rekonstruierbar und kein leichter Commit-Verweis.
- Der Base-Commit wird als vollständige Dateibasis ohne `.git`-Historie aufgenommen.
- Die Base-Dateibasis wird direkt aus Baum- und Blob-Objekten gelesen und ist unabhängig von Exportattributen.
- Result Bundles werden über eine temporäre Datei im endgültigen Result-Ordner atomar veröffentlicht.
- Der sichere Apply-Pfad prüft Entrypoint und Interpreter vor dem Schreiben endgültiger Nutzdateien.
- Der aktuelle Snapshot besteht aus `base/`, `changes/staged.patch`, `changes/unstaged.patch` und `untracked/`.
- Run-Logs sind verbindlicher Bestandteil des Result Bundles, sofern eine Ausführung stattgefunden hat.
- Ein sicher aufgelöstes Repository erhält auch bei späterer Ablehnung oder Ausführungsfehler einen Result-Bundle-Versuch.
- Ein Bundle-Fehler überschreibt einen vorhandenen primären Fehler nicht.
- `patchharbor bundle` behandelt die Bundle-Erzeugung selbst als primären Auftrag.
- Dauerhafte Logaufbewahrung und Rotation liegen nicht im Core; Watcher-Betriebslogs können durch systemd/journald verwaltet werden.
- `payload_files.py` beziehungsweise seine Nachfolge bleibt für sichere ZIP-Nutzdateien und atomisches Schreiben erhalten.
- `parser.py` bleibt für Pflichtmarker, META und MESSAGE zuständig.
- `patchharbor fs run` bleibt als expliziter manueller Runner bestehen und wird vom sicheren `apply`-Pfad klar getrennt.
- Die vorhandenen Verträge für Datei, Ordner, Pipe, ZIP-Reihenfolge, Interpreter, PowerShell, Timeout, Prozessbaum, TUI, temporäres Logging und Ressourcenlimits wurden vollständig in die neue Spezifikation übernommen.
- Der frühere Save-Modus mit chmod wird durch einen klar definierten Dry-Run ersetzt.
- Submodule werden im sicheren 1.1.0-Kontext abgelehnt, da ein vollständiger externer Snapshot nicht garantiert werden kann.

### Corrected during final specification review

- Base-Commit-Snapshots werden nicht mehr über ein exportattributabhängiges Archivverfahren erzeugt, sondern direkt aus Git-Baum und unveränderten Blob-Inhalten materialisiert.
- Committed Dateien können dadurch nicht durch `export-ignore` ausgelassen oder durch `export-subst` verändert werden.
- Der Result-Ordner wird physisch kanonisiert und darf weder identisch mit noch innerhalb irgendeiner registrierten Repository-Instanz liegen.
- Die temporäre Result-ZIP entsteht direkt im endgültigen Result-Ordner und wird dort über `os.replace()` dateisystemgleich atomar veröffentlicht.
- Das private System-Temp-Verzeichnis enthält nur Run- und Notfalldiagnosen, nicht die zu veröffentlichende ZIP-Datei.
- Entrypoint-Marker, Interpreter und Interpreter-Verfügbarkeit werden vor der ersten endgültigen Repository-Änderung geprüft.
- Temporäre STDIN-Artefakte wurden ausdrücklich in den gemeinsamen Cleanup-Vertrag aufgenommen.
- Registry-Mutationen verwenden einen globalen Lock, temporäre Registry-Dateien und atomaren Austausch.
- Für Registry- und Repository-Locks wurde eine verbindliche Lock-Reihenfolge festgelegt.
- Bei verlorener lokaler ID werden alte Zuordnungen desselben kanonischen Pfads vor der Vergabe einer neuen UUID entfernt.
- Das vollständige lokale Verzeichnis `.patchharbor/` ist reserviert, lokal ausgeschlossen und darf keine getrackten Pfade enthalten.
- Eine besondere, verlinkte oder anderweitig unsichere `.patchharbor`-Struktur wird abgelehnt.
- Assume-Unchanged, Skip-Worktree, Intent-to-add, Sparse-Checkout, Sparse-Index und nicht aufgelöste Merge-Stages werden im sicheren Pfad abgelehnt.
- Getrackte symbolische Links, Submodule, nicht reguläre Working-Tree-Einträge und nicht reguläre untracked Einträge werden im sicheren Pfad abgelehnt.
- Repository-Pfade müssen streng als UTF-8 darstellbar sein und werden ohne Unicode-Normalisierung verarbeitet.
- Die Ermittlung von Modus `100644` beziehungsweise `100755` ist über `core.fileMode` und die tatsächlichen Ausführungsbits normiert.
- Staged und unstaged Rekonstruktions-Patches werden unter einer kontrollierten Git-Umgebung ohne externe Diff-Programme, Textkonvertierung, Rename-Erkennung oder Farbe erzeugt.
- Das Result-Manifest enthält plattformunabhängige Metadaten zu Base- und untracked Dateimodi sowie Objekt- beziehungsweise Inhalts-Hashes.
- Ein eigener Tool-Exit-Code kennzeichnet nicht unterstützte Repository-Zustände.
- CLI-Optionen sind jetzt pro öffentlichem Befehl ausdrücklich begrenzt.

### Corrected during implementation-readiness review

- Für sämtliche Fingerprint-Felder ist die Payloadcodierung jetzt vollständig festgelegt: Pfade als ursprüngliche UTF-8-Bytes, Modi und Status als ASCII, Objekt-IDs als vollständige kleingeschriebene ASCII-Hex-Strings, Inhalte als rohe Bytes sowie Zähler und Größen als acht Byte unsigned big-endian.
- Zwei zusätzliche Referenzvektoren sichern eine staged Hinzufügung und eine unstaged Änderung ab.
- Base-Commit und Fingerprint werden unmittelbar vor der ersten Repository-Schreiboperation erneut geprüft; bei einer äußeren Änderung wird ohne Zielschreibzugriff abgelehnt.
- Repository-Pfade werden über Base-Baum, Index, getrackten Working Tree und untracked Dateien hinweg auf plattformübergreifende Darstellbarkeit geprüft.
- Groß-/Kleinschreibungs-Kollisionen, Windows-Gerätenamen, abschließende Punkte oder Leerzeichen, Steuerzeichen und Windows-ungültige Segmentzeichen werden abgelehnt.
- Die reservierten Segmente `.git` und `.patchharbor` werden in Base-Baum und Index ohne Beachtung der Groß-/Kleinschreibung erkannt.
- Paketformat 1 besitzt ein geschlossenes `patch.json`-Schema; unbekannte Felder, nicht kanonische UUIDs, abgekürzte Objekt-IDs und falsch formatierte Fingerprints werden abgelehnt.
- Die maschinenlesbaren Ausgaben aller vier öffentlichen `--json`-Befehle besitzen jetzt einen gemeinsamen versionierten Envelope und exakt definierte befehlsspezifische Resultate.
- Watcher-Eingangsordner müssen außerhalb aller registrierten Repositories liegen und dürfen sich mit Result-Ordnern nicht überlappen.
- Ubuntu 26.04 ist zusammen mit Ubuntu 24.04 und dem echten Windows-Runner ein normales blockierendes Release-Gate; die frühere Preview-Ausnahme entfällt.

### Removed

- FILE-Blöcke als zweiter Dateiübertragungsweg.
- FILE-spezifischer Parser-, Modell-, Anwendungs-, Darstellungs- und Testpfad.
- Base64 als vorgesehener Inline-Transport für Binärinhalte.
- Automatische Base64-Dekodierung als mögliche spätere PatchHarbor-Funktion.
- WebSocket-Quelle und WebSocket-Host aus PatchHarbor.
- Der frühere nachgelagerte WebSocket-Meilenstein.
- WebSocket-spezifische Vorbereitungen und Abhängigkeiten im PatchHarbor Core.
- Clipboard-Quelle.
- SSH-Quelle.
- Öffentliches Plugin-System.
- Zielprojekt-Testmanagement durch PatchHarbor.
- Git-Commit-, Branch-, Tag- und Release-Verwaltung durch PatchHarbor.
- Interaktive Kindskripte.
- Rekursive Ordnersuche.
- Rekursive Auflösung verschachtelter ZIP-Archive.
- Vollständige Pakettransaktion und automatische globale Rückabwicklung.
- Dauerhafte Logverwaltung und Logrotation im PatchHarbor Core.
- Automatisches Einsammeln beliebiger zusätzlicher Diagnose-, Test- oder Build-Artefakte.

### Responsibility moved

- Chat- und Netzwerktransport, Upload und Download: **PromptBridge**.
- Tests, Testbewertung, Commit, Retry, Abort und Journal: **Repo Assist**.
- Dauerhafte Download-Ordnerüberwachung: **PatchHarbor Watcher**.
- Technische Patch-Ausführung, Zustandsprüfung, Run-Logging und vollständiger Repository-Snapshot: **PatchHarbor Core**.

### Clarified

- `.git` und `.patchharbor` sind als ZIP-Pfadsegmente ausnahmslos verboten.
- Dieses Pfadverbot ist keine Sandbox und hindert ein gestartetes vertrauenswürdiges Skript nicht technisch an Benutzeraktionen.
- Ein Repository gilt erst nach eindeutiger Registrierung, lokaler ID-Prüfung und erfolgreichem Lock als sicher aufgelöst.
- Sobald ein Repository sicher aufgelöst ist, versucht PatchHarbor am Auftragsende ein Result Bundle zu erzeugen.
- `result_bundle.status=not_attempted` ist nur erlaubt, wenn kein Repository sicher aufgelöst wurde.
- Bei einem erfolgreichen primären Auftrag und fehlgeschlagenem Bundle gilt Exit `11`.
- Bei einem bereits fehlgeschlagenen primären Auftrag bleibt dessen Exit-Code erhalten; der Bundle-Fehler wird sekundär dokumentiert.
- Ein manuelles Bundle enthält keinen erfundenen Entrypoint-Log.
- Halbfertige Result Bundles werden nicht unter einem endgültigen Dateinamen veröffentlicht.
- Der Result-Ordner darf nicht innerhalb einer registrierten Repository-Instanz liegen.
- Nicht unterstützte Index-, Sparse-, Symlink- und Pfadkodierungszustände werden vor Fingerprint und Ausführung abgelehnt.
- Die erste Zustandsprüfung reserviert den erwarteten Zustand; die zweite Prüfung unmittelbar vor dem ersten Zielschreibzugriff schließt das verbleibende Änderungsfenster.
- JSON-Ausgabeformat 1 ist geschlossen und darf ohne Erhöhung von `output_version` keine zusätzlichen Felder erhalten.

### Migration and cleanup

Der erste 1.1.0-Commit ist ein Spezifikations-, Changelog- und Dokumentstruktur-Audit-Commit ohne Produktionscodeänderung.

Er aktualisiert zusätzlich den Release-Audit-Test auf:

```text
spec/SPECIFICATION.md
spec/SPECIFICATION_CHANGELOG.md
planning/1.0.0/commit-plan.md
planning/1.1.0/commit-plan-cleanup.md
planning/1.1.0/commit-plan.md
```

Das allererste anschließende Code-Cleanup ist:

> FILE-Blöcke vollständig aus Parser, Modellen, Anwendung, Darstellung, Tests und Dokumentation entfernen.

Dabei gilt:

- `payload_files.py` nicht pauschal löschen,
- sichere ZIP-Nutzdateien und atomisches Schreiben erhalten,
- ausschließlich den FILE-spezifischen Pfad entfernen,
- bestehende Base64-Nichtdekodierungs-Tests entfernen oder auf den alleinigen ZIP-Nutzdateivertrag umstellen,
- keinen Base64-Decoder entfernen, weil im aktuellen Stand keiner implementiert ist.

Danach folgen Registry mit Lock und atomarer Persistenz, normativer Fingerprint samt Sonderzustandsprüfung, `patch.json`, Apply, Repository-Lock, Dry-Run, Ergebnisvertrag, direkte Baum-/Blob-Materialisierung des vollständigen Result Bundles und separater Watcher.

---

## [1.0.0] – Implementierungsbasis vor 1.1.0

**Status:** Vorhandene stabile Produkt- und Codebasis.

### Included

- Kontrollierter plattformübergreifender Runner.
- Python 3.12 oder neuer.
- pipx-Installation und Konsolenbefehl `patchharbor`.
- `patchharbor fs run [PFAD]`.
- Direkte Datei, einmaliger nicht rekursiver Ordnerscan, ZIP und STDIN.
- Exakter Skriptmarker `# PATCHHARBOR`.
- Optionale META- und MESSAGE-Inhalte.
- ZIP-PatchBundles mit mehreren geordneten Skripten.
- Bytegenaue Text- und Binär-Nutzdateien.
- Sichere relative ZIP-Pfade und atomisches Schreiben.
- Bash, Windows PowerShell und PowerShell 7 über geprüfte Zuordnung.
- PowerShell ohne Execution-Policy-Bypass.
- Timeout, zweisekündige Beendigungsfrist und vollständiger Prozessbaum.
- Strg+C-Vertrag.
- Plain-Ausgabe, Terminaldashboard, Rolling Buffer und finaler Redraw.
- Optionales vollständiges temporäres Run-Log.
- Ressourcenlimits und ZIP-Bomben-Schutz.
- Linux-, Windows-, Wheel- und pipx-Testpfade.

### Superseded by 1.1.0

Die frühere Produktspezifikation war mit dem Commit-Plan kombiniert und enthielt zusätzliche inzwischen verworfene oder neu zugeordnete Zukunftspfade. Die neue 1.1.0-Spezifikation übernimmt alle fortgeltenden Verträge vollständig und ersetzt diese alte Produktbeschreibung.


### OFF-PLAN COMPACT-CORE / 1 — kompakte Standardausgabe

Zentrale Filterung aller technischen Dateisystem-, Git-, ZIP- und SHA-Meldungen;
--verbose/-v für Details; angehängte Punkte frühestens alle 0,8 Sekunden.
Keine Änderung der Mutation, Recovery, Rohlogs oder JSON-Verträge.


### OFF-PLAN COMPACT-CORE / 2 — neutrale Application-Beobachtung

Konkrete Konsolenparameter durch unveränderliche Ereignisse ersetzt, vollständige
Kennungen bis zur UI-Grenze erhalten, implizite stdout-Ausgabe entfernt und
interaktive Verzeichnisauswahl aus Core in den CLI-Adapter verschoben.


### OFF-PLAN COMPACT-CORE / 3 — Fehlergründe statt CLI-Status im Core

Fachliche FailureReason-Daten und neutrale Ergebnisentscheidungen; eine gemeinsame
kompatible Zahlenabbildung für CLI und vorhandene JSON-/Result-Serializer.
Skript-Exitcodes, Prioritäten, Replay-/Recovery-Daten und Versionsnummer unverändert.


## 1.2.0 Entwicklung – API-1 (noch kein Release)

Öffentliche synchrone API als additive Fassade eingeführt. Repository/Run-Werte
werden wiederverwendet, Bibliotheksaufrufe sind standardmäßig still. Explizite
Streams, vollständige Ereignisse und Eingabeprüfung dokumentiert. Die
obligatorische Result-Protokollierung bleibt von optionalen Rohsenken getrennt.
Aktiver Plan: `planning/1.2.0/commit-plan.md`.


## 1.2.0 Entwicklung – API-2 (noch kein Release)

Alle fachlichen Haupt-CLI-Aufrufe laufen über patchharbor.api. Der CLI-Adapter
übergibt Beobachter und Streams explizit, ohne Application oder OutputTargets
zu importieren. Bestehende JSON-/Result-Formate und Statuscodes bleiben erhalten.
Nichtendliche CLI-Timeouts werden als ungültige Argumente abgewiesen. Der
Watcher-Prozess-/Signalvertrag bleibt bis zum eigenen Schritt unverändert.


## 2026-09-13 – API-3: Watcher über öffentliche Python-API

Watcher-Startup nutzt die API mit derselben physischen Konfigurationsnachprüfung.
Der beibehaltene Einzelprozess pro Poll ruft `api.apply_next()` ohne CLI-Parser
auf und transportiert das bestehende Apply-JSON. Keine Änderungen an Scan,
Replay, Recovery, Locks, Result-Erzeugung, Signalen oder Serviceinstallation.
Fachliche Worker-, Konfigurations-, Prozessgrenzen- und Packaging-Prüfungen
begleiten die Migration; keine neuen Tests der Konsolendarstellung.
