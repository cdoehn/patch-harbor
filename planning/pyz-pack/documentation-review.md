# PP-07: fachlicher Dokumentationsabgleich

Der gemeinsame Normsatz bleibt `spec/SPECIFICATION.md` plus
`spec/SPECIFICATION_EXTENSION_PYZ_PACK.md`, Revision 2. Dieses Review ändert
keinen Vertrag. PP-06B ist Voraussetzung; die erneute vollständige Testsuite
und der tatsächliche Apply werden über die bestehenden Bundle-Nachweise gebunden.

| Dokument | Review und geltende Grenze |
|---|---|
| Hauptspezifikation / PYZ-PACK-Ergänzung | Beide gemeinsam, unverändert; Ausnahmen nur im ausdrücklich benannten Bereich. |
| Commit-Plan / Spezifikationschangelog | Tatsächliche Results bestätigen Fortschritt; Vorbereitung, Apply und native Abnahme bleiben unterscheidbar. |
| README | Aktuelle PYZ-/Packfunktionen, normale Installation und separater Watcher; keine globale automatische Aktualisierung. |
| CLI-Hilfe | Pack verlangt Referenz, Entrypoint und genau eine Ausgabeart; keine implizite Ausführung oder Überschreiboption. Funktionale CLI-Tests statt Wortlautsnapshots. |
| docs/python-api.md | Gemeinsame API, explizite Referenz/Zielwahl, vollständiger Erfolg trotz Cleanup-Warnungen, kontrollierter In-Process-Import. |
| docs/pack.md / pack-examples.md | Bewusste Inhalte, keine Gitignore-Heuristik; Nutzdateien vor Entrypoint. Voll-Datei-, Diff-, Misch-, Diagnose- und Fehlerbeispiele. |
| docs/runtime-artifact.md | Geschlossenes Core-Profil ohne Watcher, endliche Identität, kanonische Bytes; alte Wheelproduktion ausdrücklich historisch. |
| docs/runtime-bootstrap.md | Eigene eingebettete Stdlib-Anleitung, begrenzter Vorcheck und bewusstes Vertrauen vor Ausführung; technische Isolation ist keine Sandbox. |
| scripts/pyz_bootstrap.py / runtime_bootstrap.py | Aktueller installationfreier PYZ-Helfer und ausdrücklich alter Wheelpfad; kein zweiter nativer Vollvalidator. |
| docs/result-format-2.md / result-format-3.md | Versionierte, unterschiedliche Schemata; alter Vertrag bleibt erhalten. `unavailable` ist gültig, beschädigte deklarierte Runtime kein voller Erfolg. |
| docs/result-runtime-production.md | Ein gemeinsamer Writer, Pinning und Selbstupdate, automatische PYZ oder begründetes unavailable; Pflichtvorlage bleibt erforderlich. |
| docs/result-publication-cifs.md | Bestehende Result-Retry-/Replace-Grenze; Pack bleibt No-replace ohne Stabilitäts-Retry. Reale CIFS-Abnahme bleibt offen. |
| CHAT_INSTRUCTIONS.md | Tatsächliches Resultformat zuerst; direkter und Python-only-Start, gemeinsamer Normsatz, eine kanonische ZIP, vollständige Bindung und Hash. |
| Test- und Watcherdokumentation | Aktuelle volle parallele Gates und manueller Nutzer-CI-Start; alte Bundle-Termine entfernt, abgeschlossene native Watcher-Abnahme historisch gebunden. |
| Build-/Releasebeschreibung | Normale Wheel/sdist-Installation bleibt samt Watcher; Result-PYZ enthält keinen Watcher. Kein Tag, Hostupgrade oder Release durch diesen Schritt. |

E-08 wurde fachlich gegen den Ablauf in der kanonischen Anleitung geprüft:
Bewusste Inhalte und vollständiges Result vor Pack, native Validierung derselben
Referenz, Prüfung der finalen ZIP, genau eine kanonische Übergabe und getrennte
Paket-/Chat-Identitäten. Weder Pack noch PYZ starten Versand oder Watcher.
Ein beschädigter fachlicher Nachweis wird nicht durch manuellen Fallback grün.

E-09 wurde gegen Plan- und Normauswahl geprüft: Eine ausdrückliche Featurewahl
hat Vorrang vor historischen Versionsverzeichnissen. Der gemeinsam erklärte Satz
ist vollständig zu lesen. Fehlende Satzteile und echte konkurrierende Fassungen
bleiben sichtbar; die alte Produktversion reaktiviert keinen abgeschlossenen Plan.
PatchHarbor-spezifische CI-/Testregeln gelten nicht ungefragt in anderen Zielprojekten.

E-04 und E-07 erhalten ausführbare Verhaltensnachweise in
`tests/test_pack_examples.py`: fünf Fälle über installierte CLI, PYZ-CLI und API.
Formale Gültigkeit einer kaputten Shell ist statischer Erfolg, tatsächlicher Apply
liefert einen Fehler. Diagnose erzeugt Lognachweise ohne Repositorymutation oder
Commit. Die Tests vergleichen Verhalten und maschinenlesbare Ergebnisse, keine
Prosa, Farben oder Markdowndarstellung.

Die vollständige Suite baut Ressourcen neu und wiederholt E-10 sowie Z-11/Z-12
auf den neuen Bytes. Bereits bestandene frühere Artefakte gelten dafür nicht.
Native Windows-/Python-3.12- und reale CIFS-Nachweise sind durch dieses Review
weder ausgeführt noch ersetzt. Sie gehören zur gesonderten finalen Abnahme.
