import mysql.connector
import pandas as pd
import joblib
import warnings

warnings.filterwarnings("ignore")

print("Step 1: Connecting to AzerothCore Database...")
db_config = {
    "host": "127.0.0.1",
    "user": "acore",
    "password": "acore",
    "database": "acore_world",
    "port": 3306
}

try:
    conn = mysql.connector.connect(**db_config)
except Exception as e:
    print(f"❌ Connection Failed! Error: {e}")
    exit()

print("Step 2: Extracting baseline reference frames...")
query = """
    SELECT entry, name, itemlevel, Quality, class, subclass, InventoryType, displayid, delay, 
           dmg_min1, dmg_max1, armor, Material, sheath, SellPrice,
           stat_type1, stat_value1, stat_type2, stat_value2, stat_type3, stat_value3, stat_type4, stat_value4,
           RandomProperty, RandomSuffix
    FROM item_template 
    WHERE itemlevel BETWEEN 10 AND 284 
      AND class IN (2, 4);
"""
df = pd.read_sql(query, conn)
conn.close()

print(f"Successfully loaded {len(df)} templates. Building Synergistic Cluster Matrices...")

# Compute basic metrics
df['total_budget'] = df['stat_value1'] + df['stat_value2'] + df['stat_value3'] + df['stat_value4']
df['dps'] = 0.0
weapon_mask = (df['class'] == 2) & (df['delay'] > 0)
df.loc[weapon_mask, 'dps'] = ((df.loc[weapon_mask, 'dmg_min1'] + df.loc[weapon_mask, 'dmg_max1']) / 2) / (df.loc[weapon_mask, 'delay'] / 1000.0)

def count_active_stats(row):
    count = 0
    for i in range(1, 5):
        if int(row[f'stat_type{i}']) != 0 and int(row[f'stat_value{i}']) > 0:
            count += 1
    return count
df['num_stats'] = df.apply(count_active_stats, axis=1)

# --- SYNCED ARCHETYPES (Matches interactive_generator.py) ---
ARCHETYPES = {
    "AGI_DPS":     {3, 7, 31, 32, 36, 38, 44},
    "STR_DPS":     {4, 7, 31, 32, 36, 38, 44},
    "SP_DPS":      {5, 7, 45, 31, 32, 36},
    "HEALER":      {5, 6, 7, 45, 32, 36, 43},
    "STR_TANK":    {4, 7, 12, 13, 14, 31, 37},
    "AGI_TANK":    {3, 7, 12, 13, 31, 37, 32, 36, 38},
    "AGI_INT_DPS": {3, 5, 7, 31, 32, 36, 38, 44}
}

def classify_row_archetype(row):
    item_stats = set()
    for i in range(1, 5):
        st = int(row[f'stat_type{i}'])
        sv = int(row[f'stat_value{i}'])
        if st != 0 and sv > 0: item_stats.add(st)
    
    if not item_stats: return "STR_DPS" # Default fallback
    
    # Score intersection to find best archetype match
    scores = {arch: len(item_stats.intersection(pool)) for arch, pool in ARCHETYPES.items()}
    best_match = max(scores, key=scores.get)
    
    return best_match if scores[best_match] > 0 else "STR_DPS"

print(" -> Analyzing item distribution footprints...")
df['archetype'] = df.apply(classify_row_archetype, axis=1)

# Compile the Slot-Level Archetype Weight Distribution Maps
archetype_profiles = {}
for (cls, subcls, inv_type), group in df.groupby(['class', 'subclass', 'InventoryType']):
    total_items = len(group)
    counts = group['archetype'].value_counts()
    weights = {arch: float(count / total_items) for arch, count in counts.items()}
    
    arch_stats = {arch: list(pool) for arch, pool in ARCHETYPES.items()}
    
    archetype_profiles[(int(cls), int(subcls), int(inv_type))] = {
        "weights": weights,
        "stats": arch_stats
    }

# Step 2A: Build Macro Budget Curves by InventoryType and Quality
print(" -> Compiling Slot-Level Macro Budget Curves...")
global_budget_curves = {}
for (inv_type, qual), group in df.groupby(['InventoryType', 'Quality']):
    curve_nodes = []
    for ilvl, sub_group in group.groupby('itemlevel'):
        # Exclude RandomProperty/RandomSuffix items explicitly, not just via
        # total_budget > 0. Some of these still carry a nonzero *base* stat
        # total (the random component is generated at loot time and never
        # touches item_template), so relying on total_budget alone lets a
        # partially-itemized random item sneak in and drag that single
        # itemlevel's average down -- exactly the kind of localized dip that
        # makes a higher-ilvl node look weaker than its lower-ilvl neighbor.
        clean_rows = sub_group[
            (sub_group['RandomProperty'] == 0) & (sub_group['RandomSuffix'] == 0)
        ]
        valid_budget_rows = clean_rows[clean_rows['total_budget'] > 0]['total_budget']
        if not valid_budget_rows.empty:
            curve_nodes.append({
                "itemlevel": int(ilvl),
                "avg_budget": float(valid_budget_rows.mean())
            })
    if curve_nodes:
        global_budget_curves[(int(inv_type), int(qual))] = sorted(curve_nodes, key=lambda x: x['itemlevel'])

# Step 2B: Build Micro Structural Density Profiles
print(" -> Compiling Subclass Density Profile Tables...")
lookup_database = {}
for (cls, subcls, inv_type, qual), group in df.groupby(['class', 'subclass', 'InventoryType', 'Quality']):
    ilvl_sheet = []
    group_valid_sell = group[group['SellPrice'] > 0]['SellPrice']
    if not group_valid_sell.empty:
        group_avg_sell = float(group_valid_sell.mean())
    else:
        # Fall back to matching class & subclass across all qualities/slots
        subclass_valid_sell = df[(df['class'] == cls) & (df['subclass'] == subcls) & (df['SellPrice'] > 0)]['SellPrice']
        group_avg_sell = float(subclass_valid_sell.mean()) if not subclass_valid_sell.empty else 500.0 # 5 silver base fallback
    
    for ilvl, sub_group in group.groupby('itemlevel'):
        valid_dps_rows = sub_group[sub_group['dps'] > 0]['dps']
        avg_dps = float(valid_dps_rows.mean()) if not valid_dps_rows.empty else 0.0
        valid_armor_rows = sub_group[sub_group['armor'] > 0]['armor']
        avg_armor = float(valid_armor_rows.mean()) if not valid_armor_rows.empty else 0.0
        valid_sell_rows = sub_group[sub_group['SellPrice'] > 0]['SellPrice']
        avg_sell_price = float(valid_sell_rows.mean()) if not valid_sell_rows.empty else group_avg_sell
        profiles = []
        for idx, row in sub_group.iterrows():
            rp, rs, n_stats = int(row['RandomProperty']), int(row['RandomSuffix']), int(row['num_stats'])
            if rp != 0 or rs != 0:
                continue  # dynamic random stats aren't in item_template -- not a usable reference
            if row['total_budget'] > 0 and n_stats > 0:
                profiles.append({"num_stats": n_stats, "RandomProperty": 0, "RandomSuffix": 0})

        if not valid_dps_rows.empty or avg_armor > 0 or profiles:
            ilvl_sheet.append({
                "itemlevel": int(ilvl), "avg_dps": avg_dps, "avg_armor": avg_armor,
                "display_ids": sub_group['displayid'].dropna().astype(int).unique().tolist(),
                "stat_profiles": profiles, "avg_sell_price": avg_sell_price
            })
    ilvl_sheet = sorted(ilvl_sheet, key=lambda x: x['itemlevel'])
    lookup_database[(int(cls), int(subcls), int(inv_type), int(qual))] = ilvl_sheet

# --- Build per-slot stat profiles directly from real item data, for any ---
# --- (class, subclass, InventoryType, Quality) combo the main pass above ---
# --- left missing or empty (e.g. Cloaks with no stats, or sparsely-populated ---
# --- Bow quality tiers).                                                    ---
def build_slot_fallback(where_clause, label, is_weapon=False):
    """
    Pulls items directly from item_template matching `where_clause` and fills in
    any lookup_database[(class, subclass, InventoryType, Quality)] entry that's
    currently missing or empty.

    NOTE: we check `lookup_database.get(target_key)` (truthy on a non-empty list)
    rather than `target_key in lookup_database`. The main pass above always
    inserts a key for every (class, subclass, InventoryType, Quality) combo it
    sees -- even when that combo's ilvl_sheet ends up empty -- so a plain
    "in lookup_database" check is always True and this fallback would never
    actually run. This was the bug that silently broke Cloak generation.

    is_weapon=True computes avg_dps from dmg_min1/dmg_max1/delay instead of
    avg_armor (use this for ranged weapons like Bows; leave False for armor
    slots like Cloaks).
    """
    print(f" -> Building {label} stat profiles from actual item data...")

    conn2 = mysql.connector.connect(**db_config)
    slot_query = f"""
        SELECT entry, name, itemlevel, Quality, class, subclass, InventoryType, displayid, delay,
               dmg_min1, dmg_max1, armor, Material, sheath, SellPrice,
               stat_type1, stat_value1, stat_type2, stat_value2, stat_type3, stat_value3, stat_type4, stat_value4,
               RandomProperty, RandomSuffix
        FROM item_template
        WHERE itemlevel BETWEEN 10 AND 284
          AND {where_clause};
    """
    slot_df = pd.read_sql(slot_query, conn2)
    conn2.close()

    print(f"   Found {len(slot_df)} {label} templates. Building {label} lookup entries...")

    slot_df['total_budget'] = slot_df['stat_value1'] + slot_df['stat_value2'] + slot_df['stat_value3'] + slot_df['stat_value4']
    slot_df['num_stats'] = slot_df.apply(count_active_stats, axis=1)

    slot_df['dps'] = 0.0
    if is_weapon:
        w_mask = slot_df['delay'] > 0
        slot_df.loc[w_mask, 'dps'] = ((slot_df.loc[w_mask, 'dmg_min1'] + slot_df.loc[w_mask, 'dmg_max1']) / 2) / (slot_df.loc[w_mask, 'delay'] / 1000.0)

    added = 0
    for (cls, subcls, inv_type, qual), group in slot_df.groupby(['class', 'subclass', 'InventoryType', 'Quality']):
        target_key = (int(cls), int(subcls), int(inv_type), int(qual))
        if lookup_database.get(target_key):
            continue  # Already populated with real, non-empty data; don't overwrite

        ilvl_sheet = []
        group_valid_sell = group[group['SellPrice'] > 0]['SellPrice']
        group_avg_sell = float(group_valid_sell.mean()) if not group_valid_sell.empty else 500.0

        for ilvl, sub_group in group.groupby('itemlevel'):
            valid_dps_rows = sub_group[sub_group['dps'] > 0]['dps']
            avg_dps = float(valid_dps_rows.mean()) if not valid_dps_rows.empty else 0.0
            valid_armor_rows = sub_group[sub_group['armor'] > 0]['armor']
            avg_armor = float(valid_armor_rows.mean()) if not valid_armor_rows.empty else 0.0
            valid_sell_rows = sub_group[sub_group['SellPrice'] > 0]['SellPrice']
            avg_sell_price = float(valid_sell_rows.mean()) if not valid_sell_rows.empty else group_avg_sell

            profiles = []
            for idx, row in sub_group.iterrows():
                rp, rs, n_stats = int(row['RandomProperty']), int(row['RandomSuffix']), int(row['num_stats'])
                if rp != 0 or rs != 0:
                    continue  # dynamic random stats aren't in item_template -- not a usable reference
                if row['total_budget'] > 0 and n_stats > 0:
                    profiles.append({"num_stats": n_stats, "RandomProperty": 0, "RandomSuffix": 0})

            if profiles or avg_armor > 0 or avg_dps > 0:
                ilvl_sheet.append({
                    "itemlevel": int(ilvl), "avg_dps": avg_dps, "avg_armor": avg_armor,
                    "display_ids": sub_group['displayid'].dropna().astype(int).unique().tolist(),
                    "stat_profiles": profiles, "avg_sell_price": avg_sell_price
                })

        if ilvl_sheet:
            lookup_database[target_key] = sorted(ilvl_sheet, key=lambda x: x['itemlevel'])
            added += 1
            print(f"    [{label}] Added cls={cls}, subcls={subcls}, inv={inv_type}, qual={qual} ({len(ilvl_sheet)} ilvl entries)")

    print(f"   {label}: {added} (class, subclass, slot, quality) combination(s) filled in.")

# Cloak / Back slot (InventoryType 16)
build_slot_fallback("InventoryType = 16", "Cloak", is_weapon=False)

# Bow (class 2, subclass 2) -- ranged weapon, computed via dps instead of armor
build_slot_fallback("class = 2 AND subclass = 2", "Bow", is_weapon=True)

print("Step 3: Compiling Structural Naming Dictionaries...")

ADJECTIVE_WHITELIST = [
    # Combat / Aggressive
    "Furious", "Brutal", "Searing", "Sacrificial", "Boundless", "Fighting", 
    "Savage", "Vicious", "Deadly", "Mighty", "Fierce", "Piercing", "Crushing",
    
    # Durable / Sturdy
    "Reinforced", "Ancient", "Tempered", "Hardened", "Stalwart", "Indestructible",
    "Bulwark", "Iron-bound", "Heavy", "Jagged", "Solid",
    
    # Magical / Arcane
    "Mystic", "Arcane", "Ethereal", "Runed", "Enchanted", "Astral", 
    "Spectral", "Void", "Primal", "Crystalline",
    
    # Elemental / Nature
    "Molten", "Frozen", "Storm-forged", "Blazing", "Frost", "Thunder", 
    "Tidal", "Verdant", "Wild", "Volcanic", "Gale",
    
    # Dark / Ominous
    "Dread", "Blighted", "Cursed", "Wicked", "Forsaken", "Sinister", 
    "Grim", "Dire", "Haunted", "Shadowed", "Grave",
    
    # Noble / Radiant
    "Divine", "Hallowed", "Sacred", "Exalted", "Glorious", "Sovereign", 
    "Imperial", "Royal", "Noble", "Radiant", "Valiant", "Heroic"
]
GENITIVE_WHITELIST = [
    # --- Warcraft Alliance Icons ---
    "Arthas''s", "Uther''s", "Varian''s", "Anduin''s", "Jaina''s", "Genn''s", 
    "Magni''s", "Muradin''s", "Malfurion''s", "Tyrande''s", "Turalyon''s", 
    "Alleria''s", "Khadgar''s", "Medivh''s",

    # --- Warcraft Horde Icons ---
    "Thrall''s", "Garrosh''s", "Sylvanas''s", "Vol''jin''s", "Cairne''s", 
    "Baine''s", "Grommash''s", "Rexxar''s", "Saurfang''s", "Rokhan''s", 
    "Gazlowe''s", "Gul''dan''s",

    # --- Warcraft Villains & Cosmic ---
    "Illidan''s", "Ner''zhul''s", "Kel''Thuzad''s", "Anub''arak''s", "Ragnaros''s", 
    "Deathwing''s", "Onyxia''s", "Kael''thas''s", "Kil''jaeden''s", "Archimonde''s", 
    "Lich''s", "Dreadlord''s", "Valkyr''s",

    # --- Fantasy Archetypes & Titles ---
    "King''s", "Queen''s", "Warchief''s", "Warlord''s", "Archmage''s", 
    "Highlord''s", "Crusader''s", "Sentinel''s", "Dragon''s", "Wyrm''s", 
    "Titan''s", "Demon''s", "Giant''s", "Warden''s", "Guardian''s", 
    "Assassin''s", "Captain''s", "Paladin''s", "Shaman''s", "Druid''s", 
    "Sorcerer''s", "Hero''s", "Outlaw''s", "Hunter''s", "Seeker''s", 
    "Vindicator''s", "Exarch''s", "Elder''s", "Ancient''s", "Raven''s"
]


MATERIAL_WHITELIST = [
    # --- Classic/Basic Metals ---
    "Copper", "Bronze", "Iron", "Steel", "Tin", "Lead", 
    "Silver", "Gold", "Brass",
    
    # --- Advanced/Legendary Metals ---
    "Mithril", "Truesilver", "Arcanite", "Thorium", 
    "Adamantite", "Feliron", "Khorium", "Eternium", 
    
    # --- Exotic/Northern/High-End ---
    "Cobalt", "Saronite", "Titanium", "Elementium", 
    "Obsidian", "Shadowsteel", "Spirit-iron", "Void-forged",
    
    # --- Other Crafting Materials ---
    "Bone", "Wood", "Oak", "Ash", "Ivory", "Marble", "Granite"
]
PROPERTY_WHITELIST = [
    # --- Ominous & Dark ---
    "of Grievance", "of Massacre", "of the Scourge", "of Crimson Agony", 
    "of Ebon Depths", "of the Void", "of Lost Souls", "of the Grave", 
    "of Eternal Night", "of Ruin", "of Despair", "of Sinister Light",
    
    # --- Elemental & Nature ---
    "of the Frozen Wastes", "of Eternal Storms", "of the Molten Core", 
    "of the Tides", "of the Wild", "of Blazing Embers", "of the North",
    "of the Sunken Depths", "of the Hurricane",
    
    # --- Lore & Faction Inspired ---
    "of the Kirin Tor", "of the Silver Hand", "of the Ebon Blade", 
    "of the Cenarion Circle", "of the Dragonflight", "of the Horde", 
    "of the Alliance", "of the Burning Legion", "of the Argent Crusade",
    
    # --- Abstract & Mystical ---
    "of Ancient Echoes", "of Forbidden Secrets", "of Unspoken Truths", 
    "of Fallen Kings", "of Broken Promises", "of Sovereign Might", 
    "of Infinite Wisdom", "of the Stars", "of the Moon", "of the Sun",
    "of Timeless Travel", "of the Seeker", "of Hidden Paths",
    
    # --- Action & Impact ---
    "of the Victor", "of the Fallen", "of the Challenger", 
    "of the Protector", "of the Warlord", "of the Warden", 
    "of the Exile", "of the Renegade"
]
WEAPON_NOUNS = {
    # --- 0: One-Handed Axes ---
    0: [
        "Axe", "Cleaver", "Hacker", "Handaxe", "Chopper", "Edge", "Sickle", "Slicer",
        "Hatchet", "Reaver", "Splitter", "Tomahawk", "Render", "Butcher", "Ripper", 
        "Mutilator", "Beheader", "Crescent", "Francisca", "Skinner", "Gouger", 
        "Hedge-Axe", "Warmonger", "Huntsman", "Bone-Chopper", "Blood-Axe", "Ravager",
        "Incisor", "Viper-Tooth", "Flayer", "Skin-Peeler", "Carver"
    ],
    
    # --- 1: Two-Handed Axes ---
    1: [
        "Greataxe", "Battleaxe", "Decapitator", "Cleaver", "Reaper", "Doom-Axe", "Edge", "Ravager", "Sunderer",
        "Labrys", "Guillotine", "Executioner", "Earth-Cleaver", "World-Carver", "Star-Sunderer", 
        "Broadaxe", "Behemoth", "Dread-Axe", "Bone-Grinder", "Spine-Splitter", "Crescent-Axe", 
        "Harbinger", "Mountain-Cleaver", "Gorgon-Edge", "Titan-Axe", "Skull-Cleaver", 
        "Doom-Bringer", "Revenant", "Hell-Axe", "Warmaster", "Annihilator", "World-Breaker"
    ],
    
    # --- 2: Bows ---
    2: [
        "Bow", "Longbow", "Composite Bow", "Shortbow", "Recurve Bow", "Stinger", "Greatbow",
        "Reflex Bow", "Warbow", "Star-Bow", "Wind-Bow", "Piercer", "Rain-Maker", "Arrow-Launcher", 
        "Sky-Piercer", "Swift-Bow", "Storm-String", "Whisper-Bow", "Gale-Bow", "Hunter-Bow", 
        "Viper", "Eagle-Strike", "Heart-Piercer", "Shadow-String", "Tendon-Snap", "Stalker-Bow", 
        "Flurry-Bow", "Needler", "Striker", "Night-Bow", "Sinew-Snap"
    ],
    
    # --- 3: Guns ---
    3: [
        "Rifle", "Musket", "Shotgun", "Blunderbuss", "Handcannon", "Carbine", "Repeater", "Fusil",
        "Firelock", "Matchlock", "Flintlock", "Arquebus", "Culverin", "Cannon", "Thunderbuss", 
        "Volleygun", "Lead-Spitter", "Boomstick", "Iron-Tube", "Pistol", "Arbalest-Gun", 
        "Fire-Spitter", "Powder-Keg", "Blast-Rifle", "Storm-Rifle", "Siege-Musket", 
        "Hand-Mortar", "Gatling", "Spitfire", "Flint-Rifle", "Thunder-Pipe"
    ],
    
    # --- 4: One-Handed Maces ---
    4: [
        "Mace", "Gavel", "Club", "Hammer", "Cudgel", "Bludgeon", "Scepter", "Truncheon",
        "Flail", "Morgenstern", "Morningstar", "Warmace", "Skull-Crusher", "War-Club", 
        "Mallet", "Knocker", "Pummel", "Bludgeoner", "Sceptre", "Sledge", "Bone-Cracker", 
        "Crest-Mace", "Anvil-Hand", "Mauler", "Spike-Gavel", "Smacker", "Thumper",
        "Tenderizer", "Smasher", "Cracker", "Weight"
    ],
    
    # --- 5: Two-Handed Maces ---
    5: [
        "Greatmace", "Maul", "Warhammer", "Pummel", "Scepter", "Pounder", "World-Breaker",
        "Great-Maul", "Earth-Shaker", "Skull-Smasher", "Stone-Breaker", "Dread-Maul", 
        "Anvil-Hammer", "Juggernaut", "Titan-Maul", "Demolisher", "Battering-Ram", 
        "World-Ender", "Bone-Smasher", "Calamity", "Iron-Maul", "Goliath", "Megalith", 
        "Cataclysm", "Obliterator", "Pillar-Hammer", "Mountain-Smasher", "Titan-Gavel"
    ],
    
    # --- 6: Polearms ---
    6: [
        "Polearm", "Halberd", "Scythe", "Spear", "Pike", "Glaive", "Lance",
        "Bardiche", "Billhook", "Naginata", "Partisan", "Guisarme", "Lochaber Axe", 
        "Voulge", "Trident", "Spetum", "Ranseur", "Harpoon", "Brandestock", "Corseques", 
        "Sovnya", "Falx", "Glaive-Gisarme", "Pike-Staff", "Sky-Lighter", "Spire-Spear", 
        "Wyrm-Stalker", "Stinger-Pole", "Reap-Blade", "Death-Scythe"
    ],
    
    # --- 7: One-Handed Swords ---
    7: [
        "Sword", "Blade", "Longsword", "Saber", "Rapier", "Scimitar", "Slicer", "Quickblade",
        "Cutlass", "Falchion", "Gladius", "Shortsword", "Shamshir", "Spatha", "Estoc", 
        "Foil", "Wakizashi", "Carver", "Edge", "Broadsword", "Scian", "Brand", "Spitfire", 
        "Skewer", "Razor", "Stitcher", "Spine-Seeker", "Talwar", "Flesh-Render", 
        "Dirk-Sword", "Swift-Blade"
    ],
    
    # --- 8: Two-Handed Swords ---
    8: [
        "Greatsword", "Claymore", "Runeblade", "Broadsword", "Bastard Sword", "Edge", "Warblade",
        "Flamberge", "Zweihander", "Executioner's Sword", "Dread-Blade", "Sun-Blade", 
        "Doom-Slayer", "Void-Shearer", "Grand-Blade", "Avenger", "Colossus", 
        "Warmonger-Blade", "Souldrinker", "Lifedrinker", "Ender", "Dark-Blade", 
        "Gargoyle-Edge", "Titan-Blade", "Doomsday", "World-Carver"
    ],
    
    # --- 10: Staves ---
    10: [
        "Staff", "Spire", "Pillar", "Greatstaff", "Stave",
        "Quarterstaff", "Crook", "Rod", "Scepter", "Walking-Stick", "Arch-Stave", 
        "Conduit", "Focus", "Channeler", "Brazier", "Cane", "Gnarled-Staff", 
        "Grand-Staff", "Beacon", "Spindle", "Oracle-Staff", "Sage-Stave", "Totem",
        "Light-Wand", "World-Pillar", "Elder-Staff", "Walking-Stave"
    ],
    
    # --- 13: Fist Weapons ---
    13: [
        "Claw", "Talons", "Katar", "Fist", "Blades",
        "Tekko", "Cestus", "Bagh Nakh", "Knuckles", "Puncher", "Render", "Shredder", 
        "Bladed Gauntlet", "Spiked Fist", "Grip", "Pugilist", "Mauler-Grip", 
        "Tiger-Claw", "Razor-Fist", "Scrape", "Ripper-Fist", "Viper-Bite", "Talons-Grip"
    ],
    
    # --- 15: Daggers ---
    15: [
        "Dagger", "Dirk", "Kris", "Shanker", "Stiletto", "Blade", "Carver", "Spike",
        "Baselard", "Rondel", "Pugio", "Main-Gauche", "Poignard", "Bodkin", "Tooth", 
        "Fang", "Shard", "Splinter", "Needle", "Bodkin-Blade", "Skewer", "Stitcher", 
        "Venom-Tooth", "Razor-Shard", "Spit", "Letter-Opener", "Thorn", "Incisor", 
        "Sliver", "Quill-Blade"
    ],
    
    # --- 16: Thrown ---
    16: [
        "Darts", "Throwing Axe", "Glaive", "Knives", "Spikes",
        "Shuriken", "Kunai", "Throwing Knife", "Boomerang", "Javelin", "Dart", 
        "Throwing Star", "Francisca", "Harpoon", "Quill", "Spitfire-Dart", 
        "Plumbata", "Chakram", "Bolos", "Sling-Stone"
    ],
    
    # --- 18: Crossbows ---
    18: [
        "Crossbow", "Arbalest", "Repeater",
        "Heavy Crossbow", "Light Crossbow", "Ballesta", "Gastraphetes", 
        "Bolt-Thrower", "Siege-Crossbow", "Quick-Crossbow", "Wind-Crossbow", 
        "Arbalest-Bow", "Steel-String", "Snapper", "Quarrel-Launcher"
    ],
    
    # --- 19: Wands ---
    19: [
        "Wand", "Baton", "Rod", "Scepter",
        "Twig", "Pointer", "Focus-Wand", "Core", "Ignite-Stick", "Sparker", 
        "Channeling Wand", "Prism", "Sceptre", "Dowser", "Conductor", 
        "Spindle-Wand", "Beam-Stick", "Emberspire", "Frost-Shard", "Crystalline-Wand"
    ]
}
ARMOR_NOUNS = {
    # === 1: HEAD GEAR ===
    1: {
        # Cloth
        1: [
            "Hood", "Cowl", "Hat", "Cap", "Circlet", "Crown", "Tiara", "Diadem", "Headdress", 
            "Veil", "Coif", "Gaze", "Halo", "Cover", "Mask", "Turban", "Feather-Hat", "Keffiyeh",
            "Goggles", "Crown-Circlet", "Monocle", "Blindfold", "Amice-Hood", "Visage"
        ], 
        # Leather
        2: [
            "Helm", "Cap", "Headguard", "Mask", "Hood", "Cowl", "Eyepatch", "Bandana", "Visor", 
            "Headband", "Cover", "Crown", "Headdress", "Faceguard", "Goggles", "Stalker-Mask", 
            "Wolf-Head", "Hide-Cap", "Facemask", "Trophy-Head", "Slayer-Helm", "Guise"
        ], 
        # Mail
        3: [
            "Helm", "Coif", "Headpiece", "Headguard", "Faceguard", "Coif-Helm", "Mask", "Crown", 
            "Visor", "Bascinet", "Casque", "Greathelm", "Camail", "Barbuta", "Sallet-Mail", 
            "Chain-Helm", "Crest-Helm", "Ring-Coif", "Iron-Mask", "War-Helm", "Champion-Helm"
        ], 
        # Plate
        4: [
            "Helm", "Helmet", "Faceguard", "Crown", "Greathelm", "Visor", "Armet", "Sallet", 
            "Bascinet", "Casque", "Crest", "Barbute", "Morion", "Headguard", "Burgonet", 
            "Close-Helm", "Iron-Crown", "Vanguard-Helm", "Siege-Helm", "Juggernaut-Helm", 
            "Bulwark-Face", "Dread-Helm", "Doom-Visor", "War-Visard"
        ]
    },
    
    # === 2: NECK ACCESSORIES ===
    2: {
        0: [
            "Amulet", "Choker", "Necklace", "Pendant", "Chain", "Collar", "Talisman", "Gorget", 
            "Torc", "Locket", "Scarab", "Medallion", "Brooch", "Strand", "Cameo", "Beads", 
            "Charm", "Rosary", "Periapt", "Neck-Ribbon", "Grip-Choker", "Heart-Pendant",
            "Signet-Necklace", "Star-Amulet", "Relic-Chain"
        ]
    },
    
    # === 3: SHOULDERS ===
    3: {
        # Cloth
        1: [
            "Amice", "Mantle", "Shoulderpads", "Pads", "Epaulets", "Shawl", "Wrap", "Capelet", 
            "Cowl-Pads", "Pauldrons", "Monk-Shoulders", "Shoulder-Shroud", "Brooch-Shoulders",
            "Wings", "Arch-Epaulets", "Tier-Mantle"
        ], 
        # Leather
        2: [
            "Mantle", "Shoulderpads", "Spaulders", "Pads", "Epaulets", "Shoulderguards", 
            "Hide-Spaulders", "Pauldrons", "Wraps", "Guards", "Bark-Spaulders", "Stalker-Pads",
            "Monk-Mantle", "Rogue-Shoulders", "Spikes", "Skin-Mantle"
        ], 
        # Mail
        3: [
            "Pauldrons", "Shoulders", "Spaulders", "Shoulderguards", "Epaulets", "Plates", 
            "Mantle", "Guards", "Chain-Shoulders", "Ring-Spaulders", "Crest-Pauldrons", 
            "Scale-Shoulders", "Iron-Mantle", "Storm-Shoulders", "Champion-Spaulders"
        ], 
        # Plate
        4: [
            "Pauldrons", "Shoulders", "Spaulders", "Plated Spaulders", "Shoulderguards", 
            "Monoliths", "Wardens", "Epaulets", "Mantlets", "Guards", "Plates", "Iron-Shoulders",
            "Citadel-Spaulders", "Dread-Pauldrons", "Gargoyle-Plates", "Titan-Shoulders", 
            "Buldwar-Spaulders", "Siege-Pauldrons", "Juggernaut-Shoulders"
        ]
    },
    
    # === 16: BACK (CLOAKS) ===
    16: {
        0: [
            "Cloak", "Cape", "Drape", "Shroud", "Shawl", "Greatcloak", "Mantle", "Wrap", 
            "Canopy", "Sail", "Banner", "Pennant", "Scarf", "Pelisse", "Furl", "Blanket", 
            "Skin-Cloak", "Wind-Drape", "Shadow-Shroud", "Glory-Cape"
        ]
    },
    
    # === 5: CHEST PIECES ===
    5: {
        # Cloth
        1: [
            "Robe", "Vestments", "Tunic", "Garments", "Gown", "Vest", "Blouse", "Shirt", 
            "Raiment", "Shroud", "Wrap", "Habit", "Tabard", "Jerkin", "Kirtle", "Doublet", 
            "Surcoat", "Soutane", "Cassock", "Chasuble", "Cloth-Armor"
        ], 
        # Leather
        2: [
            "Tunic", "Vest", "Chestguard", "Jerkin", "Harness", "Jacket", "Leather-Coat", 
            "Raiment", "Garb", "Vestments", "Breastplate", "Wrap", "Brigandine", "Coat", 
            "Cuirass", "Hide-Armor", "Chestpiece", "Stalker-Vest", "Trapper-Coat"
        ], 
        # Mail
        3: [
            "Hauberk", "Chainshirt", "Chestguard", "Vest", "Cuirass", "Tunica", "Ring-Mail", 
            "Scale-Coat", "Jerkin", "Harness", "Chainmail", "Byrnie", "Coat-of-Mail", 
            "Lorica", "Iron-Hauberk", "War-Shirt", "Slayer-Hauberk", "Champion-Mail"
        ], 
        # Plate
        4: [
            "Breastplate", "Chestplate", "Cuirass", "Carapace", "Platemail", "Chestguard", 
            "Bulwark", "Aegis-Plate", "Harness", "Brigandine", "Plated-Harness", "Chestpiece",
            "Citadel-Plate", "Dread-Plate", "Juggernaut-Plates", "Titan-Breastplate", 
            "Vanguard-Plate", "Doom-Platemail", "Centurion-Armor"
        ]
    },
    
    # === 20: ROBES (FULL-BODY LORE WRAPS) ===
    20: {
        1: [
            "Robe", "Vestments", "Gown", "Raiment", "Habit", "Shroud", "Garments", 
            "Cassock", "Attire", "Kirtle-Robe", "Chasuble", "Grand-Robe", "Arch-Vestments", 
            "High-Robe", "Sorcerer-Gown", "Acolyte-Shroud", "Oracle-Robe"
        ]
    },
    
    # === 9: WRISTS (BRACERS) ===
    9: {
        0: [
            "Bracers", "Bindings", "Armguards", "Cuffs", "Bands", "Wristbands", "Vambraces", 
            "Shackles", "Wristguards", "Manacles", "Wraps", "Armbands", "Bracelets", 
            "Wrist-Plates", "Chain-Links", "Leather-Wraps", "Runed-Bracers", "Grips", 
            "Anklets-Wrist", "Forearm-Guards"
        ]
    },
    
    # === 10: HANDS ===
    10: {
        # Cloth
        1: [
            "Gloves", "Handwraps", "Mittens", "Handguards", "Wraps", "Mitts", "Touch-Gloves", 
            "Spell-Weaves", "Silk-Gloves"
        ], 
        # Leather
        2: [
            "Gloves", "Handguards", "Grips", "Handwraps", "Mitts", "Clutches", "Gauntlets", 
            "Stalker-Gloves", "Hide-Grips", "Fingerless-Gloves", "Fist-Wraps"
        ], 
        # Mail
        3: [
            "Gauntlets", "Handguards", "Gloves", "Grips", "Chain-Gloves", "Scale-Guards", 
            "Ring-Gauntlets", "Iron-Grips", "War-Gloves"
        ], 
        # Plate
        4: [
            "Gauntlets", "Handguards", "Gloves", "Fists", "Iron-Grips", "Crushers", 
            "Plate-Gloves", "Vanguard-Gauntlets", "Heavy-Fists", "Doom-Gauntlets", 
            "Slam-Grips", "Titan-Gauntlets", "Citadel-Gauntlets"
        ]
    },
    
    # === 6: WAIST (BELTS) ===
    6: {
        0: [
            "Girdle", "Belt", "Cinch", "Cord", "Sash", "Clasp", "Buckle", "Strap", 
            "Cummerbund", "Waistband", "Chain-Belt", "Girth", "Waistguard", "Leather-Strap", 
            "Links", "Waist-Rope", "Heavy-Belt", "Buckled-Girdle", "Runed-Sash"
        ]
    },
    
    # === 7: LEGS ===
    7: {
        # Cloth
        1: [
            "Trousers", "Leggings", "Pants", "Breeches", "Skirt", "Kilt", "Pantaloons", 
            "Slacks", "Wraps", "Drawers", "Loincloth", "Saron", "Hakama", "Cloth-Legs"
        ], 
        # Leather
        2: [
            "Legguards", "Leggings", "Breeches", "Pants", "Trousers", "Chaps", "Shorts", 
            "Skirt", "Kilt", "Hide-Legs", "Padded-Pants", "Trapper-Legs", "Stalker-Guards"
        ], 
        # Mail
        3: [
            "Legguards", "Leggings", "Kilt", "Chain-Legs", "Skirt", "Hauberk-Legs", 
            "Chausses", "Breeches", "Ring-Leggings", "Scale-Legguards", "Iron-Kilt", 
            "War-Legguards"
        ], 
        # Plate
        4: [
            "Legplates", "Greaves", "Legguards", "Cuisses", "Tassets", "Plate-Pants", 
            "Guards", "Chausses", "Schynbalds", "Citadel-Legplates", "Dread-Plates", 
            "Titan-Greaves", "Bulwark-Legs", "Juggernaut-Plates", "Vanguard-Greaves"
        ]
    },
    
    # === 8: FEET (BOOTS) ===
    8: {
        # Cloth
        1: [
            "Boots", "Slippers", "Sandals", "Footpads", "Shoes", "Footwraps", "Soles", 
            "Treads", "Socks", "Pumps", "Soft-Boots"
        ], 
        # Leather
        2: [
            "Boots", "Footguards", "Shoes", "Moccasins", "Treads", "Soles", "Footpads", 
            "Walkers", "Striders", "Stalker-Boots", "Hide-Walkers", "Muck-Boots"
        ], 
        # Mail
        3: [
            "Boots", "Greaves", "Footguards", "Sabatons", "Striders", "Treads", "Walkers", 
            "Chain-Boots", "Ring-Greaves", "Iron-Boots", "Scale-Boots"
        ], 
        # Plate
        4: [
            "Boots", "Sabatons", "Greaves", "Footguards", "Iron-Boots", "Soles", "Spur-Boots", 
            "Citadel-Boots", "Dread-Sabatons", "Juggernaut-Greaves", "Vanguard-Boots", 
            "Titan-Sabatons", "Heavy-Treads"
        ]
    },
    
    # === 11: FINGERS (RINGS) ===
    11: {
        0: [
            "Band", "Ring", "Signet", "Loop", "Seal", "Circle", "Promise", "Wedding-Band", 
            "Jewel", "Knot-Ring", "Coil", "Spiral", "Claw-Ring", "Stone-Band", "Insignia-Ring"
        ]
    },
    
    # === 14: SHIELDS ===
    14: {
        0: [
            "Shield", "Bulwark", "Barrier", "Aegis", "Buckler", "Crest", "Kite-Shield", 
            "Pavise", "Targe", "Round-Shield", "Greatshield", "Wall", "Ward", "Safeguard", 
            "Protector", "Blocker", "Heater-Shield", "Barricade", "Tower-Shield", "Carapace-Shield", 
            "Gargoyle-Wing", "Anvil-Shield", "Bastion", "Gladiator-Shield"
        ]
    },
    
    # === 23: HELD IN HAND (OFF-HANDS) ===
    23: {
        0: [
            "Tome", "Orb", "Grimoire", "Scroll", "Star", "Compendium", "Book", "Ledger", 
            "Eye", "Icon", "Idol", "Relic", "Talisman", "Scepter", "Branch", "Totem", 
            "Beacon", "Fragment", "Catalyst", "Manual", "Journal", "Prism", "Battery", 
            "Globe", "Chalice", "Urn", "Fetish", "Lamp", "Censer", "Glow-Stone"
        ]
    }
}
name_database = {}
for (cls, subcls), group in df.groupby(['class', 'subclass']):
    nouns = set()
    adjectives = set()
    materials = set()
    display_refs = []

    for _, row in group.iterrows():
        # A. Collect Display IDs
        display_refs.append({
            "id": int(row['displayid']),
            "lvl": int(row['itemlevel']),
            "q": int(row['Quality']),
            "source_id": int(row['entry']),
            "InventoryType": int(row['InventoryType'])
        })
        
        # B. Clean Name for Nouns/Adjectives
        cleaned = row['name'].replace("'", "").replace("-", " ")
        parts = cleaned.split()
        
        if len(parts) >= 1:
            last_word = parts[-1]
            if last_word not in ADJECTIVE_WHITELIST and last_word not in MATERIAL_WHITELIST and last_word not in GENITIVE_WHITELIST:
                nouns.add(last_word)
        
        for word in parts:
            if word in ADJECTIVE_WHITELIST: adjectives.add(word)
            if word in MATERIAL_WHITELIST: materials.add(word)

    # C. Compile Database entry
    name_database[(int(cls), int(subcls))] = {
        "adjectives": list(adjectives) if adjectives else ["Reinforced"],
        "genitives": GENITIVE_WHITELIST,
        "materials": list(materials) if materials else ["Iron"],
        "nouns": list(nouns) if nouns else ["Blade"],
        "properties": PROPERTY_WHITELIST,
        "displays": display_refs
    }

print("Naming engine compiled.")

material_library = {}

# --- NEW: Calculate Blizzlike Weapon Subclass Delay Averages ---
print(" -> Analyzing global weapon subclass speed baselines...")
# Filter for weapons with valid attack speeds
weapons_df = df[(df['class'] == 2) & (df['delay'] > 0)]
# Group by subclass and convert the float averages to integers
subclass_delays = weapons_df.groupby('subclass')['delay'].mean().round().astype(int).to_dict()

# Save this library alongside your other brain data
joblib.dump(material_library, 'material_library.joblib')



for (c, sc, q), group in df.groupby(['class', 'subclass', 'Quality']):
    # Get unique pairs of material and sheath
    valid_pairs = group[['Material', 'sheath']].drop_duplicates().to_dict('records')
    material_library[(c, sc, q)] = valid_pairs

# Save this library alongside your other brain data
joblib.dump(material_library, 'material_library.joblib')
master_brain = {
    "lookup_database": lookup_database, 
    "global_budget_curves": global_budget_curves,
    "archetype_profiles": archetype_profiles,
    "name_database": name_database,
    "subclass_delays": subclass_delays,
    "weapon_nouns": WEAPON_NOUNS,     
    "armor_nouns": ARMOR_NOUNS        
}
joblib.dump(master_brain, "blizzlike_master_brain.pkl")
print("🎉 Success! Cohesive Archetype Matrix successfully compiled and exported.")
