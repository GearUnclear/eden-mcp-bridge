# Groups, crews and waypoints

These options are not yet accepted in live Eden; see [validation](validation.md).

## `create_entity` options

| Option | Applies to | Behavior |
|---|---|---|
| `keep_crew` | Vehicle classes | `true` keeps the class's default AI crew. Default: created empty. |
| `group_id` | Infantry classes | Creates the man inside an existing group. Accepts a group ID or a member/vehicle ID (vehicle: effective commander's group, else first crew member's). Other classes, or a group of another side, are rejected before anything is created. |
| `name` | Objects, triggers, logics | Variable name matching `^[A-Za-z_][A-Za-z0-9_]*$`. A name already used by an Eden object, group, trigger, logic or waypoint (case-insensitive) is refused before creating. |
| `azimuth` | Objects, triggers, logics | Yaw in degrees, `0 <= azimuth < 360`. Pitch and roll are kept. |

`name` and `azimuth` use the same validated write and readback as `set_attribute`. If either does not read back, or a man does not join the requested group, the bridge deletes everything that request created (entity, crew, and any new group; never the existing `group_id` group) and returns an error. The response adds `group_id` (-1 if none), `crew` (`entity_id`, `classname`, lowercase `role`) and `attributes` (requested and effective values, `engine_accepted`, `verified`). `verified` still refers to the created position.

## `create_waypoint`

Appends a waypoint to one group: `entity_id` (group, member or crewed vehicle), `position`, optional `placement_mode` (as for `create_entity`), and `waypoint_type`:

`MOVE`, `SAD`, `DESTROY`, `GETIN`, `GETOUT`, `HOLD`, `GUARD`, `SENTRY`, `LOITER`, `CYCLE`, `UNLOAD`, `TR_UNLOAD`, `LOAD`, `DISMISS`, `SUPPORT`, `JOIN`, `LEADER`

Optional settings, exact uppercase values:

- `behaviour`: `CARELESS`, `SAFE`, `AWARE`, `COMBAT`, `STEALTH`, `UNCHANGED`
- `combat_mode`: `BLUE`, `GREEN`, `WHITE`, `YELLOW`, `RED`, `NO CHANGE`
- `speed`: `LIMITED`, `NORMAL`, `FULL`, `UNCHANGED`
- `formation`: `COLUMN`, `STAG COLUMN`, `WEDGE`, `ECH LEFT`, `ECH RIGHT`, `VEE`, `LINE`, `FILE`, `DIAMOND`, `NO CHANGE`
- `completion_radius`: metres, finite and `>= 0`

Each setting is read back. Eden stores formation and speed as lowercase strings, while Bohemia's SQF export reads them as indices. The bridge writes the string first, falls back to the index, and accepts either form on readback. Any mismatch deletes the waypoint and returns an error. Conditions, activation statements and other script fields are rejected; no tool sends waypoint code.

The response contains `waypoint_id`, `group_id`, `waypoint_type`, `waypoint_class`, ATL/ASL position, `verified` for the position, and per-setting `attributes`.

## `describe_group`

Read-only. Takes a group, member or crewed-vehicle ID and returns `group_id`, `side`, `leader_id`, `members` (`entity_id`, `classname`, `variable`, `vehicle_id` or -1, `role`), and `waypoints` in runtime order (`waypoint_id`, `index`, `waypoint_type`, `position`). Index 0 is usually the group's implicit starting waypoint, with `waypoint_id` -1 and a runtime AGL position; editor waypoints report their Eden ATL position. `TR UNLOAD` is reported as `TR_UNLOAD`. `editor_membership_verified` compares members with Eden's native group links, and `errors` lists anything that could not be read.
