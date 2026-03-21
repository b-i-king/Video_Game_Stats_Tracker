# Bar Chart Race — Animated Stats Visualization

Animated bar chart race showing cumulative game stats over time, inspired by
[Flourish](https://flourish.studio) and [Living Charts](https://livingcharts.com/).

---

## Overview

- **Visualization type:** Bar Chart Race (cumulative totals per game, animated over time)
- **Granularity:** Game level (game_name + game_installment)
- **Cadence:** Monthly (weekly once more data is collected)
- **Tool options:** Flourish (recommended) or Power BI custom visual
- **Data source:** AWS Redshift Serverless → Power BI direct query

---

## When to Run

Monthly cadence is recommended until you have 3+ months of multi-game data.
Weekly cadence with few sessions produces minimal bar movement and looks flat.
Once you have consistent data across Warzone, Black Ops 7, and Dispatch,
the animation becomes visually compelling.

---

## Step-by-Step Workflow

### Step 1 — Refresh Power BI

Open your Power BI report connected to Redshift and click **Refresh**.
If you have a scheduled refresh configured, this happens automatically.

---

### Step 2 — Run the Cumulative Stats Query in Redshift

Run this query in the Redshift Query Editor (or save it as a view — see below).
Filter `stat_type` to whichever stat you want to race (e.g., `Eliminations`).

```sql
SELECT
    d.game_name,
    d.game_installment,
    CAST(CONVERT_TIMEZONE('America/Los_Angeles', f.played_at) AS DATE) AS play_date,
    f.stat_type,
    SUM(f.stat_value)                                                   AS daily_total,
    SUM(SUM(f.stat_value)) OVER (
        PARTITION BY d.game_id, f.stat_type
        ORDER BY CAST(CONVERT_TIMEZONE('America/Los_Angeles', f.played_at) AS DATE)
        ROWS UNBOUNDED PRECEDING
    )                                                                   AS cumulative_total
FROM fact.fact_game_stats f
JOIN dim.dim_games d ON f.game_id = d.game_id
GROUP BY
    d.game_id,
    d.game_name,
    d.game_installment,
    CAST(CONVERT_TIMEZONE('America/Los_Angeles', f.played_at) AS DATE),
    f.stat_type
ORDER BY
    play_date,
    stat_type,
    cumulative_total DESC;
```

**Optional — save as a Redshift view so Power BI can query it directly:**

```sql
CREATE OR REPLACE VIEW analytics.vw_cumulative_stats AS
SELECT
    d.game_name,
    d.game_installment,
    CAST(CONVERT_TIMEZONE('America/Los_Angeles', f.played_at) AS DATE) AS play_date,
    f.stat_type,
    SUM(f.stat_value)                                                   AS daily_total,
    SUM(SUM(f.stat_value)) OVER (
        PARTITION BY d.game_id, f.stat_type
        ORDER BY CAST(CONVERT_TIMEZONE('America/Los_Angeles', f.played_at) AS DATE)
        ROWS UNBOUNDED PRECEDING
    )                                                                   AS cumulative_total
FROM fact.fact_game_stats f
JOIN dim.dim_games d ON f.game_id = d.game_id
GROUP BY
    d.game_id,
    d.game_name,
    d.game_installment,
    CAST(CONVERT_TIMEZONE('America/Los_Angeles', f.played_at) AS DATE),
    f.stat_type;
```

---

### Step 3 — Export the Data (Flourish path only)

In Power BI or the Redshift Query Editor, export the query results as a CSV.
Filter to **one stat_type at a time** before exporting (e.g., `WHERE stat_type = 'Eliminations'`).

---

### Step 4 — Pivot the Data for Flourish

Flourish's Bar Chart Race template expects this shape:
- **Rows:** one per game
- **Columns:** one per date (the values are cumulative totals)

| Game | Installment | 2025-01-15 | 2025-01-22 | 2025-02-01 |
|---|---|---|---|---|
| Call of Duty | Warzone | 45 | 112 | 203 |
| Call of Duty | Black Ops 7 | 0 | 67 | 145 |
| Dispatch | — | 0 | 0 | 88 |

Pivot in Excel (Insert → PivotTable) or in Power BI's Power Query editor:
- Rows: `game_name` + `game_installment`
- Columns: `play_date`
- Values: `cumulative_total`

---

### Step 5A — Flourish (Recommended)

1. Go to [https://flourish.studio](https://flourish.studio) → sign in (free account)
2. Click **New visualization** → search **Bar Chart Race**
3. Select the Bar Chart Race template
4. Click **Data** tab → paste your pivoted CSV
5. Map columns:
   - **Label:** `game_name` (or combine `game_name + game_installment`)
   - **Values:** all date columns
6. Click **Preview** to watch the animation
7. Adjust speed, colors, and labels in the **Settings** panel
8. **Publish** → copy the public link, or **Export** as MP4/GIF

**Flourish tips:**
- Set the animation speed to ~0.5–1 second per frame for monthly data
- Use the color panel to match your brand colors (`#C4A035` gold)
- The "Image" column in Flourish can show a game icon per bar (optional)

---

### Step 5B — Power BI Custom Visual (Alternative)

Use this if you want the animation to live inside your Power BI dashboard
and refresh automatically with your Redshift connection.

1. In Power BI Desktop → **Visualizations pane** → click the `...` (more visuals)
2. Search **AppSource** for `Racing Bar Chart`
3. Install the visual (Queryon or similar)
4. Add to your report canvas
5. Drag fields:
   - **Category:** `game_name`
   - **Date:** `play_date`
   - **Value:** `cumulative_total`
6. Use the play button on the visual to animate

---

## Game Mode Level (Future)

When ready to expand to game mode level, add `game_mode` to the `GROUP BY`
and `PARTITION BY` clauses in the query, and use `game_name + game_installment + game_mode`
as the bar label. Recommend waiting until you have consistent multi-mode data
across at least 2 months.

---

## Stat Types to Race

Suggested order of interest for bar chart races:

| Stat Type | Notes |
|---|---|
| Eliminations | Most universally comparable across games |
| Wins | Good for showing win rate trends |
| Damage | High numbers = more dramatic bar growth |
| Score | Only if tracked consistently across games |

Run a separate Flourish visualization per stat type — do not mix stat types
in the same race as the scales will be incompatible.

---

## Resources

- Flourish Bar Chart Race template: [https://flourish.studio/visualisations/bar-chart-race](https://flourish.studio/visualisations/bar-chart-race)
- Living Charts inspiration: [https://livingcharts.com](https://livingcharts.com)
- Redshift Query Editor: AWS Console → Redshift → Query Editor v2
- Power BI AppSource: search "Racing Bar Chart" inside Power BI Desktop
