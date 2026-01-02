# action_processor.py
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

    # don’t put __FILENAME__ inside quotes in the template; there can be '\' like D:\git\mineCEraft\...
    js_wrapper = textwrap.dedent("""
    const fs = require('fs');

    // file path injected as a proper JS string literal
    const FILENAME = __FILENAME__;

    const code = fs.readFileSync(FILENAME, 'utf8');

    // ---- mocks ----
    // Provide a Vec3-like object with .floored(), .clone(), .offset(), and .distanceTo() as Mineflayer does.
    const _pos = {
      x: __X0__, y: __Y0__, z: __Z0__,
      floored() {
        return {
          x: Math.floor(this.x),
          y: Math.floor(this.y),
          z: Math.floor(this.z),
          floored: this.floored,
          clone: this.clone,
          offset: this.offset,
          distanceTo: this.distanceTo
        };
      },
      clone() {
        return {
          x: this.x,
          y: this.y,
          z: this.z,
          floored: this.floored,
          clone: this.clone,
          offset: this.offset,
          distanceTo: this.distanceTo
        };
      },
      offset(dx, dy, dz) {
        return {
          x: this.x + dx,
          y: this.y + dy,
          z: this.z + dz,
          floored: this.floored,
          clone: this.clone,
          offset: this.offset,
          distanceTo: this.distanceTo
        };
      },
      distanceTo(other) {
        const dx = this.x - other.x;
        const dy = this.y - other.y;
        const dz = this.z - other.z;
        return Math.sqrt(dx * dx + dy * dy + dz * dz);
      }
    };
    global.bot = {
      interrupt_code: false,
      entity: { position: _pos },
      chat: async () => {} // no-op mock for bot.chat()
    };
    global.world = {
      getPosition: (_bot) => ({ x: __X0__, y: __Y0__, z: __Z0__ }),
      getBlockAtPosition: (_bot, _x, _y, _z) => ({ name: 'air' })
    };

    global.log = function () {}; // no-op

    global.skills = {
      breakBlockAt: async () => {},
      placeBlock: async (_bot, block, x, y, z, ...rest) => {
        // print one JSON object per line (parsed by Python)
        console.log(JSON.stringify({ x, y, z, material: block }));
      },
      // wait mock to avoid runtime errors in your action code
      wait: async (_bot, ms) => {
        ms = Number(ms) || 0;
        await new Promise(r => setTimeout(r, ms));
      },
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
    """).replace("__FILENAME__", json.dumps(str(file_name)))\
        .replace("__X0__", str(x0))\
        .replace("__Y0__", str(y0))\
        .replace("__Z0__", str(z0))

    res = subprocess.run(["node", "-e", js_wrapper], capture_output=True, text=True)

    coords: List[Dict[str, Any]] = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            # normalize types
            obj["x"] = int(str(obj["x"]).strip())
            obj["y"] = int(str(obj["y"]).strip())
            obj["z"] = int(str(obj["z"]).strip())
            obj["material"] = str(obj.get("material", "unknown"))
            coords.append(obj)
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

    # If nothing was captured, surface Node's error output to help debugging.
    if not coords and res.stderr:
        print("[read_coords_from_action] stderr:", res.stderr)

    return coords
