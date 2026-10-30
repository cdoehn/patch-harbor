# RF-07 – Eine gepflegte Bootstrapquelle

Basis: bestätigtes Result 063, Commit `3afcc56b00ccdc9818b2436ecde999b46176b1ea`.
Bundle 064 bereitet genau einen Commit vor; sein tatsächlicher Apply, das volle
parallele Commit-Gate und der Push sind noch nicht bestätigt.

## Pflege und Buildgrenze

Die einzige manuell gepflegte Programmquelle ist `scripts/pyz_bootstrap.py`.
Sie bleibt in RF-07 bytegleich (SHA-256 `043e5afd0e3ffee49f8bfeb6b226193dafd9b194dc257907a9054d750206b343`).
Der ausführbare Block in `CHAT_INSTRUCTIONS.md` ist ein erzeugtes Artefakt.
Seine vorhandene Kennung `# PATCHHARBOR-PYZ-BOOTSTRAP` bleibt bestehen;
zusätzliche eindeutige Generierungsmarker begrenzen ausschließlich diesen Block.

Nach einer bewussten Änderung am Skript:

```text
python scripts/render_chat_bootstrap.py --write
python scripts/render_chat_bootstrap.py --check
```

Der Generator normalisiert Zeilenenden des Programms auf LF, erhält alle Bytes
außerhalb seines Bereichs und verändert bei identischem Ergebnis keine Datei.
Er prüft Python-3.10-Syntax, führt den Quellcode aber nicht aus. Fehlende,
mehrdeutige oder vertauschte Marker und ungeeigneter Code führen zum Fehler.
Die umliegende Dokumentation lässt sich unabhängig bearbeiten.

Die PEP-517/660-Hooks für Wheel, sdist und Editable prüfen die erzeugten Bytes
**vor** dem eigentlichen Build. Kein stilles Regenerieren, kein Core-Import,
keine Netzwerk-/Installeraktivität im Checker. Sein Code wird am eigenen
Quellbaum geladen, ohne Bytecode-Dateien für diesen Check zu erzeugen.
Metadata-Hooks und setuptools-Argumente bleiben erhalten; Editable besitzt
weiterhin absichtlich keine vorbereitete portable Runtime.

Der Release-Stager und sdist transportieren genau
`scripts/pyz_bootstrap.py` und `scripts/render_chat_bootstrap.py` zusätzlich als
Build-Eingaben. Andere Wartungs-/CI-Skripte bleiben ausgeschlossen. Wheel und
PYZ erhalten die fertige eigene Anleitung, keine zusätzliche Scriptdistribution
oder Runtime-Abhängigkeit. Die normale Source-/sdist-Installation bleibt offline
mit vorhandenen Buildabhängigkeiten möglich.

## Erhaltene Verträge und Nachweise

| Vertrag | Nachweis |
| --- | --- |
| Gleiche ausführbare Bytes, LF, Wiederholbarkeit und Erhalt unabhängiger Inhalte | `test_bootstrap_generation.py`; es werden Code-/Generierungsverträge geprüft, keine Prosa oder Darstellung |
| Kein Ausführen bei Generierung; ungültige/mehrdeutige Eingaben ohne Änderung abweisen | derselbe Test mit absichtlich bei Ausführung fehlschlagendem Quellcode; Fehlerfälle für Marker, Syntax, Encoding und Codeblockgrenze |
| Prüfen ohne Reparatur, erst explizites `--write`, keine Fremdmodulauswahl | isolierter `-I -S -B`-CLI-Test und an den eigenen Quellbaum gebundene Build-Hooks |
| Builds stoppen vor Artefakterzeugung und erhalten Frontendargumente | alle drei Hooks; fehlender Checker/Source, veralteter Block, Mehrdeutigkeit und Syntaxfehler |
| Source, Wheel, sdist und PYZ tragen passende Ressourcen | vorhandene reale Packaging-/Installations-/Roundtriptests; enge sdist-Skriptliste und Bytevergleich der ausführbaren PYZ-Anleitung |
| Eigene Resultanleitung funktioniert im frischen stdlib-Prozess | bestehende `test_result3_embedded_bootstrap.py` und `test_pyz_result_e2e.py`; Pack/Validate gegen dasselbe unveränderte Result |
| Rechte, Handle-/Importgrenzen, Beschädigung und technische Nichtverfügbarkeit | unveränderte Bootstrap-/CPython-/Runtime-Verhaltenstests |
| Unveränderte 1.4.0-Referenzen, ursprüngliche IDs/Hashes, keine Vertragsumdeutung | unveränderte Originalfixtures und Kompatibilitätstests |

Es entfällt kein bestehender Testfall. Die Bootstrap-Logik, Core und Watcher,
API/CLI-Signaturen, Datenformate und die drei Normdateien bleiben unverändert.
Der allgemeine Handlungsvertrag trennt weiterhin Vorcheck, Herkunft und native
Resultvalidierung; technische Nichtverfügbarkeit behält den sicheren Fallback.

## Lokaler Prüfumfang

Development führt nur folgende Auswahl plus die privaten Tests des tatsächlich
auszuliefernden Entrypoints parallel aus. Auswahl, Collection, Outcomes und
Quelldateibindung werden im Exchange-Bericht dokumentiert. Ein Skip bleibt ein
fehlender Nachweis, kein Erfolg. Keine vollständige Development-Suite.
Die vollständige parallele Suite läuft ausschließlich im Apply vor dem Commit.
CI startet ausschließlich Christian; native Windows-/Interpreter-Lanes werden
hier nicht durch Simulation oder einen Linux-Lauf ersetzt.

- `tests/test_bootstrap_generation.py`
- `tests/test_pyz_bootstrap.py`
- `tests/test_bootstrap_python_compat.py`
- `tests/test_result3_embedded_bootstrap.py`
- `tests/test_result_capabilities.py`
- `tests/test_compatibility_140.py`
- `tests/test_runtime_profiles.py`
- `tests/test_runtime_packaging.py`
- `tests/test_packaging_e2e.py`
- `tests/test_runtime_bootstrap.py`
- `tests/test_producer_compatibility.py`
- `tests/test_result_runtime_roundtrip.py`
- `tests/test_pyz_result_e2e.py`
- `tests/test_runtime_pyz.py`
- `tests/test_pyz_resources.py`
- `tests/test_pyz_result_resources.py`
- `tests/test_python_variants.py`
- `tests/test_python_compat.py`
- `tests/test_release_audit.py`
- `tests/test_chat_contract.py`
- `tests/test_bundle_handoff.py`
- `tests/test_architecture.py`
