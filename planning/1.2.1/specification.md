# PatchHarbor 1.2.1 – generischer Entwicklungs-Chat-Vertrag

Zielversion: **1.2.1**. Diese Spezifikation ergänzt `spec/SPECIFICATION.md`.

## Ziel

Die generische `CHAT_INSTRUCTIONS.md` beschreibt nur universelle PatchHarbor-
Übergabe- und Sicherheitsregeln. Fachliche Teststrategien stammen aus dem
jeweiligen Zielprojekt und dem konkreten Nutzerauftrag. Ein Bundle darf normal
einen oder mehrere fachlich abgegrenzte Commits enthalten.

## Verbindliche Regeln

- Tatsächlich verfügbare Nutzeranweisungen, `AGENTS.md` und verbindlich
  referenzierte Projektregeln bestimmen die Projektprüfungen.
- Explizite Nutzeranweisungen haben Vorrang vor generischen PatchHarbor-Defaults.
- Ohne konkrete Testbefehle werden angemessene Prüfungen aus Testinfrastruktur
  und Auftrag abgeleitet; fehlende lokale Regeln werden nicht erfunden.
- Vor jedem Commit müssen alle für diesen Zwischenstand vorgeschriebenen Gates
  vollständig abgearbeitet sein. Rote Gates erzeugen keinen Commit dieses
  Zustands; projektspezifisch noch vorgeschriebene weitere Gates desselben
  Zustands können trotzdem erforderlich sein.
- Ein Bundle darf einen oder mehrere fachlich geschlossene Commits enthalten.
  Mehrere Commits brauchen keine besondere W/R/C-Genehmigung. W/R/C bleibt nur
  dort verbindlich, wo Projekt oder Auftrag es verlangt.
- Zwischenstände werden real nacheinander hergestellt und geprüft. Kein
  vorinstallierter Endzustand mit nachträglich künstlich erzeugten Commits.
- PLAN/FIX/OFF-PLAN, Zähler, Teilerfolg und Übergabeanzeige werden pro Commit
  beziehungsweise für die geordnete Commitfolge ausgewertet.
- Paketformat, anfängliche State-Bindung, Core-Sicherheitschecks und genau eine
  kanonische Patch-ZIP mit genau einem Entrypoint bleiben unverändert.
- Kein Testpolicy-Resolver, Scheduler oder Commitplaner wird in Core eingebaut.

## Vorlagen- und Packagingpfad

Die kanonische statische Quelle bleibt die versionierte Root-Datei
`CHAT_INSTRUCTIONS.md`. `src/patchharbor/chat_instructions.py` lädt diese Quelle
im Source-Checkout oder die als `share/patchharbor/CHAT_INSTRUCTIONS.md`
installierte Daten-Datei und rendert daraus frisch die Root-Anleitung von Result
Bundles sowie die passive Patch-Begleitdokumentation. Bereits erzeugte ZIPs
werden nicht rückwirkend geändert.

## Release

Nach erfolgreicher Vertragsbereinigung wird die Paket-/Vertragsversion auf
**1.2.1** angehoben. Der Release-Commit wird vollständig geprüft und anschließend
lokal mit `v1.2.1` getaggt. Ein Push von Branch oder Tag ist nicht Teil des
Patch-Entrypoints.
