// ── Game genres & subgenres ───────────────────────────────────────────────────
// Mirror of GENRES dict in utils/app_utils.py
export const GENRES: Record<string, string[]> = {
  "Select a Genre": ["Select a Subgenre"],
  Action: [
    "First-Person Shooter (FPS)",
    "Third-Person Shooter (TPS)",
    "Beat'Em Up",
    "Fighting Game",
    "Stealth",
    "Action-Adventure",
    "Survival",
    "Loother Shooter",
    "Rhythm",
    "Battle Royale",
  ],
  "Battle Royale": [
    "First-Person Shooter (FPS)",
    "Third-Person Shooter (TPS)",
    "Hero-Based",
    "Mobile",
    "Party",
  ],
  "Role-Playing (RPG)": [
    "Action",
    "Western",
    "Japanese",
    "Tactical",
    "Open‑World",
    "MMO",
    "Roguelike",
    "Dungeon Crawler",
    "Monster-Taming",
  ],
  "Massively Multiplayer Online RPGs (MMORPGs)": [
    "Theme-Park",
    "Sandbox",
    "Action",
    "Sci-Fi",
    "Fantasy",
    "Turn-Based",
    "Virtual-World",
    "Metaworld",
  ],
  "Action RPGs": [
    "Hack-and-Slash",
    "Masher",
    "Soulslike",
    "TPS Hybrid",
    "First‑Person",
    "Hunting",
    "Roguelike",
    "MMO",
  ],
  "Tacical RPGs": ["Grid-Based", "Western", "Roguelike", "Hybrid", "Real-Time"],
  Simulation: [
    "Construction & Management (CMS)",
    "Business",
    "Life",
    "Vehicle",
    "Sports",
    "Tactical",
    "Other",
  ],
  Shooter: [
    "Military",
    "Tactical",
    "Arena",
    "Hero",
    "Looter",
    "Immersive Sim",
    "Retro",
    "Battle Royale",
    "Stealth",
  ],
  Stealth: [
    "Tactical Action",
    "Immersive Sim",
    "Disguise-Based",
    "Horror",
    "Top-Down",
    "Procedural",
  ],
  "First‑Person Shooter (FPS)": ["Military", "Immersive Sim", "Hero"],
  Platformers: [
    "Traditional 2D Side‑Scrolling",
    "Puzzle",
    "Run‑and‑Gun",
    "Exploration RPG",
    "Cinematic",
    "Collect‑and‑Complete",
    "Endless Runner",
  ],
  Strategy: [
    "Real-Time Strategy (RTS)",
    "Real-Time Tactics (RTT)",
    "Turn-Based Strategy (TBS)",
    "Turn-Based Tactics(TBT)",
    "Grand",
    "4X",
    "Tower Defense",
    "Auto Battler",
    "MMO",
    "Construction & Management (CMS)",
    "Wargame",
    "Hybrid",
  ],
  Survival: [
    "Open-World",
    "Simulation",
    "Horror",
    "Social",
    "Space",
    "Post-Apocalyptic",
    "Narrative",
    "Settlement",
  ],
  Sports: [
    "Arcade",
    "Simulation",
    "Management",
    "Mult-Sport",
    "Extreme",
    "Combat",
  ],
  Puzzle: [
    "Logic",
    "Trivia",
    "Tile-Matching",
    "Hidden Object",
    "Physics-Based",
    "Exploration",
    "Sokoban",
    "Construction",
    "Traditional",
    "Reveal-the-Picture",
  ],
  Adventure: [
    "Text",
    "Graphic",
    "Interactive Movie",
    "Real-Time 3D",
    "Visual Novel",
    "Walking Simulator",
    "Escape Room",
    "Puzzle",
  ],
  "Action-Adventure": [
    "Cinematic",
    "Action RPG",
    "Open-World",
    "Metroidvania",
    "Survival Horror",
    "Stealth-Based",
    "Hack-and-Slash",
    "Grand Theft Auto",
  ],
  Fighting: [
    "2D Versus",
    "2.5D",
    "True 3D",
    "Anime",
    "Tag-Team",
    "Platform",
    "Weapon-Based",
  ],
  "Real-Time Strategy (RTS)": [
    "Classic Base‑Building",
    "Tactical",
    "Grand-Scale",
    "Real‑Time Tactics (RTT)",
    "Hybrid",
    "Hero‑Based",
  ],
  Racing: [
    "Simulation‑Style",
    "Touring‑Car",
    "Arcade‑Style",
    "Kart",
    "Off-Road",
    "Futuristic",
    "Street",
    "Motorcycle",
    "Top-Down",
    "Combat",
  ],
  Casual: [
    "Tile‑Matching",
    "Hidden‑Object",
    "Hyper‑Casual",
    "Time‑Management",
    "Puzzle",
    "Simulation",
    "Street",
    "Card & Board",
    "Party Games & Minigame",
  ],
  Party: [
    "Mini-Game Collections",
    "Trivia",
    "Social Deduction",
    "Social Brawlers",
    "Rhythm & Music",
    "Collaborative",
    "Card & Board",
    "Guessing",
  ],
};

// ── Stat alias glossary ───────────────────────────────────────────────────────
// Maps lowercase user input → { canonical: stored value, display: shown in UI }
// Keeps child-friendly labels ("Respawns" instead of "Deaths") while storing
// canonical names for consistent community queries and leaderboard comparisons.
export const STAT_ALIASES: Record<string, { canonical: string; display: string }> = {
  "kills":        { canonical: "Eliminations", display: "Eliminations" },
  "kill":         { canonical: "Eliminations", display: "Eliminations" },
  "frags":        { canonical: "Eliminations", display: "Eliminations" },
  "takedowns":    { canonical: "Eliminations", display: "Eliminations" },
  "deaths":       { canonical: "Deaths",       display: "Respawns"     },
  "death":        { canonical: "Deaths",       display: "Respawns"     },
  "respawns":     { canonical: "Deaths",       display: "Respawns"     },
  "kos":          { canonical: "Deaths",       display: "Respawns"     },
  "k/d":          { canonical: "K/D Ratio",    display: "K/D Ratio"   },
  "kd":           { canonical: "K/D Ratio",    display: "K/D Ratio"   },
  "kill/death":   { canonical: "K/D Ratio",    display: "K/D Ratio"   },
  "dmg":          { canonical: "Damage",       display: "Damage"       },
  "heals":        { canonical: "Healing",      display: "Healing"      },
  "heal":         { canonical: "Healing",      display: "Healing"      },
  "xp":           { canonical: "Experience",   display: "XP"           },
  "exp":          { canonical: "Experience",   display: "XP"           },
  "assists":      { canonical: "Assists",      display: "Assists"      },
  "ast":          { canonical: "Assists",      display: "Assists"      },
  "wins":         { canonical: "Wins",         display: "Wins"         },
  "w":            { canonical: "Wins",         display: "Wins"         },
  "losses":       { canonical: "Losses",       display: "Losses"       },
  "l":            { canonical: "Losses",       display: "Losses"       },
};

// ── Stat name block list ──────────────────────────────────────────────────────
// Prevents inappropriate or nonsensical stat names from being submitted.
// Checked case-insensitively against the full stat type string.
export const BLOCKED_STAT_TERMS = new Set([
  // Profanity (partial list — extend as needed)
  "fuck", "shit", "ass", "bitch", "bastard", "damn", "crap", "piss",
  "cock", "dick", "pussy", "cunt", "whore", "slut",
  // Slurs (abbreviated — extend as needed)
  "fag", "dyke", "tranny", "retard", "spaz",
  // Gibberish patterns caught separately via regex, but common ones here
  "asdf", "qwerty", "zxcv", "aaaa", "bbbb", "cccc", "test123",
]);

// Returns true if the stat name contains a blocked term as a whole word.
// Uses \b word boundaries so "ass" does not falsely block "Assists", "Class", etc.
export function isBlockedStatName(input: string): boolean {
  const lower = input.toLowerCase();
  for (const term of BLOCKED_STAT_TERMS) {
    if (new RegExp(`\\b${term}\\b`).test(lower)) return true;
  }
  return false;
}

// ── Credit style options ──────────────────────────────────────────────────────
// Maps display label → value sent to Flask
export const CREDIT_STYLE_OPTIONS: Record<string, string> = {
  "S/O (Shoutout)": "shoutout",
  "Game Credit": "credit",
  "Props To": "props",
  Playing: "playing",
  Respect: "respect",
  Vibes: "vibes",
  "Powered By": "powered",
  "Courtesy Of": "courtesy",
  "ft.": "ft",
  "Brought To You By": "brought",
};

// ── Match / session options ───────────────────────────────────────────────────
export const MATCH_TYPES = ["Solo", "Team"] as const;
export const WIN_LOSS_OPTIONS = ["", "Win", "Loss"] as const;
export const PARTY_SIZES = ["1", "2", "3", "4", "5+"] as const;
export const DIFFICULTY_OPTIONS = ["", "Easy", "Normal", "Hard", "Expert"] as const;
export const INPUT_DEVICES = ["Controller", "Keyboard & Mouse", "Mixed"] as const;
export const PLATFORMS = ["PC", "PlayStation", "Xbox", "Switch", "Mobile"] as const;
