# QA Checklist (Definition of Done)

Copy per project to `docs/qa_checklist.md` and tick per asset.

Automatic (`python tools/asset_harmonizer.py qa`):
- [ ] Filename follows `category_role_variant`: lowercase letters, digits, underscores only
- [ ] No node scale other than 1; pivot at base center
- [ ] Real-world size is plausible and inside the style guide range
- [ ] Triangle count is under the class cap
- [ ] UVs exist; texel density is within 5% of target (`pipeline/texel_report.csv`)
- [ ] Texture suffixes are `_diff`, `_nrm`, `_rma`, `_emi`; every albedo has been through the palette pass (`_pal`)

Manual:
- [ ] Tested next to the reference chair, wall and character
- [ ] Master shader assigned; albedo is sRGB, normal and RMA are Linear
- [ ] LOD and collision mesh exist where needed
- [ ] Viewed at real camera distance; texel density confirmed with a checker texture
