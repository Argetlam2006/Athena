# Sample Data

> **License**: StatsBomb Open Data — Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0)
> **Source**: https://github.com/statsbomb/open-data
> **Attribution**: StatsBomb — https://statsbomb.com

---

## What Is Included

This directory contains a minimal sample of StatsBomb Open Data for
**local demonstration without a full data download**.

```
data/sample/
├── README.md              ← This file
└── competitions.csv       ← Competition catalogue (auto-generated on first run)
```

The sample is intentionally small — enough to demonstrate that the ingestion
and validation pipeline works, but not enough to run full analytics.

---

## How to Get More Data

### Option A — Sample Only (fastest, ~30 seconds)

Downloads La Liga 2020/21 matches + events for 5 matches.
Sufficient to run the analytics pipeline end-to-end.

```bash
make data
# or
python -m backend.ingestion.load_data --sample
```

### Option B — Single Competition

```bash
python -m backend.ingestion.load_data --competition "La Liga"
python -m backend.ingestion.load_data --competition "Champions League"
```

### Option C — Full Dataset (all available competitions)

This downloads several gigabytes and may take 20–40 minutes.

```bash
python -m backend.ingestion.load_data
```

---

## Available Competitions in StatsBomb Open Data

| Competition | Coverage |
|-------------|---------|
| La Liga | Seasons 2015/16 – 2020/21 |
| Champions League | Seasons 2003/04 – 2019/20 |
| FA Women's Super League | Seasons 2018/19 – 2020/21 |
| FIFA World Cup | 2018 |
| NWSL | Season 2018 |
| Premier League | Season 2003/04 |
| Copa del Rey | Season 2019/20 |

Coverage changes as StatsBomb releases additional open data.
Always run `make data` with `--sample` first to see the current catalogue.

---

## License Notice

The StatsBomb Open Data is provided under the
**Creative Commons Attribution-ShareAlike 4.0 International License**.

You are free to:
- **Share** — copy and redistribute the material in any medium or format
- **Adapt** — remix, transform, and build upon the material

Under the following terms:
- **Attribution** — Give appropriate credit to StatsBomb
- **ShareAlike** — Distribute derivatives under the same license

Full license: https://creativecommons.org/licenses/by-sa/4.0/

---

## Data Dictionary (StatsBomb)

Key fields used in Athena's analytics pipeline:

| Field | Source | Used For |
|-------|--------|---------|
| `type.name` | Events | Identifying passes, carries, shots, etc. |
| `player.id` / `player.name` | Events | Player identification |
| `position.name` | Events | Position classification |
| `pass.length` | Events | Progressive pass calculation |
| `pass.end_location` | Events | Deep completions, final third entries |
| `carry.end_location` | Events | Progressive carry calculation |
| `shot.statsbomb_xg` | Events | Expected Goals per shot |
| `under_pressure` | Events | Press resistance derivation |
| `pass.key_pass` | Events | Key pass identification |
| `pass.through_ball` | Events | Through ball identification |

Full StatsBomb event data specification:
https://github.com/statsbomb/open-data/tree/master/doc
