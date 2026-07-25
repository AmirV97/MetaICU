"""Lab token_role assignment -- keyed on the Amsterdam source prefix, not the target vocabulary.

Every emitted ``LAB//`` source token must carry ``token_role=dynamic_event/lab`` (see
docs/policy_decisions.md). A non-lab row that happens to map to a LOINC concept (e.g. a fluid
output measurement) must NOT receive this role -- the role is a property of what Amsterdam table
and prefix the row came from, not of the destination vocabulary.
"""

from __future__ import annotations

import pandas as pd

LAB_PREFIX = "LAB//"
LAB_ROLE = "dynamic_event/lab"


def apply_lab_role_assignment(vocab: pd.DataFrame) -> pd.DataFrame:
    fixed = vocab.copy()
    emit = fixed["emit_as_model_token"].astype(str).str.lower().isin(["true", "1", "yes"])
    is_lab = fixed["source_token"].str.startswith(LAB_PREFIX, na=False)
    needs_fix = emit & is_lab & (fixed["token_role"] != LAB_ROLE)
    fixed.loc[needs_fix, "token_role"] = LAB_ROLE
    return fixed
