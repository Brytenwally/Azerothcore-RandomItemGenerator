The Cohesive Synergy Archetype Generator Engine is an intelligent, interactive tool designed to procedurally generate balanced, "Blizzlike" items for World of Warcraft private servers (specifically compatible with AzerothCore/TrinityCore database schemas).

Instead of manually crafting thousands of items, this engine uses a "Brain" (pre-trained on your existing database) to understand how item levels, stats, budgets, and visual archetypes relate to one another.

**Features**

Database-Driven Intelligence: Connects directly to your acore_world database to learn item archetypes, ensuring generated gear feels authentic.

Interactive CLI Wizard: A step-by-step console interface to define categories, item levels, and rarity.

Smart Stat Distribution: Supports multiple profiles (Even Split vs. Randomly Varied) with configurable deviation rules to prevent "stat inflation."

Item Spells: Attach an On-Equip passive aura or an On-Use activated effect (with charges and cooldown) to a batch of generated items.

Item Sets: Group items already sitting in memory into a matching Item Set, complete with set-bonus spells at configurable piece thresholds.

Mass Creation: Auto-populate large batches of items across every category with no per-category archetype prompts, for quickly filling out a database.

Loot Assignment: Automatically distributes generated items into open-world creature loot tables and dungeon/raid boss reference loot groups, matched by item level.

External Configuration: Database credentials and other settings live in a single config.json file, shared by both scripts, instead of being hardcoded.

Triple-Export Capability:

SQL: Automatically generates a formatted SQL script ready to be executed against your item_template table.

Item CSV: Generates a standardized CSV for external data management or mass-import tools (e.g. WDBXEditor / item.dbc).

Item Set CSV: Generates a second CSV matching the full ItemSet.dbc column layout, for any sets created during the session.

Dynamic Visuals: Automatically maps generated items to existing DisplayIDs based on their source archetype.


**How to use**

Before anything else, install these dependencies if you don't have them

```pip install joblib mysql-connector-python openpyxl pandas```




1. Essential Startup Order
Before running the generator, please ensure your environment is ready:

Start your AzerothCore MySQL server.

Create a config.json in the same folder as the scripts (see "Configuration" below). If it's missing, either script will generate a default one for you on first run and then exit so you can fill in your credentials.

Run train_brain.py first. This is required to process the raw item data and build the "brain" (the lookup databases) that the generator relies on.

Run interactive_generator.py. This is your main interface for creating items.

2. Configuration
Both train_brain.py and interactive_generator.py read their settings from a config.json file placed next to the scripts. This keeps database credentials and other environment-specific values out of the source code, and ensures both scripts always talk to the same database and read/write the same brain files.

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

database: Your MySQL connection details for the acore_world database.

entry_id_start: The lowest item_template entry ID the generator is allowed to use. New items always occupy the first free ID at or above this value.

brain_file / material_library_file: File names for the two files train_brain.py produces and interactive_generator.py consumes. Only change these if you want to keep multiple trained brains side by side (e.g. one per server/expansion).

If a key is missing from your config.json, the script fills it in with the default shown above rather than failing, so partial configs are safe.

3. The Generation Wizard
When you run interactive_generator.py, you will be guided through a series of inputs:

Category Selection: You can choose from all available classes and subclasses currently in your database, with the exception of Trinkets and Relics. Options [4] Mass Creation and [5] Assign Loot to Mobs and [6] Create Item Set skip the category wizard entirely (see their own sections below).

Quality & Level: Choose the item quality (Uncommon, Rare, Epic, Legendary), and specify your item level either as a single number (e.g., 85) or a bracket (e.g., 50-85).

Budget Quality Variance %: This controls how "Blizzlike" your items are.

0% will force the items to strictly adhere to the database archetypes.

Increasing this percentage adds a margin of deviation, allowing for slightly better or worse items than the original baseline.

Stat Distribution Allocation Profile: This determines how stats are weighted.

Even Split: Stats are distributed equally across the selected pool.

Randomly Varied: Stats are assigned with more randomness for a unique feel.

Stat Slot Density Rule: This determines the complexity of your gear:

Database Driven: Strictly follows the exact logic of the corresponding items already present in your database.

Progressive Blizzlike: Follows an automated progression logic (e.g., 2 stats for low-level gear, scaling up to 6 stats for high-level 264 epics).

Explicit Manual Count: You choose exactly how many stats the items will have, from 1 to 6.

Random Range: You choose a minimum and maximum stat count, and each item rolls a random value in between.

Item Binding: Choose Bind on Equip, Bind on Pickup, or a mixed ratio of both across the batch.

Random Enchantment: Optionally give a percentage of items in the batch a random RandomProperty (below level 20) or RandomSuffix (level 20+) enchantment, drawn from your database's existing item_enchantment_template entries.

Item Spell: Optionally attach a spell to items in the batch:

No spell: items generate with no spell effect (default).

On Equip: a passive aura is active for as long as the item is worn.

On Use: an activated ability, where you also configure Charges (0 = unlimited uses, or a fixed number of uses before the item is consumed) and Cooldown in milliseconds (-1 = use the spell's own cooldown from spell.dbc).

For either option, you also set what percentage of items in the batch receive the spell (0-100%).

Quantity: Finally, define how many items you wish to create in the current batch.

4. Item Sets
Once you have generated items and they are sitting in memory, you can group them into a matching Item Set (e.g. a 5-piece Tier set with a 2-piece and 4-piece bonus) via menu option [6] Create Item Set.

Item Selection: All items currently held in internal_memory are listed with an index number. Enter the indices of the items that belong to this set, comma-separated (e.g. 3,7,12,15,20). A set must contain between 2 and 17 items.

Set ID: Enter a unique numeric ID for this set. This ID is written to item_template.itemset for every selected item and used as the ID row in the exported ItemSet.dbc data, so make sure it doesn't collide with any set ID already in use on your server.

Set Name: A display name for the set (e.g. "Sorvaxis Battlegear").

Set Bonuses: Define up to 8 bonus tiers. For each tier you provide a Spell ID (the aura/effect granted) and a Threshold (how many pieces of the set must be worn to activate it, from 2 up to the total number of items in the set). Leave the Spell ID empty to stop adding bonuses.

You can create multiple sets in the same session by selecting option [6] again. Each item can only belong to one set at a time.

Important: The server itself reads ItemSet.dbc at worldserver startup (not just the client). If your worldserver logs show "Item set X for item Y not found, mods not applied," your patched ItemSet.dbc hasn't been copied into the server's DataDir (or the server hasn't been restarted since copying it). Both client and server need the same patched ItemSet.dbc, and the worldserver must be restarted to pick it up.

5. Mass Creation & Loot Assignment
Mass Creation [4]: Auto-populates a large batch of items across every category using sensible defaults, without stepping through the archetype prompts for each one. Useful for quickly bulk-filling a database.

Assign Loot to Mobs [5]: Scans your creature/loot tables and distributes the items currently in internal_memory into matching open-world creature loot tables and/or dungeon/raid boss reference loot groups, based on item level and the mob's level range. Produces a separate loot_assignments.sql file; any items that couldn't be matched to a mob are listed as comments at the bottom of that file.

6. Session Management & Exporting
Looping: Once a batch is created, the items are held in the script's internal_memory. You will be asked if you want to create more items or if you are ready to import. You can continue adding batches, creating item sets, and assigning loot as long as you like.

Final Export: When you choose to finish your session, the script generates:

SQL Query (interactive_generated_items.sql): Ready to be executed against your acore_world database. It is designed to be safe, automatically occupying empty IDs starting from entry_id_start upwards (91000 by default, configurable in config.json).

Item CSV (generated_items.csv): A secondary file specifically formatted for WDBXEditor, allowing you to import your new items directly into your item.dbc file to ensure full client-side compatibility.

Item Set CSV (generated_itemsets.csv): Only written if you created at least one Item Set during the session. Matches the full ItemSet.dbc column layout (ID, all localized name fields + mask, up to 17 item IDs, up to 8 set-bonus spells and thresholds, required skill fields) for import into ItemSet.dbc via WDBXEditor. Remember this file must be applied to both the client's ItemSet.dbc and the server's ItemSet.dbc (see the note in the Item Sets section above).

Tooltip Overview (generated_items_tooltips.xlsx): A human-readable Excel sheet summarizing every generated item's stats and tooltip for quick review.
