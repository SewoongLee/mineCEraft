"""
Minecraft block material to hex color mapping.

This module provides a comprehensive mapping of Minecraft block names to their
hex color representations for visualization purposes.
Unknown materials fallback to black (#000000).
"""

from typing import Dict

# Material → color mapping (hex). Unknown materials fallback to black.
MATERIAL_COLOR: Dict[str, str] = {
    # Stone variants
    "stone": "#888888",
    "cobblestone": "#6b6b6b",
    "stone_bricks": "#9aa0a6",
    "mossy_stone_bricks": "#6b7b5a",
    "cracked_stone_bricks": "#7a7a7a",
    "chiseled_stone_bricks": "#8a8a8a",
    "stone_slab": "#b0b0b0",
    "smooth_stone": "#a0a0a0",
    "granite": "#9a6b5a",
    "polished_granite": "#a67b6a",
    "diorite": "#d0d0d0",
    "polished_diorite": "#e0e0e0",
    "andesite": "#7a7a7a",
    "polished_andesite": "#8a8a8a",
    
    # Dirt and earth
    "dirt": "#8B4513",
    "grass_block": "#7cb342",
    "grass_path": "#9a8a5a",
    "podzol": "#6b5a3a",
    "mycelium": "#8a7a9a",
    "coarse_dirt": "#7a5a3a",
    "gravel": "#808080",
    "sand": "#d4c4a0",
    "red_sand": "#b87a5a",
    "clay": "#8a9a9a",
    "terracotta": "#9a6a5a",
    
    # Wood - Oak
    "oak_planks": "#b8860b",
    "oak_log": "#8b6b4a",
    "oak_wood": "#8b6b4a",
    "oak_fence": "#a0522d",
    "oak_stairs": "#b8860b",
    "oak_slab": "#b8860b",
    "oak_door": "#5c4305",
    "oak_trapdoor": "#b8860b",
    
    # Wood - Spruce
    "spruce_planks": "#6b4a2a",
    "spruce_log": "#4a3a2a",
    "spruce_wood": "#4a3a2a",
    "spruce_fence": "#5a4a3a",
    "spruce_stairs": "#6b4a2a",
    "spruce_slab": "#6b4a2a",
    
    # Wood - Birch
    "birch_planks": "#d4c4a0",
    "birch_log": "#d4b48a",
    "birch_wood": "#d4b48a",
    "birch_fence": "#c4b48a",
    "birch_stairs": "#d4c4a0",
    "birch_slab": "#d4c4a0",
    
    # Wood - Jungle
    "jungle_planks": "#9a7a5a",
    "jungle_log": "#7a5a3a",
    "jungle_wood": "#7a5a3a",
    "jungle_fence": "#8a6a4a",
    "jungle_stairs": "#9a7a5a",
    "jungle_slab": "#9a7a5a",
    
    # Wood - Dark Oak
    "dark_oak_planks": "#3a2a1a",
    "dark_oak_log": "#2a1a0a",
    "dark_oak_wood": "#2a1a0a",
    "dark_oak_fence": "#3a2a1a",
    "dark_oak_stairs": "#3a2a1a",
    "dark_oak_slab": "#3a2a1a",
    
    # Wood - Acacia
    "acacia_planks": "#c48a5a",
    "acacia_log": "#a06a4a",
    "acacia_wood": "#a06a4a",
    "acacia_fence": "#b47a5a",
    "acacia_stairs": "#c48a5a",
    "acacia_slab": "#c48a5a",
    
    # Wood - Crimson/Warped (Nether)
    "crimson_planks": "#6a2a3a",
    "crimson_stem": "#5a1a2a",
    "warped_planks": "#2a5a6a",
    "warped_stem": "#1a4a5a",
    
    # Bricks
    "bricks": "#9a5a5a",
    "brick_stairs": "#9a5a5a",
    "brick_slab": "#9a5a5a",
    "nether_bricks": "#2a1a1a",
    "red_nether_bricks": "#5a1a1a",
    
    # Concrete
    "white_concrete": "#e0e0e0",
    "orange_concrete": "#e67a2a",
    "magenta_concrete": "#b84a9a",
    "light_blue_concrete": "#3a9ac4",
    "yellow_concrete": "#f1c40f",
    "lime_concrete": "#7ac42a",
    "pink_concrete": "#f19aba",
    "gray_concrete": "#4a4a4a",
    "light_gray_concrete": "#8a8a8a",
    "cyan_concrete": "#1a7a8a",
    "purple_concrete": "#7a2a9a",
    "blue_concrete": "#2a3a9a",
    "brown_concrete": "#6a3a1a",
    "green_concrete": "#4a6a1a",
    "red_concrete": "#9a1a1a",
    "black_concrete": "#1a1a1a",
    
    # Wool
    "white_wool": "#e8e8e8",
    "orange_wool": "#e67a2a",
    "magenta_wool": "#b84a9a",
    "light_blue_wool": "#6a9ac4",
    "yellow_wool": "#f1c40f",
    "lime_wool": "#7ac42a",
    "pink_wool": "#f19aba",
    "gray_wool": "#4a4a4a",
    "light_gray_wool": "#8a8a8a",
    "cyan_wool": "#1a7a8a",
    "purple_wool": "#7a2a9a",
    "blue_wool": "#2a3a9a",
    "brown_wool": "#6a3a1a",
    "green_wool": "#4a6a1a",
    "red_wool": "#9a1a1a",
    "black_wool": "#1a1a1a",
    
    # Glass
    "glass": "#c0e0e0",
    "glass_pane": "#bfdadd",
    "white_stained_glass": "#e0e0e0",
    "black_stained_glass": "#1a1a1a",
    "blue_stained_glass": "#2a3a9a",
    "brown_stained_glass": "#6a3a1a",
    "cyan_stained_glass": "#1a7a8a",
    "gray_stained_glass": "#4a4a4a",
    "green_stained_glass": "#4a6a1a",
    "light_blue_stained_glass": "#3a9ac4",
    "lime_stained_glass": "#7ac42a",
    "magenta_stained_glass": "#b84a9a",
    "orange_stained_glass": "#e67a2a",
    "pink_stained_glass": "#f19aba",
    "purple_stained_glass": "#7a2a9a",
    "red_stained_glass": "#9a1a1a",
    "yellow_stained_glass": "#f1c40f",
    
    # Metals and ores
    "iron_block": "#c0c0c0",
    "iron_ore": "#9a8a7a",
    "gold_block": "#f4d03f",
    "gold_ore": "#d4b48a",
    "diamond_block": "#1ac4d4",
    "diamond_ore": "#7a9a8a",
    "emerald_block": "#2ac48a",
    "emerald_ore": "#5a8a6a",
    "lapis_block": "#1a3a9a",
    "lapis_ore": "#2a4a8a",
    "coal_block": "#1a1a1a",
    "coal_ore": "#3a3a3a",
    "redstone_block": "#c41a1a",
    "redstone_ore": "#8a4a4a",
    "netherite_block": "#2a1a1a",
    "ancient_debris": "#4a2a2a",
    
    # Nether blocks
    "netherrack": "#6a1a1a",
    "soul_sand": "#4a3a2a",
    "soul_soil": "#3a2a1a",
    "glowstone": "#f4d03f",
    "magma_block": "#9a1a1a",
    "basalt": "#2a2a2a",
    "blackstone": "#1a1a1a",
    "polished_blackstone": "#2a2a2a",
    
    # End blocks
    "end_stone": "#f4e4a0",
    "end_stone_bricks": "#e4d490",
    "purpur_block": "#9a7a9a",
    "purpur_pillar": "#8a6a8a",
    
    # Special blocks
    "bed": "#c63c3c",
    "torch": "#f1c40f",
    "lantern": "#f1c40f",
    "soul_torch": "#4a3a2a",
    "redstone_torch": "#c41a1a",
    "beacon": "#1ac4d4",
    "bedrock": "#1a1a1a",
    "obsidian": "#1a0a2a",
    "crying_obsidian": "#2a1a3a",
    "ice": "#a0e0f0",
    "packed_ice": "#b0f0ff",
    "blue_ice": "#a0d0ff",
    "snow": "#ffffff",
    "snow_block": "#f0f0f0",
    "water": "#2a5a9a",
    "lava": "#ff4a1a",
    
    # Plants and organic
    "leaves": "#4a8a2a",
    "oak_leaves": "#4a8a2a",
    "spruce_leaves": "#2a5a1a",
    "birch_leaves": "#7a9a5a",
    "jungle_leaves": "#5a7a3a",
    "acacia_leaves": "#8a6a2a",
    "dark_oak_leaves": "#2a4a1a",
    "hay_bale": "#d4b48a",
    "pumpkin": "#e67a2a",
    "melon": "#8a1a1a",
    "cactus": "#4a8a2a",
    
    # Miscellaneous
    "bookshelf": "#8b6b4a",
    "chest": "#8b6b4a",
    "crafting_table": "#b8860b",
    "furnace": "#6b6b6b",
    "tnt": "#c41a1a",
    "sponge": "#d4c48a",
    "wet_sponge": "#6a7a5a",
    "slime_block": "#7ac42a",
    "honey_block": "#e6b42a",
    "note_block": "#6a3a1a",
    "jukebox": "#3a2a1a",
}

