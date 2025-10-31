import subprocess
import textwrap
import json
from typing import List, Dict, Any

def read_coords_from_action(file_name: str, *, start_pos=(0, 0, 0)) -> List[Dict[str, Any]]:
    """
    Execute a JavaScript action file with a minimal mocked environment and
    capture all skills.placeBlock(...) calls as coords (including material).

    Returns:
        [{"x": int, "y": int, "z": int, "material": str}, ...]
    """
    x0, y0, z0 = map(int, start_pos)

    # Build a wrapper that exposes mocks as globals so the eval'ed function can reach them.
    js_wrapper = textwrap.dedent("""
    const fs = require('fs');
    const code = fs.readFileSync('__FILENAME__','utf8');

    // --- expose mocks on GLOBAL scope so eval'ed function always sees them ---
    global.bot = {
      interrupt_code: false,
      entity: { position: { x: __X0__, y: __Y0__, z: __Z0__ } }
    };

    global.world = {
      getPosition: (_bot) => ({ x: __X0__, y: __Y0__, z: __Z0__ }),
      getBlockAtPosition: (_bot, _x, _y, _z) => ({ name: 'air' })
    };

    global.log = function () {}; // no-op

    global.skills = {
      breakBlockAt: async () => {},
      placeBlock: async (_bot, block, x, y, z, ...rest) => {
        // Print one JSON object per line (parsed by Python)
        console.log(JSON.stringify({ x, y, z, material: block }));
      }
    };

    (async () => {
      try {
        const evaluated = eval(code); // expect (async (bot)=>{...})
        const fn = (typeof evaluated === 'function')
          ? evaluated
          : (evaluated && typeof evaluated.default === 'function' ? evaluated.default : null);
        if (fn) await fn(global.bot);
      } catch (e) {
        console.error("WRAPPER_ERROR:", e && e.stack || e);
      }
    })();
    """).replace("__FILENAME__", file_name)\
        .replace("__X0__", str(x0))\
        .replace("__Y0__", str(y0))\
        .replace("__Z0__", str(z0))

    res = subprocess.run(["node", "-e", js_wrapper], capture_output=True, text=True)

    coords = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            # Normalize types
            obj["x"] = int(str(obj["x"]).strip())
            obj["y"] = int(str(obj["y"]).strip())
            obj["z"] = int(str(obj["z"]).strip())
            obj["material"] = str(obj.get("material", "unknown"))
            coords.append(obj)
        except (json.JSONDecodeError, ValueError, KeyError):
            # Ignore malformed lines
            pass

    return coords
