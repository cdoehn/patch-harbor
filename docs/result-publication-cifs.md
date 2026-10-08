# Result-Veröffentlichung auf CIFS

Ein Linux-Prozess kann seinen Exchange auf einer Windows-Freigabe betreiben.
Der Client verwendet dann Linux-Dateioperationen über CIFS/SMB. Der Windows-
Dateiserver macht daraus keinen nativen Windows-Prozess.

## Anlass und Einordnung

[Issue 1](https://github.com/cdoehn/patch-harbor/issues/1) meldet unter 1.2.1
`FileChangedDuringRead` beim ersten Vergleich zwischen Pfad und geöffnetem Handle
der gerade geschriebenen temporären Result-ZIP. Der bestehende Fallback ist
aktiv; an dieser Stelle muss Größe oder Änderungszeit abweichen. Eine verzögerte
CIFS-Metadatenaktualisierung ist plausibel. Die konkreten Werte und die Wirksamkeit
des Fixes müssen am betroffenen Mount nachgewiesen werden. Grüne lokale Tests
sind kein Nachweis für diese Windows-Freigabe.

## Ablauf und Wartezeiten

Nach dem Schreiben und Schließen prüft Core die Eigentümerschaft, synchronisiert
die Datei über einen überprüften Handle sowie bestmöglich das Elternverzeichnis
und prüft die Eigentümerschaft erneut. Erst danach erfolgt die vollständige
Result-Verifikation. Linux öffnet die eigene Datei mit `O_NOFOLLOW` und
`O_NONBLOCK`; Windows öffnet Reparse-Punkte ausdrücklich ohne Auflösung und
weist sie zurück. Pfad und tatsächlich geöffneter Handle müssen zur eigenen
Datei gehören. Dateiattribut-Fallbacks ersetzen diese Identitätsprüfung nicht.

Nur ein typisierter `FileChangedDuringRead` in der expliziten Ausnahmekette ist
wiederholbar. Fremde Dateien, verschwundene eigene Dateien, defekte ZIPs, CRC-,
Schema-, Inhalts-, Bindungs- und Ressourcenfehler brechen ab. Impliziter
Ausnahmekontext und Fehlertext werden nicht zur Retry-Erkennung verwendet.

Die erste Prüfung erfolgt sofort. Danach gelten diese Pausen:

`2, 3, 5, 10, 20, 20, 30, 30, 60, 60, 60 Sekunden`

Bei dauerhaftem Stabilitätsfehler ergeben sich zwölf Versuche und 300 Sekunden
reine Wartezeit. Dateisystem-/Netzwerkoperationen kommen zeitlich hinzu; es gibt
keine Behauptung einer harten fünfminütigen Gesamtlaufzeit. Sobald eine Prüfung
gelingt, endet ihr Warten. Jede Wiederholung beginnt wieder mit Eigentumsprüfung
und Sync. Unterbrechungen werden nicht abgefangen oder automatisch wiederholt.

Auf Linux liest Core, soweit verfügbar, `/proc/self/mountinfo` und berücksichtigt
den innersten Mount. Für CIFS/SMB3 gilt für den zusätzlichen Puffer:

`Budget = max(300, 2 × (Dateiattributcache + Close-Verzögerung) + 10) Sekunden`.

`acregmax` hat Vorrang vor `actimeo`; ohne Angabe gelten wie bei `closetimeo`
eine Sekunde. Übersteigt das Budget 300 Sekunden, wird genau eine weitere Pause
um die Differenz angehängt. Normale frühe Versuche werden nicht verzögert.
Nicht-CIFS-Mounts und fehlende/unlesbare Angaben verwenden das Standardbudget.
Das ist eine konservative Anwendungsregel, keine SMB-Garantie für Metadatenkohärenz.
Ein nicht erreichbarer Server bleibt ein I/O-Fehler.

Der gesamte Veröffentlichungsvorgang teilt ein Wartebudget: ein nachfolgender
Hash-Read erhält keine neuen fünf Minuten. Der erste vollständig verifizierte
ZIP-Hash wird festgehalten. Ein optionaler Recovery-Beleg verwendet genau diesen
Hash und wird einmal geschrieben. Vor dem atomaren Rename müssen die aktuellen
Bytes erneut denselben Hash liefern. Ein inhaltlich anderes Result wird nicht
durch längeres Warten akzeptiert. Apply, Entrypoint, Commit und Push sind außerhalb
der Wiederholung. Die dokumentierten PYZ-/Legacy-Wheel-Fallbacks bleiben erhalten.

## Diagnose und Praxisabnahme

Die normale Fehlermeldung und damit auch `run.json` bewahren Prüfstufe,
Fehlertyp, Versuchszahl und Abweichungskategorie. `verification.json` im privaten
Notfallordner ergänzt bestmöglich Sync-Ergebnisse, tatsächlich absolvierte
Warteintervalle und die numerischen Metadaten vor/nach dem Vergleich.
Sie enthält keine Dateiinhalte, Zugangsdaten oder Umgebungsvariablen.
Ein fehlgeschlagener Diagnose-Write verdeckt den primären Fehler nicht.

Für die Abnahme auf der betroffenen Linux→Windows-CIFS-Verbindung:

1. Kernel-/CIFS-Version und relevante Cache-/Close-Mountoptionen ohne Zugangsdaten
   festhalten. Für vergleichbare Wiederholungen dieselbe Konfiguration verwenden.
2. Mehrfach ein tatsächliches `patchharbor bundle` erstellen. Exit-Code und den
   exakt dabei ausgegebenen Result-Pfad aufzeichnen; kein älteres Result auswählen.
3. Die entstandenen Results durch PatchHarbors vollständigen Result-Leser prüfen.
   `unzip -t` und ein bloß berechneter SHA-256 sind nur ergänzende Nachweise.
4. Auch die Result-Erzeugung nach einem kontrollierten tatsächlichen Apply prüfen;
   dessen Entrypoint darf trotz Verifikations-Retries nur einmal laufen.
5. Bei Fehlern `run.json` und `verification.json` auswerten. Bei Erfolg dürfen
   keine eigene temporäre ZIP und keine fälschliche Notfalldiagnose verbleiben.

Lokale Regressionen simulieren Cacheabweichungen und Zeitabläufe ohne echte
Minutenpausen, einschließlich Erschöpfung, Abbruch, Dateiaustausch, Symlink-/FIFO-
Rennen, Integritätsfehlern und Inhaltsänderungen gleicher Länge bei wiederhergestellter
`mtime`. Development und Apply verwenden nach der aktuellen Nutzerentscheidung
nur vollständige parallele Gates. Native Windows- und reale CIFS-Abnahme bleiben
bis zu ihren tatsächlichen Nachweisen offen. Ausschließlich Christian startet die
manuelle GitHub-CI; es gibt keinen automatischen Bundle-Termin.

Grundlagen: [CIFS-Mountoptionen](https://man7.org/linux/man-pages/man8/mount.cifs.8.html),
[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew).


## Format-3 activation (PP-06B)

Result 3 passes the new PYZ or unavailable payload through this same publication
boundary. Its typed finite retries, shared budget, sync/no-follow operations,
owned cleanup and verified SHA publication are unchanged. The expanded tests
exercise both runtime states; an integrity failure still cannot become a retry
or a weaker reference success. These tests simulate faults and do not close the
separate real Linux-to-Windows CIFS acceptance requirement. `pack` continues to
use its different no-replace/no-stability-retry publication contract.
