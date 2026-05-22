---
name: j-ant-excel-analysis
description: >-
  Reads Nokia J-Ant planning workbooks (.xlsm), uses the Gantt Chart tab to
  filter rows by Healthy (substring or exact Late), by End FB vs Target FB, by
  empty End FB, by delayed End FB vs RC FB (numeric RC FB column), by FOT
  nomination (Contact Person on CB*-SR-Z competence rows), not-committed
  competence-area rows at a given End FB (FB Committed Status open; user must
  supply End FB YYWW—no default), committed competence-area rows at a given End FB (FB Committed Status non-open),
  no-RFC competence-area rows (Status not Done/Obsolete, End FB <= Target FB, Rel Committed Status empty or not committed; CLI filter no-rfc-end-before-target),
  and exports Key (with Jira hyperlink URL when present), Competence
  Area, Assignee, Contact Person, Summary, FB dates, Status, Activity Type,
  Risk Status, Stretch Goal Reason, Rel Committed Status (release committed status text on Gantt for filter 9), and related columns. Use when the user mentions J-Ant, J-Ant_Latest, Gantt
  Chart, FOT members, Contact Person, Key hyperlinks, Healthy/Late, empty End
  FB, Start FB, End FB, Target FB, delayed items, End FB after release committed
  (RC FB), not committed, committed at End FB, no RFC, Rel Committed Status, release committed status, FB Committed Status, CNI- or CB0 feature tokens, or macro workbooks under Projects/Tools (e.g. CB015871, CB015362,
  CB015872-SR, CB013987, CNI-165443, CB014655).
---

# J-Ant Excel workbook analysis

## Goal

Analyze the **J-Ant** macro-enabled workbook (typically `J-Ant_Latest*.xlsm`) the same way as in the established workflow: locate the data table on **Gantt Chart**, apply filters, and report rows with the standard Jira/planning columns plus useful extras. Whenever a **Key** (e.g. `FPB-1604330`) is shown, include the **Jira URL** from the cell hyperlink as a markdown link `[KEY](url)` when `cell.hyperlink.target` is present.

**Automation:** `.cursor/skills/j-ant-excel-analysis/scripts/analyze_j_ant_workbook.py` implements the CLI filters in **Filters** below (including **`no-rfc-end-before-target`**, **`end-fb-not-committed`**, **`end-fb-committed`**, **`delayed-rc-fb`**, **`fot`**, etc.).

## Default workbook path (adjust if the user names another file)

If the user does not specify a path, prefer:

`C:/Users/kewang/OneDrive - Nokia/Projects/Tools/J-Ant_Latest - Copy.xlsm`

Use the path the user provides when they give one.

## Reading the file (Windows / OneDrive)

1. **Try** opening the workbook directly with **openpyxl** (`data_only=True` so cached values appear, not formulas).
2. If open fails with **PermissionError** (file open in Excel, OneDrive lock, or AV), **copy** the `.xlsm` to a writable folder (for example the project root with a name like `_J-Ant_temp.xlsm`), then open the copy.
3. Prefer sheet **`Gantt Chart`** for reporting. **`JiraData`** often mirrors the same issues; avoid double-counting unless the user asks for that sheet explicitly.

## Finding the header row

- **FB / Healthy / Key-style rows:** Scan the first ~50 rows for a header row that includes **End FB** (case/spacing-insensitive). Data starts on the next row.
- **FOT / Summary-style rows:** If the header row with **End FB** is not found or columns differ, scan for a row that includes both **Summary** and **Type** (same case/spacing rules). On **Gantt Chart**, **Contact Person** is typically column index 5 (between Assignee and Summary).

## Column names (canonical)

Map headers case-insensitively. Primary columns for user-facing tables:

- Key  
- Competence Area (may appear as `Competence area`)  
- Assignee  
- Contact Person (FOT / planning contact; may be blank or spaces only)  
- Summary  
- Start FB  
- End FB  
- Status  
- Target FB  
- Activity Type  

**Extra columns** often needed (“etc.”): Type, Item ID, RC FB (numeric; used in **delayed** vs **End FB**), **Rel Committed Status** (text; in **no RFC** filter 9 users often say *release committed status*—same column on **Gantt Chart**), FB Committed Status, Sub-Activity Type, Healthy, Time Remainig (workbook spelling), Logged Effort, Risk Status, Risk Details, Delay Explanation, Text 2, Stretch Goal Reason (when present on the sheet), #wk of CA. After those, the sheet may contain **many week columns** (numeric headers like `2508`, `2601`); include them only if the user asks for timeline cells.

## Key and Jira hyperlinks

- The **Key** column (e.g. `FPB-1604330`) often has an Excel **hyperlink** to Jira. With **openpyxl**, read the **Key** cell for each output row and, when present, use `cell.hyperlink.target` as the URL (this works with `data_only=True` on typical J-Ant files).
- In chat or markdown reports, show the key as a **link**: `[FPB-1604330](https://…/browse/FPB-1604330)` using the **exact** `target` from the workbook. **Never invent** a URL if the cell has no hyperlink—output the **Key** text only.
- Resolve the **Key** column index from the header (do not assume a fixed column letter).
- For **JSON/CSV** exports, include both `key` and `key_url` (or equivalent) so downstream tools can render links without re-parsing Excel.

## Filters (common requests)

1. **Healthy and Late**  
   - **Contains Late:** **Healthy** text contains `late` as a substring (case-insensitive), e.g. `Late`, `Late/OoB`, `Long/Late/OoB`.  
   - **Late only:** **Healthy** normalized to lowercase equals exactly `late` (excludes `Late/OoB`, `Long/Late/OoB`, etc.).

2. **End FB later than Target FB**
   - Parse **End FB** and **Target FB** as numbers when possible (int/float or numeric string).  
   - Skip rows where either value is missing or non-numeric.  
   - Include rows where **End FB > Target FB**.  
   - On the sample workbook, this set matched the “Healthy contains Late” set; still implement both filters independently.

3. **End FB empty**  
   - **End FB** is empty (same rules as **Contact Person** emptiness: blank, whitespace-only, `N/A`, `-`, etc.).  
   - Require a non-empty **Key** so blank template rows are skipped.  
   - When reporting, include **Key** with hyperlink, **Competence Area**, **Assignee**, and other useful columns.

4. **Full row payload**  
   - When the user asks for “all columns” or “etc.”, emit every header cell for matching rows (wide tables or JSON/CSV are acceptable).

5. **FOT members for a feature (e.g. CB015362, CB015872-SR, CB015871)**  
   Use **Gantt Chart** unless the user asks for **JiraData**. Base row filter for all FOT rules below:  
   - **Type** (normalized) equals **`competence area`**.  
   - **Summary** contains the user’s **feature token** as a substring (case-insensitive). Tokens may look like `CB015362` or **`CB015872-SR`** (include the `-SR` suffix when the user gives it).  
   - **Summary** must also contain **`-Z`** (effort / early planning line), e.g. `"-z" in summary.lower()`.  
   - **“FOT not nominated”:** **Contact Person** is empty after trim, or only placeholders (`N/A`, `NA`, `-`, `none`, `tbd`). Treat a **space-only** cell as empty.  
   - **“FOT provided”:** **Contact Person** has at least one substantive name (non-empty after the same trim/placeholder rules).  
   - **RAN SysSpec exclusion (optional):** When the user asks to exclude RAN SysSpec (as in CB015362 tracking), drop rows where **Competence Area** or **Summary** contains **`RAN SysSpec`** (case-insensitive). Do **not** apply this exclusion unless the user states it.  
   - **Ambiguous “list FOT members”:** If the user does not say *nominated only* vs *missing only*, give **both** cohorts in separate sub-tables (or clearly labeled sections): rows **with** and **without** a **Contact Person**, each row showing **Key** as `[KEY](url)` when the hyperlink exists.  
   - **Output — not nominated:** **Key** (with Jira hyperlink when present), **Competence Area**, **Assignee** (and Excel row if useful).  
   - **Output — provided:** **Key** (with Jira hyperlink when present), **Competence Area**, **Contact Person**, **Assignee** (and Excel row if useful).  
   - **Deduping:** Prefer one line per **Competence Area** when **JiraData** would duplicate **Gantt Chart**; do not merge rows that differ in assignee unless the user asks for unique teams only.

6. **Delayed items (End FB later than Release committed FB)**  
   Use when the user asks for **delayed** competence-area rows, **End FB** after **release committed FB**, or similar wording.

   **Sheet:** **Gantt Chart** (unless they specify **JiraData**).

   **Row filter**  
   - **Type** (normalized) = **`competence area`**.  
   - **Summary** contains the requested **feature id** substring (case-insensitive), e.g. `CB013987`, `CB015362-SR`.  
   - **Delayed:** numeric **End FB** > numeric **Release committed FB**.  
   - **Release committed FB** on **Gantt Chart** = **`RC FB`** column (header **RC FB**). There is no column literally named “Release committed FB” on that sheet.  
   - **Do not confuse** with **JiraData** column **Release Committed Status** (text status)—that is not the numeric FB used for this comparison. For **text** release commitment (e.g. *not committed*, *Ready for Commitment*), see **filter 9** (**Rel Committed Status** on **Gantt Chart**).  
   - Parse **End FB** and **RC FB** as numbers (YYWW-style integers in practice). Treat non-numeric cells as missing: blank, `Missing`, `N/A`, `-`, `none`, etc. **Skip** the row if either value cannot be parsed.  
   - **Feature id typos:** If the user’s token matches **no** Summary (e.g. `CB13987`), try plausible Nokia **CB0…** forms (e.g. `CB013987`) or ask the user to confirm. Always **state which token** was used in the result preamble.

   **Default output columns (markdown table)**  
   1. **Key** — `[KEY](url)` from `cell.hyperlink.target` when present, else plain Key.  
   2. **Summary**  
   3. **Competence Area**  
   4. **Release committed FB (RC FB)** — show the **RC FB** cell value; label the column clearly for the reader.  
   5. **End FB** — **always** include next to RC FB so the slip is obvious.  
   6. **Delay Explanation** — **Delay Explanation** column on **Gantt Chart** (on **JiraData** the header may be **Delay Explanations** plural—map case-insensitively if reading that sheet).

   **Optional:** **Excel row** number. Add **Target FB**, **Healthy**, **Assignee** only if the user asks.

   **CLI:** `python …/analyze_j_ant_workbook.py --workbook PATH.xlsm --filter delayed-rc-fb --feature CB013987` prints JSON including `key`, `key_url`, `end_fb`, `release_committed_fb`, `delay_explanation`, `summary`, `competence_area`, etc.

7. **Not committed at a given End FB (FB Committed Status open)**  
   Use when the user asks for **not committed** items, **FB Committed Status** empty / not committed, **open FB commitment**, or a filtered list at a fixed **End FB** for a feature (e.g. `CNI-165443`, `CB013987`). This is **not** the same as **delayed vs RC FB** (filter 6): delayed compares **End FB** to **RC FB**; not-committed filters on **FB Committed Status** and an exact **End FB** target.

   **End FB (YYWW) is mandatory — stop and ask**  
   When the user asks for **not committed** items but does **not** specify which **End FB** (feature-build week, e.g. `2611`, `2612`), **stop immediately**: do **not** run `analyze_j_ant_workbook.py`, do **not** invent or assume a week, and do **not** scan “all End FB” values in the workbook to substitute for a missing user choice. **Ask the user once** for the exact **End FB** they want (YYWW). Only after they provide it, run the script with **`--end-fb`** set to that value. The CLI **requires** `--end-fb` for this filter (no default).

   **Sheet:** **Gantt Chart** by default (`--sheet` overrides). **`JiraData`** is not used unless the user asks for it.

   **Required columns**  
   The sheet must have **Type**, **End FB**, **Key**, and **FB Committed Status**. If any is missing, stop with a clear error.

   **Row filter (all must pass)**  
   - **Type** (normalized) = **`competence area`** only — same normalization as FOT / delayed competence rows. This **drops** non–competence-area lines (e.g. rows whose **Summary** still mentions the feature but **Type** is Epic / other).  
   - Non-empty **Key** (skip blank template rows).  
   - Numeric **End FB** equals **`--end-fb`** (YYWW-style number). Pass **`--end-fb`** only after the user has stated the week (see *End FB is mandatory* above). To see another week, re-run with a new **`--end-fb`**. There is no “all End FB values” mode; do not emulate one by looping silently in chat—either ask which week(s) the user cares about or run once per week they name.  
   - **FB Committed Status** is treated as **open / not committed** when the cell is blank or whitespace-only, or placeholder text (`N/A`, `-`, `none`, `missing`), or any value whose normalized text contains **not committed** (case-insensitive). Rows with any other committed-style value are **excluded**.

   **Optional scope**  
   `--feature TOKEN` — keep only rows where **Summary** or **Key** contains `TOKEN` as a substring (case-insensitive). Omit for all competence-area rows matching End FB and FB Committed rules.

   **Other columns (context, not filter inputs)**  
   - **RC FB** (header **RC FB**) is exported as **Release committed FB** for readability; it is **not** part of the not-committed filter.  
   - Do **not** confuse **FB Committed Status** with **Rel Committed Status** or **Release Committed Status** on **JiraData** — only **FB Committed Status** drives this filter.

   **Markdown report (`--format markdown`)**  
   - **Preamble:** **Sheet** name; **Filter** line listing **End FB** value, FB Committed rule, and **Type = Competence area**; if `--feature` is set, add **Scope:** Summary or Key contains the token.  
   - **Table column order:** **Key** (`[KEY](url)` from `cell.hyperlink.target` when present, else plain Key), **Summary**, **Competence Area**, **End FB**, **Release committed FB (RC FB)** (values from **RC FB**), **Risk Status**, **Stretch Goal Reason**.  
   - **Risk Status:** header must match **risk** and **status** in the normalized column name.  
   - **Stretch Goal Reason:** header must match **stretch**, **goal**, and **reason**. Many workbooks have no such column on **Gantt Chart** — then markdown cells and JSON omit or leave those fields empty.

   **JSON report (default, or `--format json`)**  
   Output is `{ "count", "sheet", "rows" }`. Each row always has `excel_row`, `key`, `key_url`. Other keys are present when the column exists: `type`, `competence_area`, `assignee`, `summary`, `contact_person`, `healthy`, `start_fb`, `end_fb`, `target_fb`, `release_committed_fb`, `fb_committed_status`, `risk_status`, `stretch_goal_reason`, `delay_explanation`, `status`, `activity_type`.

   **CLI**  
   `python …/analyze_j_ant_workbook.py --workbook PATH.xlsm --filter end-fb-not-committed --end-fb 2611`  
   `python …/analyze_j_ant_workbook.py --workbook PATH.xlsm --filter end-fb-not-committed --feature CNI-165443 --end-fb 2611 --format markdown`  
   Optional: `--copy-to ./_j_ant_copy.xlsm` if direct read hits **PermissionError** (Excel open, OneDrive lock).

8. **Committed at a given End FB (FB Committed Status non-open)**  
   Use when the user asks for **committed** competence-area rows at a fixed **End FB** (e.g. “committed for CB014655 at 2611”). Inverse of filter 7 on **FB Committed Status**: keep rows where the status is **not** “open” (i.e. not blank/placeholder/`not committed` per the same rules as filter 7—typically values like **Committed**).

   **End FB (YYWW) is mandatory — stop and ask**  
   Same as filter 7: if the user does not specify **End FB**, **stop and ask** before running. **`--end-fb` is required** (no default).

   **Sheet, columns, Type, Key, End FB, optional `--feature`**  
   Same as filter 7 (**Gantt Chart**, **Type** = **competence area**, non-empty **Key**, **End FB** = **`--end-fb`**, optional **Summary** or **Key** substring via `--feature`).

   **Row filter (FB Committed Status)**  
   Include a row only when **FB Committed Status** is **not** “open” under the same rules as filter 7: exclude blank/whitespace-only, placeholders (`N/A`, `-`, `none`, `missing`), and any value whose normalized text contains **not committed**. Typical included values are **Committed** (and similar substantive statuses).

   **Markdown (`--format markdown`)**  
   Same preamble pattern as filter 7; **Filter** line states **committed (non-open)**. Table columns: **Key**, **Summary**, **Competence Area**, **End FB**, **FB Committed Status**, **Release committed FB (RC FB)**, **Risk Status**, **Stretch Goal Reason**.

   **CLI**  
   `python …/analyze_j_ant_workbook.py --workbook PATH.xlsm --filter end-fb-committed --end-fb 2611 --feature CB014655 --format markdown`

9. **No RFC (`--filter no-rfc-end-before-target`)**  
   Use when the user asks for **no RFC** items with **Status** still active, **End FB** not empty and **on or before** **Target FB**, and **release committed status** (see naming below) **empty** or **not committed**.

   **Naming:** On **Gantt Chart**, user wording **release committed status** maps to the **Rel Committed Status** column. It is **not** numeric **RC FB** (that is **filter 6** / **Release committed FB (RC FB)**). It is also **not** **FB Committed Status** (**filters 7–8**).

   **Sheet:** **Gantt Chart** by default.

   **Required columns**  
   **Type**, **Summary**, **Key**, **End FB**, **Target FB**, **Rel Committed Status**, **Status**, **Assignee**, **Competence Area**.

   **Row filter**  
   - **Type** = **competence area**.  
   - Non-empty **Key**.  
   - **`--feature` required** — **Summary** or **Key** contains the token (case-insensitive).  
   - **Status** (issue **Status** column): exclude rows whose normalized status is exactly **`done`** or **`obsolete`**. Blank **Status** is not excluded by this rule.  
   - **End FB** not empty (same empty rules as elsewhere) and parses as a number; **Target FB** parses as a number; **End FB <= Target FB** (on or before target, equality allowed).  
   - **Rel Committed Status** must be **empty** (blank/whitespace) or placeholder (`N/A`, `-`, `none`, `missing`) or text containing **not committed** (case-insensitive, e.g. `Not Committed`). Exclude rows with other substantive values (e.g. **Committed at …**, **Ready for Commitment**).

   **Markdown (`--format markdown`)**  
   - **Preamble** (align with script output): **Sheet**; **Filter** line summarizing Status rule, End FB vs Target (**<=**), Rel Committed rule, **Type = Competence area**; **Scope:** `Summary` or `Key` contains the `--feature` token.  
   - **Table columns (in order):** **Key** (hyperlink when present), **Summary**, **Status**, **Competence Area**, **Assignee**, **End FB**, **Target FB**, **Release committed status** (cell values from **Rel Committed Status**).

   **JSON**  
   Same row payload as other filters; includes **`rel_committed_status`** (same column as the markdown **Release committed status** column).

   **CLI** (`--filter no-rfc-end-before-target` — historical name; rule uses **End FB <= Target FB**.)  
   `python …/analyze_j_ant_workbook.py --workbook PATH.xlsm --filter no-rfc-end-before-target --feature CB015871 --format markdown`

   **Compared to other filters**  
   - **Filter 6 (delayed):** numeric **End FB** > **RC FB** — different from filter 9.  
   - **Filters 7–8:** **FB Committed Status** at a fixed **End FB** — different column and different intent from filter 9.

## Output

- Prefer **markdown tables** for the primary columns (**Key** as `[KEY](url)` when `cell.hyperlink.target` exists, else plain Key; plus Competence Area, Assignee, Contact Person when relevant, Summary, FB fields, Status, Activity Type). For **delayed vs RC FB** (filter 6), use the six-column layout listed there (**Key**, **Summary**, **Competence Area**, **Release committed FB (RC FB)**, **End FB**, **Delay Explanation**). For **not committed** (filter 7) with `--format markdown`, use the seven-column layout in filter 7 (**Key** through **Stretch Goal Reason**). For **committed at End FB** (filter 8) with `--format markdown`, use the eight-column layout in filter 8 (adds **FB Committed Status** before **Release committed FB (RC FB)**). For **no RFC** (filter 9) with `--format markdown`, use the eight-column layout in filter 9 (**Key**, **Summary**, **Status**, **Competence Area**, **Assignee**, **End FB**, **Target FB**, **Release committed status**). Apply the same **Key**+hyperlink convention for **Healthy**, **End FB**, **empty End FB**, and **FOT** results—not only FOT. Add a second table or JSON when the user wants wide “etc.” columns.
- Include **Excel row number** (1-based sheet row) when it helps the user find the row in Excel.  
- State **sheet name**, **filter rule**, and **row count** in a short preamble.

## Automation (optional)

From the repository root, after installing **openpyxl** if needed, `.cursor/skills/j-ant-excel-analysis/scripts/analyze_j_ant_workbook.py` prints JSON to stdout (or a markdown table when `--format markdown` is supported for that filter). Each row includes **`key`**, **`key_url`** (Jira browse URL when present), and **`excel_row`**, plus other fields when available.

```bash
python .cursor/skills/j-ant-excel-analysis/scripts/analyze_j_ant_workbook.py --workbook "PATH.xlsm" --filter healthy-late
python .cursor/skills/j-ant-excel-analysis/scripts/analyze_j_ant_workbook.py --workbook "PATH.xlsm" --filter healthy-late-exact
python .cursor/skills/j-ant-excel-analysis/scripts/analyze_j_ant_workbook.py --workbook "PATH.xlsm" --filter end-after-target
python .cursor/skills/j-ant-excel-analysis/scripts/analyze_j_ant_workbook.py --workbook "PATH.xlsm" --filter empty-end-fb
python .cursor/skills/j-ant-excel-analysis/scripts/analyze_j_ant_workbook.py --workbook "PATH.xlsm" --filter fot --feature CB015872-SR --fot-contact both
python .cursor/skills/j-ant-excel-analysis/scripts/analyze_j_ant_workbook.py --workbook "PATH.xlsm" --filter fot --feature CB015362 --fot-contact missing --exclude-ran-sysspec
python .cursor/skills/j-ant-excel-analysis/scripts/analyze_j_ant_workbook.py --workbook "PATH.xlsm" --filter delayed-rc-fb --feature CB013987
python .cursor/skills/j-ant-excel-analysis/scripts/analyze_j_ant_workbook.py --workbook "PATH.xlsm" --filter end-fb-not-committed --end-fb 2611 --format markdown
python .cursor/skills/j-ant-excel-analysis/scripts/analyze_j_ant_workbook.py --workbook "PATH.xlsm" --filter end-fb-not-committed --feature CNI-165443 --end-fb 2611 --format markdown
python .cursor/skills/j-ant-excel-analysis/scripts/analyze_j_ant_workbook.py --workbook "PATH.xlsm" --filter end-fb-not-committed --feature CNI-165443 --end-fb 2611
python .cursor/skills/j-ant-excel-analysis/scripts/analyze_j_ant_workbook.py --workbook "PATH.xlsm" --filter end-fb-committed --end-fb 2611 --feature CB014655 --format markdown
python .cursor/skills/j-ant-excel-analysis/scripts/analyze_j_ant_workbook.py --workbook "PATH.xlsm" --filter no-rfc-end-before-target --feature CB015871 --format markdown
```

`--fot-contact` is one of `provided`, `missing`, or `both` (default `both`). `--feature` is required for `fot`, `delayed-rc-fb`, and **`no-rfc-end-before-target`**; optional for `end-fb-not-committed` and `end-fb-committed` (substring match on **Summary** or **Key**). For **`end-fb-not-committed`** and **`end-fb-committed`**, **`--end-fb` is required** (the script exits if omitted). In chat, if the user did not state an End FB, **stop and ask** (filters 7–8)—never run these filters without **`--end-fb`**. `--format markdown` is implemented for **`end-fb-not-committed`**, **`end-fb-committed`**, and **`no-rfc-end-before-target`**; default **`--format json`** prints the full row payload. Use `--copy-to ./_j_ant_copy.xlsm` when direct read fails.

## Dependencies

- Python 3.x with **openpyxl** (`pip install openpyxl`).
- Filter logic and column mapping for **no RFC** (filter 9), **not / committed End FB** (filters 7–8), and other `--filter` values live in **`analyze_j_ant_workbook.py`**; keep **SKILL.md** in sync when changing that script.
