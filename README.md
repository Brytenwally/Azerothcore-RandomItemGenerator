The Cohesive Synergy Archetype Generator Engine is an intelligent, interactive tool designed to procedurally generate balanced, "Blizzlike" items for World of Warcraft private servers (specifically compatible with AzerothCore/TrinityCore database schemas).

Instead of manually crafting thousands of items, this engine uses a "Brain" (pre-trained on your existing database) to understand how item levels, stats, budgets, and visual archetypes relate to one another.

**Features**

Database-Driven Intelligence: Connects directly to your acore_world database to learn item archetypes, ensuring generated gear feels authentic.

Interactive CLI Wizard: A step-by-step console interface to define categories, item levels, and rarity.

Smart Stat Distribution: Supports multiple profiles (Even Split vs. Randomly Varied) with configurable deviation rules to prevent "stat inflation."

Dual-Export Capability:

SQL: Automatically generates a formatted SQL script ready to be executed against your item_template table.

CSV: Generates a standardized CSV for external data management or mass-import tools.

Dynamic Visuals: Automatically maps generated items to existing DisplayIDs based on their source archetype.


**How to use**

Before anything else, install these dependencies if you don't have them

```pip install joblib mysql-connector-python openpyxl pandas```




1. Essential Startup Order
Before running the generator, please ensure your environment is ready:

Start your AzerothCore MySQL server.

Run train_brain.py first. This is required to process the raw item data and build the "brain" (the lookup databases) that the generator relies on.

Run interactive_generator.py. This is your main interface for creating items.

2. The Generation Wizard
When you run interactive_generator.py, you will be guided through a series of inputs:

Category Selection: You can choose from all available classes and subclasses currently in your database, with the exception of Trinkets and Relics.

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

Quantity: Finally, define how many items you wish to create in the current batch.

3. Session Management & Exporting
Looping: Once a batch is created, the items are held in the script's internal_memory. You will be asked if you want to create more items or if you are ready to import. You can continue adding batches as long as you like.

Final Export: When you choose to finish your session, the script will generate two distinct files:

SQL Query: This file is ready to be executed against your acore_world database. It is designed to be safe, automatically occupying empty IDs starting from 91000 upwards.

CSV File: A secondary file specifically formatted for WDBXEditor, allowing you to import your new items directly into your item.dbc files to ensure full client-side compatibility.
