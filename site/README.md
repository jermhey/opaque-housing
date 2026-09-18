# Public site

Static HTML snapshot for the investigation. Pages read `data/site.json` (NYC) and `data/phl/site.json` (Philadelphia). `oh publish` writes allowlisted citywide and NTA-or-ZIP aggregates (ADR 0009, ADR 0010). The compare page is `compare.html`.

The live insight app is FastAPI + HTMX (`uv run oh serve`, ADR 0011). It uses the same visual language and the same allowlist. This directory stays a GitHub Pages snapshot until an app host is up.

This is not Evidence.dev. Do not add a Node site generator without a new ADR.

```bash
uv run oh publish --metro nyc
python3 -m http.server --directory site 8080
```

GitHub Pages deploys this directory. Parcel files, owner keys, HPD person names, and addresses are not copied here.
