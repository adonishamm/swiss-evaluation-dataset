# Case format v2: timeline and decision calls

Status: proposal, 30 Sep 2026. Replaces the "facts in, verdict out" record in README section 4 if adopted.

## 1. Idea

A court decision is a story that already happened. Somewhere in that story a company, an insurer or a bank had to make a call: pay or refuse, terminate or continue, sue or settle, appeal or accept. The court's ruling tells us, after the fact, which calls were right.

So each case becomes three things:

1. **A timeline** of dated events, reconstructed from the facts section. The source narrative is not linear: Swiss judgments tell the substantive story in thread order (the parties, the contract, the claim, the premium dispute, the fraud allegation) and only then the procedural story, and threads interleave. We present the events **shuffled**, some with relative dates only ("fourteen days after the reminder"), so the model has to rebuild the order before it can reason.
2. **Decision points.** Moments where one actor had to choose. Each has a closed list of options, and the model only sees the events up to that moment. Nothing after it is shown.
3. **Ground truth from the ruling.** The gold action at each decision point is the option the court's reasoning shows would have held up. A decision point is only scored when the court actually ruled on that action. If the court was silent, the point is kept for analysis but not scored.

The old task (predict the final outcome from the full facts) stays as a third, cheaper sub-task.

## 2. Record schema

```json
{
  "case_id": "4A_517/2024",
  "court": "CH_BGer_004",
  "decision_date": "2025-06-02",
  "language": "fr",
  "tier": "insurer_vs_company",
  "actors": {
    "INS": {"role": "insurer", "type": "company"},
    "EMP": {"role": "employer / policyholder", "type": "company", "name_in_text": "F.________ SA"},
    "B":   {"role": "insured employee, director of EMP", "type": "person"},
    "C":   {"role": "sister company, later bankrupt", "type": "company", "name_in_text": "C.________ SA"}
  },
  "timeline": [
    {"id": "E1", "date": "2017-05-30", "actor": "EMP", "event": "...", "source": "A.a"}
  ],
  "presentation": {
    "shuffle_seed": 17,
    "relative_dates": ["E14", "E15"],
    "hidden_ids": ["E22", "E23", "E24"]
  },
  "decision_points": [
    {
      "id": "DP1",
      "after_event": "E9",
      "actor": "INS",
      "question": "...",
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "gold": "D",
      "gold_basis": [{"law": "LCA", "article": "6"}, {"law": "LCA", "article": "4"}],
      "court_holding": "consid. 4.1: ...",
      "scored": true
    }
  ],
  "outcome": {"label": "dismissal", "appellant": "INS", "winner": "B", "dispositive": "..."},
  "cited_articles_substantive": [{"law": "LCA", "article": "4"}, {"law": "LCA", "article": "6"}, {"law": "LCA", "article": "7"}, {"law": "LCA", "article": "20"}, {"law": "LCA", "article": "39"}, {"law": "LCA", "article": "40"}, {"law": "CO", "article": "28"}, {"law": "CO", "article": "31"}, {"law": "CPC", "article": "7"}],
  "source_url": "https://entscheidsuche.ch/docs/CH_BGer/CH_BGer_004_4A-517-2024_2025-06-02.html"
}
```

## 3. Worked example: 4A_517/2024 (collective daily sickness allowance, insurer vs employer)

### Actors

| Key | Who |
|---|---|
| INS | Insurance company, later the appellant |
| EMP | F.________ SA, real estate company founded 2017, policyholder |
| B | Born 1959, painter, director of EMP and of the sister company C, the insured employee |
| C | C.________ SA, painting company, over-indebted, bankrupt Nov 2019 |

### Timeline (true order, as the model must reconstruct it)

| id | date | actor | event |
|---|---|---|---|
| E1 | 2017-05-30 | EMP | EMP incorporated, same address as C; B and his two sons are directors of both companies |
| E2 | 2019-02-05 / 02-12 | EMP, INS | Insurance proposal and policy: collective daily sickness allowance for EMP staff, 80 % of salary, 730 days, 30-day waiting period, effective 2019-03-01. Health questionnaire filled in |
| E3 | 2019-02-28 | B | B stops being director of C |
| E4 | 2019-03-01 | EMP | B on EMP payroll, net 7,219.70 per month plus 400 expenses |
| E5 | 2019-09-06 | B | B unable to work, reactive anxio-depressive episode |
| E6 | 2019-09 | EMP | B's September salary reduced to 5,645.70 |
| E7 | 2019-09-19 | EMP | B's registration as director of EMP deleted from the commercial register |
| E8 | 2019-10-11 | EMP | INS informed of the incapacity |
| E9 | 2019-10-16 | B | Treating physician certifies 100 % incapacity from 2019-09-06 |
| E10 | 2019-11-14 | C | C declared bankrupt |
| E11 | 2019-12-23 | B | Psychiatric expert report: mental health deteriorating since end of 2018 |
| E12 | 2019-09-06 to 2020-05-31 | INS | INS pays 239 daily allowances at 243.61 to EMP |
| E13 | 2020-02-18 | INS | Reminder for the unpaid first 2020 premium instalment; warning that benefits are suspended if not paid within 14 days |
| E14 | 2020-05-19 | INS | INS demands refund of 21,681.30 (allowances 4 Mar to 31 May 2020) because premiums still unpaid |
| E15 | mid 2020 | EMP, INS | Premiums paid. INS recognises the right for 15 Jun to 13 Sep 2020 but sets it off against the 21,681.30 and pays a balance of 487.20 |
| E16 | 2020-09-14 | INS | INS suspends payments again, "needs more information" |
| E17 | 2020-10-06 | INS | Interview of B about his real activity at EMP |
| E18 | 2020-11-20 | INS | INS announces it will reclaim every allowance paid: B has not proved any gainful activity at EMP |
| E19 | 2021-02-02 | B | B sues INS at the Fribourg cantonal court for 62,851.25 plus 56,761.15 |
| E20 | 2021-09-09 | INS | INS declares the contract cancelled retroactively to 2019-09-05: contract concluded to insure the staff of the over-indebted C, claim fraudulent under art. 40 LCA |
| E21 | 2022-05-04 | EMP | EMP terminates the contract |
| E22 | 2024-08-26 | court | Fribourg cantonal court orders INS to pay 111,817 (700 allowances minus 58,710 already paid); INS counterclaim for 58,710 rejected |
| E23 | 2024-10 / 12-02 | INS | INS appeals to the Federal Supreme Court, requests suspensive effect, granted 2024-12-02 |
| E24 | 2025-06-02 | court | Appeal dismissed. Costs 5,500 and 6,500 party costs on INS |

What the model sees for the timeline task: E1 to E21 shuffled, E15 and E14 given only relative to E13, actor keys instead of names, E22 to E24 hidden.

### Decision points

**DP1, after E9 (October 2019), actor INS.** The claim arrives five weeks after B's removal as director, six months after cover started, from a policyholder that shares an address with an over-indebted sister company.

| Option | Action |
|---|---|
| A | Refuse the claim, invoke fraud (art. 40 LCA) |
| B | Terminate the contract for non-disclosure at signature (art. 6 LCA), stating precisely which questionnaire answer was false, within four weeks |
| C | Refuse pending proof that B really worked for EMP |
| D | Pay after the waiting period, reserve rights, open an investigation |

Gold: **D**. Court, consid. 4.1: no false answer in the questionnaire was shown, INS never raised a proper non-disclosure grievance, and it never terminated in the legal form and deadline. Option B would only have been right if a specific false answer existed and INS acted within four weeks with precise reasons (art. 6 al. 2 aLCA). Basis: art. 4, 6, 7 LCA.

**DP2, after E13 (February 2020), actor INS.** The first 2020 premium instalment is unpaid.

| Option | Action |
|---|---|
| A | Formal reminder under art. 20 LCA, cover suspended after 14 days, resume when premiums are paid |
| B | Reclaim allowances already paid during the default period and set off against future allowances |
| C | Terminate the contract |

Gold: **A**. The cantonal court awarded 700 allowances minus what was paid, without excluding the March to May 2020 period, and the Supreme Court confirmed. The refund demand (E14) and the set-off (E15) did not hold. Basis: art. 20 LCA.

**DP3, after E18 (November 2020), actor INS.** INS believes the policy was taken out to insure a doomed company's staff.

| Option | Action |
|---|---|
| A | Cancel the contract retroactively for fraudulent claim (art. 40 LCA) and reclaim everything paid |
| B | Terminate for non-disclosure (art. 6 LCA) |
| C | Keep paying, contest only the amount (offset the IV pension B receives from Sept 2020) |
| D | Offer a settlement |

Gold: **C**. Court, consid. 3 to 4.3: fraud under art. 40 LCA requires deceit at the moment the claim is made and was not established; non-disclosure was never validly invoked and the four-week deadline had long passed; deceit under art. 28 CO not shown. INS chose A (E20) and lost 111,817 plus costs. Basis: art. 40 LCA, art. 6 LCA, art. 28 and 31 CO.

**DP4, after E22 (August 2024), actor INS.** The cantonal court has ruled against INS.

| Option | Action |
|---|---|
| A | Appeal to the Federal Supreme Court |
| B | Accept the judgment and pay |
| C | Negotiate a reduced amount |

Gold: **B** (C accepted as partial credit). The appeal was dismissed in full, including the subsidiary claim to deduct the IV pension, and cost INS 12,000 plus its own lawyer. The Federal Supreme Court only reviews questions of law and arbitrary fact-finding (art. 95, 105, 106 LTF), and INS's grievances were mostly re-argued facts.

### Outcome sub-task

Given all events E1 to E21 in true order: predict the ruling. Gold: INS's appeal dismissed, B wins. Substantive articles: art. 4, 6, 7, 20, 39, 40 LCA; art. 28, 31 CO; art. 7 CPC.

## 4. Tasks and scoring

| Task | Input | Output | Metric |
|---|---|---|---|
| T1 timeline | shuffled events, hidden future | ordered list of event ids | Kendall tau against true order; exact-order rate |
| T2 decision call | events up to the decision point, actor, options | chosen option, cited articles, 3-sentence justification | action accuracy on scored points; citation precision / recall against `gold_basis`; hallucinated-article rate |
| T3 outcome | full ordered timeline | approval / dismissal, who wins, articles | accuracy, macro F1, citation metrics as in README |
| cross-language | T2 asked in DE and FR | same as T2 | agreement rate on chosen option |

Report per tier (bank, insurer vs company, employer obligations, corporate finance), per language, per actor type (company decides vs insurer decides vs bank decides).

## 5. How decision points get written

1. Script drafts the timeline from the facts section (dates and actors are regular in Swiss judgments: "Par courrier du 18 février 2020, la société d'assurance a ...").
2. An LLM drafts two to four decision points per case from the timeline plus the considerations, using a fixed template: actor, moment, three to four options, the option the court's holding supports, the consideration number it rests on.
3. A law student checks every decision point against the considerations, fixes or deletes, and sets `scored` to false where the court did not actually rule on that call. Budget: 15 to 20 minutes per case, 100 cases, about 30 hours.
4. Blind check stays: 10 cases, student sees only the shuffled events up to each decision point and picks an option. If the student beats the base rate easily on DP4-type points ("should we appeal"), those points are dropped as trivially inferable.

## 6. Why this is better for a company audience

- The unit of evaluation is an action a legal or claims department takes, not a prediction only a judge makes.
- Decision points before litigation (DP1 to DP3) test whether the model knows the formal requirements that companies get wrong in practice: deadlines, precise motivation, reminder formalities.
- The final "appeal or not" point is where money is lost. In this case the wrong calls cost about 130,000 francs before lawyers' fees.
- It reuses everything already planned: same sources, same fetcher, same citation ground truth, same article validator.

## 7. Open questions

- Actor choice: score the company's calls, the insurer's, or both? The example scores the insurer because it made the decisions. For bank cases the company is usually the one deciding (sue the bank or not). Proposal: one primary actor per case, chosen as the party that made the contested moves.
- Options are closed lists. An open-ended "what would you do" plus rubric grading is possible but needs an LLM judge and a rubric per point. Start closed, add open later.
- Cases with 5,000-word facts produce 40+ events. Cap timelines at 25 events by merging minor ones.
