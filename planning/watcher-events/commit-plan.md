# PatchHarbor – Implementierungsplan für Exchange-Ereignisse

Stand: 6. Oktober 2026. Plan-ID: `watcher-events`, Revision 6.
Aktiv auf ausdrücklichen Nutzerauftrag; fünf geplante Commitschritte einschließlich
Dokumentationsbootstrap. Alle fünf geplanten Commits sind tatsächlich angewendet
und gepusht (5/5). Bundle 019 scheiterte anschließend an der fälligen CI;
die native Abschlussprüfung ist nicht bestanden. Bundle 020 bereitet eine
Korrektur des Windows-Testsetups innerhalb von WE-4 vor.
Zielversion noch nicht festgelegt.

Normative Grundlage: [Watcher-Spezifikation](specification.md) und
[zentrale Spezifikation](../../spec/SPECIFICATION.md), Abschnitt 3.2.1.
Dieser Plan ersetzt den abgeschlossenen RIV-Plan als aktiven Entwicklungsplan.

## 1. Vertrauenswürdige Ausgangsbasis

Maßgebliches tatsächliches Apply-Result:
`patchharbor-apply_Result_114833_1005_ce0723.zip`.
Vollständige SHA-256:
`dcecc3071979ecc113d3ab1a2b315affa7d45c52bfd5985eed31d7ba37daddd3`.

| Bindungsfeld | Wert |
| --- | --- |
| `repo_id` | `e7a93d72-62dc-4759-97e8-6bf6cdf10e90` |
| `base_commit` | `a02391dc045d42e317b3e766f0b1e9fa8dfadec1` |
| `state_fingerprint` | `7c9d2a24e397e0e5` |
| `fingerprint_algorithm` | `patchharbor-state-v1` |

Bundle 015 ist tatsächlich angewendet: ein Korrekturcommit, ein normaler Push
auf `dev`, saubere Arbeitskopie, 2.230 bestanden / 8 übersprungen jeweils seriell
und anschließend parallel. CI-Run `37306630290` bestätigt alle sechs Jobs
einschließlich Windows auf diesem Commit. Die 263 Result-Base-Dateien stimmen
mit dem Development-Ausgangsstand und dem lesend geprüften Apply-Stand überein.

Dieses ältere Result ist Format 1 ohne eingebettetes Wheel. Deshalb gilt für
den Bootstrap der dokumentierte bisherige Übergabeweg mit vertrauenswürdigem
lokalem Core und vollständiger Paket-/Referenzprüfung. Ein fehlendes Wheel ist
kein Grund, Repositorybindung oder Integritätsnachweise abzuschwächen.
Spätere Patches übernehmen ihre Bindung aus ihrem jeweils neuen maßgeblichen
Result; diese Tabelle ist keine dauerhafte Patch-Basis.

## 2. Geplante Commitfolge

| ID | Inhalt und Ergebnis | Abhängigkeit | Status |
| --- | --- | --- | --- |
| WE-0 | Spezifikation, Plan, zentrale Einordnung, Changelog und Abschlussvermerk des bisherigen Plans. Kein Watcher-Code. | bestätigtes Bundle 015 | durch Bundle 016 tatsächlich angewendet |
| WE-1 | Öffentliche Core-Abfrage der geprüften Beobachtungsziele, optional eingeschränkter automatischer Exchange-Scope, strukturierte Fortschritts-/Sperrbereitschaft. Bisheriger Aufruf ohne Einschränkung unverändert. | WE-0 angewendet | durch Bundle 017 tatsächlich angewendet |
| WE-2 | Native Linux-/Windows-Ereignisadapter, Filter und Ressourcenlebenszyklus; deterministische Ereignisabstraktion. Noch keine Aktivierung des neuen CLI-Betriebs. | WE-1 angewendet bzw. echter vorangehender Bundle-Zustand | durch Bundle 018 tatsächlich angewendet; native Windows-Prüfung offen |
| WE-3 | Fünfsekunden-Zustandsautomat, Startprüfung, Parallelität der Ereigniserfassung, sequenzieller Worker, Nachlauf, Konfigurationsaktualisierung und CLI-Umstellung. | WE-2 | durch Bundle 019 tatsächlich angewendet und gepusht |
| WE-4 | Vollständige Robustheits-/Plattformintegration, reale Ereignis-/Apply- und installierte Wheel-Nachweise, Dokumentationsabgleich und Abnahme. | WE-3 | durch Bundle 019 angewendet und gepusht; CI fehlgeschlagen, Korrektur in 020 vorbereitet |

Durch Bundle 019 angewendete Commits, in dieser Reihenfolge:
1. `feat(watcher): trigger scoped apply after five quiet seconds [WE-3]`
2. `test(watcher): verify native event apply and installed runtime [WE-4]`

WE-3 wurde vor Beginn der WE-4-Arbeiten separat nach vollständiger paralleler
Suite festgehalten: 2.368 bestanden / 7 übersprungen. Die erste Payload installiert
nur WE-3; der geprüfte Übergangsdelta erzeugt WE-4 erst nach dessen Vorgängercommit.
Der Endstand bestand die vollständige parallele Development-Prüfung. Apply prüfte
WE-3 parallel vor dem ersten Commit und WE-4 seriell sowie danach parallel vor
dem zweiten Commit. Danach erfolgten ein Push und die fällige CI.

Fortschritts- und Fehlernachweis für WE-3/WE-4: maßgebliches tatsächliches Result
`patchharbor-apply_Result_204527_1005_656f6e.zip`, SHA-256
`66470609a0f89bd81e22fcb9181f76c225d6e81009017e2a3deba460db08000f`.
Die vollständige Repositorybindung für Bundle 020 lautet:

| Bindungsfeld | Wert |
| --- | --- |
| `repo_id` | `e7a93d72-62dc-4759-97e8-6bf6cdf10e90` |
| `base_commit` | `1b7efeaf0569f4b7f798f564094b7bf478aa7c73` |
| `state_fingerprint` | `7c9d2a24e397e0e5` |
| `fingerprint_algorithm` | `patchharbor-state-v1` |

WE-3: Commit `e5b666bd09613fe6fbcec2e73efdab6d316f1982` nach 2.368 bestandenen
Tests / 7 Skips parallel. WE-4: Commit `1b7efeaf0569f4b7f798f564094b7bf478aa7c73`
nach jeweils 2.376 bestandenen Tests / 7 Skips seriell und anschließend parallel.
Ein normaler Push nach `dev`, saubere Arbeitskopie; alle 282 Base-Dateien und
Git-Modi sind gegen die eingefrorenen Zustände, Apply und Development geprüft.
Das Gesamtresult hat dennoch Exit-Code 1. Sein fehlendes `completed_commit`
hebt die durch Git und Ausführungslog bestätigten Teilfortschritte nicht auf.
Format-1-Fallback ohne eingebettetes Wheel; der vorherige Dry-Run bestätigt
keinen Apply.

[CI-Run 37373497123](https://github.com/cdoehn/patch-harbor/actions/runs/37373497123)
ist an den vollständigen Endcommit gebunden und wurde genau einmal gestartet.
Vier Jobs waren erfolgreich, der Windows-2025-Core-Lauf schlug fehl, der
Docker-Job für Ubuntu 24.04 wurde abgebrochen. Windows-E2E, Plattform- und
Packaging-Prüfungen wurden deshalb nicht ausgeführt; PowerShell 7 allein
bestätigt diese fehlenden Prüfungen nicht.

Im heruntergeladenen Windows-Bericht betreffen beide Fehler Setup und Teardown
derselben übergroßen Worker-Anfrage. Ihr automatisch erzeugter pytest-Node-ID
hat 1.048.653 Zeichen; der Testkörper wurde nicht erreicht. pytest übernimmt
den Node-ID in `PYTEST_CURRENT_TEST`, was die Windows-Grenze für Umgebungswerte
überschreitet. Die kurze explizite Kennung `oversized-request` behält den
Prüfwert von `MAX_REQUEST_BYTES + 1` Bytes und die Ablehnung vor Core-Aufruf bei.

Bundle 020: ein Korrekturcommit
`test(watcher): bound oversized-request test identity on Windows [WE-4-fix]`.
Keine Änderung an Laufzeitverhalten, Request-Limit oder Produktschnittstellen.
Vor Commit gelten die vollständigen seriellen und danach parallelen Apply-Gates,
gefolgt von einem normalen Push. Bundle 020 fordert keine zusätzliche CI an;
native Nachweise für seinen korrigierten Endstand bleiben offen. Die nächste
reguläre CI ist 024; ein vorgezogener Lauf benötigt einen ausdrücklichen Auftrag.

Fortschrittsnachweis für WE-0: Result
`patchharbor-apply_Result_163737_1005_90175f.zip`, SHA-256
`23b1f010aac400e0b7cc41135c37eee872dcf8401f19e780e09f141b112c88fc`.
Tatsächlicher Apply erfolgreich, kein Dry-Run; Commit
`1948cee7bb131ea4edfb18586296f47e2135051c`, ein normaler Push nach `dev`,
Arbeitskopie sauber. Vollständige serielle und danach parallele Suite jeweils
2.231 bestanden / 7 übersprungen. Alle 265 Base-Dateien und Git-Modi stimmen
mit Apply-Commit und Development-Ausgangsstand überein. Diese neue Referenz bindet
Bundle 017; Repository-ID und Fingerprint entsprechen der Tabelle oben.
Result weiterhin Format 1 ohne Wheel: dokumentierter lokaler Core-Fallback.

Fortschrittsnachweis für WE-1: Result
`patchharbor-apply_Result_173649_1005_fb7e6a.zip`, SHA-256
`7e148b1b889061e06d553988b35137a3e3a6fad7f30d374717130410618ea44b`.
Tatsächlicher Apply erfolgreich; Commit `d5ece5346158cafafe42c41c63c6a861305e534d`,
ein normaler Push nach `dev`, saubere Arbeitskopie. Vollständige serielle und
anschließend parallele Suite jeweils 2.266 bestanden / 7 übersprungen.
Alle 267 Base-Dateien und Git-Modi entsprechen Apply und Development-Ausgangsstand.
Dieses Result bindet Bundle 018; unveränderte Repository-ID und Fingerprint,
weiterhin Format-1-Fallback ohne eingebettetes Wheel. Der vorangehende Dry-Run
`patchharbor-apply_Result_173637_1005_ce705e.zip` ist kein Apply-Nachweis.

Fortschrittsnachweis für WE-2: Result
`patchharbor-apply_Result_191643_1005_9db1f1.zip`, SHA-256
`3ffd6c1338c65ed508fb01ff5e2d395429e61d14b9b33135be3362b5c194a8bc`.
Tatsächlicher Apply erfolgreich; Commit `93edc103feb20be996e1a754d8530fb90748d270`,
ein normaler Push nach `dev`, saubere Arbeitskopie. Vollständige serielle und
anschließend parallele Suite jeweils 2.333 bestanden / 7 übersprungen.
Alle 274 Base-Dateien und Git-Modi entsprechen Apply und Development-Ausgangsstand.
Dieses Result bindet Bundle 019. Format-1-Fallback ohne eingebettetes Wheel;
der vorausgehende Dry-Run ist kein Apply-Nachweis. Native Windows-Prüfung bleibt
für die fällige CI nach dem Endstand von Bundle 019 offen.

Tests für das jeweilige Verhalten entstehen im zuständigen Implementierungsschritt.
WE-4 ersetzt keine vorherigen Commit-Gates. Ein Schritt erhält erst nach Auswertung
des tatsächlichen Result die Kennzeichnung „durch Apply bestätigt“; Vorbereitung,
lokaler Test und Dry-Run sind getrennte Nachweise. Korrekturen bleiben ihrem
Schritt zugeordnet und werden samt Teilfortschritten transparent dokumentiert.

### WE-1 – Abnahmekriterien

- Beobachtungsziele stammen aus Core, physische Duplikate werden zusammengefasst.
- Unset, fehlende oder beschädigte Konfigurationen behalten die definierten Grenzen.
- Freigegebene Exchange-Scopes sind streng geprüft; leere/fremde Ziele erweitern
  den Scope nicht. Ein aktiver Download in B verhindert keinen erlaubten Scan in A.
- Keine manuelle Retry-Semantik und keine vorab freigegebenen Kandidatentokens.
- Sperrbereitschaft prüft keine Bundle-Inhalte und reserviert keine Apply-Sperre.

Durch Bundle 017 angewendete Schnittstellen: `api.watch_targets()`, `api.watch_control_paths()`,
`api.apply_next(exchanges=...)`, `api.apply_readiness(lock)` und
`RunReport.automatic`. Verhaltensprüfungen in `tests/test_watch_targets_e2e.py`
decken auch Root-Ersatz vor Mutation, explizit leere Scopes, Fehlertext-Verwechslung,
echte Sperrkonkurrenz, unverbrauchte Dry-Runs und ausbleibende automatische Retries
fehlgeschlagener Identitäten ab. Ereignisadapter und CLI-Zeitsteuerung folgen.

### WE-2 – Abnahmekriterien

- Kein rekursiver Exchange-Watch, keine Auslösung durch reine Lesezugriffe.
- Native Create/Write/Delete/Rename-Ereignisse und kontrollierter Stop.
- Root-Ersatz, Queue-Überlauf und Backend-Fehler sind strukturiert erkennbar.
- Keine neuen Laufzeitabhängigkeiten; Imports auf anderer Plattform bleiben sicher.

Vorbereitet sind der Ereignisvertrag `events.py` und die getrennten nativen
Adapter `platform/linux.py` und `platform/windows.py` im Watcher-Paket.
Die interne Factory liegt in `platform/__init__.py`; Core bleibt unabhängig. Feste Beobachtungsgenerationen, gefilterte Vorfahrenbeobachtungen,
begrenzte/coaleszierte Ereignisse, binäre Decoder, strukturierte Fehler und
unterbrechbare native Warteoperationen stehen getrennt von Timer-/Apply-Politik.
Nachweise und technische Grenzen: [Adaptervertrag](../../docs/watcher-event-adapters.md).
Echte Linux-Ereignisse sind lokal prüfbar; Windows-Transportsimulationen ersetzen
die ausstehende native Windows-CI nicht. Die CLI-Aktivierung bleibt WE-3.

### WE-3 – Abnahmekriterien

- Kein periodischer Scan oder Worker im Leerlauf; mindestens fünf Sekunden Ruhe.
- Startbestand, Reset unmittelbar vor Ablauf und Änderungen während Apply sind korrekt.
- Ein Worker, mehrere offene Wurzeln, Fortschrittsnachlauf und Sperrwiederaufnahme.
- Konfigurationsänderungen aktualisieren Ziele; `--poll-interval` wird nicht umgedeutet.
- Keine verlorenen Generationen, Fehlerwiederholungen oder Result-Endlosschleifen.

WE-3 bereitet die aktive CLI-Anbindung vor: monotone Fristen je Wurzel,
Generationserhalt während des sequenziellen Workers, private Scope-/Fortschritts-
Übertragung, gefilterte Kontrollpfade und Sperrbereitschaft mit begrenztem Backoff.
Core liefert zusätzlich unverbindliche `WatchControlPaths.exchange_paths` für
fehlende Wurzeln. Diese Pfade erlauben nur Beobachtung ihrer Wiederkehr; sie
sind keine freigegebenen `ExchangeWatchTarget`-Objekte. Der bisherige
`--poll-interval`-Aufruf wird abgewiesen. WE-4 ergänzt die Abnahme des Gesamtbetriebs.

### WE-4 – Abnahmekriterien

- Sämtliche Fälle aus Abschnitt 8 der Spezifikation sind nachgewiesen.
- Native Linux- und Windows-Nachweise beziehen sich auf den tatsächlichen Endstand.
- Wheel-/Offline-Runtime, Fallback, Prozessstop und bestehende Core-Sicherheit bestehen.
- README, API-Dokumentation, zentrale Spezifikation und Changelog beschreiben den
  implementierten Betrieb. Geplante und bestätigte Eigenschaften sind unterscheidbar.

WE-4 ergänzt reale Ereignis-/Worker- und installierte Wheel-Nachweise sowie die
[Betriebs- und Abnahmedokumentation](../../docs/watcher-events.md). Tests prüfen
unter anderem weiter eintreffende Ereignisse, mehrere vorhandene Bundles,
Fehlversuche ohne automatischen Retry und einen unabhängigen aktiven Download.
Die private Übergabe gibt CI-Nachweise im Result-Ausführungslog zurück. Lokales
Linux und Windows-Simulationen ersetzen nicht die noch ausstehende native CI.

## 3. Bundle-Grenzen und CI

Bundle 016 enthält ausschließlich WE-0 mit einem Dokumentationscommit. Danach
ist vor weiterer Entwicklung das neue Result maßgeblich. Die beauftragte
Bootstrap-Auslieferung aktiviert keine S-Schleife und liefert keine Folgebundles.

Vorgesehene Gruppierung: 017 = WE-1, 018 = WE-2, 019 = WE-3 und WE-4 als zwei
echte aufeinanderfolgende Zustände. Damit liegt die regulär fällige CI auf dem
vollständigen Endstand. Die Gruppierung darf bei belegten Korrekturen oder
praktischen Schrittgrenzen angepasst werden; CI-Zählung nicht zurücksetzen.
Mehrere Commits pro Bundle sind erlaubt; auftragsbezogene Diagnosen dürfen null
Commits haben. Keine künstlichen W/R/C-Phasen aus einem bereits fertigen Endzustand.

GitHub bleibt ausschließlich `workflow_dispatch`. Die reguläre CI zu Bundle 019
ist ausgewertet; der nächste reguläre Termin ist 024. Zusätzliche Läufe nur auf ausdrücklichen Nutzerauftrag.
016 bis 018 fordern keine CI an. Bei fälligen Bundles dispatcht der Apply-Entrypoint erst
nach dem einzigen erfolgreichen Push genau einmal und wartet auf alle Jobs
einschließlich Windows. Volle Commitbindung, Run-ID/URL, Job-/Testnachweise und
Fehlerdiagnosen stehen im Result-/Ausführungslog. Kein automatischer Retry.
Zwischenbundles werden nicht wegen fehlender eigener CI blockiert.

Falls sich der finale Code durch Korrekturen über den fälligen CI-Stand hinaus
ändert, bleiben ausstehende native Abschlussnachweise offen. Linux-Belege oder
eine ältere CI werden nicht als Nachweis für den veränderten Endstand ausgegeben.
Kein zusätzlicher CI-Lauf wird aus diesem Plan allein automatisch abgeleitet.

## 4. Tests, Übergabe und Fortschritt

- Development ausschließlich vollständige parallele Testsuite mit strukturiertem
  Bericht, Quellenbindung und Exit-Code. Keine neuen Prosa-/Layouttests für WE-0.
- Apply prüft jeden Zwischenstand vor seinem Commit vollständig parallel.
- Nur am Bundle-Endstand: vollständig seriell, danach vollständig parallel auf
  demselben unveränderten Stand, vor letztem Commit und genau einem normalen Push.
  Der letzte parallele Lauf erfüllt zugleich das Commit-Gate; kein redundanter Lauf.
- Fehler verhindern weitere Commits/Push entsprechend dem erreichten Stand;
  Teilcommits werden im nächsten tatsächlichen Result ausgewertet.
- Development führt keine Git-Mutationen aus. Commits entstehen ausschließlich
  im geprüften Apply-Entrypoint, Zielbranch `dev`, kein automatisches Tagging.
- Genau eine finale kanonische ZIP; Struktur, Payload, Hashes, Bindung, Größe und
  volle SHA-256 werden an der endgültigen Übergabedatei erneut geprüft.
- Tests laufen als eigene Prozesse. Bei noch laufenden Tests frühestens nach
  300 Sekunden erneut durch die KI kontrollieren; zuverlässig gemeldetes Testende
  darf sofort ausgewertet werden. Externe Wartezeit erzeugt keine Modellaufrufe.

Der dauerhafte Fortschritt steht zusätzlich unter
`exchange/reports/patchharbor-dev-loop-state.json` im projektspezifischen Exchange.
Verbrauchte Results werden erst bei bestätigter Folgebundle-Auslieferung markiert.
Der alte Plan bleibt als abgeschlossen dokumentiert; dieser steht bei 5/5
bestätigten Commitschritten mit offener Korrektur und nativer Abnahme. S/N und die Grenze von fünf aufeinanderfolgenden
fehlgeschlagenen tatsächlichen Bundles bleiben gemäß lokalen Rollenregeln gültig.

## 5. Abschluss

Abschluss erst nach bestätigtem Apply aller fünf Schritte, vorgeschriebenen
lokalen Gates, tatsächlichem Push und den erforderlichen nativen Endstand-
Nachweisen einschließlich Windows. Dann Zustand als abgeschlossen speichern,
automatische Fortsetzung deaktivieren und kein weiteres Bundle oder neuen Plan
ohne Nutzerauftrag erzeugen. Versionswechsel, Release und Umstellung der global
installierten Engine sind keine impliziten Schritte dieses Plans.
