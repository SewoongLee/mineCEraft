(async (bot) => {

    // Building a 20x15 rectangular foundation using stone blocks, 2 blocks deep
    // Following proper civil engineering practices for a strong foundation
    
    // Get current position
    const pos = bot.entity.position; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const startX = Math.floor(pos.x) + 3; // Offset from current position
    const startY = Math.floor(pos.y); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const startZ = Math.floor(pos.z) + 3; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    
    // Define foundation dimensions
    const width = 20;  // X-axis (switched to 20)
    const length = 15; // Z-axis (switched to 15)
    const depth = 2;   // Y-axis depth
    
    async function buildFoundation() {
      log(bot,`Starting to build a ${width}x${length} foundation with depth ${depth}`); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      
      // Build the foundation layers
      for (let y = 0; y < depth; y++) {
        // Start with the bottom layer, then build up
        const layerY = startY - y - 1; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
        
        // Build the entire rectangular layer
        for (let x = 0; x < width; x++) {
          for (let z = 0; z < length; z++) {
            // Calculate the exact position
            const blockX = startX + x; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
            const blockZ = startZ + z; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
            
            // Place stone block at this position
            await skills.placeBlock(bot, 'stone', blockX, layerY, blockZ); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
          }
        }
        
        // Small pause between layers to avoid overwhelming the server
        await skills.wait(bot, 50); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      }
      
      log(bot,"Foundation complete!"); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
      return true; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    }
    
    // Execute the foundation building function
    await buildFoundation();

log(bot, 'Code finished.');

})