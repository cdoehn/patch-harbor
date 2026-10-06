# Result-Verifikation auf CIFS – Korrekturplan

Beauftragt am 6. Oktober 2026 zu [Issue 1](https://github.com/cdoehn/patch-harbor/issues/1).
Grundlage: Fehlerbericht zu 1.2.1 und ergänzende Nutzerentscheidung für ansteigende
Pausen mit insgesamt fünf Minuten Standardwartezeit. Der Watcher-Plan ist durch
Bundle 022 und die erfolgreiche CI abgeschlossen; dies ist ein eigener Korrekturauftrag.

## Verbindliche Basis für Bundle 023

Tatsächliches Result: `patchharbor-apply_Result_101342_1006_7d3d55.zip`.
SHA-256: `ebdfde1ef19fc9a2fbb1c8205b4841919a9660bfc73d38221d300d2884b00604`.

| Bindung | Wert |
| --- | --- |
| repo_id | `e7a93d72-62dc-4759-97e8-6bf6cdf10e90` |
| base_commit | `44cc77a42b492fc1f31267db5139253ef7545b9f` |
| state_fingerprint | `7c9d2a24e397e0e5` |
| fingerprint_algorithm | `patchharbor-state-v1` |

Alle 282 Ausgangsdateien samt Modi sind mit Result, Development und Apply
abgeglichen. Tatsächlicher Apply und Push bestätigt, saubere Apply-Arbeitskopie;
jeweils 2.386 Tests bestanden / 7 übersprungen seriell und parallel.
[CI 37459998721](https://github.com/cdoehn/patch-harbor/actions/runs/37459998721)
bestätigt sechs erfolgreiche Jobs auf genau diesem Commit einschließlich Windows.
Das Format-1-Result hat kein Wheel; der vertrauenswürdige lokale Core-Fallback gilt.

## Commit und Abnahme

| Schritt | Inhalt | Status |
| --- | --- | --- |
| CIFS-1 | Sync vor Verifikation; endliche typisierte Retries; eigene No-follow-Handles; Hashbindung bis zum Rename; sichere Diagnosen; Regressionen und Dokumentation | in Bundle 023 vorbereitet; tatsächlicher Apply offen |

Ein zusammenhängender tatsächlicher Dateizustand, ein vorgesehener Commit:
`fix(result): stabilize owned Result verification on CIFS [CIFS-1]`.
Die [zentrale Spezifikation](../../spec/SPECIFICATION.md), Abschnitt 18.5, und die
[Betriebsdokumentation](../../docs/result-publication-cifs.md) legen den Vertrag fest.

Development prüft die vollständige Suite ausschließlich parallel. Der Entrypoint
prüft den Endstand vollständig seriell und danach parallel vor seinem Commit
und dem einzigen normalen Push nach `dev`. Keine Tags, kein globales Upgrade,
kein Watcher-Neustart und keine zusätzliche CI durch dieses Bundle. Reguläre CI
bleibt 024. Neue Dateien werden im installierten Wheel-/sdist-Inventar geprüft.

Offen bis zum tatsächlichen Nachweis:

- Apply-/Push-Result von 023 mit vollständigen seriellen/parallelen Gates.
- Native Windows-Abnahme der geänderten Handle-Pfade in der fälligen CI.
- Wiederholte Bundle-Erzeugung und ein kontrollierter Apply mit Linux-Zugriff auf
  die betroffene Windows-CIFS-Freigabe, einschließlich vollständiger Result-Prüfung.

Ein erfolgreicher lokaler Test ist kein CIFS-Nachweis. Bei ausgeschöpftem Budget
bleibt der Vorgang fehlgeschlagen; ohne gültige Verifikation keine Veröffentlichung.
Ein Release folgt erst nach den geforderten Nachweisen, nicht automatisch aus
diesem Korrekturbundle. Kein spekulatives Folgebundle allein für weitere Wartezeit.
