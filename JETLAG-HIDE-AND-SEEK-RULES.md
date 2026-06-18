# JetLag: The Game — Hide and Seek (Home Game) Rules Summary

A reference summary of the **Hide and Seek** home game by Jet Lag: The Game (Nebula/Wendover).
Compiled for the `jltg-mapper` companion-app project. Card/curse/coin components stay
physical — see [[no-card-deck-in-app]] — so the relevant modeling surface here is the
**timer, questions, and scoreboard**.

> Sources are listed at the bottom. Some exact numbers vary by map size and by the edition
> of the rulebook; treat the per-size values as the commonly documented defaults and confirm
> against the official rulebook for any given game.

---

## 1. Premise

A modern, city-scale game of hide and seek played on **public transit**. In each round:

- **One player is the Hider.** They travel out and conceal themselves inside a legal hiding zone.
- **The rest are Seekers** (a single team). They cooperate to locate the Hider by asking
  **questions** the Hider must answer **truthfully**.

The Hider's goal is to **stay hidden as long as possible**. The Seekers' goal is to
**find the Hider as fast as possible**. Time hidden is the score.

---

## 2. Map Sizes

The game scales to the play area. Three standard sizes, each with a different hiding-period
length and hiding-zone radius:

| Size   | Scale            | Hiding period | Hiding zone radius around a transit stop |
|--------|------------------|---------------|------------------------------------------|
| Small  | A town / district | ~30 min       | ¼ mile                                   |
| Medium | A city            | ~45 min       | ¼ mile                                   |
| Large  | A region/country  | ~3 hours      | ½ mile                                   |

The hiding zone must be a publicly accessible location within the listed radius of a
**transit stop** (train/bus/metro station, etc.). The Hider may move freely anywhere inside
that circle. If the hiding zone is in a park, the Hider must stay **within 6 feet of a
footpath**.

---

## 3. Game Phases

### A. Hiding Period
The Hider gets uninterrupted travel time (per the table above) to ride transit to a hiding
zone and conceal themselves. Seekers wait (eyes closed / at the start station) and may not
track the Hider. When the timer expires, the Hider must be hidden and stationary.

### B. Seeking Period (the main game)
The clock that matters — the Hider's **run time** — starts. Seekers move around the map and
ask **questions** to narrow down the Hider's location. The Hider answers truthfully, and
**every question lets the Hider draw cards** from the Hider deck (time bonuses, power-ups,
curses) that they use to defend their position.

### C. Endgame
When Seekers reach the Hider's hiding zone / transit station and are within the **endgame
radius**, the round enters the endgame: the Hider **may no longer move**, and Seekers close
in to make physical contact. The round ends the moment a Seeker **finds the Hider**.

The Hider's run time (plus any earned time bonuses) is recorded. Roles rotate and the next
round begins.

---

## 4. The Six Question Categories

Seekers narrow the search by asking questions. Questions are the Seekers' only investigative
tool, and the **category determines how many cards the Hider draws** (broader/more powerful
questions reward the Hider with more cards). Typical structure:

| Category     | What it asks                                                                 | Hider draws |
|--------------|------------------------------------------------------------------------------|-------------|
| **Matching**   | "Is your *X* the same as our *X*?" (e.g. nearest golf course, library, river) | draw 3, keep 1 |
| **Measuring**  | "Are you closer to *X* than we are?" (e.g. an airport, the coast)            | draw 3, keep 1 |
| **Radar**      | "Are you within *N* km of us?"                                               | draw 2, keep 1 |
| **Thermometer**| Seekers travel a set distance, then ask "Did we get hotter or colder?"       | draw 2, keep 1 |
| **Tentacles**  | "Of all *X* (e.g. aquariums) within radius *R* of us, which is your nearest?" — answered only if the Hider is inside that radius | draw 4, keep 2 |
| **Photos**     | The Hider sends a photo of a Seeker-chosen subject (e.g. tallest building visible, the ceiling above you) | draw 1, keep 1 |

Common procedural rules:
- The Hider must answer **honestly**.
- Seekers generally may not ask the **same category twice in a row** (and/or there is a
  cooldown / pacing between questions — varies by ruleset).
- Each answer is logged so Seekers can triangulate over time.

---

## 5. The Hider Deck (Cards)

Each question lets the Hider draw and keep cards. Three broad types:

- **Time Bonuses** — added to the Hider's run time at the end of the round if conditions are
  met (e.g. "+5 minutes if you discard 2 cards"). These reward the Hider for surviving and
  for holding/expending resources.
- **Power-ups** — utility cards the Hider plays for an advantage (e.g. duplicating a question's
  draw, randomizing/veto, etc.).
- **Curses** — cards the Hider plays **on the Seekers** to impede them: forcing a detour,
  a silly task, a movement restriction, a temporary ban on transit or on asking questions,
  blindfolds, etc. Curses are the Hider's main active defense.

**Curse stacking rule:** if a curse currently blocks the Seekers from **asking questions** or
from **moving on public transport**, another curse may **not** be played on them until the
first is resolved.

---

## 6. Coins / Tokens Economy

The card draws and curses are the core resource loop in the base game. Editions / expansions
layer a **coin (token) economy** on top: the Hider earns coins and spends them to play curses
or power-ups, creating a trade-off between hoarding for time bonuses and spending to slow the
Seekers. Treat exact coin costs as edition-specific.

---

## 7. Scoring & Winning

- A Hider's **score for a round = total run time** (seeking-period elapsed time **+** earned
  time bonuses).
- **Roles rotate**: every player takes a turn as the Hider over the course of the game.
- The **overall winner is the player with the longest single hiding time** (i.e. the best
  individual round as Hider). The Seekers collectively try to minimize each Hider's time.

---

## 8. San Francisco Small-Game Homebrew (community v1.2, Jun 2026)

A locally maintained **Small-game** variant scoped to San Francisco. This is the ruleset the
`jltg-mapper` project targets. ([Source Google Doc](https://docs.google.com/document/d/17xUTygVHs2I1ohq7xvBnkbqEZYaWY5ZM7zHXJmdUIgs/edit))

> The curated lists below are broken out as machine-readable GeoJSON + JSON in
> [data/](data/) — see [data/README.md](data/README.md).

**Map & movement**
- **Borders**: City & County of San Francisco land limits, **including Treasure Island**.
  Excluded: Alcatraz (federal), the Farallones, the SF-owned slivers of Angel/Alameda Islands.
  Daly City / Brisbane zips (94015, 94014, 94005) are out.
- **Starting point**: Van Ness & Market (Van Ness Station).
- **Hiding period**: 30 minutes (Small game). The Hider **may leave the borders during hiding
  time** as long as they return to a valid hiding station's zone before time runs out (so a
  border-edge zone can be a semicircle).
- **Transit allowed**: BART, Muni Metro, Caltrain, heritage streetcars (F), cable cars, the
  Treasure Island ferry, and public buses (Muni, SamTrans, Golden Gate Transit) + public
  shuttles. **No private vehicles, rideshare, robotaxi, or rental bikes/scooters.**

**Hiding stations** — Instead of the official "within ¼ mi of a transit stop," this variant
uses a curated list of **~200 valid hiding stations** (all BART/Caltrain + ferry terminals +
Muni Metro stations + ~130 hand-picked Muni bus stops for park/geographic coverage). The Hider
must end within **¼ mi** of one of these and stay in that zone (maintained as a Google Sheet +
Atlas map + Google Maps list).

**Question modifications (vs official Small)**
- **Transit Line (Matching)** reworked for bus density: Seekers must be *moving* on a line and
  ask "Does \[my line] stop in your hiding zone?" — Yes if the line stops within ¼ mi of the
  Hider's chosen station (limited/rapid lines: only where they actually stop).
- **Localized definitions**: "4th Administrative Division" = SF Supervisorial Districts D1–11;
  "Mountain" = one of **16 hills >400 ft** (curated list, since Google Maps is unreliable);
  "Park" = one of **36 dog parks**; curated lists also fixed for hospitals (16), SFPL libraries
  (28 + TI kiosk), golf courses (8), consulates (38, honoraries excluded), museums, theaters.
- **Removed as unusable**: Commercial Airport, 1st/2nd/3rd admin divisions, Amusement Park, Zoo,
  High-Speed Train Line, International Border, and **Matching Aquarium** (too powerful — measuring
  Aquarium is kept). "Coastline" expanded to include the Bay side to avoid a 50/50.
- **Added from Medium/Large**: extra Photo questions (Trace Nearest Street/Path, Two Buildings,
  Restaurant Interior, Park, Grocery Store Aisle, Place of Worship).
- **Untested homebrew additions**: Matching — Farmers Market, Residential Parking-Permit-zone
  color; Measuring — Cannabis Dispensary; Photo — house number, 30 s of ambient audio.

**Untested homebrew curses** (flavor-rich, SF-themed):
- **Curse of the 49er** — a gambling/dice curse (clear it, or the Hider banks +4 min bonuses).
- **Curse of Antoinette Cattani** — Seekers must each down a shot of Fernet Branca before the
  next question.
- **Curse of Carcinization** — Seekers tape their fingers into a "crab claw"; freeing the hand
  early gives the Hider +30 min.

---

## Modeling notes for `jltg-mapper`

The companion app should model the parts that are software-shaped, not the physical deck:

- **Timer** — hiding-period countdown, then the seeking-period run-time stopwatch, plus
  endgame lock. Time bonuses get added to the run time at round end.
- **Questions** — the six categories, pacing/cooldown and no-repeat-category rule, and a log
  of asked questions + answers for Seeker triangulation.
- **Scoreboard** — per-round run times across rotating Hiders, and the leaderboard (max time).

Cards, curses, and coins remain physical components and are out of scope per
[[no-card-deck-in-app]].

---

## Sources

- [Hide + Seek Expansion Pack Vol. 1 Rules — rules.jetlagthegame.com](https://rules.jetlagthegame.com/expansion/)
- [Jet Lag The Game: Hide and Seek rules (denull mirror)](https://jetlag.denull.ru/en/rules/)
- [The Game — Questions (denull mirror)](https://jetlag.denull.ru/en/rules/questions/)
- [Hide + Seek — Jet Lag: The Wiki (Fandom)](https://jetlag.fandom.com/wiki/Hide_%2B_Seek)
- [Hide + Seek: Japan — Jet Lag: The Wiki (Fandom)](https://jetlag.fandom.com/wiki/Hide_%2B_Seek:_Japan)
- [What is Jet Lag: Hide and Seek? — Moof.Space](https://moof.space/what-is-jet-lag/)
- [Jet Lag Hide + Seek Rulebook (PDF, Scribd)](https://www.scribd.com/document/937613966/Jet-Lag-Hide-Seek-Rulebook)
- [awesome-jetlag-hide-and-seek — community resources (GitHub)](https://github.com/jltg-community/awesome-jetlag-hide-and-seek)
- [SF Small-Game Homebrew rules (Google Doc, v1.2)](https://docs.google.com/document/d/17xUTygVHs2I1ohq7xvBnkbqEZYaWY5ZM7zHXJmdUIgs/edit)
- [SF valid hiding stations / curated lists (Google Sheet)](https://docs.google.com/spreadsheets/d/1VyhjPUGxNSybxBV7yFSEECI9sKcdJOME2TpFpAaXpok/edit)
