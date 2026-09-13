# PatchHarbor 1.2.0 – Commit-Plan

Ziel- und Paketversion: **1.2.0**.
Spec: `planning/1.2.0/specification.md` (ergänzt `spec/SPECIFICATION.md`).
Initiale Basis: `62020dab617d54925c8dd0ac192aaff685cda0f3`.
API-3/API-4-Basis: `e0cd8f800783add13cbac595323067b492edb62f`.

**Planstatus:** 4 / 4 Plan-Schritte implementiert; 0 weitere Plan-Commits offen.
Die Abschluss-Commits werden nur nach den lokalen Gates angelegt. Dieses Dokument
behauptet weder einen bereits erfolgten Push noch eine erfolgreiche externe CI.

Der Benutzer erlaubt adaptive Paketgrenzen. Fachliche Commits bleiben getrennt:
Tests vor jedem Commit, vollständige Suite einschließlich Packaging vor dem
Release-Commit, kein Push zwischen Commits, genau ein normaler abschließender Push
nach allen Gates des jeweiligen Pakets. Keine Rückabwicklung bei Teilfehlern.

1. **API-1** – `feat(api): add typed synchronous Python facade`
   Öffentliche Imports, Ergebnis-/Fehler-/Stream-/Event-Verträge, stille Nutzung,
   bestehende Application-Pfade, funktionale API-Tests und Dokumentation.
   Status: umgesetzt im Basisstand (`ccd1198`); vorheriges Paket abgeschlossen.
2. **API-2** – `refactor(cli): route all commands through public Python API`
   Gesamte Haupt-CLI über API führen, kompatible Darstellung/JSON/Exitcodes,
   fachliche Adapter- und Architekturgates, vollständige Suite vor Commit.
   Status: umgesetzt im Basisstand (`e0cd8f8`); vorheriges Paket abgeschlossen.
3. **API-3** – `refactor(watcher): use public Python API`
   Konfiguration über API mit Revalidierung; separater privater Worker pro Poll
   ruft die API direkt auf. Unveränderte Signal-, Retry-, Replay- und Servicegrenze.
   Status: implementiert; separates funktionales Gate vor diesem Commit.
4. **API-4** – `release: finalize public Python API for 1.2.0`
   Öffentlicher API-Vertrag, Typing-Marker, installierte API-/Worker-Prüfung,
   Dokumentation, `CHAT_INSTRUCTIONS.md`, Versionierung und Release-Audit.
   Status: implementiert; vollständige lokale Suite vor dem Release-Commit.

API-3 und API-4 bilden ein gemeinsames Zwei-Commit-Paket. Nach beiden lokalen
Gates erfolgt ein abschließender Push; keine automatischen Tags oder Publikation.
Die externe CI bewertet anschließend genau diesen finalen Commit. Ein Fehler
lässt den tatsächlichen Zwischenstand stehen und verlangt eine neue Analyse.
