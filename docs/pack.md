# Pakete aus vorbereiteten Inhalten erzeugen

Der Vertrag steht gemeinsam in [Hauptspezifikation](../spec/SPECIFICATION.md)
und [PYZ/PACK-Ergänzung, Revision 3](../spec/SPECIFICATION_EXTENSION_PYZ_PACK.md).
Der [aktive Plan](../planning/pyz-pack/commit-plan.md) führt den Fortschritt.
Installierte CLI, Core-PYZ und öffentliche Python-API verwenden denselben
Pack-Core. Python ab 3.12 ist nötig. Die PYZ enthält den Core ohne Watcher und
braucht keine Installation; ihr Start aus einem Result folgt dem
[geprüften Bootstrap](runtime-bootstrap.md).

```bash
patchharbor pack ./patch-inhalt --reference-bundle ./result.zip \
  --entrypoint apply.sh --output-dir ./vorhandene-ausgabe \
  --mode scripts/neues-tool.sh=0755 --json
```

`--reference-bundle`, `--entrypoint` und genau eine der Optionen `--output-dir`
oder `--output` sind Pflicht. `--mode` ist wiederholbar und verlangt genau vier
oktale Ziffern; doppelte Pfade sind Nutzungsfehler. Die CLI korrigiert keine
unsicheren Paketpfade oder Modi und bietet kein Überschreib-/Validierungs-Aus-Flag.
Ohne `--json` werden Pfad und Hash ausgegeben. JSON verwendet `output_version: 2`,
`command: "pack"` und enthält den vollständigen Validierungsnachweis samt Warnungen.
Fehlende Optionen/Modussyntax ergeben Exit 2, fachliche Fehler behalten die
bestehenden Codes. Scheitert nach Veröffentlichung nur die Ausgabe oder ihr Flush,
endet die CLI mit 7 (I/O) beziehungsweise 130 (Unterbrechung), ohne erneut zu bauen.
Soweit stderr funktioniert, nennt sie den veröffentlichten Pfad und Hash. Es wird
kein zweiter Fehler-Envelope an eine teilweise geschriebene Erfolgsantwort gehängt.

```python
from patchharbor import api

result = api.pack_patch(
    "patch-inhalt",
    reference_bundle="result.zip",
    entrypoint="apply.sh",
    output_directory="vorhandene-ausgabe",
    modes={"scripts/neues-tool.sh": 0o755},
)
print(result.path, result.package_sha256)
```

Der Inhaltsordner ist die bewusste Auswahl: Entrypoint und gewünschte Nutzdateien,
keine `.git`-/`.patchharbor`-Daten. Es gibt keine `.gitignore`-Filterung oder
selbstständige Änderungswahl. Alle zulässigen Dateien werden bytegleich aufgenommen;
Archive bleiben Nutzdateien. Leere Verzeichnisse entfallen mit einem Hinweis.
`patch.json` und der Root-Namensraum `PATCHHARBOR_META` sind für generierte Dateien
reserviert. Eine normale Repositorydatei `CHAT_INSTRUCTIONS.md` bleibt Nutzdatei.

Der Entrypoint braucht den bestehenden Bash-/PowerShell-Vertrag samt Pflichtmarker.
Pack verändert weder Marker, Shebang, Encoding noch Zeilenenden. Die statische
Prüfung benötigt keine installierte Ziel-Shell und bestätigt keine Shellsyntax.
Alle angeforderten Paketmodi sind zunächst `0644`; explizite sichere Modi sind
möglich, Hostrechte werden nicht übernommen. Modusschlüssel müssen vorhandene
reguläre Eingabedateien bezeichnen. Das spätere Apply erhält vorhandene sichere
POSIX-Zielrechte nach dem bestehenden Vertrag.

## Referenz und Begleitdaten

Ein ausdrücklich benanntes, vollständig gültiges Result ist Pflicht. Alte,
Dirty-, Fehler-, Diagnose- und Dry-Run-Results sind zulässig. Die vier Bindungswerte
kommen aus dem tatsächlichen Kontext, nie aus `expected_*` eines früheren Apply.
Eine deklarierte defekte Runtime bleibt ein Fehler; gültiges `unavailable` ist
zulässig. Die Referenz wird nur einmal vollständig erfasst. Ihr Hash, Suffix und
passive Zielinformationen stammen aus genau diesen geprüften Bytes.

Manifest und Handoff sind neue Dateien. Die Vorlage stammt aus den verifizierten
Ressourcen des ausführenden Packers; die schon gerenderte Referenzanleitung wird
nicht als neue Vorlage eingesetzt. Bekannte Zielpfade, Runtimeinformationen und
Erfassungszeit bleiben erhalten. Unbekannte Legacy-Umgebungswerte bleiben `null`.
Fremde Pfade werden als Text verwendet und nicht auf dem Pack-Rechner aufgelöst.

## Ausgabe und Veröffentlichung

Genau eine Ausgabeart ist nötig: `output_directory` erzeugt den kanonischen Namen
`<Repository>_Patch_<HHMMSS>_<MMDD>_<ID6>.zip<bundle_suffix>`; `output` erlaubt einen
bewussten Namen mit `.zip` plus dem Referenzsuffix. Beide haben eine eigene UUID v4
und UTC-Erzeugungszeit. Die Paket-ID ist weder Referenz-Run-ID noch Chat-Bundle-Nummer.
Für Chat-Auslieferungen bleibt der kanonische Name vorgeschrieben.

Der Zielordner muss vorhanden und außerhalb des Inhaltsbaums liegen. Pack schreibt
ausschließlich darin, zunächst unter einem erkennbaren `.partial`-Namen. Es prüft
Eigentum und Datei-Sync und verwendet anschließend den vollständigen gemeinsamen
Validator für die tatsächlich geschriebenen ZIP-Bytes. Vor der exklusiven
Veröffentlichung werden Quellinventar, Referenz, Identität und Hash nochmals geprüft.
Es gibt keine Stabilitäts-Retries und kein Überschreiben bestehender Ziele.

Linux veröffentlicht die gepinnte Datei über ihren offenen Handle mit `linkat`;
Windows verwendet eine No-replace-Umbenennung über den gepinnten Datei-Handle.
Unterstützt das gewählte Dateisystem diese sicheren Voraussetzungen nicht, scheitert
der Auftrag. Das ist keine allgemeine CIFS- oder Stromausfallgarantie. Der bestehende
Result-Sync-/Replace-/Retry-Vertrag bleibt getrennt erhalten.

Vor Veröffentlichung führt ein Fehler zu keinem Erfolgsresultat. Fremde Dateien
werden nicht zur Bereinigung entfernt. Nach bestätigter Veröffentlichung bleibt
bei einem optionalen Cleanup-Fehler dagegen der vollständige `PatchPackResult`
erhalten; seine Warnungen nennen eigene Reste. Es ist kein nachträgliches Öffnen
des finalen Pfads nötig. Ein separat laufender Watcher darf ihn bereits übernehmen.
Pack startet selbst keinen Watcher und hat keinen impliziten Exchange-Ausgabeort.

## Grenzen und Nachweise

Die Inhaltsaufnahme ist auf 10.000 Dateisystemknoten (Dateien und Verzeichnisse)
begrenzt. Daneben gilt die gemeinsame äußere ZIP-Grenze von 250.010 Einträgen,
einschließlich der drei generierten Dateien; sie hebt die engere Scan-Grenze
nicht auf. Es gelten weiterhin 256 MiB je Inhalt/fertigem ZIP und 512 MiB
unkomprimiert. Die Result-Referenz darf bis zu 250.000 Base-/Untracked-Dateien
zusammen enthalten; ihre innere Runtime bleibt auf 1.000 Einträge begrenzt.
Handoff-Dateien dürfen je 128 KiB erreichen. Links, Reparse-Punkte, Sonderdateien,
unsichere Archivpfade und case-ambige Kollisionen werden abgelehnt. Bekannte Änderungen
führen ohne Neuaufnahme zum Abbruch; ein beliebig parallel manipulierter Baum wird
nicht als atomarer Snapshot versprochen.

`PatchPackResult` enthält endgültigen Pfad, Paket-ID, Erzeugungszeit, vollständige
Referenzvalidierung, Hashes, Größe und Warnungen. Das bestätigt Paketformat und
Bindung. Es bestätigt keine fachliche Richtigkeit, Shellausführung, Projekttests,
Authentizität, Replayfreigabe oder den späteren Zustand des Zielrepositories.
Pack startet weder Git, Shell, Netzwerk, Installer, Build noch Apply.

Die Tests für Referenzen, Inhaltsaufnahme, Kandidatenbau und öffentliche API laufen
in der vollständigen parallelen Suite. Linux-Nachweise ersetzen keine native
Windows-/CIFS-Abnahme. Der tatsächliche Handoff- und Apply-Status steht im Plan und
im zugehörigen Result. Die Erstnutzung aus der eigenen eingebetteten Anleitung
und drei echte Result-/PYZ-Generationen sind eigene vollständige Tests.
[Funktionsbeispiele](pack-examples.md) zeigen Voll-Datei-, Diff-, Misch- und
Diagnosepakete sowie die Grenze einer erfolgreichen statischen Prüfung.
