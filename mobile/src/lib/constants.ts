// Mirrors web/lib/constants.ts — keep both files in sync.
// When updating either file, update the other to match.

export const GENRES: Record<string, string[]> = {
  'Select a Genre': ['Select a Subgenre'],
  Action: [
    'First-Person Shooter (FPS)', 'Third-Person Shooter (TPS)', "Beat'Em Up",
    'Fighting Game', 'Stealth', 'Action-Adventure', 'Survival', 'Loother Shooter',
    'Rhythm', 'Battle Royale',
  ],
  'Battle Royale': ['First-Person Shooter (FPS)', 'Third-Person Shooter (TPS)', 'Hero-Based', 'Mobile', 'Party'],
  'Role-Playing (RPG)': ['Action', 'Western', 'Japanese', 'Tactical', 'Open-World', 'MMO', 'Roguelike', 'Dungeon Crawler', 'Monster-Taming'],
  'Massively Multiplayer Online RPGs (MMORPGs)': ['Theme-Park', 'Sandbox', 'Action', 'Sci-Fi', 'Fantasy', 'Turn-Based', 'Virtual-World', 'Metaworld'],
  'Action RPGs': ['Hack-and-Slash', 'Masher', 'Soulslike', 'TPS Hybrid', 'First-Person', 'Hunting', 'Roguelike', 'MMO'],
  'Tacical RPGs': ['Grid-Based', 'Western', 'Roguelike', 'Hybrid', 'Real-Time'],
  Simulation: ['Construction & Management (CMS)', 'Business', 'Life', 'Vehicle', 'Sports', 'Tactical', 'Other'],
  Shooter: ['Military', 'Tactical', 'Arena', 'Hero', 'Looter', 'Immersive Sim', 'Retro', 'Battle Royale', 'Stealth'],
  Stealth: ['Tactical Action', 'Immersive Sim', 'Disguise-Based', 'Horror', 'Top-Down', 'Procedural'],
  'First-Person Shooter (FPS)': ['Military', 'Immersive Sim', 'Hero'],
  Platformers: ['Traditional 2D Side-Scrolling', 'Puzzle', 'Run-and-Gun', 'Exploration RPG', 'Cinematic', 'Collect-and-Complete', 'Endless Runner'],
  Strategy: ['Real-Time Strategy (RTS)', 'Real-Time Tactics (RTT)', 'Turn-Based Strategy (TBS)', 'Turn-Based Tactics (TBT)', 'Grand', '4X', 'Tower Defense', 'Auto Battler', 'MMO', 'Construction & Management (CMS)', 'Wargame', 'Hybrid'],
  Survival: ['Open-World', 'Simulation', 'Horror', 'Social', 'Space', 'Post-Apocalyptic', 'Narrative', 'Settlement'],
  Sports: ['Arcade', 'Simulation', 'Management', 'Mult-Sport', 'Extreme', 'Combat'],
  Puzzle: ['Logic', 'Trivia', 'Tile-Matching', 'Hidden Object', 'Physics-Based', 'Exploration', 'Sokoban', 'Construction', 'Traditional', 'Reveal-the-Picture'],
  Adventure: ['Text', 'Graphic', 'Interactive Movie', 'Real-Time 3D', 'Visual Novel', 'Walking Simulator', 'Escape Room', 'Puzzle'],
  'Action-Adventure': ['Cinematic', 'Action RPG', 'Open-World', 'Metroidvania', 'Survival Horror', 'Stealth-Based', 'Hack-and-Slash', 'Grand Theft Auto'],
  Fighting: ['2D Versus', '2.5D', 'True 3D', 'Anime', 'Tag-Team', 'Platform', 'Weapon-Based'],
  'Real-Time Strategy (RTS)': ['Classic Base-Building', 'Tactical', 'Grand-Scale', 'Real-Time Tactics (RTT)', 'Hybrid', 'Hero-Based'],
  Racing: ['Simulation-Style', 'Touring-Car', 'Arcade-Style', 'Kart', 'Off-Road', 'Futuristic', 'Street', 'Motorcycle', 'Top-Down', 'Combat'],
  Casual: ['Tile-Matching', 'Hidden-Object', 'Hyper-Casual', 'Time-Management', 'Puzzle', 'Simulation', 'Street', 'Card & Board', 'Party Games & Minigame'],
  Party: ['Mini-Game Collections', 'Trivia', 'Social Deduction', 'Social Brawlers', 'Rhythm & Music', 'Collaborative', 'Card & Board', 'Guessing'],
};

export const CREDIT_STYLE_OPTIONS: Record<string, string> = {
  'S/O (Shoutout)': 'shoutout',
  'Game Credit': 'credit',
  'Props To': 'props',
  Playing: 'playing',
  Respect: 'respect',
  Vibes: 'vibes',
  'Powered By': 'powered',
  'Courtesy Of': 'courtesy',
  'ft.': 'ft',
  'Brought To You By': 'brought',
};

export const MATCH_TYPES = ['Solo', 'Team'] as const;
export const WIN_LOSS_OPTIONS = ['', 'Win', 'Loss'] as const;
export const PARTY_SIZES = ['1', '2', '3', '4', '5+'] as const;
export const DIFFICULTY_OPTIONS = ['', 'Easy', 'Normal', 'Hard', 'Expert'] as const;
export const INPUT_DEVICES = ['Controller', 'Keyboard & Mouse', 'Mixed'] as const;
export const PLATFORMS = ['PC', 'PlayStation', 'Xbox', 'Switch', 'Mobile'] as const;

// ── Stat alias glossary (WRITE PATH — input normalization only) ───────────────
export const STAT_ALIASES: Record<string, { canonical: string; display: string }> = {
  'kills':        { canonical: 'Eliminations', display: 'Eliminations' },
  'kill':         { canonical: 'Eliminations', display: 'Eliminations' },
  'frags':        { canonical: 'Eliminations', display: 'Eliminations' },
  'takedowns':    { canonical: 'Eliminations', display: 'Eliminations' },
  'k/d':          { canonical: 'E/R Ratio',    display: 'E/R Ratio'   },
  'kd':           { canonical: 'E/R Ratio',    display: 'E/R Ratio'   },
  'kill/death':   { canonical: 'E/R Ratio',    display: 'E/R Ratio'   },
  'dmg':          { canonical: 'Damage',        display: 'Damage'      },
  'heals':        { canonical: 'Healing',       display: 'Healing'     },
  'heal':         { canonical: 'Healing',       display: 'Healing'     },
  'xp':           { canonical: 'Experience',    display: 'XP'          },
  'exp':          { canonical: 'Experience',    display: 'XP'          },
  'ast':          { canonical: 'Assists',       display: 'Assists'     },
  'w':            { canonical: 'Wins',          display: 'Wins'        },
  'l':            { canonical: 'Losses',        display: 'Losses'      },
};

// ── Stat display labels (READ PATH — child-friendly overrides) ────────────────
export const STAT_DISPLAY_LABELS: Record<string, string> = {
  'Deaths': 'Respawns',
};

// ── Stat name block list ──────────────────────────────────────────────────────
export const BLOCKED_STAT_TERMS = new Set([
  'asdf', 'qwerty', 'zxcv', 'aaaa', 'bbbb', 'cccc', 'test123',
]);

export function isBlockedStatName(input: string): boolean {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { default: Filter } = require('bad-words');
    if (new Filter().isProfane(input)) return true;
  } catch {
    // Package not installed yet — fall through to custom list only
  }
  const lower = input.toLowerCase();
  for (const term of BLOCKED_STAT_TERMS) {
    if (new RegExp(`\\b${term}\\b`).test(lower)) return true;
  }
  return false;
}

export function resolveAlias(input: string) {
  return STAT_ALIASES[input.trim().toLowerCase()] ?? null;
}
