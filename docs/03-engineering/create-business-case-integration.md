# Create Business Case integration

`CreatePresentation` has nullable composite references to the Business Case and exact Business Case version plus a checked `base|all` selection. The service accepts only a current approved case/version matching the selected Account/Opportunity and revalidates it during generation, presentation approval, download-grant issuance and proxied download.

The customer-safe context adds exact `approved_business_case` items. The composer prioritises one highlighted output per selected scenario, the approved disclaimer and a material assumption, then other customer-facing outputs. It uses only editable approved template slides; locked slides remain unchanged.

Each generated claim points to the case-version UUID. The case snapshot holds the downstream formula/input/source lineage. A new calculation, deleted Evidence, exceeded source age or expired assumption makes the source set invalid and blocks new approval/export.
