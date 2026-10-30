# Guyue Fangyuan · 古月方源

> **Grab it, refine it, make it yours.**
> Throw anything in. What comes out is parts you can use.

An agent skill (SKILL.md) for turning arbitrary material — books, code repositories, PDFs, apps, web pages, chat logs, a methodology — into **executable rules, reusable structures, and verifiable evidence**. Not a summary.

[中文说明](README.md)

---

## The problem it solves

You have probably been here:

- Dozens of saved articles, tutorial videos, and books — and when you actually need one, you can't recall any of it
- You want to learn how a project is architected, spend two days reading source, and still can't say why it was designed that way
- You want to borrow a feature from some app, and end up with a shell that only looks similar
- You ask an AI to summarize a document, get a wall of paraphrased text, and have to go back to the original anyway

**The root cause**: most "summarizing" makes long things short. What you usually want is to **turn external material into parts you can plug in directly**. Those are different operations.

Rule #2 of this skill puts it plainly:

> **Refining is not summarizing.** Summarizing makes long things short. Refining turns external material into parts usable right here — executable rules, reusable structures, verifiable evidence. **The output must be directly consumable by the next step.**

---

## Structure

### Five domains (routed by input form)

| Domain | What comes in | Handbook |
|---|---|---|
| **Text** | Articles, books, notes, transcripts | `references/TEXT.md` |
| **Document** | PDF, Word, PPT, Excel, images, scans | `references/DOCUMENT.md` |
| **Code** | Source repositories, scripts, configs, dependency manifests | `references/CODE.md` |
| **Software** | Executables, APKs, ASAR, firmware, running processes | `references/SOFTWARE.md` |
| **Conversation** | Chat logs, session transcripts, tickets, comments | `references/CONVERSATION.md` |

### Seven cross-domain guides (routed by what you need to do)

| File | Read it when |
|---|---|
| `references/DONTS.md` | **Scan the prohibitions before starting.** Includes a table of 13 excuses an agent gives itself, each with a rebuttal |
| `references/ARTIFACTS.md` | You need to know what traces something left on a machine; or to reconstruct facts from traces |
| `references/TAKE.md` | You want to turn a dismantled thing into your own product — five extraction axes, carrier table, rebuild order |
| `references/DISTILL.md` | You want to distill a person, an author, or a body of skill into usable rules — six-step skeleton, four depth levels |
| `references/DISTILL-CORE.md` | You want to **start distilling now** rather than read theory — six-layer model, three output templates |
| `references/MERGE.md` | Several skills or documents overlap and must become one — three merge modes, replay verification |
| `references/HONESTY.md` | You need to judge "is this being honest?" or handle pushback |
| `references/REVIEW.md` | Strict pre-delivery self-review, or reviewing someone else's artifact — 9-dimension scoring |

### Standing references

`PLAYBOOK.md` (hard-won pitfalls, subagent protocol) · `QUANTIFY.md` (how much effort to spend) · `METHOD.md` (what the user typically wants, how to accept it) · `PEERS.md` (comparable systems and what we absorbed) · `batch-processing.md` (batch ledgers and receipts) · `distillation.md` · `quality-and-recall-gates.md`

---

## Usage

### Three typical scenarios

**1. Turn a book into something executable**

```
User: refine this book, I need methods I can actually apply
→ Read TEXT.md. Three steps: split (smallest judgeable units) → judge (one conditional
  claim per unit) → assemble (rule set / checklist / decision tree)
```

**2. Dismantle an app and extract its mechanism**

```
User: I want this feature from an APK — how is it implemented?
→ SOFTWARE.md for forensics (structure / classes / references), then TAKE.md's five axes
→ Output: a mechanism spec — problem / structure / data flow / contract /
  decision rules / boundaries and failures / my minimal equivalent implementation /
  what I explicitly did not get
```

**3. Several overlapping skills, merge them**

```bash
python scripts/skill_conflict_scan.py <skills-dir> --only-red
```

```
→ MERGE.md: judge whether to merge (three hard signals) → choose how (three modes)
  → 🔴 STOP and present the decision package → only then build baseline and replay
```

### The one rule that matters most

> **Read on demand.** Only open the handbook for the domain this task lands in.
> A PDF? Ignore the software section. A repository? Ignore the document section.
> Reading everything is not diligence — it burns context and dilutes attention.

Reading can be narrowed further, down to the **section** level. Every handbook follows the same section order: *when to read → criteria → procedure → failure modes → verification → sources*. So:

| You only want to know | Read |
|---|---|
| Should I use this file at all | the first blockquote |
| Am I doing it right | criteria + verification |
| I'm stuck | failure modes |
| Can I trust this claim | sources |

---

## Design baseline (condensed from the ten rules)

1. **Judge the composition before choosing a tool** — not by file extension, but by "is this text, image, or machine code"
2. **Refining is not summarizing** — output must be directly consumable by the next step
3. **Every conclusion needs a landing point** — text → character range; documents → page; code → file:line; software → address / evidence ID
4. **Keep observation / inference / unknown separate** — never blend them into one paragraph
5. **Never pretend to have read something** — if a tool is missing, say so and offer a degraded path
6. **One block at a time** — split large material, parallelize what can be parallelized, but synthesis and final wording stay with the main agent
7. **Split output in two piles** — directly usable vs. pending judgment
8. **Source material is read-only**
9. **Check for duplicates before adding** — if an existing file can hold it, don't create a new one; check across skills too
10. **Back up before anything irreversible, then only touch the backup**

Full version in `SKILL.md`.

---

## Repository layout

```
guyue-fangyuan/
├── SKILL.md                     # Entry: five-domain map + ten rules + three checkpoints
├── README.md / README.en.md
├── LICENSE
├── references/
│   ├── 00-map.md                # When you can't tell which domain
│   ├── TEXT.md DOCUMENT.md CODE.md SOFTWARE.md CONVERSATION.md
│   ├── ARTIFACTS.md             # Traces: five data sources / volatility order / forward-backward tracing
│   ├── TAKE.md                  # Take & rebuild: five axes / four-layer fusion / rebuild order
│   ├── DISTILL.md               # Distillation skeleton
│   ├── DISTILL-CORE.md          # Distillation implementation (six layers, templates)
│   ├── MERGE.md                 # Merging: capacity line / three modes / replay / conflict scanner
│   ├── DONTS.md                 # Prohibitions + the excuse table
│   ├── HONESTY.md               # Six honesty rules
│   ├── REVIEW.md                # 9-dimension delivery review
│   ├── PLAYBOOK.md QUANTIFY.md METHOD.md PEERS.md
│   ├── batch-processing.md distillation.md quality-and-recall-gates.md
│   ├── digest-workflow-v2.md card-contract-v2.md
│   └── domain-profile.md        # Adapting to a vertical knowledge base
├── scripts/
│   ├── digest_batch.py          # Inventory / chunking / hashing / receipt reconciliation (stdlib only)
│   ├── style_metrics.py         # Writing-style quantification (sentence length, punctuation, hedges...)
│   ├── skill_conflict_scan.py   # Skill conflict scanner (trigger collisions, not similarity)
│   └── test_digest_batch.py
└── feedback/                    # Run receipts: pitfalls, carried across sessions
```

---

## Requirements

**Core logic has zero dependencies** — it is Markdown, plain text, readable by anyone.

Scripts use the Python standard library only. Optional additions:

| Optional | Purpose |
|---|---|
| Python 3.10+ | Running the scripts |
| MarkItDown / MinerU | Document → text (see `DOCUMENT.md`) |
| apktool + jadx + JDK 21 | Android decompilation (see `TAKE.md` appendix) |
| REA (MCP server) | Binary forensics (see `SOFTWARE.md`) |
| Ghidra / IDA | Native code decompilation (optional; falls back to black-box) |

> Paths like `D:\tools\...` or `C:\Users\<user>\` in the docs are **examples — substitute your own**.

---

## Known limitations (stated honestly)

- **Steps that depend on external tools will fail without them.** No decompiler engine means black-box only; no OCR means scanned files can't be read. The skill's approach is to **report the gap honestly**, never to fabricate a result.
- **The "five extraction axes" in `TAKE.md` is an inductive synthesis**, not a quotation from any single source. Treat it as inference and verify it once yourself.
- **The "excuse table" in `DONTS.md` comes from field practice**, not from a paper. It does work, but it's not peer-reviewed.
- **The conflict scanner only detects trigger collisions**, not contradictory instructions (one skill says "must do X", another says "never do X"). The latter still needs human reading.
- **Many rules came from one person's long-term single-machine work** (Windows, Chinese paths, a pile of hard-won pitfalls). On a different host, path- and tool-specific parts need re-checking.

---

## License

**MIT + Commons Clause** — see `LICENSE`.

| You may | You may not |
|---|---|
| Use it for anything, **including commercial products** | Sell the software itself, or a product whose value derives substantially from it |
| Modify and redistribute your changes | Rename it and sell it as your own product |
| Embed it in a larger product and sell that product | |
| Offer your product as a paid service (SaaS) | |
| Provide consulting and support | |

> ⚠️ **Strictly speaking this is not "open source"** (OSI-approved licenses cannot restrict commercial use). It is **source-available**. The code is fully public, readable, modifiable, and commercially usable; the only restriction is on reselling it as-is.

⚠️ One more caveat: when using this skill to dismantle someone else's work, **take mechanisms and designs only — never copy code, assets, or trademarks**. See the legal boundary table in `TAKE.md` §7.

> *"Reverse engineering is not copying code; it is re-implementing after understanding the principle."*

---

## Credits

| Source | What we absorbed |
|---|---|
| [Anthropic Agent Skills](https://agentskills.io) | SKILL.md standard, progressive disclosure |
| Hermes Agent `/learn` (Nous Research, MIT) | Three-tier progressive disclosure |
| SkillBank | Deduplication needs a threshold |
| SkillClaw | Before adding, ask: refine / create / skip |
| Cognee | Provenance for every piece of knowledge |
| ORRI methodology | Observation → Reverse → Reconstruct → Innovate |
| NIST SP 800-86 + RFC 3227 | Digital forensics phases, order of volatility |
| Anthropic《Building Skills for Claude》 | Anti-patterns, put critical validation in scripts |
| Ruben Hassid's "Taste Interviewer" | The three negative dimensions (aesthetic crimes / hard no's / red flags) |
| `distill-persona` (open source) | ≥2 source minimum, never invent quotes |
| MIND (arXiv 2601.03717) | Eight cognitive perspectives against distribution collapse |
| EvoSC (arXiv 2026) | Failures carry more signal than successes |

Every reference file ends with a source table stating where each rule came from and how strong the evidence is.
