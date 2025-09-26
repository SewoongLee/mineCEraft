(async (bot) => {

    
    // Plan:
    // 1. Use the bot's current integer position (world.getPosition) as the south-west corner of the foundation.
    // 2. Foundation size: width (x) = 15, depth (z) = 20, height (y layers) = 2.
    // 3. For every block in that volume:
    //    - If an obstructing block exists (not air), break it first.
    //    - Place a stone block at that coordinate.
    // 4. Use try/catch around operations so a single failure doesn't stop the whole build.
    // Note: using world.getPosition to get a stable integer reference point for coordinates.
    
    const pos = world.getPosition(bot); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const startX = pos.x; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const startY = pos.y; // build starting at bot's feet-level Y (example convention)
    const startZ = pos.z; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    
    const width = 15; // x size
    const depth = 20; // z size
    const height = 2;  // number of block layers (two blocks deep/high)
    
    for (let yOff = 0; yOff < height; yOff++) {
      const y = startY + yOff; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      for (let dx = 0; dx < width; dx++) {
        const x = startX + dx; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
        for (let dz = 0; dz < depth; dz++) {
          const z = startZ + dz; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    
          try {
            // Check relative block at target position to avoid needless breaking
            const relX = x - pos.x; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
            const relY = y - pos.y; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
            const relZ = z - pos.z; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
            const block = world.getBlockAtPosition(bot, relX, relY, relZ); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    
            if (block && block.name && block.name !== 'air') {
              // Clear obstructing block
              await skills.breakBlockAt(bot, x, y, z); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
            }
    
            // Place stone block at the target position
            await skills.placeBlock(bot, 'stone', x, y, z); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
          } catch (err) {
            // If any single placement/break fails, continue with the rest.
            // Errors are ignored to maximize progress.
            continue; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
          }
        }
      }
    }

log(bot, 'Code finished.');

})