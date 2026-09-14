# Manual Portal Deployment Checklist — STC Pipeline

Use this only if `portal.azure.com` sign-in works but `az login`/Cloud Shell
doesn't. Build resources in this exact order — later resources reference
earlier ones by name, so skipping ahead causes confusing "resource not
found" errors partway through.

Every name below matches `AZURE_MIGRATION.md` exactly — keep them identical
even building by hand, so this stays consistent with the Bicep template if
you ever go back to it.

## 1. Resource Group
**Create a resource** → search "Resource group"
- Name: `rg-stc-prd-uks-001`
- Region: **UK South**

## 2. Storage Account (ADLS Gen2)
**Create a resource** → "Storage account"
- Resource group: the one above
- Name: `stocustcprd001`
- Region: UK South | Redundancy: LRS (cheapest, fine for this)
- **Advanced tab → "Enable hierarchical namespace" → tick this.** Easy to
  miss, and without it this is just plain Blob storage, not ADLS Gen2 — the
  pipeline's folder-listing logic depends on it.
- Once created: **Containers** blade → **+ Container** → name `stc-data`

## 3. Key Vault
**Create a resource** → "Key Vault"
- Name: `kv-stc-prd-uks-001`
- Permission model: **Azure role-based access control** (not "Vault access
  policy" — the pipeline's managed identity needs RBAC)
- Once created: **Objects → Secrets → + Generate/Import**
  - Name: `safetyculture-api-key`
  - Value: your real SafetyCulture API key

## 4. Log Analytics Workspace
**Create a resource** → "Log Analytics workspace"
- Name: `law-stc-prd-uks-001`

## 5. Application Insights
**Create a resource** → "Application Insights"
- Name: `appi-stc-prd-uks-001`
- Resource Mode: **Workspace-based**, linked to the Log Analytics workspace above

## 6. Managed Identity
**Create a resource** → search "User Assigned Managed Identity"
- Name: `id-stc-prd-uks-001`

## 7. Container Registry
**Create a resource** → "Container Registry"
- Name: `acrocustcprd001`
- SKU: **Basic**
- **Access keys → Admin user → leave OFF** (the pipeline authenticates via
  the managed identity, not admin credentials)

### 7a. Build the image without any local Docker or CLI
- Open the registry → **Tasks → Quick task** won't work without a local
  Dockerfile upload, so instead: **Tasks → Task templates → GitHub** (or
  **+ Add → Task**, "Build and push a Docker image")
- Connect it to whichever GitHub repo has your `pipeline/infra/Dockerfile`
  and `pipeline/Scripts/` — same content as the zip I gave you
- Context: repo root's `pipeline/` folder | Dockerfile path: `infra/Dockerfile`
- Image name: `stc-pipeline:latest`
- Trigger it manually once ("Run now") to build the first image — no
  `az acr build`, no local Docker required.

## 8. RBAC — grant the managed identity access
Do this on **three separate resources**, same pattern each time:
**Resource → Access control (IAM) → + Add → Add role assignment**

| On this resource | Assign this role | To |
|---|---|---|
| Storage account (`stocustcprd001`) | Storage Blob Data Contributor | `id-stc-prd-uks-001` |
| Key Vault (`kv-stc-prd-uks-001`) | Key Vault Secrets User | `id-stc-prd-uks-001` |
| Container Registry (`acrocustcprd001`) | AcrPull | `id-stc-prd-uks-001` |

When picking the identity, search "User-assigned managed identity" under
**Assign access to**, then pick `id-stc-prd-uks-001` by name.

## 9. Container Apps Environment
**Create a resource** → search "Container Apps Environment"
- Name: `cae-stc-prd-uks-001`
- Logs destination: the Log Analytics workspace from step 4

## 10. Container App Job — the last and fiddliest one
**Create a resource** → search "Container Apps" → **Container App Job**
(not "Container App" — that's for always-on services, Job is what runs on
a schedule and exits)
- Name: `caj-stc-prd-uks-001`
- Container Apps Environment: the one from step 9
- **Trigger type: Schedule**
- Cron expression: `0 2 * * *` (daily 02:00 UTC — adjust once you know real run time)
- **Identity tab**: Type = User-assigned → select `id-stc-prd-uks-001`
- **Container tab**:
  - Image source: **Azure Container Registry** → `acrocustcprd001` → `stc-pipeline:latest`
  - CPU/Memory: 2.0 vCPU / 4Gi (pipeline does real pandas work, don't starve it)
  - Environment variables:
    - `ADLS_ACCOUNT_URL` = `https://stocustcprd001.blob.core.windows.net`
    - `ADLS_FILESYSTEM` = `stc-data`
    - `AZURE_CLIENT_ID` = (paste the Client ID shown on the `id-stc-prd-uks-001` identity's Overview page)
    - `SAFETYCULTURE_API_KEY` = **use "Reference a secret"**, not a plain value → point it at the Key Vault secret from step 3

## 11. Test-fire it
Open the job → **Overview → Start execution** button. Watch it in
**Execution history**, click through to **Logs** (Log Analytics) if it fails.

## 12. Confirm data landed
Storage account → **Storage browser → Blob containers → stc-data** → check
`TNS/` is filling up with `.csv` files.

---

**Being straight with you**: this works, but it's slower, more error-prone
(one typo in an env var name and it silently fails), and leaves no
repeatable record of what got built — next time you need a `dev` copy,
you're clicking through all this again by hand instead of changing one
parameter in the Bicep file. If IT ever unblocks the CLI or sets up the
GitHub Actions service principal, that's still the better long-term path —
this is a legitimate way to get moving *today*, not necessarily the way to
keep running this forever.
