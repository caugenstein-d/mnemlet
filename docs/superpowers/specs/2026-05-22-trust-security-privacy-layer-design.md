# Trust / Security / Privacy Layer — v0.2/v0.3 Design

**Datum:** 2026-05-22  
**Status:** Draft  
**Autor:** Mira (Research & Systems-Design)  
**Projekt:** Mnémlet  
**Vorgänger:** Memory Intelligence Core v0.2  

---

## Executive Summary

Mnémlet v0.1 hat keinerlei Auth, kein Audit, keine Secret Detection, keine Erklärbarkeit für Menschen. Die Intelligence Layer (v0.2) bringt Semantik – forget, replace, confirm, provenance – aber keine Vertrauensschicht. Der **Trust/Security/Privacy Layer** ergänzt v0.2 um den Schutz- und Transparenz-Aspekt: Wer darf was? Was wurde gespeichert und von wem? Welche Secrets sind versehentlich gelandet? Und wie können Daten gesichert und wiederhergestellt werden?

**Architektur-Entscheidung:** Middleware + Selective Hooks. Auth und Audit als FastAPI Middleware (cross-cutting, kann nicht vergessen werden). Secret Detection und Namespace Policies als Hooks an spezifischen Stellen (nur wo relevant).

**Prinzipien:**
- Solo self-hosted first. Keine Enterprise-Features.
- Sichere Defaults. Unsichere Konfiguration wird laut gewarnt, nicht blockiert.
- Auditability über Access Control. Wir loggen alles, aber wir blockieren selten hard.
- Ergänzung, nicht Redesign. v0.2 existiert und funktioniert. Trust Layer baut darauf auf.

---

## Abgrenzung zu v0.2

| Feature | v0.2 (Intelligence) | Trust Layer (v0.3) |
|---------|---------------------|---------------------|
| `mnemlet_forget` | Semantik: Status=`forgotten`, vom Recall ausgeschlossen | Audit-Trail: Wer hat vergessen? Wann? Bestätigungsschritt bei Policy |
| `mnemlet_replace` | Semantik: Alte → `superseded`, neue → `active`, Verknüpfung | Audit-Trail: Wer hat ersetzt? Warum? Alte Version bleibt im Audit |
| `mnemlet_confirm` | Semantik: `+0.20` Retention Score, Interaction `type='confirm'` | Trust: Confirmation-Zähler, Confirm-History im Explain |
| `mnemlet_explain` | Provenance: Source, Score, Type, Age | Trust+: Ingested-by, Caller-Identity, Secret-Guard-Result, Bestätigungen |
| Policies | Memory-Type-Retention, Supersession, Confirmation | Namespace-Access-Policies, Secret-Guard-Policies |

---

## Bedrohungsmodell: Solo Self-Hosted Homelab

**Angenommenes Umfeld:** Ein Pi (oder lokaler Server), 127.0.0.1 bind, mehrere lokale Agenten (Mira, OpenWebUI, evt. Ari auf separatem Pi im selben Netzwerk).

### Bedrohungen

| # | Bedrohung | Wahrscheinlichkeit | Auswirkung | Gegenmaßnahme |
|---|----------|-------------------|------------|---------------|
| T1 | **Versehentliche Port-Exposition** – Mnémlet mit `0.0.0.0` gestartet, von außen erreichbar | Mittel | Hoch | Single API Key, `--host` Warnung |
| T2 | **Secret-Leak im Ingest** – API-Keys, Passwörter, Tokens als Memory gespeichert | Mittel | Hoch | Regex Secret Guard bei Ingest |
| T3 | **Böswilliger lokaler Prozess** – Prozess auf demselben Host greift auf `localhost:4050` zu | Niedrig | Hoch | API Key (Local-Process kann Key lesen) |
| T4 | **Datenverlust** – DB-Korruption, versehentliches `forget all`, Hardware-Fail | Mittel | Hoch | Backup/Restore mit atomarem Snapshot |
| T5 | **Cross-Namespace-Zugriff durch Agent** – Agent liest/schreibt im falschen Namespace | Niedrig | Mittel | Namespace Policy (Konvention, nicht Enforcement) |
| T6 | **Agent-Attributionsverlust** – keine Nachvollziehbarkeit, wer was gespeichert hat | Mittel | Mittel | Audit Log mit Caller-Identifikation |
| T7 | **Unbeabsichtigtes Vergessen** – Agent vergisst wichtige Memory | Niedrig | Mittel | Confirm-Flow (v0.2), Audit Log |

### Explizit NICHT im Threat Model

| Out-of-Scope | Warum |
|--------------|-------|
| **Remote-Attack über Netzwerk** | Localhost-only. Externe Zugänge über Reverse Proxy + TLS. |
| **Encryption at Rest** | Solo auf Pi. OS-Level (LUKS) ist der richtige Platz. |
| **Multi-User-Isolation (RBAC)** | Solo-Setup. Eine Person = ein Nutzer. |
| **TLS** | Localhost. Reverse Proxy für externe Zugänge. |
| **Supply-Chain-Angriffe** | Dependencies gepinnt. Außerhalb dieses Scopes. |
| **Side-Channel-Angriffe** | Nicht adressierbar auf dieser Ebene. |

### Sicherheitsannahmen

1. **Localhost ist semi-trusted.** Prozesse auf demselben Host können den API Key lesen, wenn sie Dateizugriff haben. Der Key schützt vor versehentlicher/entfernter Exposition, nicht vor einem kompromittierten lokalen Prozess.
2. **Agenten sind trusted.** Mira, OpenWebUI, OpenCode, Ari arbeiten für denselben Nutzer. Keine Agenten-Isolation nötig.
3. **OS-Level-Security ist vorausgesetzt.** LUKS, File Permissions, Firewall – nicht Mnémlets Job.
4. **Kein Multi-Tenancy.** Eine Instanz = ein Nutzer. Wer Isolation braucht, betreibt mehrere Instanzen.

---

## Feature-Prioritäten

### P0 – Muss haben (sofort)

| Feature | Begründung | Abhängigkeit |
|---------|-------------|--------------|
| **Single API Key Auth** | Schützt vor versehentlicher Exposition (T1). Ohne Auth ist jeder Port-Scan ein Full-Access. | Keine |
| **Secret Regex Guard** | Verhindert API-Keys, Passwörter, Tokens im Speicher (T2). | Ingest-Engine |
| **Audit Log** | Nachvollziehbarkeit (T6, T7). Ohne Audit kein "Why do you know this?". | Keine (erweitert `interactions`) |
| **Startup-Security-Check** | Warnt bei unsicherer Konfiguration (0.0.0.0, fehlender Key, world-readable Files). | Keine |

### P1 – Soll haben (v0.3, erweitert v0.2)

| Feature | Begründung | Abhängigkeit |
|---------|-------------|--------------|
| **Namespace Policies** | Organisatorische Leitplanken (T5). Warning bei Policy-Verletzung, kein Hard-Block. | v0.2 Policy Engine |
| **"Why do you know this?" (Explain+)** | Erweitert v0.2s `mnemlet_explain` um Trust-Informationen. Human-first. | v0.2 Provenance + Audit Log |
| **Forget/Replace/Confirm Trust-Erweiterungen** | Audit-Trail für Forget/Replace, Confirmation-Proof, Undo-Logik für versehentliches Forget. | v0.2 Review Commands |
| **Backup/Restore (Full Snapshot)** | Schutz vor Datenverlust (T4). CLI-Befehle, atomare Snapshots. | Keine |

### P2 – Nice to have (später)

| Feature | Begründung |
|---------|-------------|
| **Per-Agent API Keys** | Bessere Audit-Zuordbarkeit. Mehr Management-Overhead. |
| **Secret Guard Custom Patterns** | Nutzer-definierte Regex-Patterns pro Namespace. |
| **Selective Export** | Namespace- oder Zeitraum-basierter Export. |
| **Namespace Soft-Enforcement** | Warnungen statt Blocks bei Cross-Namespace-Zugriff. |

### Explizit NICHT gebaut (YAGNI für Solo self-hosted)

- **Encryption at Rest** – OS-Level (LUKS) ist der richtige Platz.
- **RBAC / Multi-User** – Solo-Setup, Namespace = Org-Einheit, nicht Sicherheitsgrenze.
- **TLS** – Localhost-only. Reverse Proxy existiert für externe Zugänge.

---

## Architektur: Middleware + Selective Hooks

```
┌──────────────────────────────────────────────────────────┐
│                    Request Flow                           │
│                                                          │
│  REST/MCP Request                                       │
│       │                                                  │
│       ▼                                                  │
│  ┌─────────────────────────────┐                        │
│  │     Auth Middleware          │  ← P0: API Key Check   │
│  │     Audit Middleware          │  ← P0: Audit Logging   │
│  └─────────────┬───────────────┘                        │
│                │                                         │
│       ┌────────┴────────┐                               │
│       │ Is Ingest/Write? │                               │
│       └────┬────────┬───┘                               │
│            Yes       No                                  │
│            │          │                                  │
│  ┌─────────▼──┐      │                                  │
│  │ Secret Guard│      │                                  │
│  │ Hook        │      │  ← P0: Regex Scan               │
│  └─────────┬──┘      │                                  │
│            │          │                                  │
│  ┌─────────▼──┐      │                                  │
│  │ Namespace   │      │                                  │
│  │ Policy Hook │      │  ← P1: Soft Warnings             │
│  └─────────┬──┘      │                                  │
│            │          │                                  │
│       ┌────▼──────────▼────┐                            │
│       │  v0.2 Intelligence  │                            │
│       │  + Core Engine      │                            │
│       └────────┬────────────┘                            │
│                │                                         │
│       ┌────────▼────────┐                                │
│       │  Storage Layer   │                                │
│       └─────────────────┘                                │
└──────────────────────────────────────────────────────────┘
```

**Prinzip:** Auth und Audit sind Middleware – sie betreffen jeden Request und können nicht vergessen werden. Secret Guard und Namespace Policies sind Hooks – sie betreffen nur spezifische Operationen und sind dort platziert, wo sie gebraucht werden.

---

## API / MCP-Kommandos

### Single API Key Auth

**Konfiguration** in `mnemlet.toml`:
```toml
[auth]
api_key = "mnemlet_a1b2c3d4e5f6..."  # 32+ Zeichen Hex, Prefix "mnemlet_"
```

Alternativ: Umgebungsvariable `MNEMLET_API_KEY`.

**Verhalten:**
| Zustand | Verhalten |
|---------|-----------|
| Key konfiguriert + korrekter Key im Request | Zugriff erlaubt |
| Key konfiguriert + falscher/kein Key | `401 Unauthorized` |
| Kein Key konfiguriert | Zugriff erlaubt, Warnung im Log bei jedem Request |

**REST:** Header `X-Mnemlet-Key: <key>` oder `Authorization: Bearer <key>`  
**MCP:** `auth_token` Feld in der MCP-Server-Konfiguration (OpenCode/OpenWebUI übergeben den Key im Connection-Setup).

### Secret Regex Guard

**Neues Modul:** `src/mnemlet/security/secret_guard.py`

**Standard-Patterns:**

| Pattern | Erkennt |
|---------|---------|
| `ghp_[0-9a-zA-Z]{36}` | GitHub Personal Access Token |
| `sk-[0-9a-zA-Z]{48}` | OpenAI API Key |
| `AKIA[0-9A-Z]{16}` | AWS Access Key ID |
| `[0-9a-f]{32,}` in Kontext von `api.?key`, `token`, `secret` | Generische Keys |
| `(?:password|passwd|pwd)\s*[=:]\s*\S+` | Password-Zuweisungen |
| `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` | E-Mail-Adressen (optional, per Namespace) |

**Aktionen bei Ingest:**

| Aktion | Beschreibung |
|--------|-------------|
| `block` | Ingest wird abgelehnt, 400 mit Liste der erkannten Patterns |
| `warn` | Ingest geht durch, Warnung im Audit Log + `secret_detected` Flag in `metadata_json` |
| `allow` | Kein Scan (für vertrauenswürdige Namespaces) |

**Konfiguration pro Namespace:**
```toml
[security.secret_guard]
default_action = "block"
namespaces.opencode = { action = "allow" }
namespaces.shared = { action = "warn" }
patterns = []  # Standard-Set, optional ergänzbar
```

### Audit Log

**Neue Tabelle: `audit_log`**

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    action TEXT NOT NULL,          -- ingest, recall, forget, replace, confirm, classify, decay, backup, restore, config_change
    memory_id TEXT,                -- NULL bei config_changes
    namespace TEXT NOT NULL,
    caller TEXT NOT NULL,          -- 'rest' | 'mcp' | 'sleep' | 'decay' | 'cli' | 'system'
    caller_identity TEXT,          -- API Key Hash (erste 8 Zeichen) oder 'internal'
    result TEXT DEFAULT 'success', -- 'success' | 'blocked' | 'denied' | 'warning'
    details_json TEXT DEFAULT '{}' -- Freies JSON für Aktion-spezifische Metadaten
);

CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_namespace ON audit_log(namespace);
CREATE INDEX idx_audit_timestamp ON audit_log(timestamp);
```

**Eigenschaften:**
- Keine Löschung über die API. Audit Log wächst, wird nicht vom Decay-Prozess berührt.
- Backup enthält Audit Log.
- `caller_identity` speichert SHA256(api_key)[:8], nicht den Key selbst.
- `result` Feld markiert den Ausdruck der Aktion: `success` (normal), `blocked` (Secret Guard hat Ingest blockiert), `denied` (Auth-Fehlgeschlagen), `warning` (Namespace-Policy-Verletzung).

**REST-Endpunkt:** `GET /api/v1/audit?namespace=...&action=...&since=...&limit=100`  
**MCP-Tool:** `mnemlet_audit` (read-only, gleiche Parameter)

### "Why do you know this?" (Explain+)

Erweitert v0.2s `mnemlet_explain` um Trust-Informationen. Human-first – die Antwort ist für den Menschen verständlich.

```json
{
  "memory_id": "abc123",
  "content_preview": "Christoph nutzt Ubuntu auf dem Pi",
  "provenance": {
    "source": "hybrid",
    "original_rank": 2,
    "decay_adjusted_score": 0.73,
    "memory_type": "fact",
    "age_days": 14,
    "access_count": 5
  },
  "trust": {
    "ingested_by": "rest",
    "caller_identity": "mnemlet_a1b2",
    "secret_guard_result": "clean",
    "confirmed": false,
    "confirmations": 0,
    "forgotten_at": null,
    "replaced_by": null
  },
  "audit_trail": [
    {"action": "ingest", "timestamp": "2026-05-08T10:30:00Z", "caller": "rest"},
    {"action": "classify", "timestamp": "2026-05-08T10:31:00Z", "caller": "sleep"},
    {"action": "recall", "timestamp": "2026-05-10T09:15:00Z", "caller": "mcp"}
  ]
}
```

**Neue Spalten in `memories`-Tabelle** (zusätzlich zu v0.2):

```sql
ALTER TABLE memories ADD COLUMN ingested_by TEXT DEFAULT 'api';
ALTER TABLE memories ADD COLUMN caller_identity TEXT DEFAULT NULL;
ALTER TABLE memories ADD COLUMN secret_guard_result TEXT DEFAULT NULL;  -- 'clean' | 'warn' | 'block' | NULL (pre-guard)
ALTER TABLE memories ADD COLUMN confirmation_count INTEGER DEFAULT 0;
```

### Namespace Policies (Trust-Erweiterung)

v0.2 hat `policy_configs` (namespace + memory_type → retention/supersede/confirm). Der Trust Layer fügt **Zugriffspolicies** hinzu.

**Neue Tabelle: `namespace_policies`**

```sql
CREATE TABLE IF NOT EXISTS namespace_policies (
    namespace TEXT NOT NULL,
    policy_key TEXT NOT NULL,
    policy_value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (namespace, policy_key)
);
```

**Verfügbare Policies:**

| Policy | Default | Beschreibung |
|--------|---------|-------------|
| `secret_guard_action` | `block` | `block`, `warn`, `allow` für Secret Guard |
| `allow_recall` | `true` | Ob Recall in diesem Namespace erlaubt ist (soft) |
| `allow_ingest` | `true` | Ob Ingest in diesem Namespace erlaubt ist (soft) |
| `confirm_before_forget` | `false` | Ob Forget einen Bestätigungsschritt erfordert. Wenn `true`: `mnemlet_forget` benötigt Parameter `confirm=true`, sonst wird der Request mit Hinweis abgelehnt (kein Header-Reply, sondern 409 Conflict mit Erklärung). Zweiter Aufruf mit `confirm=true` führt Forget aus. |
| `max_memories` | `0` | Maximale Memories pro Namespace (0 = unbegrenzt, soft) |

**Wichtig:** Diese Policies sind **organisatorische Leitplanken**, keine harten Access Controls. Bei Verletzung: Audit-Log-Eintrag mit `policy_violation` im `details_json`, kein Hard-Block (außer Secret Guard `action=block`).

### Backup / Restore

**CLI-Befehle:**
```bash
mnemlet backup [--output PATH]         # Default: ~/.mnemlet/backups/mnemlet_YYYYMMDD_HHMMSS.tar.gz
mnemlet restore [--input PATH]         # Bestätigung erforderlich, wenn DB nicht leer
```

**Snapshot-Inhalt:**
- `mnemlet.db` (SQLite, inklusive `audit_log`)
- `chroma_data/` (ChromaDB)
- `vault/` (Markdown-Vault)
- `mnemlet.toml` (Konfiguration, **ohne** `api_key`!)

**Restore-Verhalten:**
1. Bestehende DB wird als `mnemlet.db.pre_restore` gesichert
2. Restore ersetzt DB + ChromaDB + Vault atomar
3. Audit Log bekommt `restore`-Eintrag
4. `api_key` nicht im Backup – bestehender oder neuer Key bleibt gültig
5. Nach Restore: Startup-Security-Check läuft automatisch

---

## Sichere Defaults

| Einstellung | Default | Begründung |
|-------------|---------|------------|
| **Host** | `127.0.0.1` | Existierte bereits. Exposition ist bewusst. |
| **API Key** | Nicht gesetzt → Warnung bei Start | Rückwärtskompatibel, aber deutlich. |
| **Secret Guard Default Action** | `block` | Sicherer Default – Secrets werden nicht stillschweigend gespeichert. |
| **Audit Log** | Aktiv | Kein Opt-out. Audit ist immer an. |
| **Audit Log Retention** | Unbegrenzt | Wächst langsam. Kein automatisches Löschen. |
| **Backup API Key** | Nein | API Key wird nicht im Backup gespeichert. |
| **CORS** | `localhost` statt `*` | Kein Wildcard-Origin mehr. |
| **DB Permissions** | `0600` | SQLite-DB mit user-only Permissions. Warnung bei world-readable. |
| **Vault Permissions** | `0700` | Vault-Verzeichnis analog. |

### Startup-Security-Check

Bei jedem Start von `mnemlet serve`:

1. Ist `host` auf `0.0.0.0`? → **WARNING** ins Log.
2. Ist `api_key` nicht konfiguriert? → **WARNING** ins Log + jeder Request wird mit `"unauthenticated"` im Audit geloggt.
3. Sind `mnemlet.db` oder `vault/` world-readable? → **WARNING** ins Log.
4. Ist die DB leer (first run)? → **INFO** mit Empfehlung, API Key zu setzen.
5. CORS-Konfiguration geprüft.

Kein Start-Block – Warnungen reichen. Der Nutzer ist informiert, nicht gezwungen.

---

## Datenmodell-Erweiterungen

### Vollständiges Migration-Script

```sql
-- P0: Audit Log
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    action TEXT NOT NULL,
    memory_id TEXT,
    namespace TEXT NOT NULL,
    caller TEXT NOT NULL,
    caller_identity TEXT,
    details_json TEXT DEFAULT '{}'
);

CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_namespace ON audit_log(namespace);
CREATE INDEX idx_audit_timestamp ON audit_log(timestamp);

-- P0: Trust-Felder in memories
ALTER TABLE memories ADD COLUMN ingested_by TEXT DEFAULT 'api';
ALTER TABLE memories ADD COLUMN caller_identity TEXT DEFAULT NULL;
ALTER TABLE memories ADD COLUMN secret_guard_result TEXT DEFAULT NULL;
ALTER TABLE memories ADD COLUMN confirmation_count INTEGER DEFAULT 0;

-- P1: Namespace Policies
CREATE TABLE IF NOT EXISTS namespace_policies (
    namespace TEXT NOT NULL,
    policy_key TEXT NOT NULL,
    policy_value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (namespace, policy_key)
);
```

**Migration-Prinzip:** Alle neuen Spalten sind `DEFAULT NULL` oder `DEFAULT wert`. Bestehende Daten werden nicht invalidiert. Reines `ADD COLUMN`, kein `ALTER COLUMN` oder `DROP`.

---

## Dateistruktur (vorgeschlagen)

```
src/mnemlet/
├── security/                # NEU: Trust/Security Layer
│   ├── __init__.py
│   ├── auth.py              # API Key Validation (Middleware + MCP)
│   ├── audit.py             # Audit Logger (Middleware + Hooks)
│   ├── secret_guard.py      # Regex Secret Detection (Pre-Ingest Hook)
│   ├── startup_check.py     # Startup Security Checks
│   └── namespace_policies.py # Namespace Policy Engine
├── backup/                   # NEU: Backup/Restore
│   ├── __init__.py
│   ├── backup.py             # CLI: mnemlet backup
│   └── restore.py            # CLI: mnemlet restore
├── server/
│   ├── app.py               # ERWEITERT: Auth + Audit Middleware
│   ├── mcp_server.py         # ERWEITERT: Auth Interceptor + Audit
│   └── routes/
│       ├── audit.py          # NEU: GET /api/v1/audit
│       └── ...                # BESTEHEND, unverändert
├── engine/
│   ├── ingest.py             # ERWEITERT: Secret Guard Hook
│   └── ...                    # BESTEHEND, unverändert
└── storage/
    ├── sqlite.py             # ERWEITERT: Migration + neue Tabellen
    └── ...                    # BESTEHEND, unverändert
```

---

## Tests

### Unit Tests

| Test | Beschreibt |
|------|-------------|
| `test_api_key_valid` | Korrekter API Key im Header → Request geht durch |
| `test_api_key_missing` | Kein Key + Key konfiguriert → 401 |
| `test_api_key_wrong` | Falscher Key → 401 |
| `test_no_key_configured_allows` | Kein Key konfiguriert → Request geht durch, Warnung geloggt |
| `test_secret_guard_blocks_github_pat` | `ghp_xxx` im Content → 400 + Fehlermeldung |
| `test_secret_guard_blocks_openai_key` | `sk-xxx` im Content → 400 |
| `test_secret_guard_warns_email` | E-Mail im Content + Action=`warn` → Ingest geht durch, `secret_detected` Flag |
| `test_secret_guard_allows_trusted_ns` | Namespace mit Action=`allow` → kein Scan |
| `test_secret_guard_custom_pattern` | Nutzer-definiertes Pattern → Erkennung |
| `test_audit_log_ingest` | Ingest erzeugt Audit-Eintrag mit action=`ingest` |
| `test_audit_log_recall` | Recall erzeugt Audit-Eintrag |
| `test_audit_log_forget_replace` | Forget/Replace erzeugen Audit-Einträge |
| `test_audit_log_no_delete` | Audit Log kann nicht über die API gelöscht werden |
| `test_audit_log_query_filters` | Filter nach namespace, action, since funktionieren |
| `test_explain_plus_trust_fields` | Explain liefert ingested_by, caller_identity, secret_guard_result, confirmation_count |
| `test_namespace_policy_soft_violation` | Recall auf Namespace mit `allow_recall=false` → geht durch, Audit-Warning |
| `test_namespace_policy_max_memories` | Ingest über max_memories → Audit-Warning, Ingest geht durch |
| `test_backup_creates_tarball` | Backup erzeugt tar.gz mit allen Daten |
| `test_backup_excludes_api_key` | mnemlet.toml im Backup enthält keinen api_key |
| `test_restore_replaces_db` | Restore ersetzt DB und sichert alte als .pre_restore |
| `test_restore_audit_entry` | Restore erzeugt Audit-Eintrag |
| `test_startup_warning_no_key` | Start ohne api_key → Warnung |
| `test_startup_warning_public_host` | Start mit 0.0.0.0 → Warnung |
| `test_startup_warning_world_readable` | DB world-readable → Warnung |

### Integration Tests

| Test | Beschreibt |
|------|-------------|
| `test_full_ingest_with_secret_guard` | Ingest mit API Key + Secret Guard Block + Audit Log |
| `test_full_recall_with_audit` | Recall erzeugt Audit-Eintrag + Explain+ zeigt Trust-Felder |
| `test_forget_with_confirm_policy` | Forget auf Namespace mit `confirm_before_forget=true` → 409 Conflict beim ersten Versuch, Erfolg beim zweiten Aufruf mit `confirm=true` |
| `test_backup_restore_cycle` | Backup → Änderung → Restore → Zustand wie beim Backup |
| `test_mcp_auth` | MCP-Calls mit Token → durch, ohne Token → Abbruch |
| `test_cors_restricted` | CORS nur für localhost |

### End-to-End Tests

| Test | Beschreibt |
|------|-------------|
| `test_security_lifecycle` | Start ohne Key → Warnung → Key setzen → Restart → Request mit Key → Secret Guard blockt → Audit Trail |
| `test_backup_restore_lifecycle` | Daten anlegen → Backup → Daten ändern → Restore → Ursprünglich Daten zurück + Audit zeigt Restore |
| `test_full_audit_trail` | Ingest → Classify → Recall → Forget → Restore → Audit zeigt komplette Historie |

---

## Akzeptanzkriterien

1. **Auth:** Ohne konfigurierten API Key startet Mnémlet mit Warnung und erlaubt Zugang. Mit Key wird jeder Request ohne korrekten Key mit 401 abgelehnt.
2. **Secret Guard:** Ein Ingest, der einen GitHub PAT oder OpenAI Key enthält, wird standardmäßig abgelehnt (400). Die Fehlermeldung enthält den erkannten Pattern-Typ.
3. **Audit Log:** Jeder REST/MCP-Request erzeugt einen Audit-Eintrag. Audit Log ist read-only über die API.
4. **Explain+:** `mnemlet_explain` liefert Trust-Felder (ingested_by, caller_identity, secret_guard_result, confirmation_count) zusätzlich zu v0.2s Provenance.
5. **Namespace Policies:** Policies werden gelesen, bei Verletzung wird eine Warnung ins Audit Log geschrieben. Hard Block nur bei Secret Guard `action=block`.
6. **Backup:** `mnemlet backup` erzeugt einen tar.gz-Snapshot von DB + ChromaDB + Vault + Config (ohne api_key). Backup läuft auf dem laufenden Server: SQLite im WAL-Mode unterstützt konsistente Reads, für Vault/ChromaDB werden kurze Schreib-Locks gesetzt.
7. **Restore:** `mnemlet restore` sichert die aktuelle DB, ersetzt sie durch den Snapshot, loggt den Restore im Audit.
8. **Startup-Check:** Bei jedem Start werden Host, API Key, und File Permissions geprüft. Probleme werden prominent geloggt.
9. **Abwärtskompatibilität:** Bestehende Mnémlet-Instanzen ohne api_key, ohne neue Tabellen, ohne Security-Modul starten weiterhin. Neue Spalten sind additive Defaults.

---

## Risiken

| Risiko | Wahrscheinlichkeit | Auswirkung | Gegenmaßnahme |
|--------|-------------------|------------|---------------|
| **Secret Guard False Positives** | Mittel | Mittel | Warn-Modus als Alternative. Regex-Patterns konservativ gewählt. Namespace-spezifisch konfigurierbar. |
| **Audit Log wächst unbegrenzt** | Niedrig | Niedrig | Solo-Pi-Betrieb: DB-Größe wächst langsam. Backup sichert Audit mit. Für Jahre ausreichend. |
| **API Key im Config-File lesbar** | Mittel | Mittel | Start-Warnung bei world-readable Config. Dokumentation empfiehlt `0600`. |
| **Regex-Bypass (Secret nicht erkannt)** | Mittel | Mittel | Guards sind Defense-in-Depth, nicht alleinige Maßnahme. Solo-Setup limitiert Risiko. |
| **Backup-Größe auf Pi** | Niedrig | Niedrig | SQLite + Vault kompakt. ChromaDB kann größer werden. gzip-Kompression. |
| **v0.2/v0.3-Abhängigkeit** | Mittel | Hoch | P0-Features (Auth, Guard, Audit) sind unabhängig und können vor v0.2 geliefert werden. P1-Features (Explain+, Namespace Policies) benötigen v0.2. |

---

## Was bewusst NICHT gebaut wird

| Feature | Warum nicht |
|---------|-------------|
| **Encryption at Rest** | Solo auf Pi. OS-Level (LUKS) ist der richtige Platz. Mnémlet wäre ein schlechter Krypto-Layer. |
| **Multi-User RBAC** | Solo-Setup. Namespace = Organisation, nicht Isolation. Wer Multi-User braucht: separate Instanzen. |
| **TLS** | Localhost-only. Reverse Proxy (Caddy/Nginx) für externe Zugänge. Mnémlet nicht als TLS-Terminator missbrauchen. |
| **Per-Agent API Keys** | P2. Mehrwert (bessere Audit-Zuordbarkeit) steht nicht im Verhältnis zum Setup-Overhead für Solo. |
| **LLM-basierte Secret Detection** | Braucht Ollama bei jedem Ingest. Regex deckt 95% der kritischen Fälle ab. |
| **Selective Namespace Export** | P2. Full Snapshot reicht. Partieller Export ist Nice-to-have, nicht Muss. |
| **Rate Limiting** | Solo + Localhost. Ein lokaler Prozess, der floodet, ist ein anderes Problem. |
| **Audit Log Cleanup/Rotation** | Solo-Betrieb. DB wächst langsam. Backup sichert Audit mit. Cleanup ist P2. |

---

## Offene Punkte (v0.3 nicht im Scope)

- **Per-Agent API Keys:** Better audit attribution, but more management. P2 for v0.4+.
- **Secret Guard Custom Patterns:** User-defined regex patterns per namespace. P2.
- **Selective Export:** Namespace or time-range based export. P2.
- **Audit Log Retention Policies:** Configurable cleanup, but not yet needed. P2.
- **mTLS or Token Rotation:** Not needed for Solo self-hosted. P3+.