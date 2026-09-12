# PatchHarbor 1.2.0 – Commit-Plan

Zielversion: **1.2.0**; installierbare Paketversion bleibt bis API-4 **1.1.1**.
Spec: `planning/1.2.0/specification.md` (ergänzt `spec/SPECIFICATION.md`).
Basis: `62020dab617d54925c8dd0ac192aaff685cda0f3`.

Der Benutzer erlaubt adaptive Paketgrenzen. Fachliche Commits bleiben getrennt:
Tests vor jedem Commit, vollständige Suite bei schichtenübergreifendem Scope,
kein Push zwischen Commits, genau ein normaler abschließender Push nach allen
Gates des jeweiligen Pakets. Keine automatische Rückabwicklung bei Teilfehlern.

1. **API-1** – `feat(api): add typed synchronous Python facade`
   Öffentliche Imports, Ergebnis-/Fehler-/Stream-/Event-Verträge, stille Nutzung,
   bestehende Application-Pfade, funktionale API-Tests und erste Dokumentation.
   Status: in diesem Schritt implementiert; Commit erst nach lokalem Gate.
2. **API-2** – `refactor(cli): route all commands through public Python API`
   Gesamte Haupt-CLI über API führen, kompatible Darstellung/JSON/Exitcodes,
   fachliche Adapter- und Architekturgates, vollständige Suite vor Commit.
   Status: offen.
3. **API-3** – `refactor(watcher): use public Python API`
   Watcher-Konfiguration und automatischen Poll migrieren; Prozess-/Signal-
   Verhalten und Betriebsprotokolle gesondert absichern.
   Status: offen.
4. **API-4** – `release: finalize public Python API for 1.2.0`
   API-Audit, Dokumentation, Versionsanhebung und vollständige Release-Gates.
   Status: offen.

Implementierungsstatus ersetzt keinen CI-Nachweis. Die aktuelle Paket-CI wird
extern nach dem abschließenden Push bewertet; keine vorweggenommene Grün-Aussage.
