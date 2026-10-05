# Result-Format 2: festgelegter Leservertrag

Stand `1.d.C`. Der produktive Writer bleibt Format 1; Fixtures prüfen bereits
Format 2. Allgemeine Referenzgültigkeit und Archiv-/Recovery-Erfolg bleiben
getrennt. Der Leser importiert, installiert oder startet keinen Wheel-Code.

Ein Format-2-Manifest enthält die bisherigen geschlossenen Felder und zusätzlich
genau `runtime`. Dessen Felder sind `status`, `reason`, `metadata` und `wheel`.
Deskriptoren besitzen genau `path`, `size` (Integer, nicht Bool, nicht negativ)
und `sha256` (64 kleingeschriebene Hexzeichen). `metadata.path` ist immer
`runtime/runtime.json`; der einzige Wheel-Pfad ist
`runtime/patchharbor-<version>-py3-none-any.whl`. Alle Größen und Hashes beziehen
sich auf die tatsächlichen Bytes. Root-CHAT und environment.json sind in Format 2
Pflicht; die bisherige optionale Legacy-Paarung in Format 1 bleibt lesbar.

`runtime.json` hat genau folgende Felder:

| Feld | `embedded` | `unavailable` |
|---|---|---|
| `marker` | `patch-harbor-runtime` | gleich |
| `format_version` | Integer `1` | gleich |
| `status` | `embedded` | `unavailable` |
| `reason` | `null` | einer der acht Gründe unten |
| `distribution` | `patchharbor` | gleich, bezeichnet den bekannten Produzenten |
| `version` | Version aus dem Wheel-Rezept | belegte Produzentenversion oder `null` |
| `requires_python` | Anforderung aus dem Rezept | belegte Anforderung oder `null` |
| `content_id` | vollständige Rezept-Inhalts-ID | `null` |
| `content_id_algorithm` | `patchharbor-runtime-content-v1` | `null` |
| `wheel` | exakt derselbe vollständige Deskriptor wie im Manifest | `null` |
| `tags` | `["py3-none-any"]` | `null` |
| `runtime_dependencies` | `[]` | `null` |
| `provenance` | geschlossenes Objekt unten | `null` |
| `capabilities` | geschlossenes Objekt unten | `null` |

`provenance` besitzt genau `mode="canonical_resources"`, `source_commit`
(vollständiger belegter Commit oder `null`, exakt wie im Rezept) und
`recipe_format_version=1` (Integer, nicht Bool).

`capabilities` besitzt genau `operations=["inspect_patch","validate_patch"]`,
`patch_formats=[1]` und `result_formats=[1]` oder `[1,2]`. Die geordneten
Formatlisten enthalten ausschließlich Integer. Angaben beschreiben den
Produzenten; der Leser gewährt dadurch weder Ausführungsrechte noch einen
Apply-/Recovery-Erfolgsnachweis. Unbekannte Operationen oder Formate erweitern
dieses geschlossene Schema nicht stillschweigend.

Unavailable-Gründe: `source_not_prepared`, `source_changed`, `artifact_missing`,
`artifact_mismatch`, `artifact_corrupt`, `artifact_unsupported`, `resource_limit`,
`read_error`. Im Runtime-Namensraum steht dann ausschließlich runtime.json.
Ein Run mit diesem Diagnosezustand enthält mindestens eine Warnung; der bisherige
konservative Archiv-/Recovery-Verbraucher akzeptiert Warnungen nicht als Erfolg.
Es gibt keine erfundene Inhalts-ID, kein Wheel und keine unbelegten Fähigkeiten.

Root-Manifest, Runtime-Metadaten und Wheel stimmen in allen redundanten Angaben
überein. Doppelte JSON-Schlüssel, BOM, Zusatzfelder und nichtendliche JSON-Literale
sind ungültig. Metadaten enthalten keinen eigenen Hash und kein äußeres Result.
`base/runtime/...` ist ausschließlich Repositoryinhalt, ein anderer Namensraum.
Repositorypfade in Results dürfen weiterhin Unicode und Leerzeichen enthalten.
Die breitere Pfadprüfung gilt ausschließlich bei einem Root-Result-Marker;
ausführbare Patch-Pakete behalten ihr enges ASCII-Pfadprofil.

Die Limits aus Spec 39.3 gelten vor inneren Nutzdatenreads: Runtime-Metadaten
128 KiB, Rezept 1 MiB, Wheel 16 MiB, 1.000 innere Einträge, 32 MiB innere
Nutzdaten. Zusätzlich gelten die kleineren Request-Grenzen für Einträge und
einzelne Inhalte. Die gelesenen äußeren Nutzdaten einschließlich Wheel werden
vom gemeinsamen `max_zip_total_bytes` abgezogen; nur der Rest steht für innere
Nutzdaten zur Verfügung. Es gibt genau eine bekannte innere Archivebene.

Schon vor der ZipInfo-Allokation ist das innere zentrale Verzeichnis begrenzt:
geschlossener EOCD, keine Mehrdatenträger-/ZIP64-Erweiterung, begrenzte tatsächliche
Eintragsanzahl und Pfadbytes, keine Zusatz-/Kommentardaten und exakte Grenzen.
Eine gefälschte kleine EOCD-Anzahl verdeckt keine weiteren Verzeichniseinträge.
Die Standardbibliothek und die nachfolgenden Profilprüfungen validieren weiterhin
das vollständige Archiv. JSON-Rekursionstiefe erzeugt keinen unkontrollierten
Abbruch der schnellen Exchange-Erkennung.

Der Leser prüft das kanonische ZIP_STORED-Profil aus `runtime-artifact.md`,
einschließlich lokaler Header, zentralem Inventar, Reihenfolge, Grenzen, RECORD,
Metadata-/Rezeptkonsistenz und Identitätsliteral. Er hält beim inneren Lesen nur
jeweils einen Nutzdateneintrag sowie Rezept und benötigte Metadaten. Keine
Extraktion, zweite Materialisierung oder Ausführung beschriebener Module.

Referenzprüfung, Archiv-/Recovery-Fakten und die Kontrolle vor Veröffentlichung
verwenden den gemeinsamen versionierten Result-Leser. Die Publikation nutzt
dessen bereits ausgeführte vollständige CRC-/Inventarprüfung und ergänzt nur
ihre Pflicht zu Handoff und passendem Ausführungszustand. Es gibt keinen zweiten
vollständigen CRC-Lesedurchgang. Markerprüfung und striktes JSON-Decoding der
Result-Verbraucher sind gemeinsam; ihre verschiedenen Policies bleiben getrennt.
Die schnelle
Exchange-Klassifikation bleibt ein sicherer Typ-Hinweis und akzeptiert auch
unbekannte Result-Versionen ausdrücklich nicht als ausführbares Patch-Paket.
Der gemeinsame produktive Writer wird erst in `1.e.W` auf Format 2 umgestellt.

Positive und negative Eingaben werden in `tests/test_result_format2.py` aus
festgelegten Metadaten-Fixtures und einem tatsächlich gebauten kanonischen Wheel
erzeugt; bestehende Format-1-Referenz-, Archiv-/Recovery- und Writer-Tests bleiben.

`tests/fixtures/result_format1/` enthält die drei unveränderten Lesermodule
`result_reader.py`, `archive_evidence.py` und `exchange.py` vom tatsächlichen
Commit `d31047b2feca049c2db5443bb61df2ce7ce5e7f6`. Herkunft und Datei-SHA-256 sind
in provenance.json festgehalten. Vor dem Hashvergleich werden ausschließlich
Git-Checkout-Zeilenenden von CRLF zu LF normalisiert; der Kindprozess erhält die
ursprünglichen Quellbytes. Funktionale Kindprozesse verwenden diese Module mit
der übrigen Test-Infrastruktur des aktuellen Quellstands; dies
behauptet keine Prüfung einer vollständigen historischen Binärdistribution.
Sie archivieren gültige ältere Format-1-Results weiterhin, behalten neue
Format-2-Results konservativ und wählen weder Results noch Wheels als Patch.
