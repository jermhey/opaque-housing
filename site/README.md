# Public site

Static HTML for the investigation. Pages read `data/site.json`, which `oh publish` writes from allowlisted citywide and NTA-or-coarser aggregates (ADR 0009).

This is not Evidence.dev. Do not add a Node site generator without a new ADR.

```bash
uv run oh publish --metro nyc
python3 -m http.server --directory site 8080
```

GitHub Pages deploys this directory. Parcel files, owner keys, HPD person names, and addresses are not copied here.
