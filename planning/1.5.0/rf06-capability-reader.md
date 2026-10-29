# RF-06A: Geschlossene Capability-Profile lesen

Basis: bestätigtes Bundle 061, Commit `5ee194153d1338777cb6b77a60b7854e7b009388`.
Der bestehende RF-06-Auftrag verlangt ausdrücklich einen Leser vor der
Writer-Umstellung. Zwei echte, jeweils im Apply vollständig parallel geprüfte
Commits machen diese Reihenfolge nachvollziehbar: A bereitet die Leser vor;
B stellt Writer um und entfernt die zugeordneten Legacy-Pfade und Tests.
RF-06 bleibt bis zur bestätigten Abnahme von B offen.

## Begrenzter Produktumfang

Die drei bestehenden Prüfstellen in `result_pyz.py`, `scripts/pyz_bootstrap.py`
und dem ausführbaren Bootstrap in `CHAT_INSTRUCTIONS.md` akzeptieren genau
`result_formats: [1, 2, 3]` und `[3]`. Das ist bereits in PYZ/PACK FMT-03 und
im aktiven Plan festgelegt. Es gibt keinen neuen Formatstand oder Normvertrag.
Die Bootstrap-Kopie bleibt bytegleich zum Skript; die dauerhafte Erzeugung aus
einer einzigen gepflegten Quelle ist weiterhin RF-07 vorbehalten.

Patchformate bleiben genau `[1]`. Reihenfolge, Ganzzahltypen ohne boolesche Werte,
geschlossene Felder und Operationen, Deskriptoren, Pfade, Hashes, Rezeptidentität,
Ressourcenbudgets und unavailable-Regeln bleiben verbindlich. Der Bootstrap
liefert weiterhin nur eine Vorprüfung; Pack/Validate prüfen den gesamten Result.
Statische Leser führen die beschriebene PYZ nicht aus.

Der Writer behält `[1, 2, 3]`, solange der Produzent die alten Resultformate noch
liest. Seine Deklaration wird erst in RF-06B mit dem tatsächlichen Abbau auf `[3]`
umgestellt. Result-1/2-, Wheel- und historische Buildpfade bleiben hier unverändert.
Originale 1.4.0-Fixtures, Artefaktbytes, IDs/Hashes, Produktversion, öffentliche API,
CLI und Watcher-Verträge werden nicht umgeschrieben.

## Verhaltenstests und vollständige Fallzuordnung

`test_result_capabilities.py` ergänzt 33 Fälle:

- Zwei gültige Profile behalten Originalbytes, alle vier Bindungswerte und die
  tatsächlich gelesenen Fähigkeiten; native Reader/Pack/Validate und Bootstrap
  prüfen statisch ohne Prozess, Netzwerk, Runtime-Vorbereitung oder API-Import.
  Die synthetische PYZ enthält einen Ausführungswächter, keine ausführbare API.
- 15 ungültige Resultlisten: leere/alte/Teil-Listen, Duplikate, falsche Reihenfolge,
  Zukunftsformat, boolesche Werte, Fließkommazahlen, Text, Skalar, null und Objekt.
  Native APIs liefern SOURCE_ERROR, der Bootstrap lehnt ab; keine Patchdatei entsteht.
- Sieben ungültige Patchlisten werden für jedes der beiden gültigen Resultprofile
  abgelehnt (14 Fälle); die neue Alternative lockert den Patchvertrag nicht.
- Beide Capability-Profile bleiben bei `unavailable` unzulässige Runtime-Behauptungen.

Der bestehende Packaging-Durchstich
`test_own_embedded_bootstrap_runs_in_fresh_process_and_pack_uses_same_result`
behält beide bisherigen Fälle und erweitert jeden um beide Profile:

| Bisherige Parameter-ID | Neue Parameter-IDs | Erhaltenes Verhalten |
| --- | --- | --- |
| `[False]` | `[False-original_caps]`, `[False-current_caps]` | eigene gebaute PYZ aus eigenem Handoff; Pack/Inspect/Validate und exakte Referenz-SHA |
| `[True]` | `[True-original_caps]`, `[True-current_caps]` | Bootstrap-Vorprüfung reicht nicht; native Prüfung lehnt manipulierten Snapshot ab, kein Output |

Die Metadatenvarianten in diesen Tests sind ausdrücklich synthetisch; die
aktuelle Writer-Deklaration wird damit nicht als umgestellt ausgegeben.
Die Prozesse laufen isoliert mit `-I -S -B`, ohne Installer, Netzwerk, weitere
Prozesse oder Watcher. Keine bisherigen Verhaltenstests werden entfernt.
Die zwei bisherigen Node-IDs gehen in vier neue über; zusammen mit den 33 neuen
Fällen wächst die Produktauswahl netto um 35. Kein neuer Skip oder Xfail.

## Ausgewählte parallele Development-Prüfung

Development führt ausschließlich die folgende änderungsbezogene Auswahl aus.
Sie prüft beide Capability-Leser, ausführbaren Handoff, native Referenzprüfung,
unveränderte 1.4.0-Artefakte, gültige und beschädigte/unavailable-Runtimes,
gemeinsame Ressourcenlimits, Pack/Publikation und Architekturgrenzen.
Der Controller-Bericht muss dieselbe Collection auf allen Workern und eine
Bindung an diesen Quellstand bestätigen. Die bisherigen Fälle und Outcomes
werden mit dem vollständigen Apply-Bericht von Bundle 061 abgeglichen;
ausschließlich die oben zugeordneten Erweiterungen sind erlaubt.

- `tests/test_result_capabilities.py`
- `tests/test_result_format3.py`
- `tests/test_result_format3_consumers.py`
- `tests/test_result3_embedded_bootstrap.py`
- `tests/test_pyz_bootstrap.py`
- `tests/test_compatibility_140.py`
- `tests/test_reference_validation.py`
- `tests/test_reference_validation_errors.py`
- `tests/test_pyz_resources.py`
- `tests/test_pyz_result_resources.py`
- `tests/test_pyz_result_e2e.py`
- `tests/test_pack_api.py`
- `tests/test_pack_sources.py`
- `tests/test_pack_examples.py`
- `tests/test_architecture.py`
- `tests/test_architecture_boundaries.py`
- `tests/test_chat_contract.py`
- `tests/test_release_audit.py`

Zusätzlich prüft Development die 23 bestehenden privaten Übergabefälle gegen
den tatsächlich erzeugten Entrypoint. Es ist keine lokale Vollsuite.
Der Watcher führt vor dem tatsächlichen Commit die vollständige parallele
Suite mit `python tools/run_tests.py --suite all --report ...` aus, prüft
Quellbindung und Ergebnisnachweise und pusht erst nach erfolgreichem Commit
einmal normal. CI startet ausschließlich Christian. Native Windows- und
andere Interpreter-Abnahmen werden durch diese lokale Auswahl nicht behauptet.
