WoW Cohesive Synergy Archetype Generator Engine
The Cohesive Synergy Archetype Generator Engine is an intelligent, interactive tool designed to procedurally generate balanced, "Blizzlike" items for World of Warcraft private servers (specifically compatible with AzerothCore/TrinityCore database schemas).

Instead of manually crafting thousands of items, this engine uses a "Brain" (pre-trained on your existing database) to understand how item levels, stats, budgets, and visual archetypes relate to one another.

🚀 Features
Database-Driven Intelligence: Connects directly to your acore_world database to learn item archetypes, ensuring generated gear feels authentic.

Interactive CLI Wizard: A step-by-step console interface to define categories, item levels, and rarity.

Smart Stat Distribution: Supports multiple profiles (Even Split vs. Randomly Varied) with configurable deviation rules to prevent "stat inflation."

Dual-Export Capability:

SQL: Automatically generates a formatted SQL script ready to be executed against your item_template table.

CSV: Generates a standardized CSV for external data management or mass-import tools.

Dynamic Visuals: Automatically maps generated items to existing DisplayIDs based on their source archetype.
