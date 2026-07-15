# airway (Type Of Airway Ventilation) -- proposed category schema

Draft only -- not yet applied to `aumc_grid_feature_manifest_review_claude.md`.
3 categories: default `None`, `Endotracheal tube`, `Tracheostomy`. One match
rejected (not an airway type at all).

Validated against a six-patient airway-candidate audit plot generated during development:
admission 19579 shows a clean ETT -> tracheostomy transition (itemid 6735
`Geintubeerd` stops firing right as itemid 8189 `Spreekklepje`/`Trach.stoma`
starts); admission 14433 has ETT evidence only via tube-size/depth entries,
no `Geintubeerd` hit at all, confirming the merge is load-bearing, not
cosmetic; admission 152 shows the rejected `Fixatie reden` entry landing
mid-way through an already-continuous `Geintubeerd` stretch (a safety event
during intubation, not a state change).

## Endotracheal tube

| match | table | itemid | valueid | raw label | raw value |
|---|---|---|---|---|---|
| 1 | listitems | 6735 | 8 | Beste verbale reactie | Geintubeerd |
| 4 | listitems | 12751 | 1 | Tube referentiepunt | Mondhoek |
| 5 | listitems | 12625 | 1 | Tube route | Oraal |
| 6 | listitems | 12623 | 5 | Tube diepte | 23 |
| 7 | listitems | 19640 | 15 | V_EMV_NICE_Opname | Geintubeerd |
| 8 | listitems | 12624 | 6 | Tube maat | 8.5 |
| 9 | listitems | 12623 | 3 | Tube diepte | 21 |
| 11 | listitems | 12623 | 4 | Tube diepte | 22 |
| 12 | listitems | 12623 | 6 | Tube diepte | 24 |
| 13 | listitems | 12624 | 4 | Tube maat | 7.5 |
| 14 | listitems | 12624 | 5 | Tube maat | 8 |
| 15 | listitems | 12751 | 2 | Tube referentiepunt | Tandenrij |
| 16 | listitems | 12623 | 7 | Tube diepte | 25 |
| 18 | listitems | 19637 | 9 | V_EMV_NICE_24uur | Geintubeerd |
| 19 | listitems | 12624 | 3 | Tube maat | 7 |
| 20 | listitems | 12623 | 2 | Tube diepte | 20 |

Rationale: match 1/7/18 are the direct "intubated" flag (main flowsheet +
2 NICE admission/24h variants). Matches 4/5/6/8/9/11/12/13/14/15/16/19/20
are documentation detail (depth, size, route, reference point) that only
exists because an oral ETT is in place -- they imply the same state, not a
distinct one, and matter because some patients (e.g. admission 14433) only
have these, never a direct `Geintubeerd` hit.

## Tracheostomy

| match | table | itemid | valueid | raw label | raw value |
|---|---|---|---|---|---|
| 2 | listitems | 8189 | 19 | Toedieningsweg | Spreekklepje |
| 3 | listitems | 8189 | 18 | Toedieningsweg | Spreekcanule |
| 17 | listitems | 8189 | 11 | Toedieningsweg | Trach.stoma |

Rationale: speaking valve/cannula are tracheostomy-weaning devices; itemid
8189 (`Toedieningsweg`/administration route) is a generic multi-purpose
route field elsewhere in the vocab -- only these 3 specific valueids are
airway-relevant, the itemid itself is not.

## Reject

| match | table | itemid | valueid | raw label | raw value | reason |
|---|---|---|---|---|---|---|
| 10 | listitems | 13397 | 1 | Fixatie reden | Verwijderen tube, lijnen | Restraint *reason* ("why is the patient restrained" -> "to stop them pulling at tube/lines"), a safety/behavioral flag, not an airway-type observation. |

## None (default)

No source row -- the absence of any Endotracheal tube / Tracheostomy signal
for a given hour. Same convention as the other categorical features
(rass, vgcs, etc.).

## Known gap

No nasal-ETT-specific item appeared in this candidate set (only `Oraal`
route). If AmsterdamUMCdb records nasal intubation as a separate raw label,
it wasn't caught by the term search used to build this match list -- worth
a targeted follow-up search before treating "Endotracheal tube" as
oral-only, but not blocking this schema.
