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
           dmg_min1, dmg_max1, armor, Material, sheath,
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
        valid_budget_rows = sub_group[sub_group['total_budget'] > 0]['total_budget']
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
    for ilvl, sub_group in group.groupby('itemlevel'):
        valid_dps_rows = sub_group[sub_group['dps'] > 0]['dps']
        avg_dps = float(valid_dps_rows.mean()) if not valid_dps_rows.empty else 0.0
        valid_armor_rows = sub_group[sub_group['armor'] > 0]['armor']
        avg_armor = float(valid_armor_rows.mean()) if not valid_armor_rows.empty else 0.0
        
        profiles = []
        for idx, row in sub_group.iterrows():
            rp, rs, n_stats = int(row['RandomProperty']), int(row['RandomSuffix']), int(row['num_stats'])
            if rp != 0 or rs != 0:
                profiles.append({"num_stats": 0, "RandomProperty": rp, "RandomSuffix": rs})
            elif row['total_budget'] > 0 and n_stats > 0:
                profiles.append({"num_stats": n_stats, "RandomProperty": 0, "RandomSuffix": 0})

        if not valid_dps_rows.empty or profiles:
            ilvl_sheet.append({
                "itemlevel": int(ilvl), "avg_dps": avg_dps, "avg_armor": avg_armor,
                "display_ids": sub_group['displayid'].dropna().astype(int).unique().tolist(),
                "stat_profiles": profiles
            })
    ilvl_sheet = sorted(ilvl_sheet, key=lambda x: x['itemlevel'])
    lookup_database[(int(cls), int(subcls), int(inv_type), int(qual))] = ilvl_sheet

# --- FIX: Imputation Layer (Filling missing categories) ---
print(" -> Running Imputation Layer (Borrowing Ring stats for Cloaks)...")
# Map: Source InventoryType (11=Rings) -> Target InventoryType (16=Cloaks)
imputation_map = {11: 16}

for (cls, subcls, inv_type, qual), ilvl_sheet in list(lookup_database.items()):
    if inv_type in imputation_map:
        target_inv_type = imputation_map[inv_type]
        target_key = (cls, subcls, target_inv_type, qual)
        if target_key not in lookup_database:
            lookup_database[target_key] = ilvl_sheet
            print(f"    [Impute] Mapped InvType {target_inv_type} from {inv_type} (Qual: {qual})")

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
    "Arthas's", "Uther's", "Varian's", "Anduin's", "Jaina's", "Genn's", 
    "Magni's", "Muradin's", "Malfurion's", "Tyrande's", "Turalyon's", 
    "Alleria's", "Khadgar's", "Medivh's",

    # --- Warcraft Horde Icons ---
    "Thrall's", "Garrosh's", "Sylvanas's", "Vol'jin's", "Cairne's", 
    "Baine's", "Grommash's", "Rexxar's", "Saurfang's", "Rokhan's", 
    "Gazlowe's", "Gul'dan's",

    # --- Warcraft Villains & Cosmic ---
    "Illidan's", "Ner'zhul's", "Kel'Thuzad's", "Anub'arak's", "Ragnaros's", 
    "Deathwing's", "Onyxia's", "Kael'thas's", "Kil'jaeden's", "Archimonde's", 
    "Lich's", "Dreadlord's", "Valkyr's",

    # --- Fantasy Archetypes & Titles ---
    "King's", "Queen's", "Warchief's", "Warlord's", "Archmage's", 
    "Highlord's", "Crusader's", "Sentinel's", "Dragon's", "Wyrm's", 
    "Titan's", "Demon's", "Giant's", "Warden's", "Guardian's", 
    "Assassin's", "Captain's", "Paladin's", "Shaman's", "Druid's", 
    "Sorcerer's", "Hero's", "Outlaw's", "Hunter's", "Seeker's", 
    "Vindicator's", "Exarch's", "Elder's", "Ancient's", "Raven's"
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
    "name_database": name_database
}
joblib.dump(master_brain, "blizzlike_master_brain.pkl")
print("🎉 Success! Cohesive Archetype Matrix successfully compiled and exported.")
