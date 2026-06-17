import joblib
import random
import os
import warnings
import mysql.connector
import csv
material_library = joblib.load('material_library.joblib')
warnings.filterwarnings("ignore")

DB_CONFIG = {
    'user': 'acore', 'password': 'acore',
    'host': '127.0.0.1', 'database': 'acore_world', 'port': 3306
} 
try:
    conn = mysql.connector.connect(
        user='acore', password='acore', 
        host='127.0.0.1', database='acore_world', port=3306
    )
    cursor = conn.cursor()
    print("✅ Connected to acore_world database.")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    exit()
try:
    master = joblib.load("blizzlike_master_brain.pkl")
    lookup_database = master["lookup_database"]
    global_budget_curves = master["global_budget_curves"]
    archetype_profiles = master["archetype_profiles"]
    name_database = master["name_database"]
    subclass_delays = master.get("subclass_delays", {})
except Exception as e:
    print("❌ Critical Error: Model components failed to load. Run train_brain.py first.")
    exit()

STAT_NAMES = {
    0: ("Mana", "Primary/Resource"), 1: ("Health", "Primary/Resource"), 3: ("Agility", "Primary"),
    4: ("Strength", "Primary"), 5: ("Intellect", "Primary"), 6: ("Spirit", "Primary"), 7: ("Stamina", "Primary"),
    12: ("Defense Rating", "Secondary"), 13: ("Dodge Rating", "Secondary"), 14: ("Parry Rating", "Secondary"),
    15: ("Block Rating", "Secondary"), 16: ("Melee Hit Rating", "Secondary"), 17: ("Ranged Hit Rating", "Secondary"),
    18: ("Spell Hit Rating", "Secondary"), 19: ("Melee Crit Rating", "Secondary"), 20: ("Ranged Crit Rating", "Secondary"),
    21: ("Spell Crit Rating", "Secondary"), 28: ("Melee Haste Rating", "Secondary"), 30: ("Spell Haste Rating", "Secondary"),
    31: ("Hit Rating", "Secondary"), 32: ("Critical Strike Rating", "Secondary"), 35: ("Resilience", "Secondary"),
    36: ("Haste Rating", "Secondary"), 37: ("Expertise Rating", "Secondary"), 38: ("Attack Power", "Secondary"),
    43: ("Mana Regeneration (MP5)", "Secondary"), 44: ("Armor Penetration Rating", "Secondary"),
    45: ("Spell Power", "Secondary"), 48: ("Block Value", "Secondary")
}

# Updated master catalog with 1H Mace added (ID 22)
CATEGORIES = {
    # Weapons
    1: {"name": "Wand", "class": 2, "subclass": 19, "InventoryType": 26, "delay": 1800, "dmg_type1": 3},
    2: {"name": "One-Handed Sword", "class": 2, "subclass": 7, "InventoryType": 13, "delay": 2600, "dmg_type1": 0},
    3: {"name": "Two-Handed Sword", "class": 2, "subclass": 8, "InventoryType": 17, "delay": 3600, "dmg_type1": 0},
    4: {"name": "Dagger", "class": 2, "subclass": 15, "InventoryType": 13, "delay": 1800, "dmg_type1": 0},
    5: {"name": "Staff", "class": 2, "subclass": 10, "InventoryType": 17, "delay": 3200, "dmg_type1": 0},
    6: {"name": "Fist Weapon", "class": 2, "subclass": 13, "InventoryType": 13, "delay": 2600, "dmg_type1": 0},
    7: {"name": "One-Handed Axe", "class": 2, "subclass": 0, "InventoryType": 13, "delay": 2600, "dmg_type1": 0},
    8: {"name": "Two-Handed Mace", "class": 2, "subclass": 5, "InventoryType": 17, "delay": 3600, "dmg_type1": 0},
    9: {"name": "Polearm", "class": 2, "subclass": 6, "InventoryType": 17, "delay": 3500, "dmg_type1": 0},
    10: {"name": "Two-Handed Axe", "class": 2, "subclass": 1, "InventoryType": 17, "delay": 3600, "dmg_type1": 0},
    11: {"name": "Crossbow", "class": 2, "subclass": 18, "InventoryType": 26, "delay": 3000, "dmg_type1": 0},
    12: {"name": "Bow", "class": 2, "subclass": 2, "InventoryType": 26, "delay": 2800, "dmg_type1": 0},
    13: {"name": "Gun", "class": 2, "subclass": 3, "InventoryType": 26, "delay": 2800, "dmg_type1": 0},
    14: {"name": "Thrown Weapon", "class": 2, "subclass": 16, "InventoryType": 25, "delay": 2000, "dmg_type1": 0},
    15: {"name": "One-Handed Mace", "class": 2, "subclass": 4, "InventoryType": 13, "delay": 2600, "dmg_type1": 0},
    
    # Cloth (Subclass 1)
    16: {"name": "Cloth Helm", "class": 4, "subclass": 1, "InventoryType": 1, "delay": 0, "dmg_type1": 0},
    17: {"name": "Cloth Shoulders", "class": 4, "subclass": 1, "InventoryType": 3, "delay": 0, "dmg_type1": 0},
    18: {"name": "Cloth Chest", "class": 4, "subclass": 1, "InventoryType": 5, "delay": 0, "dmg_type1": 0},
    19: {"name": "Cloth Wrist", "class": 4, "subclass": 1, "InventoryType": 9, "delay": 0, "dmg_type1": 0},
    20: {"name": "Cloth Gloves", "class": 4, "subclass": 1, "InventoryType": 10, "delay": 0, "dmg_type1": 0},
    21: {"name": "Cloth Waist", "class": 4, "subclass": 1, "InventoryType": 6, "delay": 0, "dmg_type1": 0},
    22: {"name": "Cloth Legs", "class": 4, "subclass": 1, "InventoryType": 7, "delay": 0, "dmg_type1": 0},
    23: {"name": "Cloth Feet", "class": 4, "subclass": 1, "InventoryType": 8, "delay": 0, "dmg_type1": 0},
    
    # Leather (Subclass 2)
    24: {"name": "Leather Helm", "class": 4, "subclass": 2, "InventoryType": 1, "delay": 0, "dmg_type1": 0},
    25: {"name": "Leather Shoulders", "class": 4, "subclass": 2, "InventoryType": 3, "delay": 0, "dmg_type1": 0},
    26: {"name": "Leather Chest", "class": 4, "subclass": 2, "InventoryType": 5, "delay": 0, "dmg_type1": 0},
    27: {"name": "Leather Wrist", "class": 4, "subclass": 2, "InventoryType": 9, "delay": 0, "dmg_type1": 0},
    28: {"name": "Leather Gloves", "class": 4, "subclass": 2, "InventoryType": 10, "delay": 0, "dmg_type1": 0},
    29: {"name": "Leather Waist", "class": 4, "subclass": 2, "InventoryType": 6, "delay": 0, "dmg_type1": 0},
    30: {"name": "Leather Legs", "class": 4, "subclass": 2, "InventoryType": 7, "delay": 0, "dmg_type1": 0},
    31: {"name": "Leather Feet", "class": 4, "subclass": 2, "InventoryType": 8, "delay": 0, "dmg_type1": 0},
    
    # Mail (Subclass 3)
    32: {"name": "Mail Helm", "class": 4, "subclass": 3, "InventoryType": 1, "delay": 0, "dmg_type1": 0},
    33: {"name": "Mail Shoulders", "class": 4, "subclass": 3, "InventoryType": 3, "delay": 0, "dmg_type1": 0},
    34: {"name": "Mail Chest", "class": 4, "subclass": 3, "InventoryType": 5, "delay": 0, "dmg_type1": 0},
    35: {"name": "Mail Wrist", "class": 4, "subclass": 3, "InventoryType": 9, "delay": 0, "dmg_type1": 0},
    36: {"name": "Mail Gloves", "class": 4, "subclass": 3, "InventoryType": 10, "delay": 0, "dmg_type1": 0},
    37: {"name": "Mail Waist", "class": 4, "subclass": 3, "InventoryType": 6, "delay": 0, "dmg_type1": 0},
    38: {"name": "Mail Legs", "class": 4, "subclass": 3, "InventoryType": 7, "delay": 0, "dmg_type1": 0},
    39: {"name": "Mail Feet", "class": 4, "subclass": 3, "InventoryType": 8, "delay": 0, "dmg_type1": 0},
    
    # Plate (Subclass 4)
    40: {"name": "Plate Helm", "class": 4, "subclass": 4, "InventoryType": 1, "delay": 0, "dmg_type1": 0},
    41: {"name": "Plate Shoulders", "class": 4, "subclass": 4, "InventoryType": 3, "delay": 0, "dmg_type1": 0},
    42: {"name": "Plate Chest", "class": 4, "subclass": 4, "InventoryType": 5, "delay": 0, "dmg_type1": 0},
    43: {"name": "Plate Wrist", "class": 4, "subclass": 4, "InventoryType": 9, "delay": 0, "dmg_type1": 0},
    44: {"name": "Plate Gloves", "class": 4, "subclass": 4, "InventoryType": 10, "delay": 0, "dmg_type1": 0},
    45: {"name": "Plate Waist", "class": 4, "subclass": 4, "InventoryType": 6, "delay": 0, "dmg_type1": 0},
    46: {"name": "Plate Legs", "class": 4, "subclass": 4, "InventoryType": 7, "delay": 0, "dmg_type1": 0},
    47: {"name": "Plate Feet", "class": 4, "subclass": 4, "InventoryType": 8, "delay": 0, "dmg_type1": 0},
    
    # Miscellaneous (Subclass 0)
    48: {"name": "Cloak", "class": 4, "subclass": 0, "InventoryType": 16, "delay": 0, "dmg_type1": 0},
    49: {"name": "Necklace", "class": 4, "subclass": 0, "InventoryType": 2, "delay": 0, "dmg_type1": 0},
    50: {"name": "Ring / Band", "class": 4, "subclass": 0, "InventoryType": 11, "delay": 0, "dmg_type1": 0},
    51: {"name": "Shield", "class": 4, "subclass": 6, "InventoryType": 14, "delay": 0, "dmg_type1": 0},
    52: {"name": "Offhand", "class": 4, "subclass": 0, "InventoryType": 23, "delay": 0, "dmg_type1": 0},
}

QUALITIES = {
    1: {"name": "Uncommon (Green)", "code": 2}, 2: {"name": "Rare (Blue)", "code": 3},
    3: {"name": "Epic (Purple)", "code": 4}, 4: {"name": "Legendary (Orange)", "code": 5}
}

BLUEPRINTS = {
    "AGI_DPS":   {"pool": [3, 7, 31, 32, 36, 38, 44], "anchors": [3], "weights": {3: 130, 7: 100, 31: 90, 32: 90, 36: 60, 38: 80, 44: 70}},
    "STR_DPS":   {"pool": [4, 7, 31, 32, 36, 38, 44], "anchors": [4], "weights": {4: 130, 7: 100, 31: 90, 32: 90, 36: 60, 38: 80, 44: 70}},
    "SP_DPS":    {"pool": [5, 7, 45, 31, 32, 36],     "anchors": [5, 45], "weights": {5: 120, 45: 130, 7: 90, 31: 85, 32: 85, 36: 80}},
    "HEALER":    {"pool": [5, 6, 7, 45, 32, 36, 43],   "anchors": [5, 45], "weights": {5: 110, 6: 110, 45: 120, 7: 90, 32: 80, 36: 80, 43: 75}},
    "STR_TANK":  {"pool": [4, 7, 12, 13, 14, 31, 37],  "anchors": [7, 4],  "weights": {7: 130, 4: 100, 12: 85, 13: 90, 14: 90, 31: 75, 37: 85}},
    "AGI_TANK":  {"pool": [3, 7, 12, 13, 31, 37, 32, 36, 38], "anchors": [3, 7], "weights": {3: 150, 7: 140, 12: 85, 13: 100, 31: 80, 37: 85, 32: 45, 36: 45, 38: 40}},
    "AGI_INT_DPS": {"pool": [3, 5, 7, 31, 32, 36, 38, 44], "anchors": [3, 5], "weights": {3: 130, 5: 100, 7:100, 31: 90, 32: 90, 36: 60, 38: 80, 44: 70}}
}

# (Helper functions interpolate_macro_budget, interpolate_local_dps, get_interpolated_properties remain same)
def get_dynamic_sell_price(sheet, ilvl):
    """
    Finds the closest item level nodes in the sheet and returns the 
    linearly interpolated average sell price in copper.
    """
    if not sheet:
        return 0
    if ilvl <= sheet[0]["itemlevel"]:
        return sheet[0]["avg_sell_price"]
    if ilvl >= sheet[-1]["itemlevel"]:
        return sheet[-1]["avg_sell_price"]
        
    for i in range(len(sheet) - 1):
        p1 = sheet[i]
        p2 = sheet[i+1]
        if p1["itemlevel"] <= ilvl <= p2["itemlevel"]:
            if p2["itemlevel"] == p1["itemlevel"]:
                return p1["avg_sell_price"]
            ratio = (ilvl - p1["itemlevel"]) / (p2["itemlevel"] - p1["itemlevel"])
            return p1["avg_sell_price"] + ratio * (p2["avg_sell_price"] - p1["avg_sell_price"])
    return sheet[0]["avg_sell_price"]

def calculate_item_sell_price(lookup_database, category, quality_code, ilvl):
    """
    Finds a sell price baseline using a rigid multi-tiered fallback architecture:
    1. Exact match (Quality, Slot, Subclass)
    2. Alternative Quality match (Same Slot & Subclass)
    3. Global Subclass match (Any Slot or Quality matching the base weapon/armor type)
    """
    cls, subcls, inv_type = category["class"], category["subclass"], category["InventoryType"]
    
    # Tier 1: Exact Match
    exact_key = (cls, subcls, inv_type, quality_code)
    if exact_key in lookup_database and lookup_database[exact_key]:
        return get_dynamic_sell_price(lookup_database[exact_key], ilvl)
        
    # Tier 2: Check alternative qualities for the same slot/subclass configuration
    quality_ladder = [quality_code] + [3, 4, 2, 1, 0, 5] # Priorities: Rare, Epic, Uncommon, etc.
    for q in quality_ladder:
        alt_key = (cls, subcls, inv_type, q)
        if alt_key in lookup_database and lookup_database[alt_key]:
            return get_dynamic_sell_price(lookup_database[alt_key], ilvl)
            
    # Tier 3: Broadest Subclass Fallback (Scan full database for matching class/subclass structure)
    for (c, sc, it, q), sheet in lookup_database.items():
        if c == cls and sc == subcls and sheet:
            return get_dynamic_sell_price(sheet, ilvl)
            
    return 500 # 5 Silver safety baseline if completely empty
def get_weapon_delay(category_data):
    """
    Fetches the database-calculated average speed for a weapon subclass,
    applies a +/-15% swing variation, and snaps it cleanly to the nearest 100ms.
    """
    subclass = category_data["subclass"]
    
    # Grab the true average from the DBC/Database via train_brain. 
    # Fallback to the hardcoded CATEGORIES delay if the dataset doesn't have it.
    base_delay = subclass_delays.get(subclass, category_data["delay"])
    
    # Calculate 15% boundaries
    min_delay = base_delay * 0.85
    max_delay = base_delay * 1.15
    
    # Roll the randomized raw speed value
    raw_delay = random.uniform(min_delay, max_delay)
    
    # Snap smoothly to the nearest 100ms step
    return int(round(raw_delay / 100) * 100)
def get_sheathe_type(cat):
    """
    Returns the Sheath ID based on WoW standards:
    1: 2H Weapon, 2: Staff, 3: 1H Weapon, 4: Shield, 7: Off-hand
    """
    inv = cat.get("InventoryType")
    cls = cat.get("class")
    sub = cat.get("subclass")

    # Shield (InvType 6)
    if inv == 6: return 4
    
    # Armor (Class 4) - Usually no sheath type
    if cls == 4: return 0
    
    # Weapons (Class 2)
    if cls == 2:
        # Staff (Subclass 10)
        if sub == 10: return 2
        # Off-hand (InvType 23)
        if inv == 23: return 7
        # 2H Weapons (Various Subclasses: 1=Axe, 5=Mace, 6=Polearm, 8=Sword, 17=Knife/Dagger sometimes, etc)
        # Add your specific 2H subclasses here
        if sub in [1, 5, 6, 8, 17]: return 1
        
        # Everything else (1H swords, daggers, maces)
        return 3
        
    return 0 # Default fallback
def parse_ilvl_input(x):
    if '-' in x:
        low, high = map(int, x.split('-'))
        if not (10 <= low <= 284 and 10 <= high <= 284 and low <= high): raise Exception
        return (low, high)
    else:
        val = int(x)
        if not (10 <= val <= 284): raise Exception
        return (val, val)
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def get_appropriate_req_level(cursor, ilvl, quality):
    # Search for items within +/- 3 levels of target ilvl, same quality
    query = """
    SELECT AVG(RequiredLevel) 
    FROM item_template 
    WHERE itemlevel BETWEEN %s AND %s 
    AND Quality = %s 
    AND RequiredLevel > 1
    """
    cursor.execute(query, (ilvl - 10, ilvl + 10, quality))
    result = cursor.fetchone()[0]
    
    # Calculate initial value
    req_level = int(result) if result else max(1, int(ilvl * 0.75))
    
    # --- LEVEL CLAMPING LOGIC ---
    # 1. Cap for iLevel 90 and below (Raiding bracket)
    if ilvl <= 90:
        req_level = min(req_level, 60)
        
    # 2. Cap for iLevel 154 and below (BC Raiding bracket)
    elif ilvl <= 154:
        req_level = min(req_level, 70)
        
    # 3. Global absolute cap
    req_level = min(req_level, 80)
    
    return req_level
    
def interpolate_armor(nodes, target_ilvl):
    valid_nodes = [n for n in nodes if n["avg_armor"] > 0]
    if not valid_nodes: return 0.0
    
    # ... logic identical to interpolate_local_dps ...
    for n in valid_nodes:
        if n["itemlevel"] == target_ilvl: return n["avg_armor"]
    
    low_node = max([n for n in valid_nodes if n["itemlevel"] <= target_ilvl], key=lambda x: x['itemlevel'], default=None)
    high_node = min([n for n in valid_nodes if n["itemlevel"] >= target_ilvl], key=lambda x: x['itemlevel'], default=None)
    
    if low_node and high_node and low_node != high_node:
        x0, x1 = low_node["itemlevel"], high_node["itemlevel"]
        t = (target_ilvl - x0) / (x1 - x0)
        return low_node["avg_armor"] + t * (high_node["avg_armor"] - low_node["avg_armor"])
    return valid_nodes[0]["avg_armor"]
def get_next_entry_id(cursor):
    cursor.execute("SELECT MAX(entry) FROM item_template WHERE entry >= 91000")
    result = cursor.fetchone()[0]
    return (result + 1) if result else 91000
def generate_item_name(cat_keys):
    ndb = name_database.get(cat_keys, {
        "adjectives": ["Reinforced"], 
        "materials": ["Iron"], 
        "nouns": ["Blade"], 
        "properties": ["of Power"]
    })
    adj_pool = ndb.get("adjectives", ["Reinforced"])
    mat_pool = ndb.get("materials", ["Iron"])
    noun_pool = ndb.get("nouns", ["Blade"])
    prop_pool = ndb.get("properties", ["of Power"])
    
    while True:
        noun = random.choice(noun_pool)
        adj = random.choice(adj_pool) if random.random() < 0.6 else ""
        mat = random.choice(mat_pool) if random.random() < 0.4 else ""
        prop = random.choice(prop_pool) if random.random() < 0.3 else ""
        final_name = f"{adj} {mat} {noun} {prop}".strip().replace("  ", " ")
        if len(final_name.split()) >= 2:
            return final_name

def get_appropriate_display_id(cat_keys, target_ilvl, target_qual, target_inv_type): # Add argument
    ndb = name_database.get(cat_keys)
    if not ndb or "displays" not in ndb: return {"id": 42531, "lvl": 0, "q": 0}
    
    pool = ndb["displays"]
    valid_qualities = [target_qual - 1, target_qual, target_qual + 1]
    min_lvl, max_lvl = target_ilvl * 0.8, target_ilvl * 1.2
    
    candidates = [
        d for d in pool 
        if d["q"] in valid_qualities 
        and min_lvl <= d["lvl"] <= max_lvl 
        and d.get("InventoryType") == target_inv_type
    ]
    
    return random.choice(candidates) if candidates else random.choice(pool)
    
    # Return match or random fallback from the category pool
    return random.choice(candidates) if candidates else random.choice([d["id"] for d in pool])
def interpolate_macro_budget(curves, inv_type, qual, target_ilvl):
    key = (inv_type, qual)
    if key not in curves: return 0.0
    nodes = curves[key]
    for n in nodes:
        if n["itemlevel"] == target_ilvl: return n["avg_budget"]
    if len(nodes) == 1: return nodes[0]["avg_budget"]
    low_node, high_node = None, None
    for n in nodes:
        if n["itemlevel"] < target_ilvl: low_node = n
        if n["itemlevel"] > target_ilvl and high_node is None: high_node = n
    if low_node is not None and high_node is not None:
        x0, x1 = low_node["itemlevel"], high_node["itemlevel"]
        t = (target_ilvl - x0) / (x1 - x0)
        return low_node["avg_budget"] + t * (high_node["avg_budget"] - low_node["avg_budget"])
    return nodes[0]["avg_budget"]

def interpolate_local_dps(nodes, target_ilvl):
    valid_nodes = [n for n in nodes if n["avg_dps"] > 0]
    if not valid_nodes: return 0.0
    for n in valid_nodes:
        if n["itemlevel"] == target_ilvl: return n["avg_dps"]
    if len(valid_nodes) == 1: return valid_nodes[0]["avg_dps"]
    low_node, high_node = None, None
    for n in valid_nodes:
        if n["itemlevel"] < target_ilvl: low_node = n
        if n["itemlevel"] > target_ilvl and high_node is None: high_node = n
    if low_node is not None and high_node is not None:
        x0, x1 = low_node["itemlevel"], high_node["itemlevel"]
        t = (target_ilvl - x0) / (x1 - x0)
        return low_node["avg_dps"] + t * (high_node["avg_dps"] - low_node["avg_dps"])
    return valid_nodes[0]["avg_dps"]

def get_interpolated_properties(ilvl_sheet, target_ilvl, inv_type, qual):
    if not ilvl_sheet: return None
    final_budget = interpolate_macro_budget(global_budget_curves, inv_type, qual, target_ilvl)
    final_dps = interpolate_local_dps(ilvl_sheet, target_ilvl)
    closest_node = min(ilvl_sheet, key=lambda x: abs(x["itemlevel"] - target_ilvl))
    return {
        "itemlevel": target_ilvl, "avg_budget": final_budget, "avg_dps": final_dps,
        "display_ids": closest_node["display_ids"] if closest_node["display_ids"] else [42531],
        "stat_profiles": closest_node["stat_profiles"]
    }

internal_memory = []

def get_input(prompt, validation_fn):
    while True:
        try:
            val = input(prompt).strip()
            return validation_fn(val)
        except Exception:
            print(f"⚠️ Invalid choice. Attempt verification again.")

print("=======================================================")
print("  🔮 COHESIVE SYNERGY ARCHETYPE GENERATOR ENGINE       ")
print("=======================================================")

while True:
    print("\n--- NEW ITEM GENERATION BATCH ---")
    print("Select Category Group:")
    print("  [1] Weapons")
    print("  [2] Armor")
    group_choice = get_input("Choice: ", lambda x: int(x) if x in ['1', '2'] else int("err"))
    
    cat_idx = -1

    if group_choice == 1: # WEAPONS
        print("\n  [1] 1H Weapons [2] 2H Weapons [3] Ranged")
        wpn_group = get_input("Select Group: ", lambda x: int(x) if x in ['1', '2', '3'] else int("err"))
        
        if wpn_group == 1: # 1H
            print("    [1] Daggers [2] Fist [3] 1H Axes [4] 1H Maces [5] 1H Swords")
            sub = get_input("Select: ", lambda x: int(x) if x in ['1','2','3','4','5'] else int("err"))
            cat_idx = {1: 4, 2: 6, 3: 7, 4: 15, 5: 2}[sub]
        elif wpn_group == 2: # 2H
            print("    [1] Staves [2] Polearms [3] 2H Axes [4] 2H Maces [5] 2H Swords")
            sub = get_input("Select: ", lambda x: int(x) if x in ['1','2','3','4','5'] else int("err"))
            cat_idx = {1: 5, 2: 9, 3: 10, 4: 8, 5: 3}[sub]
        elif wpn_group == 3: # Ranged
            print("    [1] Bows [2] Crossbows [3] Guns [4] Thrown [5] Wands")
            sub = get_input("Select: ", lambda x: int(x) if x in ['1','2','3','4','5'] else int("err"))
            cat_idx = {1: 12, 2: 11, 3: 13, 4: 14, 5: 1}[sub]

    else: # ARMOR
        print("\n  [1] Cloth [2] Leather [3] Mail [4] Plate [5] Miscellaneous")
        mat = get_input("Select Material: ", lambda x: int(x) if x in ['1','2','3','4','5'] else int("err"))
        
        if mat <= 4:
            # Material base start indices: Cloth(16), Leather(24), Mail(32), Plate(40)
            base = {1: 16, 2: 24, 3: 32, 4: 40}[mat]
            print("    [1] Helm [2] Shoulder [3] Chest [4] Wrist [5] Gloves [6] Waist [7] Legs [8] Feet")
            slot = get_input("Select Slot: ", lambda x: int(x) if 1 <= int(x) <= 8 else int("err"))
            cat_idx = base + (slot - 1)
        elif mat == 5: # Miscellaneous & Shields
            print(" [1] Cloak [2] Necklace [3] Ring [4] Shield [5]OffHand")
            sub = get_input("Select: ", lambda x: int(x) if x in ['1','2','3','4','5'] else int("err"))
            cat_idx = {1: 48, 2: 49, 3: 50, 4: 51, 5:52}[sub]

    category = CATEGORIES[cat_idx]

    # [Blueprint Routing Logic remains unchanged from original]
    chosen_blueprint_key = None
    subc = category["subclass"]
    cls = category["class"]

    if cls == 2:  # WEAPONS
        if subc == 19:  # Wand
            print("\nSelect Wand Archetype Variant:")
            print("  [1] Spell Power DPS\n  [2] Healer")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2'] else int("err"))
            chosen_blueprint_key = "SP_DPS" if bp_choice == 1 else "HEALER"
        elif subc == 7:  # 1H Sword
            print("\nSelect 1H Sword Archetype Variant:")
            print("  [1] Agility DPS\n  [2] Strength Tank\n  [3] Strength DPS\n  [4] Spell Power DPS\n  [5] Healer")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3','4','5'] else int("err"))
            chosen_blueprint_key = {1: "AGI_DPS", 2: "STR_TANK", 3: "STR_DPS", 4: "SP_DPS", 5: "HEALER"}[bp_choice]
        elif subc == 8:  # 2H Sword
            print("\nSelect 2H Sword Archetype Variant:")
            print("  [1] Agility DPS\n  [2] Strength DPS\n  [3] Strength Tank\n  [4] Agi/Int DPS")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3','4'] else int("err"))
            chosen_blueprint_key = {1: "AGI_DPS", 2: "STR_DPS", 3: "STR_TANK", 4: "AGI_INT_DPS"}[bp_choice]
        elif subc == 15:  # Dagger
            print("\nSelect Dagger Archetype Variant:")
            print("  [1] Agility DPS\n  [2] Spell Power DPS\n  [3] Healer\n  [4] Agi/Int DPS")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3','4'] else int("err"))
            chosen_blueprint_key = {1: "AGI_DPS", 2: "SP_DPS", 3: "HEALER", 4: "AGI_INT_DPS"}[bp_choice]
        elif subc == 10:  # Staff
            print("\nSelect Staff Archetype Variant:")
            print("  [1] Agility DPS\n  [2] Spell Power DPS\n  [3] Healer\n  [4] Agility Tank\n  [5] Strength DPS\n  [6] Agi/Int DPS")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3','4','5','6'] else int("err"))
            chosen_blueprint_key = {1: "AGI_DPS", 2: "SP_DPS", 3: "HEALER", 4: "AGI_TANK", 5: "STR_DPS", 6: "AGI_INT_DPS"}[bp_choice]
        elif subc == 13:  # Fist Weapon
            print("\nSelect Fist Weapon Archetype Variant:")
            print("  [1] Agility DPS\n  [2] Spell Power DPS\n  [3] Agi/Int DPS")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3'] else int("err"))
            chosen_blueprint_key = {1: "AGI_DPS", 2: "SP_DPS", 3: "AGI_INT_DPS"}[bp_choice]
        elif subc == 0:  # 1H Axe (Class 2)
            print("\nSelect 1H Axe Archetype Variant:")
            print("  [1] Agility DPS\n  [2] Strength DPS\n  [3] Strength Tank\n  [4] Agi/Int DPS")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3','4'] else int("err"))
            chosen_blueprint_key = {1: "AGI_DPS", 2: "STR_DPS", 3: "STR_TANK", 4: "AGI_INT_DPS"}[bp_choice]
        elif subc == 1:  # 2H Axe
            print("\nSelect 2H Axe Archetype Variant:")
            print("  [1] Agility DPS\n  [2] Strength DPS\n  [3] Strength Tank\n  [4] Agi/Int DPS")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3','4'] else int("err"))
            chosen_blueprint_key = {1: "AGI_DPS", 2: "STR_DPS", 3: "STR_TANK", 4: "AGI_INT_DPS"}[bp_choice]
        elif subc in [5, 6]:  # 2H Mace or Polearm
            print(f"\nSelect {category['name']} Archetype Variant:")
            print("  [1] Strength DPS\n  [2] Agility DPS\n  [3] Strength Tank\n  [4] Agility Tank\n  [5] Agi/Int DPS")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3','4','5'] else int("err"))
            chosen_blueprint_key = {1: "STR_DPS", 2: "AGI_DPS", 3: "STR_TANK", 4: "AGI_TANK", 5: "AGI_INT_DPS"}[bp_choice]
        elif subc in [2, 3, 18]:  # Bows, Guns, Crossbows
            print(f"\nSelect {category['name']} Archetype Variant:")
            print("  [1] Strength Tank\n  [2] Strength DPS\n  [3] Agility DPS\n  [4] Agi/Int DPS")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3','4'] else int("err"))
            chosen_blueprint_key = {1: "STR_TANK", 2: "STR_DPS", 3: "AGI_DPS", 4: "AGI_INT_DPS"}[bp_choice]
        elif subc == 16:  # Thrown
            print("\nSelect Thrown Weapon Archetype Variant:")
            print("  [1] Agility DPS\n  [2] Strength DPS\n  [3] Strength Tank")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3'] else int("err"))
            chosen_blueprint_key = {1: "AGI_DPS", 2: "STR_DPS", 3: "STR_TANK"}[bp_choice]
        elif subc == 4: # 1H Mace
            print("\nSelect 1H Mace Archetype Variant:")
            print("  [1] Strength DPS\n  [2] Strength Tank\n  [3] Healer\n  [4] Spell Power DPS")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3','4'] else int("err"))
            chosen_blueprint_key = {1: "STR_DPS", 2: "STR_TANK", 3: "HEALER", 4: "SP_DPS"}[bp_choice]

    elif cls == 4:  # ARMOR
        if subc == 1: # Cloth
            print("\nSelect Cloth Archetype:")
            print("  [1] Spell Power DPS\n  [2] Healer")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2'] else int("err"))
            chosen_blueprint_key = {1: "SP_DPS", 2: "HEALER"}[bp_choice]
        elif subc == 2: # Leather
            print("\nSelect Leather Archetype:")
            print("  [1] Agility DPS\n  [2] Agility Tank\n  [3] Healer\n  [4] Spell Power DPS\n  [5] Agi/Int DPS")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3','4','5'] else int("err"))
            chosen_blueprint_key = {1: "AGI_DPS", 2: "AGI_TANK", 3: "HEALER", 4: "SP_DPS", 5: "AGI_INT_DPS"}[bp_choice]
        elif subc == 3: # Mail
            print("\nSelect Mail Archetype:")
            print("  [1] Agility DPS\n  [2] Strength DPS\n  [3] Healer\n  [4] Spell Power DPS\n  [5] Agi/Int DPS")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3','4','5'] else int("err"))
            chosen_blueprint_key = {1: "AGI_DPS", 2: "STR_DPS", 3: "HEALER", 4: "SP_DPS", 5: "AGI_INT_DPS"}[bp_choice]
        elif subc == 4: # Plate
            print("\nSelect Plate Archetype:")
            print("  [1] Strength DPS\n  [2] Strength Tank\n  [3] HEALER")
            bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3'] else int("err"))
            chosen_blueprint_key = {1: "STR_DPS", 2: "STR_TANK", 3: "HEALER"}[bp_choice]
        elif subc == 0 or subc == 6: # Miscellaneous (0) OR Shields (6)
            print(f"\nSelect {category['name']} Archetype:")
            
            # 1. Shield (Subclass 6)
            if subc == 6:
                print("  [1] Strength Tank\n  [2] Spell Power DPS\n  [3] Healer")
                bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3'] else int("err"))
                chosen_blueprint_key = {
                    1: "STR_TANK", 2: "SP_DPS", 3: "HEALER"
                }[bp_choice]
            
            # 2. Offhand (InventoryType 23)
            elif category['InventoryType'] == 23:
                print("  [1] Spell Power DPS\n  [2] Healer")
                bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2'] else int("err"))
                chosen_blueprint_key = {
                    1: "SP_DPS", 2: "HEALER"
                }[bp_choice]
            
            # 3. Standard Miscellaneous (Cloak, Neck, Ring)
            else:
                print("  [1] Agility DPS\n  [2] Strength DPS\n  [3] Spell Power DPS\n  [4] Healer")
                print("  [5] Agi/Int DPS\n  [6] Strength Tank\n  [7] Agility Tank")
                bp_choice = get_input("Choice: ", lambda x: int(x) if x in ['1','2','3','4','5','6','7'] else int("err"))
                chosen_blueprint_key = {
                    1: "AGI_DPS", 2: "STR_DPS", 3: "SP_DPS", 4: "HEALER",
                    5: "AGI_INT_DPS", 6: "STR_TANK", 7: "AGI_TANK"
                }[bp_choice]
        else:
            print(f"⚠️ Configuration mapping missing for Subclass {subc} (Class {cls}). Defaulting to STR_DPS.")
            chosen_blueprint_key = "STR_DPS"

    # ... [Rest of the generation logic remains the same]
    print("\nAvailable Qualities:")
    for k, v in QUALITIES.items(): print(f"  [{k}] {v['name']}")
    quality_code = QUALITIES[get_input("Select Item Quality (Number): ", lambda x: int(x) if int(x) in QUALITIES else int("err"))]["code"]

    print("\nEnter Target Item Level (e.g., '85' or '50-85'):")
    ilvl_range = get_input("Choice: ", parse_ilvl_input)
    variance = get_input("Enter Budget Quality Variance % (0 to 25): ", lambda x: float(x) / 100.0 if 0 <= float(x) <= 25 else float("err"))
    
    print("\nSelect Stat Distribution Allocation Profile:")
    print("  [1] Even Split\n  [2] Randomly Varied Split")
    dist_mode = get_input("Select Profile Mode (1 or 2): ", lambda x: int(x) if int(x) in [1, 2] else int("err"))
    skew_factor = get_input("Enter Max Deviation %: ", lambda x: float(x) if 0 <= float(x) <= 100 else float("err")) if dist_mode == 2 else 0.0

    print("\nSelect Stat Slot Density Rule:")
    print("  [1] Database-Driven\n  [2] Progressive Blizzlike\n  [3] Explicit Manual Count")
    density_mode = get_input("Select Density Rule (1, 2, or 3): ", lambda x: int(x) if int(x) in [1, 2, 3] else int("err"))
    chosen_density_count = get_input("Enter exact count (1 to 6): ", lambda x: int(x) if 1 <= int(x) <= 6 else int("err")) if density_mode == 3 else 0

    quantity = get_input("\nHow many items?: ", lambda x: int(x) if int(x) > 0 else int("err"))

    available_levels = list(range(ilvl_range[0], ilvl_range[1] + 1))
    random.shuffle(available_levels)
    
    lookup_key = (category["class"], category["subclass"], category["InventoryType"], quality_code)
    if lookup_key not in lookup_database:
     print(f"⚠️ Configuration mapping missing for {category['name']}. Skipping.")
    # Exit or handle error here
    else:
     sheet = lookup_database[lookup_key]
     
     for _ in range(quantity):
        # 4. Handle the "Deck" (Refill if empty)
        if not available_levels:
            available_levels = list(range(ilvl_range[0], ilvl_range[1] + 1))
            random.shuffle(available_levels)
        
        # 5. DRAW THE NEW ILEVEL for THIS specific item
        ilvl = available_levels.pop()
        
        # 6. GET INTERPOLATION for THIS specific iLevel
        interpolated = get_interpolated_properties(sheet, ilvl, category["InventoryType"], quality_code)
        
        if not interpolated:
            print(f"⚠️ Interpolation frame fault at iLvl {ilvl}. Skipping.")
            continue

        # --- ALL MATH LOGIC IS NOW INSIDE THIS ONE LOOP ---
        fuzz_factor = random.uniform(1.0 - variance, 1.0 + variance)
        final_budget = int(interpolated["avg_budget"] * fuzz_factor)
        final_dps = interpolated["avg_dps"] * fuzz_factor if category["class"] == 2 else 0.0
        
        dynamic_delay = 0
        if category["class"] == 2:
            # Fallback to the hardcoded CATEGORIES configuration value if database lacks tracking 
            base_delay = subclass_delays.get(category["subclass"], category.get("delay", 2600))
            raw_delay = random.uniform(base_delay * 0.85, base_delay * 1.15)
            dynamic_delay = int(round(raw_delay / 100) * 100) # Snap to clean hundredths

        # --- DYNAMIC SWING RANGE DAMAGE CALCULATIONS ---
        dmg_min, dmg_max = 0, 0
        if category["class"] == 2 and final_dps > 0:
            # CHANGED: Replaced static category["delay"] with our randomized dynamic_delay
            avg_damage = (final_dps * (dynamic_delay / 1000.0))
            spread_fuzz = random.uniform(-0.02, 0.02)
            dmg_min = int(avg_damage * (0.70 + spread_fuzz))
            dmg_max = int(avg_damage * (1.30 + spread_fuzz))
            final_dps = round(((dmg_min + dmg_max) / 2) / (dynamic_delay / 1000.0), 2)

        if interpolated["stat_profiles"]:
            chosen_profile = random.choice(interpolated["stat_profiles"])
            random_prop_id = chosen_profile.get("RandomProperty", 0)
            random_suff_id = chosen_profile.get("RandomSuffix", 0)
            db_stats_count = chosen_profile.get("num_stats", 2)
        else:
            random_prop_id, random_suff_id = 0, 0
            db_stats_count = 2

        if random_prop_id != 0 or random_suff_id != 0:
            num_stats_to_roll = 0
        else:
            if density_mode == 1:
                num_stats_to_roll = db_stats_count if db_stats_count > 0 else 2
            elif density_mode == 2:
                if ilvl < 30: num_stats_to_roll = random.choices([1, 2], weights=[40, 60], k=1)[0]
                elif ilvl < 45: num_stats_to_roll = random.choices([2, 3], weights=[65, 35], k=1)[0]
                elif ilvl < 60: num_stats_to_roll = random.choices([2, 3], weights=[40, 60], k=1)[0]
                else: num_stats_to_roll = random.choices([2, 3, 4], weights=[20, 65, 15], k=1)[0]
            else:
                num_stats_to_roll = chosen_density_count

        stats = {f"stat_type{i}": 0 for i in range(1, 7)}
        stats.update({f"stat_value{i}": 0 for i in range(1, 7)})
        has_random_enchant = (random_prop_id != 0 or random_suff_id != 0)

        if not has_random_enchant and num_stats_to_roll > 0:
            if chosen_blueprint_key and chosen_blueprint_key in BLUEPRINTS:
                blueprint = BLUEPRINTS[chosen_blueprint_key]
                pool, anchors, current_weights = list(blueprint["pool"]), list(blueprint["anchors"]), blueprint["weights"].copy()
            else:
                profile_key = (category["class"], category["subclass"], category["InventoryType"])
                profile = archetype_profiles.get(profile_key)
                if profile and profile["weights"]:
                    archs, weights = list(profile["weights"].keys()), list(profile["weights"].values())
                    chosen_arch = random.choices(archs, weights=weights, k=1)[0]
                    pool, anchors, current_weights = list(profile["stats"].get(chosen_arch, [4, 7])), [4, 7], {s: 100 for s in [4, 7]}
                else:
                    pool, anchors, current_weights = [4, 7], [4, 7], {4: 100, 7: 100}

            if ilvl < 60:
                forbidden = {28, 30, 35, 36, 44}
                pool = [s for s in pool if s not in forbidden]
                anchors = [s for s in anchors if s not in forbidden]

            if category["InventoryType"] in [17, 25, 26] or category["subclass"] in [1, 5, 6, 8, 10]:
                pool = [s for s in pool if s not in [15, 48]]
                anchors = [s for s in anchors if s not in [15, 48]]
            if chosen_blueprint_key == "AGI_TANK":
                pool = [s for s in pool if s != 14]
                anchors = [s for s in anchors if s != 14]

            chosen_stats = []
            if anchors and num_stats_to_roll > 0:
                for a in anchors:
                    if a in pool and a not in chosen_stats:
                        chosen_stats.append(a)
                        num_stats_to_roll -= 1
                        if num_stats_to_roll <= 0: break
            
            remaining_pool = [s for s in pool if s not in chosen_stats]
            if remaining_pool and num_stats_to_roll > 0:
                actual_extra = min(num_stats_to_roll, len(remaining_pool), 6 - len(chosen_stats))
                for _ in range(actual_extra):
                    valid_remaining = [s for s in remaining_pool if s not in chosen_stats]
                    if not valid_remaining: break
                    weights = [current_weights.get(s, 50) for s in valid_remaining]
                    chosen_stat = random.choices(valid_remaining, weights=weights, k=1)[0]
                    chosen_stats.append(chosen_stat)
                
            num_active_stats = len(chosen_stats)
            shares = [(1.0 / num_active_stats) for _ in range(num_active_stats)]
            if dist_mode == 2 and num_active_stats > 1:
                shares = [max(0.01, s + random.uniform(-skew_factor / 100.0, skew_factor / 100.0)) for s in shares]
                s_sum = sum(shares)
                shares = [s / s_sum for s in shares]
            
            allocated_values = [max(1, int(final_budget * s)) for s in shares]
            remainder = final_budget - sum(allocated_values)
            if remainder != 0 and allocated_values:
                max_idx = allocated_values.index(max(allocated_values))
                allocated_values[max_idx] += remainder
            
            for idx, stat_type in enumerate(chosen_stats):
                stats[f"stat_type{idx+1}"] = stat_type
                stats[f"stat_value{idx+1}"] = allocated_values[idx]
        
        m_key = (category["class"], category["subclass"], quality_code) 
        if m_key in material_library:
    # Pick a random valid pair from existing items in the database
         chosen_pair = random.choice(material_library[m_key])
         item_material = chosen_pair['Material']
         item_sheath = get_sheathe_type(category)
        else:
         fallback_key = (category["class"], category["subclass"])
         possible_keys = [k for k in material_library.keys() if k[0:2] == fallback_key]
         if possible_keys:
          chosen_pair = random.choice(random.choice([material_library[k] for k in possible_keys]))
          item_material = chosen_pair['Material']
          item_sheath = get_sheathe_type(category)
         else:
             item_material = 1
             item_sheath = 0
        cat_keys = (category["class"], category["subclass"])
        generated_name = generate_item_name(cat_keys)
        display_obj = get_appropriate_display_id(cat_keys, ilvl, quality_code, category["InventoryType"])
        predicted_display_id = display_obj["id"]
        req_level = get_appropriate_req_level(cursor, ilvl, quality_code)
        if category['InventoryType'] == 23: avg_armor = 0.0
        else: avg_armor = interpolate_armor(sheet, ilvl) if category['class'] == 4 else 0.0
        fuzz_factor = random.uniform(1.0 - variance, 1.0 + variance)
        final_armor = int(avg_armor * fuzz_factor) if avg_armor > 0 else 0
        base_sell_price = calculate_item_sell_price(lookup_database, category, quality_code, ilvl)
        final_sell_price = int(base_sell_price * fuzz_factor)
        
        internal_memory.append({
    "config": category, "quality": quality_code, "ilvl": ilvl, "name": generated_name,
    "displayid": predicted_display_id, "dmg_min": dmg_min, "dmg_max": dmg_max, "displayid": display_obj.get("id"), "display_source": display_obj, "delay": dynamic_delay,
    "dps": final_dps, "armor": final_armor, # <--- ARMOR IS HERE, 
    "stats": stats, "RandomProperty": random_prop_id, "RandomSuffix": random_suff_id, "budget": final_budget, "required_level": req_level, "Material": item_material,
    "sheath": item_sheath, "sell_price": final_sell_price
})

    print(f"Saved {quantity} items. Total cached: {len(internal_memory)}")
    if get_input("\nAdd another batch? (y/n): ", lambda x: x.lower() if x.lower() in ['y', 'n'] else int("err")) == 'n': break

output_filename = "interactive_generated_items.sql"
conn = get_db_connection()
cursor = conn.cursor()
start_entry_id = get_next_entry_id(cursor)

print(f"\n💾 Session completed! Exporting to SQL database format...")
with open(output_filename, "w") as f:
    f.write("-- AI-Assisted Smart Item Generation Suite (Cohesive Synergy & Complete Spec Blueprints)\n\n")
    for idx, item in enumerate(internal_memory):
        current_id = start_entry_id + idx
        c = item["config"]
        s = item["stats"]
        description = f"iLvl {item['ilvl']} {c['name']} generated via structural blueprint routing."
        
        sql_string = f"""DELETE FROM `item_template` WHERE `entry` = {current_id};
INSERT INTO `item_template` (`entry`, `class`, `subclass`, `name`, `displayid`, `Quality`, `InventoryType`, `itemlevel`, `RequiredLevel`, `armor`, `delay`, `dmg_min1`, `dmg_max1`, `dmg_type1`, `stat_type1`, `stat_value1`, `stat_type2`, `stat_value2`, `stat_type3`, `stat_value3`, `stat_type4`, `stat_value4`, `stat_type5`, `stat_value5`, `stat_type6`, `stat_value6`, `RandomProperty`, `RandomSuffix`, `Material`, `sheath`, `SellPrice`, `Description`) 
VALUES ({current_id}, {c['class']}, {c['subclass']}, '{item['name']}', {item['displayid']}, {item['quality']}, {c['InventoryType']}, {item['ilvl']}, {item['required_level']}, {item.get('armor', 0)}, {item['delay']}, {item['dmg_min']}, {item['dmg_max']}, {c['dmg_type1']}, {s['stat_type1']}, {s['stat_value1']}, {s['stat_type2']}, {s['stat_value2']}, {s['stat_type3']}, {s['stat_value3']}, {s['stat_type4']}, {s['stat_value4']}, {s['stat_type5']}, {s['stat_value5']}, {s['stat_type6']}, {s['stat_value6']}, {item['RandomProperty']}, {item['RandomSuffix']}, {item['Material']}, {item['sheath']}, {item.get('sell_price', 0)},  '{description}');\n"""
        f.write(sql_string)
        
        combat_info = f" ({item['dps']} DPS | Min-Max: {item['dmg_min']}-{item['dmg_max']})" if c['class'] == 2 else " (Armor Piece)"
        print(f" -> Compiled [ID: {current_id}] '{item['name']}' - iLvl {item['ilvl']}{combat_info}")
        
        primaries, secondaries = [], []
        for i in range(1, 7):
            st, sv = s[f"stat_type{i}"], s[f"stat_value{i}"]
            if sv > 0:
                if st in STAT_NAMES:
                    name, classification = STAT_NAMES[st]
                    formatted_stat = f"+{sv} {name}"
                    primaries.append(formatted_stat) if "Primary" in classification else secondaries.append(formatted_stat)
                else:
                    secondaries.append(f"+{sv} Unknown Stat (ID: {st})")
        
      
        if item['RandomProperty'] != 0 or item['RandomSuffix'] != 0:
            print(f"    ↳ [Debug Allocation] Budget Frame: {item['budget']} | Set to 0 (Delegated dynamically to Client DBC Pools)")
        else:
            print(f"    ↳ [Debug Allocation] Total Budget: {item['budget']}")
            
        # UPDATED: Print Source Metadata including the ID
        src = item.get("display_source", {})
        print(f"    ↳ [Visuals] DisplayID: {item['displayid']} (Source ID: {src.get('source_id', 'N/A')} | iLvl {src.get('lvl', 0)}, Qlty {src.get('q', 0)})")
            
        print(f"        🔹 Primaries:    [{', '.join(primaries) if primaries else 'None'}]")
        print(f"        🔸 Secondaries: [{', '.join(secondaries) if secondaries else 'None'}]")
         
cursor.close()
conn.close()
print(f"\n✅ Database connection closed. SQL file saved as {output_filename}")

csv_filename = "generated_items.csv"
print(f"\n💾 Exporting to CSV format: {csv_filename}")

import csv
with open(csv_filename, "w", newline='') as f:
    writer = csv.writer(f, quoting=csv.QUOTE_ALL)
    
    # Write the header row
    writer.writerow(["ID", "ClassID", "SubclassID", "Sound_Override_Subclassid", "Material", "DisplayInfoID", "InventoryType", "SheatheType"])
    
    # Write the data rows
    for idx, item in enumerate(internal_memory):
        current_id = start_entry_id + idx
        c = item["config"]
        
        writer.writerow([
            current_id,                      # ID
            c['class'],                      # ClassID
            c['subclass'],                   # SubclassID
            -1,                              # Sound_Override_Subclassid
            item.get('Material', 1),         # Material
            item['displayid'],               # DisplayInfoID
            c['InventoryType'],              # InventoryType
            item.get('sheath', 0)            # SheatheType
        ])

print(f"✅ CSV export successful!")
