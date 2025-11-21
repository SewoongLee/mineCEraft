(async (bot) => {

    
    // Plan:
    // 1. Determine center position from bot.
    // 2. Parameters: length=13 (x axis), width=5 (z axis), walkwayWidth=3, arch rise=3.
    // 3. Build a 3-block-wide oak_planks walkway along X from startX to endX at walkwayY.
    // 4. Build a semi-circular arch (stone_bricks) along the centerline above the walkway with max rise.
    // 5. Add oak_fence rails at the outer edges and place torches every 3 blocks on top of rails.
    // 6. Add periodic stone_brick supports (vertical columns) under outer edges down several blocks.
    // 7. Add stone_brick_stairs ramps at both ends to make the bridge walkable from ground level.
    // Notes: using await for all async actions. This will operate relative to the bot's current block-aligned position.
    
    let pos = world.getPosition(bot); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    let centerX = Math.round(pos.x); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    let centerY = Math.floor(pos.y); // use floor for block coordinates
    let centerZ = Math.round(pos.z); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    
    // Bridge parameters
    let length = 13; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    let half = Math.floor(length / 2); // 6
    let startX = centerX - half; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    let endX = centerX + half; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    let walkwayWidth = 3; // centered: z offsets -1,0,1
    let width = 5; // full width including rails: z offsets -2..2
    let rise = 3; // max arch rise above walkway
    let radius = half; // normalize arch across length
    
    let walkwayY = centerY; // place walkway at this Y (relative to bot)
    
    // Helper to place a block and log (we avoid console to keep minimal; check return)
    async function tryPlace(blockType, x, y, z, placeOn = 'bottom') {
      return await skills.placeBlock(bot, blockType, x, y, z, placeOn); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    }
    
    // 1) Lay walkway (oak_planks) width 3: z offsets -1..+1
    for (let x = startX; x <= endX; x++) {
      for (let dz = -1; dz <= 1; dz++) {
        await tryPlace("oak_planks", x, walkwayY, centerZ + dz, 'top'); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      }
    }
    
    // 2) Build arch (stone_bricks) along centerline (z = centerZ)
    //    Use a normalized semicircle profile scaled to 'rise'.
    for (let x = startX; x <= endX; x++) {
      let dx = x - centerX; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      let normalized = dx / (radius === 0 ? 1 : radius); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      let t = 1 - Math.min(1, Math.abs(normalized)); // guard numeric issues
      let height = 0; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      if (Math.abs(normalized) <= 1) {
        height = Math.round(Math.sqrt(Math.max(0, 1 - normalized * normalized)) * rise); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      }
      let archY = walkwayY + height; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      // Avoid placing a block that would overwrite the walkway center (if archY == walkwayY)
      // Still place it: arch may touch walkway.
      await tryPlace("stone_bricks", x, archY, centerZ, 'top'); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      // Optionally make the arch 1-block thick in Z (a little more visible): place at z-1 and z+1 at upper half
      if (height >= Math.ceil(rise / 2)) {
        await tryPlace("stone_bricks", x, archY, centerZ - 1, 'top'); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
        await tryPlace("stone_bricks", x, archY, centerZ + 1, 'top'); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      }
    }
    
    // 3) Add fence rails on both outer edges (z = centerZ -2 and centerZ +2) one block above walkway
    for (let x = startX; x <= endX; x++) {
      await tryPlace("oak_fence", x, walkwayY + 1, centerZ - 2, 'top'); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      await tryPlace("oak_fence", x, walkwayY + 1, centerZ + 2, 'top'); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    
      // torches every 3 blocks on top of the fence posts
      if ((x - startX) % 3 === 0) {
        // Attempt to place torch one block above the fence (walkwayY+2). If not possible, placing on the fence (placeOn 'side') may work.
        await tryPlace("torch", x, walkwayY + 2, centerZ - 2, 'top'); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
        await tryPlace("torch", x, walkwayY + 2, centerZ + 2, 'top'); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      }
    }
    
    // 4) Place stone_brick supports under outer edges every 3 blocks (down several blocks)
    let supportDepth = 6; // try placing up to 6 blocks down from walkway level
    for (let x = startX; x <= endX; x += 3) {
      for (let dz of [-2, 2]) {
        for (let d = 1; d <= supportDepth; d++) {
          let y = walkwayY - d; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
          // place support block; continue even if a placement fails to attempt filling the column
          await tryPlace("stone_bricks", x, y, centerZ + dz, 'top'); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
        }
        // cap the top of the support to meet the walkway level
        await tryPlace("stone_bricks", x, walkwayY, centerZ + dz, 'top'); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      }
    }
    
    // 5) Add stone_brick foundations below the walkway centerline and edges (one layer under walkway)
    for (let x = startX; x <= endX; x++) {
      for (let dz = -2; dz <= 2; dz++) {
        await tryPlace("stone_bricks", x, walkwayY - 1, centerZ + dz, 'top'); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      }
    }
    
    // 6) Add stone_brick_stairs ramps at both ends for a smooth approach (3-step ramps)
    let rampLength = 3; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    for (let i = 1; i <= rampLength; i++) {
      // West/end start side
      await tryPlace("stone_brick_stairs", startX - i, walkwayY - (i - 1), centerZ, 'top'); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      // East/end other side
      await tryPlace("stone_brick_stairs", endX + i, walkwayY - (i - 1), centerZ, 'top'); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    }
    
    // Done: small pause to ensure world updates (await used)
    await skills.wait(bot, 200);

log(bot, 'Code finished.');

})