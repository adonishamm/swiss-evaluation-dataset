# Dossier format: procedural steps, generated documents, traps

Status: proposal, 1 Oct 2026. Builds on `case-format-timeline.md`. Replaces "predict the verdict" as the main task.

## 1. Idea

A case is a procedure with steps. At each step a party has to act: file a claim, object, appeal, produce evidence. Each step has a deadline, a legal basis, and documents to use. The agent walks the steps one at a time, with a **dossier** of documents in front of it, and is scored at each step on the action, the deadline, the documents it uses and refuses, and the articles it cites.

We do not have the original PDFs. We generate the documents from the facts section, in the case's language, with a realistic header (author, date, recipient, reference, subject). Because we generate them, we also generate **traps** and label them at creation time.

## 2. Steps of a Swiss social insurance procedure

| Step | Actor | Act | Legal basis | Deadline |
|---|---|---|---|---|
| S1 claim | insured, employer | file the claim with the insurer / IV office | art. 29 ATSG / LPGA | none, but benefits start from filing |
| S2 inquiry | insurer | medical reports, expert opinion, home inquiry, employer questionnaire | art. 43, 44 ATSG | right to be heard on the expert |
| S3 pre-decision | IV office | Vorbescheid / préavis | art. 57a IVG | objection within 30 days |
| S4 decision | insurer | formal decision | art. 49 ATSG | |
| S5 objection | insured | Einsprache / opposition (UV, KV, AHV, BVG none, IV none) | art. 52 ATSG | 30 days |
| S6 cantonal appeal | insured or insurer | Beschwerde to the cantonal insurance court | art. 56-61 ATSG, art. 7 CPC for VVG | 30 days |
| S7 federal appeal | losing party, federal office | Beschwerde in öffentlich-rechtlichen Angelegenheiten / recours en matière de droit public, or civil appeal for VVG | art. 82 ff. LTF, art. 95, 97, 105 LTF review limits | 30 days, cost advance |
| S8 outcome | Federal Supreme Court | dismissal, approval, remand | | |

Private insurance (VVG / LCA) differs: no objection, no pre-decision; the policyholder sues before the cantonal court as single instance (art. 7 CPC), then civil appeal to the Federal Supreme Court (art. 72 ff. LTF). The step template is chosen by domain.

Not every case has every step. The procedural history is extracted from the facts section ("Par décision du ...", "Saisi d'un recours ...", "Mit Verfügung vom ...", "Dagegen erhob ... Beschwerde").

## 3. Document record

```json
{
  "doc_id": "D07",
  "type": "decision",
  "title": "Décision de l'Office AI du canton de Vaud",
  "author": "Office AI Vaud",
  "recipient": "A.________, par ses parents",
  "date": "2023-10-26",
  "reference": "AI 123.456",
  "language": "fr",
  "body": "...",
  "ground_truth": {
    "status": "real",
    "step_created": "S4",
    "use_at_steps": ["S6", "S7"],
    "trap_type": null,
    "source_sentence": "par décision du 26 octobre 2023, l'office AI a informé l'assuré ..."
  }
}
```

`ground_truth` is never shown to the agent. `status` is `real`, `trap` or `absent` (the document that should exist but does not).

## 4. Trap types

| Code | Trap | Rule the agent must apply |
|---|---|---|
| T1 future | document dated after the current step | it does not exist yet; do not use |
| T2 superseded | earlier version replaced by a later one (first inquiry report, first medical certificate) | use the latest; the old one may still matter for history |
| T3 unsent | draft objection or appeal never filed or never notified | no legal effect; deadline keeps running |
| T4 wrong person | similar document for a sibling, a colleague, another insured | discard |
| T5 wrong law version | article text in force today instead of at the decision date | apply the version in force at the relevant date |
| T6 look-alike | plausible but irrelevant document (unrelated diagnosis, unrelated insurer letter) | discard |
| T7 absent | the decisive document is missing from the dossier (IQ test, accident report, employer salary statement) | say it must be requested; never cite it as if it existed |

Each dossier carries 6 to 10 real documents and 3 to 5 traps, at least one T1 and one T7. Documents are numbered in random order, not chronologically.

## 5. Worked example: 8C_229/2024 (IV, allocation pour impotent, autism, Vaud)

### Procedural history, from the facts

| Step | Date | Actor | Act |
|---|---|---|---|
| S1 | 2011-10-18 | parents | claim to the IV for the child (TED, CIM-10 F84) |
| S2 | 2011 | IV office, SMR | congenital disorder recognised (ch. 405 OIC); medical measures from 2011-07-21; helplessness allowance light from 2011-06-01, medium from 2012-03-01 |
| S1' | 2022-02-28 | insured, parents | two adult claims: helplessness allowance; vocational measures and pension |
| S2' | 2023-08-23 | IV office | home inquiry report: autonomous in daily acts, needs life-management support 2h50 per week |
| S4 | 2023-10-26 | IV office | decision: allowance withdrawn from 2024-01-01, autism classed as psychic impairment, so a pension entitlement would be required (art. 42 al. 3 LAI) |
| (info) | 2023-12-04 | IV office | takes over an initial vocational training INSOS 2023-11-21 to 2025-11-20 |
| S6 | 2023/2024 | insured | appeal to the Vaud cantonal court; court admits, allowance light from 2024-01-01: autism is a mental, not psychic, impairment |
| S7 | 2024 | OFAS | federal appeal; suspensive effect requested, granted 2024-08-28 |
| S8 | 2025-09-24 | Federal Supreme Court | partial approval: new criterion, a mental impairment is one with an accompanying intellectual disability; remand to the IV office for a medical expert opinion on that point |

### Dossier (real documents)

| id | type | date | content |
|---|---|---|---|
| D01 | claim | 2011-10-18 | parents' claim form for A., diagnosis TED |
| D02 | SMR opinion | 2011 | congenital disorder ch. 405 OIC recognised |
| D03 | decision | 2012 | helplessness allowance medium from 2012-03-01 |
| D04 | claim | 2022-02-28 | adult claim, helplessness allowance |
| D05 | claim | 2022-02-28 | adult claim, vocational measures and pension |
| D06 | inquiry report | 2023-08-23 | home inquiry, 2h50 per week support |
| D07 | decision | 2023-10-26 | allowance withdrawn from 2024-01-01, art. 42 al. 3 LAI |
| D08 | letter | 2023-12-04 | INSOS training taken over, daily allowances paid as salary |
| D09 | appeal | 2023-11 | cantonal appeal: autism is mental, not psychic |
| D10 | judgment | 2024 | cantonal judgment admitting the appeal |
| D11 | appeal | 2024 | OFAS federal appeal, cites 9C_566/2019 |

### Dossier (traps)

| id | type | trap | content |
|---|---|---|---|
| D12 | inquiry report | T2 superseded | home inquiry 2022-06, 4h per week support, replaced by D06 |
| D13 | judgment | T1 future | the cantonal judgment D10 is in the dossier at step S4, before it exists |
| D14 | objection draft | T3 unsent | draft objection to D07 dated 2023-11-10, never filed |
| D15 | medical certificate | T4 wrong person | certificate for the insured's brother, ADHD |
| D16 | statute extract | T5 wrong version | art. 42 LAI in its 2024 wording, with the amended paragraph |
| D17 | medical letter | T6 look-alike | paediatrician letter about a food allergy |
| none | IQ assessment | T7 absent | the neuropsychological test proving or disproving intellectual disability. It decided the case and was never produced |

### Questions at step S6 (insured must appeal the decision of 2023-10-26)

Agent sees: D01 to D09, D12, D13, D14, D15, D16, D17 in random order, and the facts up to 2023-12.

1. Next action and deadline. Gold: appeal to the cantonal insurance court within 30 days of notification of D07 (art. 56, 60 LPGA); D14 has no effect because it was never filed and IV decisions are not subject to objection anyway (art. 69 LAI).
2. Documents to use: D06, D07, D04, D02. To discard: D12 (superseded), D13 (does not exist yet), D14 (unsent), D15 (wrong person), D16 (wrong version: the 2023 wording applies), D17 (irrelevant). Missing and to be requested: a neuropsychological assessment of intellectual functioning (T7).
3. Legal basis: art. 42 al. 3 LAI (version in force in 2023), art. 37 RAI, art. 56, 60, 61 LPGA.
4. Argument: the law reserves the pension condition for *exclusively psychic* impairments; autism is a developmental disorder; the decisive fact is whether an intellectual disability accompanies it; evidence must be produced.

Gold for 4 comes from consid. 4 to 6 of the ruling, which created the intellectual-disability criterion and remanded for exactly that evidence.

## 6. Scoring per step

| Metric | Definition |
|---|---|
| action | correct next act (closed list per domain) |
| deadline | correct length and starting point |
| doc precision / recall | documents used vs gold `use_at_steps` |
| trap rate by type | share of traps of each type that the agent used |
| phantom document | agent cites a document not in the dossier (and not the T7 request) |
| absent handling | agent names the missing document and asks for it |
| articles | precision / recall against the step's legal basis, version-aware |

Aggregate per case, per domain, per language, per trap type. Report the trap-rate table separately: it is the most readable result for a non-technical audience.

## 7. Build plan

1. `06_procedural_history.py`: regex over the facts for dated acts ("par décision du", "Mit Verfügung vom", "Saisi d'un recours", "a déposé", "hat ... Beschwerde erhoben", "Einsprache", "opposition"), output the step table per case. Target: 100 cases, 4 to 8 steps each.
2. `07_generate_dossier.py`: LLM generates real documents from the step table and the facts, one template per document type, then generates the traps from the same templates with the labels set. Language = case language.
3. Jurist review of the real documents only: they must not say more than the facts say. Traps need no review.
4. `08_step_questions.py`: for each step, build the agent prompt (facts so far, dossier subset, question) and the gold.
5. Scoring in `eval/scoring.py`.

## 8. Pilot results (1 Oct 2026)

Generator: `scripts/07_generate_dossier.py`, one headless call to the Claude Code CLI per case (Sonnet), input = facts + procedural skeleton only. Five pilot cases (FR IV, DE IV, DE VVG, IT UV, FR KV).

| Measure | Result |
|---|---|
| Time per case | 100 to 120 s |
| Cost per case | about 0.21 to 0.25 USD |
| Documents per case | 8 to 10 real, 5 traps |
| Automatic checks (counts, mandatory trap types, body length, absent document) | all passed |
| Leak scan (federal outcome wording in any document) | none |
| Language of documents | always the case language |
| Step questions per case (`08_step_questions.py`) | 6 to 12, about 9 documents on the table, 4 traps among them |

Three rules added after reading the first batch:

1. **Traps must not announce themselves.** The first batch wrote "brouillon, à relire avant envoi" and "BOZZA, NON SPEDITA" on the unsent drafts. The prompt now forbids any such label; the giveaway has to be a detail (unsigned block, no registered-mail number, consolidation date, different birth date) and goes into `trap_note` for the reviewer only.
2. **Institutional disputes are excluded from the test set.** 9C_250/2025 (federal office vs canton, premium subsidies), 9C_212/2025 (pharma company vs federal office, drug list) and 8C_531/2024 (IV office vs court, costs) have no insured person at the centre. Rule in `02_sample_cases.py`; check in `04_assemble_testset.py`: the facts must mention an anonymised person.
3. **Visibility window.** Just after step k the agent sees real documents created up to step k plus those dated before step k+1 (or 45 days when that date is unknown), the T1 and T5 traps always, and the other traps when dated inside the window. Without the window, the unsent draft objection dated ten days after the decision was never shown at the step where it matters.

The absent document chosen by the generator is reasonable but not always the one the ruling later made decisive (for 8C_229/2024 it picked "a current medical opinion on the adult diagnosis" where the court remanded for an intelligence assessment). That is expected: the generator never sees the considerations. The reviewer refines the absent document from the considerations in step 3 of the build plan.

## 9. Open points

- How many steps to ask per case: all, or only the two or three where the real parties made a mistake. Proposal: all steps, but weight the decisive ones double.
- Whether the agent gets the facts narrative at all, or only the dossier. Proposal: dossier only. The facts narrative is what the court wrote afterwards; a practitioner never has it.
- Generated documents can leak the outcome if the LLM paraphrases the considerations. Rule: generation prompt receives the facts and the step table only, never the considerations or the dispositive.
