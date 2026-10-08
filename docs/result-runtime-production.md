# PYZ in erzeugten Results

Ab PP-06B erzeugt der gemeinsame Core Result-Format 3 mit Runtime-Metadaten 2.
Eine normale Wheel-, Source- oder sdist-Installation enthält die vorbereiteten
Ressourcen für genau eine kanonische Core-PYZ ohne Watcher. Neue Results betten
kein zusätzliches Runtime-Wheel ein. Der normale Installationsvertrag mit Wheel,
sdist, CLI und separat installiertem Watcher bleibt bestehen.

Ein Source-/Editable-Checkout ohne vorbereitete Ressourcen liefert
`unavailable/source_not_prepared`. Das ist eine Diagnose, kein Buildauftrag.
Eine noch laufende alte Installation produziert weiterhin ihr eigenes Format;
ein Repository-Patch aktualisiert weder globale Installation noch laufenden Dienst.

Nach Repositoryauflösung und vor Payload/Entrypoint fixiert der Request Runtime
und statische Vorlage gemeinsam aus seinem tatsächlich geladenen Erzeuger. Der
spätere Snapshot beschreibt den tatsächlichen Repositoryzustand. Selbst bei einem
Update gleicher Version während Apply stammen Runtime und Anleitung aus den
fixierten alten Bytes, während der Snapshot schon den neuen Commit enthalten darf.
Ein frischer Prozess nutzt die neue Installation; ein alter erkennt geänderte
Ressourcen an seinem beim Import festgehaltenen Producer-ID.

| Befund | Ergebnis |
|---|---|
| Optionale Runtime fehlt, ist beschädigt oder zu groß | Vollständiges Result mit `unavailable`, solange alle Pflichtdaten nachweisbar bleiben |
| Runtime defekt, eigene Pflichtvorlage noch gültig | Begrenzte Vorlagenprüfung gegen geladenen Producer-ID, Rezept, Größe und SHA; keine behauptete Runtime-Vollvalidierung |
| Pflichtvorlage oder Snapshot fehlt/ist unprüfbar | Echter Resultfehler und vorhandene Notfalldiagnose |
| Schreiben, Verifikation oder Publikation scheitert | Kein fertiges Teil-ZIP; Primärergebnis, Log und letzter geprüfter Kontext bleiben erhalten |
| Abbruch oder Programmierfehler | Keine Umdeutung in erfolgreichen Runtime-Fallback |

Result-Sync, No-follow, atomare Ersetzung, typisierte endliche CIFS-Retries,
gemeinsames Wartebudget und geprüfte SHA bis zur Veröffentlichung bleiben
unverändert. Runtime-Fallback wird vor dem ZIP-Schreiben entschieden und entfernt
keine Snapshot-, Änderungs- oder Logdaten. Warnungsbehaftete Results sind weiterhin
kein warnungsfreier Archivierungs-/Recovery-Erfolgsbeweis. `pack` besitzt seinen
separaten No-replace-/No-retry-Vertrag.

Die Packaging-Prüfungen installieren aus Wheel, Source und sdist, entfernen
Buildquellen und Installer-Caches und erzeugen drei echte Result-/PYZ-Generationen.
Ab der zweiten Generation läuft ausschließlich die vorherige Result-PYZ in einem
frischen Prozess, ohne Neuinstallation. Ihre SHA-256, Größe und Bytes müssen
identisch bleiben; schreibgeschützte Runtimeverzeichnisse werden mitgeprüft.
Die Self-update-Tests ersetzen eine echte isolierte Installation während Apply
und prüfen erfolgreichen sowie fehlgeschlagenen Entrypoint mit neuem Commit.

E-10 entnimmt den Bootstrap ausschließlich der eigenen Root-Anleitung des ersten
neuen Results aus einer echten Installation. Der frische Python-only-Prozess
packt und validiert gegen genau dieses Result. Danach führen vollständige Dateien,
Diff-Payload und gemischte Pakete einen regulären Apply im isolierten Repository
aus. Dieselbe PYZ unterstützt Kontext, Registry/Konfiguration, Result-Erzeugung
und den älteren `fs run`-Weg. Der installierte Watcher nutzt den gemeinsamen Core;
Watcher-Code wird nicht in die PYZ aufgenommen.

Pro Generation werden Artefaktgröße, komprimierter Result-Mehrbedarf und maximale
`tracemalloc`-Python-Allokation unter `foreign-repository-*-metrics.json` erfasst.
Die kleinen Fixture-Repositories haben Grenzen von 2 MiB komprimiertem Mehrbedarf
und 128 MiB Python-Allokation. Das ist keine Messung des gesamten Prozess-RSS und
keine Behauptung über beliebig große Snapshots. Native Windows-/Python-3.12-CI
startet nur Christian manuell; reale Linux→Windows-CIFS-Nachweise bleiben separat.

Der [Bootstrap-Vertrag](runtime-bootstrap.md) trennt begrenzte Runtime-Vorprüfung,
Herkunftsentscheidung und vollständige native Referenzvalidierung. Defekte
Runtime-Zusätze dürfen nicht als native Vollintegrität ausgegeben werden.
