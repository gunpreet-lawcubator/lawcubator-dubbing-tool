# Glossary overrides

Each file here (`hi.json`, `mr.json`, `bn.json`) is a flat English-term -> approved-translation map for that language, e.g.:

```json
{
  "course": "कोर्स",
  "code of conduct": "आचार संहिता"
}
```

Every entry is injected into the translation prompt for that language, so a fix made once — after a native speaker flags a wrong word, for example — applies to every video from then on instead of needing to be re-caught each time.

Edit these files directly; no restart needed since they're read fresh on every translation call.
