# STC Pipeline — Azure Migration (Phase 1)

## Architecture chosen: Container Apps Jobs

Your existing code stays almost as-is: 23 Python scripts, orchestrated by
`STC Pipeline Runner.py` exactly as before, packaged into a single Docker
image and run on a schedule as an **Azure Container App Job**. No rewrite to
Spark/Databricks, no Data Factory pipeline to maintain in parallel with your
actual logic - the thing that runs in Azure is the thing you've been testing.

```
Container Apps Job (cron trigger, e.g. daily 02:00 UTC)
   -> runs the Docker image
   -> STC Pipeline Runner.py (unchanged orchestration logic)
      -> archive_stage_data()          [Stage 0, now writes to ADLS]
      -> STC API IN.py                 [Stage 1, now writes to ADLS]
      -> ...22 more stages, subprocess-launched exactly as before
   -> reads/writes CSVs in ADLS Gen2 instead of a local OneDrive folder
   -> authenticates to Storage/Key Vault via a user-assigned managed identity
      (no secrets in the image, no connection strings in code)
```

Your `TNS -> BNZ -> SLV -> GLD -> REP` folder structure carries over directly
as top-level folders inside one ADLS Gen2 filesystem (`stc-data`) - this is
already a bronze/silver/gold/reporting medallion layout in every way that
matters, it just didn't have the Databricks vocabulary attached to it before.

## What's actually done vs. what's next

**Done and tested (against a local Azurite emulator, not yet a real Azure
subscription - see "Before you deploy" below):**
- `infra/main.bicep` - deploys every resource, named per the OCUG policy.
- `infra/Dockerfile` + `infra/requirements.txt` - packages the pipeline.
- `Scripts/_shared/azure_io.py` - the shared read/write/list/copy/archive
  helper every script needs instead of local `open()`/`pd.read_csv()`.
  Unit-tested: round-trip read/write, append-only writes, archive-and-re-run,
  folder listing that correctly ignores nested `archive/` output.
- `STC Pipeline Runner.py` - the pre-pull archive step (Stage 0) converted to
  ADLS and tested end-to-end against the emulator.
- `STC API IN.py` - the ingestion writer (`store_batch_records`,
  `_get_table_path`, `local_data_summary`) converted to ADLS and tested
  end-to-end: multiple sequential batches into the same table verified to
  accumulate correctly, columns and row order intact.

**Not yet converted - genuinely next, not silently skipped:**
The remaining ~21 scripts (`RP1/RP2/RP3/MAP/*`, `STC Data Clean.py`,
`STC JSON Map and Clean.py`, `STC Table Merge.py`, `STC Date Scrape.py`,
`RP4 GLD to TLB.py`) each still read and write against their own hardcoded
local path constants (`GLD_INPUT_PATH`, `SLV_INPUT_PATH`, etc. - one of the
things flagged in the very first audit). The mechanical pattern to convert
each is the same one just proven twice above:

```python
# before
df = pd.read_csv(os.path.join(GLD_INPUT_PATH, "gld_sites.csv"), dtype=str)
df.to_csv(os.path.join(GLD_INPUT_PATH, "output.csv"), index=False)

# after
import azure_io
client = azure_io.get_client()
df = client.read_csv("GLD/gld_sites.csv", dtype=str)
client.write_csv(df, "GLD/output.csv", index=False)
```

I didn't batch-apply this across 21 files with a regex sweep, because each
script has its own path constants and a couple have report-specific output
folders (`REP/...`) that deserve a human eyeball rather than a blind
substitution in a pipeline that other people depend on. Say the word and I'll
work through them the same way - one script at a time, compiled and tested
against the emulator before moving to the next - rather than all at once
unreviewed.

## Naming - what's built, and what needs sign-off

Everything below follows OCUG Azure Cloud Resource Naming Standards Policy
v1.2 (workload code `stc`, environment `prd`, region `uks`):

| Resource | Name | Notes |
|---|---|---|
| Resource Group | `rg-stc-prd-uks-001` | In Appendix A |
| Storage Account (ADLS Gen2) | `stocustcprd001` | Special case per Section 5 (no hyphens, ≤24 chars) - 14 chars |
| Key Vault | `kv-stc-prd-uks-001` | In Appendix A, ≤24 chars - 18 chars |
| Log Analytics Workspace | `law-stc-prd-uks-001` | In Appendix A |
| Application Insights | `appi-stc-prd-uks-001` | In Appendix A |

**⚠️ Not in Appendix A - need Cloud & Infrastructure Team sign-off before a real
deployment** (Section 8 of the policy: new resource types not covered by
Appendix A trigger a policy review). Proposed codes below follow Microsoft's
own Cloud Adoption Framework abbreviations, but they are **proposals, not
approved codes**:

| Resource | Proposed name | Proposed code | Note |
|---|---|---|---|
| User-Assigned Managed Identity | `id-stc-prd-uks-001` | `id` | |
| Container Registry | `acrocustcprd001` | `acr` | Also needs a Section 5 special case: no hyphens, alphanumeric only, like storage accounts |
| Container Apps Environment | `cae-stc-prd-uks-001` | `cae` | |
| Container App Job | `caj-stc-prd-uks-001` | `caj` | |

## Before you deploy for real

1. **Get the four proposed codes above approved** (or told what to use
   instead) by the Cloud & Infrastructure Team - this is a five-minute ask
   given the policy already anticipates it in Section 8.
2. **Compile-check the Bicep yourself**: this sandbox has no Azure CLI, so
   `main.bicep` has not been run through `az bicep build`. Do that before
   `az deployment group create`.
3. **Choose dev/tst/uat treatment**: the template parameterises `environment`,
   so standing up a `dev` copy first (same Bicep, `environment = 'dev'`) to
   test against real SafetyCulture data before touching `prd` is one
   parameter change, not a rewrite.
4. **Decide on private networking**: this Phase 1 design uses the storage
   account's public endpoint with RBAC + managed identity (no keys, but not
   network-isolated). Private endpoints + a VNet are a reasonable Phase 2
   hardening step for a `prd` data lake holding incident/audit data, not
   included here to keep the first working version shippable.
5. **Supply the real SafetyCulture API key** at deploy time via the
   `safetyCultureApiKey` secure parameter - never commit a real value into
   `main.bicepparam`.

## Scheduling

Container Apps Jobs have a native cron trigger - no separate Data Factory or
Logic App needed just to kick the run off. Default in the template is daily
at 02:00 UTC (`0 2 * * *`); change `cronSchedule` once you know real run
duration and how fresh the data needs to be.
