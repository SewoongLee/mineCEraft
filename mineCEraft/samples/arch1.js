(async (bot) => {

    // Plan:
    // 1) Determine integer center position from bot.
    // 2) Compute start/end X for a 12-block span centered on the bot.
    // 3) Clear a 14x5 area around the planned bridge footprint.
    // 4) Build end supports (pillars) of stone_bricks just outside the bridge span.
    // 5) Construct a symmetric arch (stone_bricks) under the deck along the centerline.
    // 6) Lay a 3-wide oak_planks deck at the arch top level.
    // 7) Add oak_fence railings one block above the deck at both sides.
    // 8) Add stone_slab transitions at both ends and place torches every 3 blocks on the deck.
    // Uses await for all async operations.
    
    const pos = world.getPosition(bot); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const cx = Math.floor(pos.x); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const cy = Math.floor(pos.y); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const cz = Math.floor(pos.z); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    
    const span = 12; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const half = span / 2; // 6
    const startX = cx - half; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const endX = cx + half - 1; // inclusive end so total span = 12
    const clearStart = startX - 1; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const clearEnd = endX + 1; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const clearZMin = cz - 2; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const clearZMax = cz + 2; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const clearYMin = cy; // clear from deck ground-level upward
    const clearYMax = cy + 4; // 5 blocks tall
    
    const archRise = 3; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const deckY = cy + archRise; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    
    // Helper to safely check block presence using relative offsets
    function getRelativeOffsets(absX, absY, absZ) {
      return {
        x: Math.floor(absX - pos.x),
        y: Math.floor(absY - pos.y),
        z: Math.floor(absZ - pos.z)
      }; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    }
    
    // 1) Clear area (14 x 5 footprint around the bridge)
    for (let x = clearStart; x <= clearEnd; x++) {
      for (let y = clearYMin; y <= clearYMax; y++) {
        for (let z = clearZMin; z <= clearZMax; z++) {
          const rel = getRelativeOffsets(x, y, z); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
          // world.getBlockAtPosition uses relative offsets
          const block = world.getBlockAtPosition(bot, rel.x, rel.y, rel.z); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
          if (block && block.name && block.name !== 'air') {
            await skills.breakBlockAt(bot, x, y, z); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
          } else if (block && block.type && block.type !== 'air') {
            await skills.breakBlockAt(bot, x, y, z); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
          }
        }
      }
    }
    
    // 2) End supports (pillars of stone_bricks just outside the bridge span)
    // Build 3-wide pillar (to align with deck width) at startX-1 and endX+1
    const supportXs = [startX - 1, endX + 1]; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    for (const sx of supportXs) {
      for (let dz = -1; dz <= 1; dz++) {
        const z = cz + dz; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
        for (let y = cy; y <= deckY; y++) {
          await skills.placeBlock(bot, 'stone_bricks', sx, y, z); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
        }
      }
    }
    
    // 3) Arch: place stone_bricks under the deck along the centerline (cz)
    for (let x = startX; x <= endX; x++) {
      const rel = Math.abs(x - cx); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      // Arch height formula: gradual falloff by two blocks per step outward
      const archHeight = Math.max(0, archRise - Math.floor(rel / 2)); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      // Place supporting bricks under the deck centerline
      for (let h = 1; h <= archHeight; h++) {
        const y = deckY - h; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
        await skills.placeBlock(bot, 'stone_bricks', x, y, cz); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      }
      // Optionally add a centerline cap if archHeight is zero (close to ground)
      if (archHeight === 0) {
        // ensure at least a stone_brick at deckY - 1 to connect supports
        await skills.placeBlock(bot, 'stone_bricks', x, deckY - 1, cz); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      }
    }
    
    // 4) Deck: 3-wide oak_planks at deckY across the span
    for (let x = startX; x <= endX; x++) {
      for (let dz = -1; dz <= 1; dz++) {
        const z = cz + dz; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
        await skills.placeBlock(bot, 'oak_planks', x, deckY, z); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      }
    }
    
    // 5) Railings: oak_fence on both sides one block above the deck
    for (let x = startX; x <= endX; x++) {
      // left rail (z = cz - 1)
      await skills.placeBlock(bot, 'oak_fence', x, deckY + 1, cz - 1); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      // right rail (z = cz + 1)
      await skills.placeBlock(bot, 'oak_fence', x, deckY + 1, cz + 1); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    }
    
    // 6) Stone_slab step transitions at both ends (on the deck extension at supports)
    for (const sx of supportXs) {
      // place slab across the three-width at the support x coordinate
      for (let dz = -1; dz <= 1; dz++) {
        const z = cz + dz; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
        await skills.placeBlock(bot, 'stone_slab', sx, deckY, z, 'top'); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      }
    }
    
    // 7) Torches every 3 blocks along the deck center
    let torchIndex = 0; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    for (let x = startX; x <= endX; x++) {
      if (torchIndex % 3 === 0) {
        // place torch on top of the center plank (deckY+1) using 'top' placement
        await skills.placeBlock(bot, 'torch', x, deckY + 1, cz, 'top'); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      }
      torchIndex++; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    }
    
    // Done.

log(bot, 'Code finished.');

})