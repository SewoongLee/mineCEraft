(async (bot) => {

    
    // Build a geodesic dome with a radius of 5 blocks
    // Get current position
    const pos = bot.entity.position.floored(); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const center = new Vec3(pos.x, pos.y, pos.z); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const radius = 5; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    const material = 'glass'; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    
    // Function to check if a point is on the dome surface
    function isOnDomeSurface(x, y, z) {
        // Calculate distance from center to the point
        const dx = x - center.x; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
        const dy = y - center.y; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
        const dz = z - center.z; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
        
        // Calculate squared distance
        const distanceSquared = dx * dx + dy * dy + dz * dz; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
        
        // Point is on the surface if it's close enough to the radius
        return Math.abs(distanceSquared - radius * radius) < radius * 0.4; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
    }
    
    // Build the dome
    async function buildDome() {
        // Iterate through a cube that contains the dome
        for (let y = center.y; y <= center.y + radius; y++) {
            for (let x = center.x - radius; x <= center.x + radius; x++) {
                for (let z = center.z - radius; z <= center.z + radius; z++) {
                    // Check if this point is on the dome surface
                    if (isOnDomeSurface(x, y, z)) {
                        await skills.placeBlock(bot, material, x, y, z); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
                        // Small delay to prevent overloading
                        await skills.wait(bot, 50); if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}
                    }
                }
            }
        }
    }
    
    // Execute the dome building function
    await buildDome();

log(bot, 'Code finished.');

})