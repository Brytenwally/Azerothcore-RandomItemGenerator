# Cohesive Synergy Archetype Generator Engine

An intelligent, interactive tool for procedurally generating balanced, "Blizzlike" items for World of Warcraft private servers (AzerothCore/TrinityCore database schemas).

Instead of manually crafting thousands of items, this engine uses a **"Brain"** — pre-trained on your existing database — to understand how item levels, stats, budgets, and visual archetypes relate to one another.

---

## Features

- **Database-Driven Intelligence** — Connects directly to your `acore_world` database to learn item archetypes, ensuring generated gear feels authentic.
- **Interactive CLI Wizard** — Step-by-step console interface to define categories, item levels, and rarity.
- **Smart Stat Distribution** — Even Split or Randomly Varied profiles, with configurable deviation to prevent "stat inflation."
- **Item Spells** — Attach an On-Equip passive aura or an On-Use activated effect (with charges/cooldown) to a batch of items.
- **Item Sets** — Group items already in memory into a matching Item Set, with set-bonus spells at configurable piece thresholds.
- **Mass Creation** — Auto-populate large batches across every category with no per-category prompts.
- **Loot Assignment** — Automatically distributes generated items into open-world and boss loot tables, matched by item level.
- **External Configuration** — DB credentials and settings live in one shared `config.json`, no hardcoding.
- **Triple-Export** — SQL for `item_template`, CSV for `item.dbc`, and CSV for `ItemSet.dbc`.
- **Dynamic Visuals** — Auto-maps generated items to existing DisplayIDs based on their source archetype.

---

## Setup

### 1. Install dependencies

```
pip install joblib mysql-connector-python openpyxl pandas
```

### 2. Configure `config.json`

Both scripts read their settings from `config.json`, placed in the same folder. If it's missing, either script creates a default one and exits so you can fill it in.

```json
{
  "database": {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "acore",
    "password": "acore",
    "database": "acore_world"
  },
  "entry_id_start": 91000,
  "brain_file": "blizzlike_master_brain.pkl",
  "material_library_file": "material_library.joblib"
}
```

| Key | Description |
|---|---|
| `database` | MySQL connection details for `acore_world`. |
| `entry_id_start` | Lowest `item_template` entry ID the generator may use. New items take the first free ID at or above this value. |
| `brain_file` / `material_library_file` | File names produced by `train_brain.py` and consumed by `interactive_generator.py`. Only change these to keep multiple trained brains side by side. |

Missing keys fall back to the defaults above instead of crashing — partial configs are safe.

### 3. Startup order

1. Start your AzerothCore MySQL server.
2. Run `train_brain.py` — builds the "brain" (lookup databases) the generator relies on.
3. Run `interactive_generator.py` — your main interface for creating items.

---

## The Generation Wizard

Running `interactive_generator.py` walks you through:

1. **Category Selection** — Any class/subclass in your database except Trinkets and Relics.
   *(Menu options `[4]` Mass Creation, `[5]` Assign Loot, and `[6]` Create Item Set skip this — see their own sections below.)*
2. **Quality & Level** — Pick a quality (Uncommon/Rare/Epic/Legendary) and item level as a single number (`85`) or a bracket (`50-85`).
3. **Budget Quality Variance %** — How "Blizzlike" items should be.
   - `0%` strictly matches database archetypes.
   - Higher % adds deviation, allowing slightly better/worse items than baseline.
4. **Stat Distribution Profile**
   - **Even Split** — stats distributed equally.
   - **Randomly Varied** — more randomness per stat.
5. **Stat Slot Density Rule**
   - **Database Driven** — follows existing DB items exactly.
   - **Progressive Blizzlike** — auto progression (2 stats low-level → 6 stats at 264 epics).
   - **Explicit Manual Count** — you set an exact count (1–6).
   - **Random Range** — you set a min/max, each item rolls within it.
6. **Item Binding** — Bind on Equip, Bind on Pickup, or a mixed ratio.
7. **Random Enchantment** — Optional % of items get a RandomProperty (<20) or RandomSuffix (20+), drawn from your existing `item_enchantment_template` entries.
8. **Item Spell** — Optionally attach a spell to a % of items in the batch:
   - **No spell** (default)
   - **On Equip** — passive aura while worn.
   - **On Use** — activated ability; also set **Charges** (`0` = unlimited, or a fixed use count before the item is consumed) and **Cooldown** in ms (`-1` = use the spell's own cooldown).
9. **Quantity** — How many items to generate this batch.

---

## Item Sets

Menu option **`[6] Create Item Set`** groups items already sitting in memory into a matching set (e.g. a 5-piece Tier set with 2-piece/4-piece bonuses).

1. **Item Selection** — All items in memory are listed by index. Enter the indices belonging to the set, comma-separated (`3,7,12,15,20`). A set needs 2–17 items.
2. **Set ID** — A unique numeric ID. Written to `item_template.itemset` for every member item and used as the row ID in the exported `ItemSet.dbc` data. Make sure it doesn't collide with an existing set ID on your server.
3. **Set Name** — Display name (e.g. `"Sorvaxis Battlegear"`).
4. **Set Bonuses** — Up to 8 tiers, each a **Spell ID** + **Threshold** (pieces required, 2 up to the set size). Leave Spell ID empty to stop adding tiers.

You can create multiple sets per session — just run `[6]` again. Each item belongs to only one set at a time.

> **⚠️ Server-side DBC required:** AzerothCore's worldserver reads `ItemSet.dbc` itself at startup — not just the client. If your worldserver log shows `Item set X for item Y not found, mods not applied`, your patched `ItemSet.dbc` hasn't been copied into the server's `DataDir` (or the server hasn't restarted since). **Both client and server need the same patched file**, and the worldserver must be restarted to pick it up.

---

## Mass Creation & Loot Assignment

- **`[4]` Mass Creation** — Bulk-generates items across every category with sensible defaults, skipping per-category prompts. Good for quickly filling out a database.
- **`[5]` Assign Loot to Mobs** — Scans creature/loot tables and distributes items in memory into open-world creature loot and/or dungeon/raid boss reference loot groups, matched by item level and mob level range. Writes `loot_assignments.sql`; unmatched items are listed as comments at the bottom.

---

## Session Management & Exporting

**Looping:** Items stay in `internal_memory` across batches. After each batch you're asked to add another, create a set, assign loot, or finish.

**On finishing, the script exports:**

| File | Contents |
|---|---|
| `interactive_generated_items.sql` | Ready to run against `acore_world`. IDs start at `entry_id_start` (default `91000`, set in `config.json`). |
| `generated_items.csv` | For WDBXEditor — import into `item.dbc` for client-side compatibility. |
| `generated_itemsets.csv` | Only written if you created at least one Item Set. Full `ItemSet.dbc` column layout (ID, localized name fields + mask, up to 17 item IDs, up to 8 set-bonus spells/thresholds, required skill fields). **Apply to both client and server `ItemSet.dbc`** — see the warning above. |
| `generated_items_tooltips.xlsx` | Human-readable Excel summary of every generated item's stats and tooltip, for quick review. |
