# Bundle 082 — Persistenter Aktivitätsverlauf und betriebliche Übersicht

Auftrag vom 10. November 2026, OFF-PLAN `VIEW-UX`, ursprünglicher Planzähler
unverändert. Vorgesehener Commit:
`feat(monitor): show persistent activity and operational repository status [VIEW-UX]`.

## Nachgewiesener Ausgang

- Dev/Apply-Commit: `023e08a47eb30bd88a7440533e4f45ab8add54b8`, sauber.
- Native Referenz: `patchharbor-apply_Result_091701_1110_bfbbe7.zip`.
- SHA-256: `4593c9a442b5333120f0d463c0c9a9a3d6160ed61611e5747ea07b5239b33c00`.
- Der öffentliche Snapshot-Leser prüfte die Referenz; alle 480 effektiven
  Quelldateien wurden bytegleich mit dem isolierten Development-Worktree verglichen.

## Gelieferter Umfang

Fünf dauerhaft sichtbare Zeilen zeigen zwei beobachtete Schritte, die aktuelle
Tätigkeit in der Mitte mit animiertem Spinner sowie zwei bedingte Folgeschritte.
Der Watcher-Kopf bleibt global und unabhängig vom Repositoryfilter. Gleichzeitige
Vorgänge behalten eigene Instanzen; die älteste aktive Operation erhält stabil
den Kopf. Keine Tests, Commits oder Pushes aus Entrypoint-Inhalten erraten.

Repositorys zeigen PatchHarbor-Zustand, Exchange-Zustand und letzten beobachteten
Apply. Die Auswahl ergänzt Paket/Exchange-Kontext, die Exchange-Ansicht gruppiert
ihre Repositorys. Git ist mit `g` zuschaltbar. `v` schaltet vollständige IDs ein,
`l` springt zum aktiven Vorgang. Zeiten erscheinen lokal, Dauern verständlich.
Erfolg: grüner Haken; Fehler: rotes Kreuz; Aktivität: cyanfarbener Spinner;
Vorschau: Lila; unbekannt/wartend: Grau. Vollständige Werte bleiben in den
umgebrochenen Details, JSON und ursprünglichen Logs erhalten.

Beobachtungsversion 2 ergänzt eine begrenzte Ereignishistorie (32 Vorgänger),
Entrypoint-Namen und optionale eindeutig deklarierte Handoff-Bundle-Nummern.
Diese Nummer ist ausschließlich Anzeige, kein Identitäts-/Ausführungsbeweis.
Auch manuelle Git-Result-Erzeugung hat einen eigenen beobachteten Vorgang.
Version 1 bleibt lesbar. Die Watcher-Ereignisschleife publiziert ihre tatsächlichen
Änderungen, Sperrprüfungen, Arbeit und Beendigung; keine neue Ausführungssteuerung.

Zwei separat begrenzte Hintergrundabfragen erheben kompakte Exchange-Nachweise
für alle sichtbaren Repositorys. Unvollständige/alte Quellen werden nicht zu
leeren Warteschlangen oder vermeintlicher Bereitschaft. Gemeinsame Exchanges
behalten vollständige Repository-/Paketbindungen. Ein grüner Entrypoint und
fehlgeschlagene Result-Veröffentlichung bleiben ein roter Gesamtausgang.

## Prüfungen und Übergabe

Development prüft gezielt parallel Monitor-Daten, Historie, neue Oberfläche,
Aktualisierung, echte Applies/Result-Erzeugung, Watcher-Ereignisschleife,
öffentliche API, Architektur und Release-Paketierung. Neue Verhaltenstests
prüfen insbesondere die feste Mitte in allen sieben Ansichten, unabhängige
Auswahl, mehrere Läufe, alte Quellen, Versionskompatibilität, Bundle-Nummern,
volle IDs, schmale Terminals, begrenzte Hintergrundabfragen und native Bindung.
Praktische Terminal-/Farbprüfungen und die tatsächlichen Controllerberichte
liegen außerhalb des Quellstands im Development-Arbeitsbereich `monitor-082/reports`.

Die fünf zusätzlichen Produktionsmodule stehen in der expliziten Release-Liste.
Ein erstes Wheel misst 444591 Bytes; das Releasebudget steigt gezielt von 432
auf 448 KiB. Eingabe-/Runtime-Ressourcenlimits bleiben unverändert.

Der Entrypoint prüft Ausgang, Nutzdatei-Hashes, erlaubten Git-Scope und führt die
vollständige parallele Suite mit vier Workern vor dem einzigen Commit aus.
Er pusht genau einmal normal nach `dev`; bei einem Fehler bleiben Nachweise und
Zwischenstand erhalten. Erst ein natives Apply-Result belegt Erfolg.
Kein CI-Dispatch, Tag oder Dienst-/Installationswechsel gehört zur Lieferung.
Laufende ältere Prozesse liefern ihre bisherigen Beobachtungen bis zu ihrem
normalen nächsten Start mit der neuen Runtime; der neue Leser kann sie anzeigen.
