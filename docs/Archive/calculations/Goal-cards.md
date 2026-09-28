Logic flow and attributes: [Calculations.md](Calculations.md).

## Goal cards — formulas

After predict, **Score** and **Plan** change a need by writing slider
fields onto the session and calling **`POST /v1/needs`** (debounced).  
**Code:** `frontend/src/lib/needEdit.ts` (`patchNeedInputs`, `fillNeedEdit`).

`fillNeedEdit` reads stored fields for the editor. `needCardHave` /
`needCardGap` read `n.have` and `n.gap` from the last calculator
response.

---
