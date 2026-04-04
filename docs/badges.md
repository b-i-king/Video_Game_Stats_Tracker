# Badge System — Video Game Stats Tracker

Badge assets live in `web/public/badges/{slug}.png` and are served by
Vercel's CDN. The frontend only renders the download button when
`app.user_badges` contains a row for that user + badge combination.

---

## Design Language

All badges follow the app icon's visual style:

- **Shape:** Rounded square (match `icon.png` corner radius)
- **Background:** Gold — `#C9A84C` (matches `--gold` CSS variable)
- **Base motif:** White game controller (same as app icon)
- **Overlay symbol:** Small icon in the bottom-right or center to distinguish badge type (see table below)
- **Dimensions:** 512×512px (source), export at 256×256px for web
- **Format:** PNG with transparent outer corners if used on non-gold backgrounds

Recommended tool: Figma or Canva. Use the app icon as the base layer and
add the overlay symbol per badge.

---

## Core Badges (12)

| Slug | Name | Trigger | Overlay Symbol |
|---|---|---|---|
| `first_session` | First Log | Submit your first session | ✏️ pencil |
| `streak_7` | Week Warrior | 7-day logging streak | 🔥 small flame |
| `streak_30` | Monthly Grind | 30-day logging streak | 🔥 larger flame |
| `streak_90` | Dedicated | 90-day logging streak | 🔥 triple flame |
| `first_pb` | Personal Best | Hit your first personal best | ⭐ star |
| `pb_10` | Top Form | 10 personal bests recorded | ⭐ star cluster |
| `sessions_25` | Getting Started | 25 sessions logged | 📊 bar chart |
| `sessions_100` | Century | 100 sessions logged | 💯 bold 100 |
| `sessions_365` | Year One | 365 sessions logged | 📅 calendar |
| `challenge_complete` | Challenger | Complete first seasonal challenge | 🏆 trophy |
| `multi_game` | Versatile | Track stats across 3+ games | 🎮 second controller |
| `bolt_10` | Data Curious | Ask Bolt 10 questions | ⚡ lightning bolt |

---

## Seasonal Challenge Badges

One unique badge per seasonal challenge, named `challenge_{period}_{slug}`.

| Example Slug | Name | Period |
|---|---|---|
| `challenge_apr_2026` | April Challenger | April 2026 |
| `challenge_may_2026` | May Challenger | May 2026 |

Seasonal badge designs can reuse the base template with a month/year
label banner across the bottom.

---

## Access Control

| User tier | Can download badge? | Can auto-post badge? |
|---|---|---|
| Free | ✓ (manual download) | ✗ |
| Premium | ✓ (manual download) | ✗ |
| Trusted | ✓ | ✓ via social pipeline |
| Owner | ✓ | ✓ via social pipeline |

The download button is gated by `app.user_badges.earned_at` — it only
appears after the badge has been awarded. The asset URL (`/badges/{slug}.png`)
is publicly accessible by direct URL but users won't see it in the UI
unless they've earned it.

---

## DB Reference

```sql
-- Badge catalog (seeded by owner)
app.badges          -- slug, name, description, image_url, tier_required

-- Badges earned per user
app.user_badges     -- user_id, badge_id, earned_at
```

See `migration_plan.md` → Gamification section for full DDL.

---

## Asset Checklist

- [ ] Design base template in Figma/Canva using `icon.png` as reference
- [ ] Export all 12 core badge PNGs at 256×256px
- [ ] Add to `web/public/badges/` — filenames must match slug exactly
- [ ] Create seasonal badge template (reusable with month/year label)
- [ ] Export `challenge_apr_2026.png` for first seasonal challenge
