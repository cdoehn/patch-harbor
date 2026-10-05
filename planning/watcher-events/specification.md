# PatchHarbor – Ereignisgesteuerter Exchange-Watcher

Stand: 5. Oktober 2026. Plan-ID: `watcher-events`. Status: verbindliches
Entwicklungsziel, noch nicht implementiert. `WE-0` übernimmt ausschließlich
Dokumentation. Die installierte Polling-Schleife ändert sich dadurch nicht.
Produktversion und Release-Tag werden durch diesen Plan nicht angehoben.

## 1. Ziel und Ausgangslage

Der Watcher beobachtet die oberste Ebene jedes konfigurierten Exchange über
Betriebssystemereignisse. Erst nach mindestens fünf zusammenhängenden Sekunden
ohne relevante Änderung darf er diesen Exchange durch Core untersuchen lassen.
Jede weitere relevante Änderung startet die Ruhefrist erneut. Im unveränderten
Leerlauf gibt es weder periodische Verzeichnis-Scans noch Apply-Workerstarts,
Dateihashes oder KI-/API-Aufrufe zur Zeitsteuerung.

Ausgangsbasis ist der durch Result und CI bestätigte Commit
`a02391dc045d42e317b3e766f0b1e9fa8dfadec1`. Heute setzt
`src/patchharbor_watcher/cli.py` `--poll-interval` auf 1,0 Sekunden;
`loop.py` startet unabhängig von Änderungen nach jedem Durchlauf einen Worker.
Core liest Exchange-Dateien samt SHA-256 vor dem Klassifikationscache.
Unterdrückte doppelte Logmeldungen verhindern diese Arbeit nicht.

## 2. Beobachtungsumfang

- Core liefert validierte Exchange-Wurzeln und die für deren Aktualisierung
  notwendigen Registry-/Konfigurationspfade über seine öffentliche API.
  Der Watcher liest keine eigene Registry oder Konfigurationsdatei als Ersatz.
- Physisch identische Exchanges werden zusammengefasst; globale Zuständigkeit
  für alle registrierten Repositories bleibt erhalten. CWD ist kein Filter.
- Exchange-Beobachtung ist nicht rekursiv. Änderungen innerhalb bestehender
  Unterordner, insbesondere `reports/` und Archiv, lösen keinen Bundle-Scan aus.
  Erstellen, Entfernen oder Umbenennen eines direkten Eintrags zählt dagegen
  als Änderung der Wurzelebene, auch wenn dieser Eintrag ein Verzeichnis ist.
- Erzeugen, Schreiben, Schließen nach Schreiben, Entfernen, Hinein-/Herausbewegen,
  Umbenennen und relevante Größen-, Änderungszeit- oder Rechteänderungen zählen.
  Öffnen, Lesen, Schließen ohne Schreiben und reine Zugriffszeitänderungen zählen
  nicht. Ein eigener Scan darf keine Ereignisschleife erzeugen.
- Dateinamen und Endungen entscheiden nicht über die Beobachtung. Core behält
  Inhaltsklassifikation, temporäre Downloadfilter und das Bundle-Suffix-Verhalten.
  Symlinks/Junctions werden nicht als zusätzliche überwachte Dateibäume verfolgt.

## 3. Ruhefrist und Start

Die Frist beträgt fest `5.0` Sekunden und verwendet eine monotone Uhr.
Pro physischer Wurzel werden mindestens Änderungsstand, Bearbeitungsbedarf und
frühester Scanzeitpunkt geführt. Es existiert höchstens eine offene Frist je
Wurzel, kein eigener Thread oder Timer pro Dateiereignis.

1. Beim Start erst Ereignisse abonnieren, anschließend jede gültige Wurzel einmal
   als prüfbedürftig vormerken. So werden schon vorhandene Bundles gefunden.
2. Der erste Scan darf frühestens fünf Sekunden nach aktivierter Beobachtung
   beginnen. Weitere Ereignisse verschieben auch diese Startfrist.
3. Eine Änderung zur monotonen Zeit `t` setzt die Frist auf mindestens `t + 5`.
   Beispiel: Ereignisse bei 0, 3 und 7 erlauben den Scan frühestens bei 12.
4. Vor dem Start werden bereits eingegangene Ereignisse und die aktuelle
   Änderungskennung berücksichtigt; eine überholte Timer-Auslösung startet nichts.
5. Ohne Bearbeitungsbedarf wartet der Prozess blockierend auf Ereignisse oder
   Stoppsignal. Es gibt keinen wiederkehrenden Kontrolltimer für leere Exchanges.

Die Ruhefrist ist eine Auslösebedingung, kein Vollständigkeits- oder
Sicherheitsbeweis. Änderungen können nach der Freigabe erneut auftreten.
Core muss deshalb sämtliche bestehenden Stabilitäts-, Paket-, Hash-, Pfad-,
Repository-, Fingerprint- und Replayprüfungen unverändert durchführen.

## 4. Core-Grenze und mehrere Exchanges

Die öffentliche automatische Apply-Grenze bekommt eine optionale, durch Core
validierte Einschränkung auf die aktuell freigegebenen Exchange-Wurzeln.
Ohne Einschränkung behält `api.apply_next()` seinen bisherigen globalen Vertrag.
Mit Einschränkung darf die Discovery ausschließlich diese Exchanges auflisten
oder deren Bundles lesen; Registry und Repositorykonfiguration bleiben durch
Core zu prüfen. Eine leere Einschränkung bedeutet niemals implizit „alle“.
Nicht registrierte, ausgetauschte oder widersprüchliche Ziele werden abgelehnt.

Mehrere ruhige Wurzeln können gemeinsam freigegeben werden. Ein noch beschriebener
Exchange darf andere ruhige Exchanges nicht dauerhaft blockieren. Die bestehende
deterministische Kandidatenreihenfolge gilt innerhalb des freigegebenen Scopes.
Ein neuer Download in einem bereits freigegebenen Scope bleibt durch erneute
Ereignisse und die unabhängigen Core-Prüfungen abgesichert.

Ein Dateiereignis ist niemals die Erlaubnis zu einem expliziten manuellen Apply
des gemeldeten Pfads. Der automatische Ursprung, seine fehlende automatische
Wiederholung fehlgeschlagener Identitäten und sämtliche Locks bleiben erhalten.
Beobachtungsinformationen sind keine Reservierung und keine neue Vertrauensgrenze.

## 5. Ausführung, Nachlauf und Konkurrenz

- Höchstens ein Apply-Worker läuft gleichzeitig. Seine bestehende Prozessgrenze
  und sein maschinenlesbarer Result-Vertrag bleiben erhalten.
- Ereigniserfassung läuft während Scan und Apply weiter. Eine neue Generation
  wird beim Abschluss einer älteren Generation nicht versehentlich gelöscht.
- Nach echtem Bearbeitungsfortschritt darf Core weitere schon vorhandene
  Kandidaten desselben freigegebenen Scopes prüfen. Vor jeder Fortsetzung gilt
  weiterhin die Ruhebedingung. Ein einmaliges Ablegen mehrerer Bundles muss
  deren spätere Verarbeitung ermöglichen, ohne künstliche neue Dateiereignisse.
- „Kein geeigneter Kandidat“ ohne zwischenzeitliche Änderung beendet den
  Bearbeitungsbedarf. Result-Dateien können einen Nachlauf auslösen, bleiben
  jedoch Nichtkandidaten; es gibt kein pauschales Ignorieren eigener Ereignisse,
  das gleichzeitig eingehende fremde Änderungen verlieren könnte.
- Sperrkonflikte vor Ausführung verbrauchen keinen Auftrag. Core stellt für den
  konkreten offenen Sperrkonflikt eine reine Bereitschaftsprüfung bereit, die
  keine Exchange-Dateien auflistet, liest oder hasht und keine Sperre reserviert.
  Nur für diesen offenen Auftrag sind lokale Bereitschaftsprüfungen mit
  wachsendem Abstand (5, 10, 20, 40, 80, 160, danach höchstens alle 300 Sekunden)
  zulässig. Erst bei Bereitschaft und erfüllter Ruhefrist wird wieder delegiert.
  Dies ist kein allgemeiner Scan-Fallback. Beim Stoppen entfällt die Prüfung;
  der anschließende Apply muss alle Locks erneut selbst erwerben.
- Ein tatsächlich fehlgeschlagener Patch wird nicht automatisch erneut versucht.
  Fortsetzungsentscheidungen verwenden strukturierte Core-Ergebnisse und
  bestätigten Fortschritt, keine erratenen Konsolenmeldungen.
- Reine Git-/Working-Tree-Änderungen außerhalb der Exchanges sind künftig kein
  allgemeiner Scan-Auslöser. Ein bislang state-inkompatibles Bundle wird bei der
  nächsten Exchange-Änderung, beim Watcher-Neustart oder bewusst manuell erneut
  geprüft. Ein rekursiver Repository-Watcher gehört nicht zu diesem Plan.

## 6. Konfiguration, Ereignisverlust und Stoppen

Registry- und lokale Konfigurationsänderungen werden über eng begrenzte
Kontrollbeobachtungen erkannt. Bei atomarem Dateiaustausch werden Elternpfad und
Dateiname berücksichtigt; keine rekursive Überwachung von Repositories.
Core liefert und revalidiert die neue Zielmenge. Hinzugefügte Wurzeln durchlaufen
die Startfrist, entfernte erhalten keine neuen Aufträge. Gültiges `null` und
fehlende Repositorypfade behalten den bestehenden Core-Vertrag. Beschädigte
Konfigurationen werden nicht repariert oder still übersprungen.

Bei Austausch, Umbenennung, Verlust oder Wiederkehr einer Exchange-Wurzel muss
die physische Zuordnung erneut geprüft und die Beobachtung neu eingerichtet
werden. Gezielte Elternbeobachtung darf die Wiederkehr erkennen. Bis zur
erfolgreichen Revalidierung wird der betroffene Scope nicht ausgeführt.

Erkannter Ereignisverlust, insbesondere Queue-Überlauf, markiert betroffene
Wurzeln als prüfbedürftig und erneuert erforderlichenfalls die Beobachtung.
Ein kontrollierter Abgleich erfolgt erst nach einer neuen vollständigen Ruhefrist.
Unbegrenzte Ereignislisten sind zu vermeiden; Änderungskennungen und zusammen-
gefasster Bearbeitungsbedarf reichen. Backend-Ausfall darf nicht unbemerkt als
gesunder Leerlauf erscheinen und nicht still auf periodisches Polling wechseln.

SIGINT/SIGTERM unterbrechen auch ereignisloses Warten. Nach Stop werden keine
neuen Worker gestartet; laufende Applies behalten ihre bisherige Stop-/Prozess-
Semantik. Handles, Threads und Fristen werden geordnet beendet. Neustart verwendet
den bestehenden persistenten Core-Replayzustand und die initiale Bestandsprüfung.

## 7. Plattformen, Installation und CLI

Linux verwendet `inotify`, Windows `ReadDirectoryChangesW` mit nicht rekursiver
Beobachtung. Schmale, getrennte Adapter binden die nativen Schnittstellen über
die Standardbibliothek ein. PatchHarbor bleibt ohne zusätzliche Laufzeit-
abhängigkeiten; Wheel, Offline-Runtime und bisheriger Fallback bleiben verwendbar.
Tests müssen die unterstützten nativen Plattformen tatsächlich nachweisen.
Termux erhält hierdurch keine neue zugesagte Watcher-Service-Unterstützung.

Nicht unterstützte Plattformen oder Dateisysteme werden mit eindeutigem
strukturiertem Fehler gemeldet. Insbesondere sind entfernte Änderungen auf
Netzwerk-/virtuellen Dateisystemen nicht pauschal zuverlässig ereignisfähig.
Der dokumentierte manuelle Apply bleibt verfügbar; ein automatischer Polling-
Fallback gehört nicht zum Zielvertrag.

`patchharbor-watcher` startet nach Aktivierung den Ereignisbetrieb.
`--install-systemd-user-unit` behält seinen bestehenden Zweck.
`--poll-interval` entfällt bei WE-3 mit gezieltem Aufruffehler und dokumentierter
Umstellung; der alte Wert wird nicht als neue Ruhefrist umgedeutet.
Vorhandene unveränderte systemd-Units benötigen keinen zusätzlichen Parameter.
Ein laufender installierter Watcher wird durch diese Entwicklung nicht ersetzt;
der spätere Betreiberwechsel erfolgt nach Ende laufender Applies mit Neustart.

## 8. Verbindliche Abnahme

Deterministische Uhren-/Ereignis-Fixtures prüfen mindestens: ruhigen Leerlauf ohne
Scan/Worker; anfängliche fünf Sekunden; Zurücksetzen der Frist und Grenzfälle;
Ereignisse kurz vor Timerablauf, während Scan/Apply und beim Stop; Lesen und
Unterordner ohne Auslösung; Kopieren in mehreren Schritten und atomare Rename-
Übergabe; mehrere Bundles und unabhängige/geteilte Exchanges; kein fremder Scan;
Konfigurationswechsel, Root-Austausch, Queue-Überlauf und Backend-Ausfall;
Sperrkonflikt samt Wiederaufnahme; kein Retry tatsächlich fehlgeschlagener Patches;
Neustart, Replay und unveränderte Hash-/State-Bindung.

Zusätzlich: echte native Dateiereignisse unter Linux und Windows, echte Apply-
Resultate, Stop ohne Hängen, installierter Wheel-/Runtime-Pfad ohne neue
Abhängigkeiten und der vorhandene Offline-Fallback. Keine neuen Tests auf Farben,
Wortlaut, README-Prosa oder Markdownlayout. Die Projekt-Test-/CI-Regeln stehen im
[Commit-Plan](commit-plan.md); allein lokale Linux-Tests bestätigen kein Windows.

## 9. Technische Referenzen

- [Linux inotify](https://man7.org/linux/man-pages/man7/inotify.7.html):
  blockierender Ereignisempfang, Masken, Queue-Überlauf und Dateisystemgrenzen.
- [Microsoft ReadDirectoryChangesW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-readdirectorychangesw):
  flache Beobachtung, Änderungsfilter und Behandlung verlorener Änderungen.

Die Referenzen beschreiben OS-Möglichkeiten; die tatsächliche PatchHarbor-
Umsetzung und ihre Grenzen müssen durch die oben genannten Nachweise bestätigt werden.
