# HANDOFF-NR – Spezifikation

## Ziel

Patch-Auslieferungen wiederholen ihren Status am Antwortende und kennzeichnen die kanonische ZIP mit einer dreistelligen, repositorybezogenen Bundle-Nummer. Der Patch-Link ist bei Erfolg die letzte Zeile der gesamten Antwort.

## Grenzen

- Genau eine kanonische ZIP und unveränderte State-/Payload-Sicherheitsregeln.
- Die Nummer ist ein Best-Effort-Handoff-Merkmal des externen Chats, keine zentrale, transaktionale oder sicherheitsrelevante Identität.
- Ohne verlässliche Historie beginnt die bekannte Folge bei `001`; unabhängige Chats dürfen deshalb kollidieren.
- Dieselbe ZIP behält beim erneuten Link/Backup/Versand dieselbe Nummer.
- STOP ohne Bundle vergibt keine Nummer.
- Der Entrypoint druckt dieselbe Nummer nur nach erfolgreichem Abschluss und sauberem Zielzustand.
- Backupregeln bleiben unverändert Best Effort und verwenden dieselbe kanonische ZIP.
- Tests prüfen den Anweisungsvertrag, nicht das Layout zukünftiger Produkt-CLI-Ausgaben.
