# Runtime in erzeugten Results

Seit RIV 1.e erzeugen alle regulären Bundle-, Apply-, Dry-Run- und Watcher-Pfade
Result-Format 2. Eine normale, unveränderte Installation liefert das kanonische
Wheel. Ein unvorbereiteter Source-/Editable-Checkout liefert dagegen
`unavailable/source_not_prepared`; dies ist eine Diagnose und kein Buildauftrag.

Nach sicherer Repositoryauflösung und vor Payload/Entrypoint fixiert der Request
Runtime-Bytes und kanonische statische Vorlage gemeinsam. Die spätere
Snapshotaufnahme erfasst den tatsächlichen Repositoryzustand. Auch nach einer
Neuinstallation derselben Version im Entrypoint stammen Runtime und Vorlage aus
dem ursprünglichen Prozess; das Result darf bereits den neuen Commit enthalten.
Ein frisch gestarteter Prozess verwendet die neue Installation. Ein alter Prozess
erkennt geänderte Ressourcen anhand ihrer Inhaltsidentität.

| Befund | Ergebnis |
|---|---|
| Runtime fehlt, ist beschädigt oder überschreitet das Zusatzbudget | Vollständiges Result mit begründetem `unavailable` und Warnung, soweit Pflichtdaten publizierbar sind |
| Pflichtvorlage oder Snapshot fehlt | Echter Result-Fehler; bisherige Notfalldiagnose |
| Schreiben, Verifikation oder atomare Publikation scheitert | Kein fertiges Teil-ZIP; Primärergebnis und Ausführungslog bleiben in der Notfalldiagnose |
| Snapshot war bereits erfolgreich erfasst | Notfallbericht behält dessen geprüften Kontext, auch nach einem neuen Commit |
| Abbruchsignal | Keine Umdeutung in einen Runtime-Fallback oder erfolgreichen Lauf |

Der gemeinsame interne Dokumentensatz hält Report, Handoff, Manifest, Kontext
und Runtime zusammen. Beide Erzeugungswege nutzen denselben Publikationshelfer;
der Runtime-Fallback wird vor Öffnen der temporären ZIP entschieden.

Nur eigene temporäre Dateien werden entfernt. Vorhandene fremde Dateien und
geänderte Reservierungen bleiben geschützt. Runtime-Fallback entfernt keine
Snapshot-, Änderungs- oder Untracked-Dateien. Results mit Warnungen sind weiterhin
kein warnungsfreier Archivierungs- oder Recovery-Nachweis.

Die installierten Packaging-Tests erzeugen für Wheel-, Repository- und
sdist-Installation jeweils Result A, installieren dessen enthaltenes Wheel in
eine frische Umgebung und wiederholen dies bis Result C. Wheel-SHA und Größe
bleiben identisch. Die Standardinstallationen werden schreibgeschützt geprüft;
ursprüngliche Builds und Installer-Caches stehen dabei nicht mehr zur Verfügung.
Die zusätzlichen Self-update-Tests ersetzen eine echte isolierte Installation
während eines wirklichen Apply und prüfen Erfolg sowie Fehler nach dem Commit.

Die Result-Roundtrips messen pro Generation kanonische Wheel-Größe, zusätzliche
komprimierte ZIP-Bytes und maximale durch `tracemalloc` erfasste Python-Allokation.
Für das kleine Fremdprojekt gelten Regressionsgrenzen von 2 MiB komprimiertem
Mehrbedarf und 128 MiB Python-Allokation. Dies ist keine Aussage über den gesamten
Prozess-RSS oder beliebig große Repository-Snapshots. Messwerte werden im jeweiligen
isolierten Testverzeichnis als `foreign-repository-*-metrics.json` gespeichert.
Native Windows-Nachweise kommen aus dem fälligen CI-Lauf; ein lokaler Linux-Test
ersetzt sie nicht.

Die Verwendung des eingebetteten Wheels folgt dem separat geprüften
[Bootstrap- und Fallback-Vertrag](runtime-bootstrap.md). Ein beschädigter
Runtime-Zusatz darf nicht als native Vollintegrität ausgewiesen werden;
Repository-only-Evidence gehört ausschließlich zum dort beschriebenen bisherigen
Übergabeweg und verändert keine Archivierungs-/Recovery-Regeln.


## PP-06A: prepared PYZ resources before the writer switch

The current production selection remains Result 2 until PP-06B. The private
`capture_pyz_result_resources` path prepares immutable Format-3 metadata and
PYZ bytes through the same Result writer/publication boundary. A payload carries
its format, and a resource-budget fallback preserves that format's unavailable
schema. No new user switch or CLI command is introduced.

Runtime and required template are pinned before repository mutation. A failed
optional PYZ resource does not discard a separately proven mandatory template:
the loaded producer ID, canonical recipe, exact template length/hash and bounded
own-directory/own-ZIP reads must agree. No other installation, cache, builder or
network is consulted. Missing/corrupt required documents retain normal Result
failure and emergency diagnostics; cancellation/programming failures propagate.

The preparation tests generate real fixture Results through the existing routes,
including failed Apply, and check full Format-3 integrity and snapshot/log
preservation. The production switch, normal-installation self-update and three
actual Result/PYZ generations remain PP-06B gates, including first-output E-10.
