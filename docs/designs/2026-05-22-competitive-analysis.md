# Mnémlet — Wettbewerbsanalyse & Positionierung

**Datum:** 2026-05-22  
**Autor:** Mira (Produktstrategie)  
**Status:** Vorlage zur Diskussion — keine Entscheidungen, kein Code  
**Fokus:** Konzeptioneller Vergleich, glaubwürdige Claims, Positionierung

---

## 1. Was andere gut machen

### Mem0
Der Marktführer. 41k GitHub-Stars, $24M Series A, AWS Agent SDK exklusiver Memory-Provider.  
**Stärken:**
- Multi-Store-Architektur (KV + Vector + Graph) — die differenziertesten Speichertypen im Feld
- Adaptive Updates: Erkennt Duplikate und aktualisiert bestehende Memories statt anzuhäufen
- Intent-aware Retrieval: Sucht nicht nur semantisch, sondern filtert nach Intention
- Reife Integrationen: CrewAI, LangChain, OpenAI-nativ, TypeScript-SDK, CLI
- Self-hosted möglich (Docker + Qdrant)
- 26% höhere Accuracy als OpenAI Memory auf LoCoMo (0.96 vs 0.76), 91% weniger Latenz als Full-Context

**Schwächen:**
- LLM-abhängig bei Ingestion (Extract + Update erfordert OpenAI/Anthropic-Calls) = Token-Kosten
- Cloud-First-DNA: Self-hosted ist möglich, aber klar zweitrangig
- Kein Decay/Forgetting — Memories bleiben für immer, es sei denn man löscht manuell
- Kein lesbarer Vault — Qdrant-Vector-Store ist eine Blackbox
- Kein Sleep/Consolidation-Modell

### OpenMemory MCP (Mem0)
Mem0's MCP-Server-Variante. Local-first, SSE-basiert.  
**Stärken:**
- MCP-native Integration (Cursor, Claude Desktop, Windsurf, Cline)
- Architecturally sauber: `/mcp/` Endpunkte, Qdrant-Backend
- Audit-Logs und Access Controls (im Server-Mode)

**Schwächen:**
-起居gleiche LLM-Abhängigkeit wie Mem0
- Kein Decay, kein Forgetting
- Kein lesbares Storage
- Keine isolierte Sleep/Consolidation
- In der Praxis: „Mem0, aber als MCP-Server" — kein eigenständiges Produkt

### Letta / MemGPT
Von der Forschung ins Produkt. Stateful Agents mit Memory-Block-Architektur.  
**Stärken:**
- OS-inspiriertes Modell: Main Memory ↔ Archival Memory, explizite Context-Window-Verwaltung
- Agent File (.af) Format — Serialisierbare, portable Agent-Zustände
- Conversations API: Shared Memory über parallele Agenten-Sessions
- Letta Code: Memory-first Coding Agent (Apr 2026)
- DeepLearning.AI-Kurs — stärkste akademische Glaubwürdigkeit im Feld
- Transparente Memory-Verwaltung: Agent kann selbst Memory Blocks einsehen und bearbeiten

**Schwächen:**
- Agent-First-DNA: Es ist ein Agent-Framework, kein Memory-Service. Memory ist an Agenten-Instanz gebunden
- Schwerer Setup: Letta Server + LLM-Provider + State-Management
- Kein Decay — Memory Blocks verfallen nicht automatisch
- Kein bitemporales Modell — kein „Wann wurde das gewusst?"
- Kein lesbares Vault-Format
- Vendor Lock-in: Tiefe Integration in Letta-eigenes Agenten-Modell

### LangMem / LangGraph Memory
LangChains Memory-SDK über LangGraph StateGraph.  
**Stärken:**
- Drei Memory-Typen: Episodic (Vergangenheit), Semantic (Fakten), Procedural (selbst-modifizierende System-Prompts)
- Procedural Memory ist einzigartig — Agenten lernen eigenen Operating-Modus
- Namespaced by user_id/team_id/app_id
- Background-Extraction ohne Blocking
- LangChain-Ökosystem — niedrige Einstiegshürde für bestehende Nutzer

**Schwächen:**
- Harter Lock-in an LangChain/LangGraph — funktioniert nicht ohne
- Kein Managed Hosting — Storage-Backend selbst konfigurieren
- Kein Decay/Forgetting
- Kein lesbares Vault
- Procedural Memory ist experimentell und unzureichend dokumentiert
- Fragmentiertes Ökosystem (LangChain → LangGraph → LangMem)

### Zep / Graphiti
Temporal Knowledge Graph. Das anspruchsvollste Architektur-Modell im Feld.  
**Stärken:**
- Bi-temporales Modell: Event-Zeit + Ingestion-Zeit für jeden Fakt — einzigartig
- Knowledge Graph + Vector + BM25 Hybrid-Retrieval
- 63.8% auf LongMemEval (vs. Mem0 49.0%) — stärkste Retrieval-Qualität benchmarked
- Episodische + semantische + Community-Subgraphs
- Explicite Invalidierung: Fakten haben Validity Windows, veraltete werden invalidiert, nicht gelöscht
- MCP Server v1.0 (Nov 2025)

**Schwächen:**
- Hohe Token-Kosten: >600.000 Token pro Konversation laut Mem0-Papier
- Latenter Retrieval: Korrekte Antworten erscheinen erst Stunden nach Ingestion (Background-Graph-Verarbeitung)
- Schwergewichtig: PostgreSQL + Neo4j + Graphiti + Embeddings — kein Pi-Setup
- Commercial-First: Community Edition wurde eingestellt (Apr 2025)
- Komplexe Operations — kein „pip install und los"

### Einfache Vector-DB-Agent-Memories
(ChromaDB/Weaviate/Pinecone + Embedding-Lookup, wie es viele Tutoriale zeigen)  
**Stärken:**
- Simpel, gut dokumentiert, schnell implementiert
- Keine zusätzliche Infrastruktur nötig wenn man sowieso RAG betreibt

**Schwächen:**
- Kein Lifecycle: Memories verfallen nie, werden nie konsolidiert
- Keine Typisierung: Alles ist ein Embedding-Vector
- Keine Deduplikation: Gleicher Fakten in 10 verschiedenden Formulierungen
- Kein Widerspruchs-Handling: Neue und alte, widersprüchliche Fakten koexistieren
- Keine Provenance: Woher kommt ein Ergebnis? Seit wann?
- Skaliert nicht: Ab ~1000 Memories wird das Retrieval-Problem offensichtlich

---

## 2. Vergleichstabelle

| Dimension | **Mnémlet** | **Mem0** | **OpenMemory** | **Letta/MemGPT** | **LangMem** | **Zep/Graphiti** | **Simple Vector-DB** |
|---|---|---|---|---|---|---|---|
| **Architektur** | SQLite + ChromaDB + Markdown Vault | KV + Vector + Graph (Qdrant) | Mem0 + MCP Wrapper | Memory Blocks (main + archival) | LangGraph StateGraph Store | Temporal Knowledge Graph | Vector-Only |
| **Decay / Forgetting** | ✅ Exponentiell, konfigurierbar, Interaction-basiert | ❌ | ❌ | ❌ | ❌ | ⚠️ Validity Windows (kein Decay) | ❌ |
| **Sleep / Consolidation** | ✅ Dedup, Rescore, Cluster, Briefing | ❌ | ❌ | ❌ | ⚠️ Background Extraction (nur Ingest) | ⚠️ Background Graph Processing (aber: verzögert) | ❌ |
| **Inspectable Vault** | ✅ Markdown + YAML Frontmatter | ❌ (Vector-DB) | ❌ | ⚠️ .af Format (JSON-artig) | ❌ | ❌ (Graph-DB) | ❌ |
| **MCP-Tools** | 8 (ingest, recall, search, status, namespaces, update, decay_config, export) | ~10 | ✅ (add, search, list) | ❌ (eigene Agent-API) | ❌ (SDK-basiert) | ✅ (MCP Server v1.0) | ❌ |
| **REST API** | ✅ | ✅ | ✅ | ✅ | ❌ (SDK-first) | ✅ | ❌ |
| **Self-Hosted** | ✅ First-Class | ⚠️ Möglich, aber Cloud-First | ✅ | ✅ | ✅ | ⚠️ Community Edition eingestellt | ✅ |
| **Local LLM** | ✅ Ollama (Gemma3:4b, CPU-only Pi) | ❌ (OpenAI/Anthropic) | ❌ | ⚠️ Konfigurierbar | ⚠️ Konfigurierbar | ❌ | N/A |
| **Pi / Low-Resourced** | ✅ 450 MB baseline | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ ChromaDB ja, aber kein Memory-Lifecycle |
| **Zero API Costs** | ✅ (ONNX Embeddings lokal) | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (wenn Embeddings lokal) |
| **Bitemporales Modell** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Graph-basiert** | ❌ | ✅ (Graph-Modus) | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Agent-Framework-Kopplung** | Framework-agnostisch | Framework-agnostisch | MCP-Clients | Letta-gebunden | LangChain-gebunden | Framework-agnostisch | Handgestrickt |
| **Procedural Memory** | ❌ (v0.2: Typ-Policies) | ❌ | ❌ | ⚠️ Memory Blocks | ✅ (System-Prompt-Updates) | ❌ | ❌ |
| **Auth / Security** | ⚠️ v0.3 geplant (API Key, Secret Guard, Audit) | ✅ (Platform: Enterprise RBAC) | ⚠️ (Self-hosted: Admin API Key) | ✅ | ❌ | ✅ | ❌ |
| **Backup/Restore** | ⚠️ v0.3 geplant | ✅ (Cloud) | ⚠️ (Qdrant-Backup) | ✅ (.af Export) | ⚠️ (StateGraph-Export) | ✅ | ❌ |
| **Team / Organization** | Solo-Setup | ✅ Multi-Tenant, org_id | ⚠️ | ✅ (Conversations API) | ✅ (namespaced) | ✅ | ❌ |
| **Benchmark Public** | ✅ (48 Queries, LoCoMo-derivat, reproduzierbar) | ✅ (LoCoMo, eigener Benchmark) | — | ⚠️ (Letta Evals) | — | ✅ (LongMemEval) | — |
| **License** | MIT | Apache 2.0 | Apache 2.0 | Apache 2.0 | MIT | Apache 2.0 (Graphiti) | Various |
| **Reife** | v0.1, solo-dev, dogfooded | v1.x, $24M Funding, Production | v0.x, Mem0-Add-on | v1.x, VC-backed, Production | v0.x, experimentell | v1.x, Production | Ad-hoc |

---

## 3. Wo ist Mnémlets Differenzierung?

### Was Mnémlet einzigartig macht (und andere NICHT haben):

1. **Brain-Inspired Decay** — Kein Konkurrent hat konfigurierbares exponentielles Decay mit Interaction-Basiertem Boosting. Jeder andere hortet für immer oder nutzt starre Validity Windows (Zep). Mnémlets Ansatz: Was du benutzt, bleibt. Was du ignorierst, verblasst. Das ist kein Feature, das ist eine Philosophie.

2. **Sleep Engine** — Ein Nightly-Consolidation-Cycle (Dedup → Rescore → Cluster → Briefing) ist konkurrenzlos. Others haben Background-Ingestion (LangMem, Zep), aber niemand hat einen bewussten Konsolidierungszyklus der während Inaktivität läuft. Das entspricht tatsächlich dem, was das Gehirn im Schlaf macht.

3. **Inspectable Markdown Vault** — Eine Memory-Engine deren Output man in Obsidian öffnen, `grep`en, `git` versionieren kann. Zero black box. Jeder Konkurrent nutzt Vector-DBs, Graph-DBs oder JSON-Blobs. Kein anderer bietet menschenlesbares Storage als First-Class-Konzept.

4. **Local-First bis ins Mark** — Nicht "self-hosted möglich", sondern "self-hosted first". Lokale ONNX-Embeddings, lokales Ollama-LLM, lokale SQLite+ChromaDB, Pi-kompatibel. Mem0 und Zep sagen "self-hosted" und meinen "du kannst es auf deinem Server laufen lassen, aber du brauchst OpenAI-Keys und Qdrant und PostgreSQL und Neo4j".

5. **Solo-Setup-Philosophie** — Keine Multi-Tenancy, keine Organizations, keine Enterprise-Features. One person, one instance, one config. Das ist kein Mangel, das ist eine Design-Entscheidung.

### Was Mnémlet NICHT einzigartig macht (und sich nicht darauf berufen sollte):

- **Hybrid Search (BM25 + Vector)** — Das hat Zep auch, und besser (Graph + BM25 + Vector).
- **Namespaces** — Mem0 hat user_id/agent_id/run_id/app_id, LangMem hat namespaced stores, Zep hat Entity-Graphs. Mnémlets Namespaces sind einfacher, aber nicht einzigartig.
- **MCP-Server** — OpenMemory hat das auch, Zep hat das auch. MCP wird zum Kommoditäts-Feature.
- **REST API / SDK** — Jeder hat das.
- **Benchmark-Ergebnisse** — 48 Queries auf einem synthetischen Dataset reichen nicht, um Behauptungen über Retrieval-Qualität aufzustellen.

---

## 4. Glaubwürdige vs. Unseriöse Claims

### Glaubwürdig ✅

| Claim | Begründung |
|---|---|
| "First brain-inspired memory engine with configurable forgetting" | Exponentielles Decay + Interaction-Boosting + Sleep Engine — kein Konkurrent hat dieses Modell |
| "Runs on a Raspberry Pi with zero API costs" | 450 MB RAM, lokale ONNX-Embeddings, nachgewiesen funktionsfähig |
| "Human-readable Markdown vault — no black box" | Tatsächlich als `.md` + YAML auf der Platte, in Obsidian öffnbar |
| "Sleep consolidation: dedup, rescore, cluster, briefing" | Implementiert und funktionsfähig |
| "Framework-agnostic MCP server with 8 tools" | REST + MCP + CLI + SDK, kein Framework-Lock-in |
| "Solo self-hosted, no cloud dependency" | Konfigurierbar ohne externe Services, alle Defaults lokal |

### Unseriös ❌

| Claim | Warum nicht |
|---|---|
| "State-of-the-art retrieval quality" | 48 Queries auf einem synthetischen Dataset sind kein LoCoMo-Ergebnis. Keine Peer-Review, kein externer Benchmark. |
| "Better than Mem0 at X" | Kein vergleichbarer Benchmark. Mem0 hat LoCoMo, Zep hat LongMemEval. Mnémlet hat 48 Queries. |
| "Production-ready memory infrastructure" | Kein Auth, kein Audit, kein Backup/Restore, keine Multi-Session-Garantien. v0.1. |
| "Enterprise-grade" | Solo-Setup by Design. Keine RBAC, keine Org-Isolation, kein SLA. |
| "Graph-enhanced memory" | Mnémlet hat keinen Knowledge Graph. BM25 + Vector ≠ Graph. |
| "93% MRR" oder andere quantitative Retrieval-Claims | Benchmark zu klein, Dataset synthetisch, keine externe Validierung. |
| "The only local-first AI memory" | OpenMemory heißt OpenMemory. MemPalace heißt MemPalace. Viele sind lokal möglich. Der Unterschied ist "local-first by design, not by deployment option". |

---

## 5. Was Mnémlet braucht, um als eigenständiges Produkt ernst genommen zu werden

### Must-Have (ohne diese wird man nicht ernst genommen)

| Feature | Warum | Status |
|---|---|---|
| **Auth: API Key** | Jeder Mem0-Vergleich startet mit "aber Mem0 hat Auth". Ohne das ist Mnémlet ein lokales Spielzeug. | v0.3 geplant |
| **Secret Detection bei Ingest** | API-Keys in Memories zu speichern ist ein echtes Risiko. Ohne Guard: kein ernsthafter Nutzer. | v0.3 geplant |
| **Audit Log** | Grundvoraussetzung für Nachvollziehbarkeit. Jeder ernste Konkurrent hat das. | v0.3 geplant |
| **Konträr-Handling (Supersession)** | "Ich nutze tabs" + "Ich nutze spaces" = Verwirrung. Ohne das ist Recall unzuverlässig. | v0.2 geplant |
| **Abstention Logic (Nix-Treffer-Handhabung)** | Besser kein Ergebnis als ein falsches. Aktuell liefert Recall immer etwas. | v0.2 geplant |
| **Reproduzierbarer Benchmark auf öffentlichem Dataset** | LoCoMo oder LongMemEval-Ergebnis. Ohne das: "show me the numbers" endet die Diskussion. | Design vorhanden, nicht ausgeführt |

### Should-Have (stärkt die Positionierung erheblich)

| Feature | Warum | Status |
|---|---|---|
| **Context Pack Builder** | Strukturierte Ergebnisse statt flacher Liste. Jeder Konkurrent hat eine Response-Structure. | v0.2 geplant |
| **Memory Classifier (Typisierung)** | Fact/Preference/Instruction/Event/Context — filterbares Retrieval. Mem0 hat das, Letta hat Memory Blocks. | v0.2 geplant |
| **Backup/Restore** | GBM-Strategie für Solo-Nutzer. Pi-SD-Karten sterben. | v0.3 geplant |
| **Namespace Policies** | Konfigurierbare Isolation zwischen Agents/Namespaces. Aktuell nur konventionell. | v0.3 geplant |
| **Provenance / Explainability** | "Warum wurde das geliefert?" — Trust-Frage. | v0.2 geplant |

### Nice-to-Have (unterstützt die Nische)

| Feature | Warum |
|---|---|
| **Obsidian-Integration (Plugin)** | Vault ist Markdown — ein Obsidian-Plugin wäre der logical next step |
| **Git-basiertes Vault-Versioning** | Memories als commit-bare Files, Diff zwischen Sessions |
| **Web Dashboard** | TUI reicht für Nerd-Nische, aber Web-UI öffnet andere Zielgruppen |
| **Telegram/Discord Bot Interface** | Erreichbarkeit, Mnemlet via Chat bedienen |
| **Multi-Instance Sync** | Für den Fall: zwei Pis, eine Synchronisation |

---

## 6. Positionierungsoptionen

### Positionierungssatz (Kern)

> **Mnémlet ist die einzige AI-Memory-Engine, die von Grund auf für Localhost gebaut ist — mit konfigurierbarem Vergessen, nächtlicher Konsolidierung und einem lesbaren Markdown-Vault. Für Menschen, die ihre Daten auf eigener Hardware kontrollieren wollen.**

### Drei mögliche Produkt-Narrative

---

**Narrativ A: "The Brain That Forgets"**

*Pitch:* Jede andere Memory-Engine hortet. Keine vergisst. Mnémlet ist die erste Engine, die das Vergessen als Feature behandelt — exponentiell abklingend, konfigurierbar, interaktionsgesteuert. Wie dein Gehirn im Schlaf konsolidiert: wegwerfen, was nicht mehr relevant ist, und zusammenfassen, was bleibt.

*Zielgruppe:* Agent Engineers, die das Context-Window-Problem verstehen und gezielt steuern wollen, was im Memory bleibt und was nicht.

*Risiko:* "Forgetting" ist schwer zu verkaufen. Die intuitive Assoziation ist "das ist doch falsch, ich will dass mein Agent sich an alles erinnert". Man muss das Vergessen als Feature erklären, nicht als Verlust.

*Stärke:* Klar differenziert. Niemand anderes macht das. Die Sleep-Engine-Metapher ist einprägsam.

---

**Narrativ B: "Your Memory, Your Hardware"**

*Pitch:* Mem0 ist hervorragend — wenn du ihre Cloud nutzt. OpenMemory läuft lokal — wenn du Qdrant und einen Cloud-LLM-Provider hast. Mnémlet läuft auf einem Raspberry Pi, ohne API-Key, ohne externe Dependency, ohne SQLite-Lizenz. Du öffnest deinen Vault in Obsidian. Du `grep`st durch deine Agenten-Erinnerungen. Du bist der Server.

*Zielgruppe:* r/selfhosted, r/LocalLLaMA, Homelab-Betreibende, Pi-Enthusiasten — Menschen für die "local" ein Wert, nicht eine Deployment-Option.

*Risiko:* Die Nische ist klein. Die meisten Leute, die AI-Memory wollen, nehmen die Cloud-Lösung. Und "läuft auf einem Pi" klinget nach einem Hack, nicht nach einem Produkt.

*Stärke:* Die treueste aller Zielgruppen. Selfhoster sind community-getrieben, bloggen, evangelisieren.

---

**Narrativ C: "The Transparent Alternative"**

*Pitch:* Jede Memory-Engine speichert in Vektor-Datenbanken und Graph-Stores, die du nicht lesen kannst. Mnémlet speichert jede Erinnerung als Markdown-Datei, die du in jedem Editor öffnen kannst. Du siehst genau, was dein Agent über dich weiß. Du kannst es bearbeiten, löschen, versionieren. No black box. No trust required. Audit by opening a folder.

*Zielgruppe:* Privacy-Bewusste, Sicherheits-Fokusierte, Leute die AI-Agenten einsetzen aber nicht blind vertrauen.

*Risiko:* "Transparent" heißt auch: man sieht die ganzen hässlichen Memories. Keine schöne Kuratierung. Das kann abschrecken. Und: Transparenz ohne Auth, Audit und Policies ist Transparenz ohne Schutz.

*Stärke:* Adressiert ein echtes, wachsendes Problem. Je mehr AI-Agenten Memory nutzen, desto wichtiger wird Nachvollziehbarkeit. Zep und Mem0 können das nicht bieten — ihre Stores sind undurchsichtig.

---

## 7. Risiken

| Risiko | Wahrscheinlichkeit | Auswirkung | Mitigation |
|---|---|---|---|
| **Mem0 OpenMemory wird gut genug lokal** | Hoch | Mittel | OpenMemory bleibt LLM-abhängig und hat kein Decay. Differenzierung bleibt, aber "läuft lokal" allein reicht nicht. |
| **Mem0 fügt Decay/Forgetting hinzu** | Mittel | Hoch | Die deutlichste Differenzierung fällt weg. Mnémlet muss dann auf Vault-Transparenz und Pi-Kompatibilität setzen. |
| **Zep Open-Source-Community wächst** | Mittel | Mittel | Graphiti (Zep's OSS-Komponente) hat 5k+ Stars. Aber: schwergewichtig, nicht Pi-tauglich, kein Decay. |
| **Mnémlet wird als "Mem0-Klon ohne Cloud" wahrgenommen** | Mittel | Hoch | Aktuelle README positioniert gut ("not because Mem0 is bad"). Bisherige Kommunikation ist ehrlich. Weiter so, aber noch schärfere Abgrenzung nötig. |
| **Solo-Dev-Burnout / Bus Factor = 1** | Hoch | Kritisch | Kein Mitstreiter, keine Funding, kein Dev-Team. Wenn Christoph aufhört, stirbt das Projekt. Community-Aufbau ist überlebenswichtig. |
| **Benchmark-Ernsthaftigkeit** | Mittel | Mittel | 48 Queries auf synthetischen Daten gegen LoCoMo/LongMemEval-Validierung der Konkurrenz ist ein David-vs-Goliath-Vergleich. Aber: nicht behaupten, was man nicht belegt hat. |
| **v0.2/v0.3-Features kommen zu langsam** | Mittel | Hoch | Die geplanten Features (Classifier, Supersession, Auth, Audit) sind die, die Mnémlet von "interessant" zu "nutzbar" machen. Ohne Supersession ist Recall bei widersprüchlichen Memoriesbroken. |
| **MCP wird Kommodität** | Hoch | Niedrig | MCP wird zum erwarteten Standardtool. Mnémlets 8 Tools sind gut, aber nicht mehr differenzierend. |

---

## 8. Empfehlung

### Kurzfristig (v0.2 — Intelligence Core)

Priorität 1: **Supersession + Abstention Logic** bauen. Ohne das ist Mnémlets Recall bei sich ändernden Präferenzen broken. Das ist kein Nice-to-have, das ist ein funktionaler Mangel. Der Classifier und Context Pack sind wichtig, aber zweitrangig — wenn Recall falsche/konträre Ergebnisse liefert, nützt die schönste Struktur nichts.

Priorität 2: **Benchmark auf LoCoMo oder einem öffentlichen, etablierten Dataset durchführen.** Nicht um zu gewinnen. Sondern um eine belastbare Baseline zu haben. Konservativ bleiben: "Wir evaluierten auf X, unsere Hit@3 war Y. Mem0 berichtet Z auf demselben Dataset." Nicht besser behaupten als man ist.

### Mittelfristig (v0.3 — Trust Layer)

Auth, Secret Guard, Audit Log, Backup/Restore. Das sind die Features, ohne die kein ernsthafter Nutzer Mnémlet in Produktion nehmen wird. Jeder Vergleich mit Mem0 endet bei "aber Mem0 hat Auth und Mnémlet nicht". Das muss zuende sein.

### Positionierung

**Narrativ B ("Your Memory, Your Hardware") als Primär-Narrativ, Narrativ A ("The Brain That Forgets") als Differenzierungs-Argument.**

Begründung:
- Die Local-First/Pi/Self-Hosted-Botschaft ist die breiteste Tür. Selfhoster sind eine wachsende, lautstarke Community.
- Das Decay/Sleep-Argument ist einprägsam und einzigartig, aber zu abstrakt als Lead. Es funktioniert als "once you're in the door"-Argument.
- Narrativ C (Transparenz) stützt beide, ist aber allein zu nischig.

**Konkreter Satz für README/Landing Page:**

> Mnémlet is a local-first AI memory engine that runs on hardware you control. It forgets what doesn't matter, consolidates while you sleep, and stores every memory as a readable Markdown file. No cloud. No API bills. No black box.

### Was wir NICHT tun sollten

- **Nicht gegen Mem0 antreten.** Mem0 hat $24M und 41k Stars. Ein Solo-Projekt kann diesen Kampf nicht gewinnen. Mnémlet ist die Alternative für die, die Mem0 nicht wollen — nicht der Mem0-Killer.
- **Keine Enterprise-Claims.** Kein Multi-Tenant, keine RBAC, keine SLAs. Solo-Setup, ehrlich kommuniziert.
- **Keine Retrieval-Quality-Claims ohne externen Benchmark.** Die 48-Query-Suite ist intern reproduzierbar, aber nicht mit LoCoMo vergleichbar. Entweder auf LoCoMo evaluieren, oder die Claims auf "reproduzierbares Setup" beschränken.
- **Keine "first" oder "only"-Claims ohne Recherche.** Mnémlet ist nicht "the first local-first memory engine", nicht "the only one with forgetting" (NeoCortex hat Decay, wenn auch anders). Präzise bleiben.

### Der wichtigste Satz

> Mnémlet ist nicht besser als Mem0. Mnémlet ist die Antwort auf die Frage: "Und wenn ich Mem0 nicht will?"

Das ist die Positionierung. Nicht Überlegenheit. Souveränität.

---

*Erstellt von Mira. Kein Code angefasst. Zur Diskussion.*