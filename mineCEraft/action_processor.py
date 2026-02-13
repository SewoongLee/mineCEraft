# action_processor.py
import subprocess
import textwrap
import json
from typing import List, Dict, Any, Tuple

def read_coords_from_action(file_name: str, *, start_pos=(0, 0, 0)) -> List[Dict[str, Any]]:
    """
    Execute a JavaScript action file with a minimal mocked environment and
    capture all skills.placeBlock(...) calls as coords (including material).
    Ignores skills.breakBlockAt (use read_placed_and_removed_from_action for multi-turn).

    Returns:
        [{"x": int, "y": int, "z": int, "material": str}, ...]
    """
    placed, _ = read_placed_and_removed_from_action(file_name, start_pos=start_pos)
    return placed


def read_placed_and_removed_from_action(
    file_name: str, *, start_pos=(0, 0, 0)
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Execute a JavaScript action file and capture skills.placeBlock (placed)
    and skills.breakBlockAt (removed) as lists of coords.

    Returns:
        (placed, removed)
        - placed: [{"x", "y", "z", "material"}, ...]
        - removed: [{"x", "y", "z"}, ...]
    """
    x0, y0, z0 = map(int, start_pos)

    # don’t put __FILENAME__ inside quotes in the template; there can be '\' like D:\git\mineCEraft\...
    js_wrapper = textwrap.dedent("""
    const fs = require('fs');

    // file path injected as a proper JS string literal
    const FILENAME = __FILENAME__;

    let code = fs.readFileSync(FILENAME, 'utf8');
    code = code.replace(/^\\s*export\\s+default\\s+/m, '');

    // ---- mocks ----
    // Vec3 constructor mock (from vec3 package)
    function Vec3(x, y, z) {
      if (this instanceof Vec3) {
        this.x = x;
        this.y = y;
        this.z = z;
      } else {
        return new Vec3(x, y, z);
      }
    }
    Vec3.prototype.floored = function() {
      return new Vec3(Math.floor(this.x), Math.floor(this.y), Math.floor(this.z));
    };
    Vec3.prototype.floor = Vec3.prototype.floored; // alias for compatibility
    Vec3.prototype.clone = function() {
      return new Vec3(this.x, this.y, this.z);
    };
    Vec3.prototype.offset = function(dx, dy, dz) {
      return new Vec3(this.x + dx, this.y + dy, this.z + dz);
    };
    Vec3.prototype.distanceTo = function(other) {
      const dx = this.x - other.x;
      const dy = this.y - other.y;
      const dz = this.z - other.z;
      return Math.sqrt(dx * dx + dy * dy + dz * dz);
    };
    global.Vec3 = Vec3;
    
    // Helper function to create position objects with all methods
    function createPosObj(x, y, z, baseMethods) {
      return {
        x, y, z,
        floored() {
          return createPosObj(Math.floor(this.x), Math.floor(this.y), Math.floor(this.z), baseMethods);
        },
        floor() {
          return this.floored(); // alias for compatibility
        },
        clone() {
          return createPosObj(this.x, this.y, this.z, baseMethods);
        },
        offset(dx, dy, dz) {
          return createPosObj(this.x + dx, this.y + dy, this.z + dz, baseMethods);
        },
        distanceTo(other) {
          const dx = this.x - other.x;
          const dy = this.y - other.y;
          const dz = this.z - other.z;
          return Math.sqrt(dx * dx + dy * dy + dz * dz);
        }
      };
    }
    
    // Provide a Vec3-like object with .floored(), .floor(), .clone(), .offset(), and .distanceTo() as Mineflayer does.
    const _pos = createPosObj(__X0__, __Y0__, __Z0__, {});
    // Minimal block mock for bot.blockAt (action code may call it e.g. in safePlaceBlock).
    const airTypeId = 0;
    const mockRegistry = { blocks: { [airTypeId]: { name: 'air' } } };
    global.bot = {
      interrupt_code: false,
      entity: { position: _pos },
      chat: async () => {}, // no-op mock for bot.chat()
      registry: mockRegistry,
      blockAt(pos) {
        return { type: airTypeId, position: pos };
      },
    };
    global.world = {
      getPosition: (_bot) => _pos,
      getBlockAtPosition: (_bot, _x, _y, _z) => ({ name: 'air' })
    };

    global.log = function () {}; // no-op

    global.skills = {
      breakBlockAt: async (_bot, x, y, z) => {
        console.log(JSON.stringify({ action: 'remove', x, y, z }));
      },
      placeBlock: async (_bot, block, x, y, z, ...rest) => {
        console.log(JSON.stringify({ action: 'place', x, y, z, material: block }));
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

    placed: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            x = int(str(obj["x"]).strip())
            y = int(str(obj["y"]).strip())
            z = int(str(obj["z"]).strip())
            act = obj.get("action")
            if act == "remove":
                removed.append({"x": x, "y": y, "z": z})
            else:
                # "place" or legacy line without action
                placed.append({"x": x, "y": y, "z": z, "material": str(obj.get("material", "unknown"))})
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

    if not placed and not removed and res.stderr:
        print("[read_placed_and_removed_from_action] stderr:", res.stderr)

    return (placed, removed)
