# Pygame Studio editor - capability map and MCP coverage

Every feature of the editor, and how an MCP client (VS Code Copilot, Claude
Desktop, a custom agent) can reach it. This is the inventory the tool set was
built from; it is also served to agents as the resource
`pygs://editor/capabilities` and the **live** tool schemas are available as
`pygs://editor/tools`.

Legend: **yes** = covered by a tool, **partly** = covered with a caveat, **no** =
not exposed (with the reason). Tool names are the MCP tool names.

## 1. Project

| Capability | Editor entry point | MCP |
| --- | --- | --- |
| Read project name/folder/screen size/counts | Project Settings, window title | `get_project_info` |
| Change project settings (`project.pygs`: caption, screen size, start scene, build section) | Project Settings window | `update_project_config` |
| Project list: create / open / import / rename / delete | Dashboard window | **no** - the dashboard runs before the editor exists; the server attaches to an open project |
| Editor preferences (language, theme) | Editor Settings window | `get_editor_settings`, `update_editor_settings` |

## 2. Files and assets (Asset panel)

| Capability | Editor entry point | MCP |
| --- | --- | --- |
| Browse the project tree, filter/sort, search | Asset panel | `list_files` (filter by folder, kind, name) |
| Create folder / script / scene / txt / json | Asset context menu > Add | `write_file`, `create_script` |
| Open a file in the code/block editor | Asset context menu > Open | `open_in_code_editor`, `block_editor_open` |
| Rename, move, duplicate | cut + paste, rename in the tree | `move_file` |
| Delete file/folder | context menu > Delete | `delete_file` (folders need `recursive`) |
| Import a file from the computer | drag & drop, copy into the folder | `import_file` |
| Open in terminal / file explorer | context menu | **no** - launches external processes, an agent should not need it |
| Play and edit audio, edit image, edit tile map | Audio Editor / Image Editor / Tile Map Editor | `audio_editor_open`, `audio_editor_state`, `audio_editor_control`; `audio_editor_edit` (delete / trim / silence / fade in-out / gain / pitch / speed - selection or whole file, undoable), `audio_editor_append` (concatenate files, one undo step), `audio_editor_save` (in place or Save As wav/flac/ogg/mp3); `image_editor_open`, `image_editor_state`, `image_editor_set_tool`, `image_editor_set_color`, `image_editor_set_grid`, `image_editor_draw`, `image_editor_draw_shape`, `image_editor_fill`, `image_editor_pick_color`, `image_editor_transform`, `image_editor_save`, `image_editor_capture`; `tile_map_editor_open`, `tile_map_editor_paint`, `tile_map_editor_fill`, `tile_map_editor_layer` |

## 3. Scenes

| Capability | Editor entry point | MCP |
| --- | --- | --- |
| New scene (empty canvas) | File > New Scene | `new_scene` |
| Open / switch scene | double click a `.scene`, or Run | `load_scene` |
| Save scene / Save As | File > Save Scene / Save As | `save_scene` (with optional path) |
| List scenes, mark the loaded/start scene | Asset panel | `list_scenes` |
| Unsaved-changes state | window title `*unsaved` | `editor_status`, `get_current_scene` |
| Scene content overview | Scene panel / Hierarchy | `get_scene_tree` |

## 4. Objects (Hierarchy + Inspector)

| Capability | Editor entry point | MCP |
| --- | --- | --- |
| Create any object type (rect, ellipse, polygon, line, text, image, button, particle, text input, progress bar, slider, frame sequence, keyframe, tile map, empty node) | Hierarchy > Add | `create_object`, `apply_scene_patch` |
| Read one object (all inspector properties + world rect) | Inspector | `get_object` |
| Find objects | Hierarchy search | `find_objects` (name/type/script/visibility) |
| Which properties exist per type | Inspector layout | `object_types` |
| Edit properties (move, resize, scale, rotate, color, text, font, image, collision, particle, slider, progress bar, frame sequence, keyframe, ...) | Inspector widgets | `update_object`, `apply_scene_patch` |
| Keyframe animation (snapshot timeline: keyframes with easing, duration, loop, auto play, playback speed; each keyframe stores x/y/scale/angle/color/image) | Animation Editor panel | `update_object` on a KEYFRAME object: `keyframes` (normalized + sorted), `duration` (hundredths of a second, fractions welcome - at least 0.1 s and at least the last keyframe - a lower value is raised), `auto_play`, `loop`, `playback_speed` (1 = real time, the game plays at it too), `image_path` - all undoable |
| Animation Editor panel: bind a Keyframe object, read the timeline, preview playback (play / pause / stop, 0.1-8x speed), scrub the playhead (the scene shows that pose, so `capture_scene_view` / `analyze_image` show the animation; without a selected keyframe the nearest frame on the LEFT is held, with one selected the values are interpolated), step a keyframe (the value row edits it) or clear the selection | Animation Editor tab | `animation_editor_open`, `animation_editor_state`, `animation_editor_control`; the panel itself is reachable with `open_panel` (`animation`) and `list_editor_panels` |
| Cut a sprite sheet PNG into single-frame files (cell size, offset, spacing; re-slicing a sheet replaces its earlier frames; the files feed keyframe images or a frame-sequence folder) | Animation Editor toolbar > scissors | `slice_sprite_sheet` |
| Fit a text box to its text (a TEXT label is clipped to its width/height otherwise) | Inspector > Size (by hand) | `fit_object_size`; `create_object` / `update_object` accept `"auto_size": true` |
| Rename | Hierarchy > Rename | `update_object` (`name`) |
| Show / hide | Inspector > Visibility | `update_object` (`visible`) |
| Transform pivot ("anchor"): the point rotation and scaling happen around - `pivot` is `center` (default), the eight other anchors or `custom` with `pivot_x` / `pivot_y` in content pixels. With the default centre a rotated or mirrored object stays in place, and the children of a rotated/scaled/mirrored parent follow it (parent transforms compose through the whole subtree) | Inspector > Pivot | `update_object` (`pivot`, `pivot_x`, `pivot_y`) |
| Negative scale = flip / mirror: `scale_x` = -1 mirrors horizontally, `scale_y` = -1 vertically, both = 180 degrees; the mirror happens around the pivot, so the object does not move (the box, click area and collision shapes follow the mirrored pixels) | Inspector > Scale (type -1) | `update_object` (`scale_x`, `scale_y`) |
| Drawing model: the whole tree is drawn FLAT at world coordinates (parent + children on the same surface), so a child that leaves its parent's box is still drawn in full; only the game window clips. `clip_children` (default false, per object) brings the old "one layer inside the box" rendering back - the parent then clips (and hides) whatever leaves its rect | Inspector > (no row yet) | `update_object` ({"clip_children": true}) |
| Delete (with children) | Hierarchy > Delete | `delete_object` |
| Duplicate (with children) | Hierarchy > Duplicate | `duplicate_object` |
| Cut / copy / paste | Edit menu / hierarchy context menu | `copy_objects` + `paste_objects` (paste under any parent, fresh uuids, one undo step; the clipboard is a data snapshot and survives switching scenes); cut stays UI-only (cut + `paste_objects` is not supported) |
| Re-parent (drag under another object) | Hierarchy drag & drop | `move_object` |
| Reorder siblings | Hierarchy drag & drop | **no** - no undoable primitive exists for it yet |
| Select objects (and show the user what is happening) | Hierarchy / Scene | `select_objects` |
| Select previous/next object | Inspector buttons | **no** - pure navigation |
| Expand / collapse in the tree | Hierarchy | **no** - UI state only, not scene content |
| Attach / detach a script | Inspector > Script Path | `create_script` (`attach_to`), `update_object` (`script_path`) |
| Collision shape editing (type, offset, size, polygon points) | Inspector > collision section | `update_object` (`collision_*`) |
| Rigid body editing (enable, body type, mass, friction, elasticity, gravity scale, fixed rotation, damping, rigid-body shape) | Inspector > physics section | `update_object` (`physics_*`, incl. `physics_shape_*`) - separate from the collision shape |
| Tile map painting, tile layers | Tile Map Editor | `tile_map_editor_paint` (cells, undoable), `tile_map_editor_fill`, `tile_map_editor_layer` (add/remove/rename/select/visible/collision); `update_object` can still set the tileset/tile size/grid |

## 5. Scripts

| Capability | Editor entry point | MCP |
| --- | --- | --- |
| Create a script from the ObjectScript template | Asset > Add > Script | `create_script` |
| Read / write script files | Code Editor | `read_file`, `write_file` |
| Jump to a file (and line) in the editor | Asset / console click | `open_in_code_editor` |
| Visual (block) scripting | Block Editor | `block_editor_open`, `block_editor_list_types`, `block_editor_get_blocks`, `block_editor_add_block`, `block_editor_set_field`, `block_editor_move_block`, `block_editor_delete_block`, `block_editor_save` (block scripts stay plain `.py` files) |

## 6. Running and debugging

| Capability | Editor entry point | MCP |
| --- | --- | --- |
| Run the project (saves the scene — a scene with no file must be saved first — starts `main.py`; the game of an earlier run is stopped first, `stop_running: false` starts an additional instance) | Project > Run | `run_project` |
| Stop running game processes | (editor keeps them alive until exit) | `stop_project` |
| Runtime status (pids, console length) | Console | `get_runtime_status` |
| Read the console (info/error/warning, search) | Console panel | `get_console_logs` |
| Clear the console | Console > Clear | `clear_console_logs` |
| Write to the console (progress notes for the user) | - | `log_to_console` |

## 7. Scene view / panels

| Capability | Editor entry point | MCP |
| --- | --- | --- |
| Look at the scene as the user sees it | Scene panel | `capture_scene_view` (PNG, whole canvas or a region, scalable) |
| Understand a picture without seeing it (for text-only models): background colour + share, content position/margins, main colours with boxes, brightness, a coarse colour grid | - | `analyze_image` (fresh scene-view capture by default, or `path` for any project image, e.g. a screenshot a script saved) |
| Which panels exist and are visible | tab bars | `list_editor_panels` |
| Show a panel (select its tab, raise a detached window, re-show one hidden from the Window menu) | tab bars / Window menu | `open_panel` |
| Pan/zoom/grid, gizmos, alignment guides | Scene panel + mouse | **no** - interactive only |

## 8. Building

The Build window has two tabs: **Desktop App** (PyInstaller executable for the
current operating system) and **Web App** (a folder with `index.html` +
`game.zip` that plays the game in a browser through Pyodide and pygame-ce - the
browser itself plays all audio (any format it supports: MP3/OGG/WAV/...), the
loop is paced by the display's animation frame (smooth scrolling; a hidden tab
pauses the game) and sound begins with the first click/tap/key because of the
browser autoplay rule. A project that uses physics also gets pymunk's Pyodide
wheel next to the page, so nothing is fetched from PyPI at runtime; the
project code/assets are protected like in the desktop build, the result lands
in `<output dir>/build/Web` and the installed engine is never modified).

| Capability | Editor entry point | MCP |
| --- | --- | --- |
| Read build settings (desktop values + `build.web`, running state, progress, last web bundle) | Build window | `get_build_settings` |
| Start a desktop build (PyInstaller executable) | Build window > Desktop App > Build | `start_build` |
| Start a web build (browser bundle) | Build window > Web App > Build | `start_web_build` |
| Stop a build (whichever tab is building) | Build window > Stop | `stop_build` |
| Open the desktop output / the web bundle folder | Build window > Open Output Dir | `open_output_dir` (`target`: `"desktop"` / `"web"`) |
| Run the built app / preview the web build | Run Game / Run in Browser buttons | **no** - buttons only |


## 9. Undo / history

| Capability | Editor entry point | MCP |
| --- | --- | --- |
| Undo / redo (including everything an agent changed) | Edit menu, Ctrl+Z / Ctrl+Y | `undo`, `redo` |
| History state (next step names) | - | `editor_status`, `get_undo_state` inside tool results |

Every tool that changes the scene funnels through the editor's `QUndoStack`, and
`apply_scene_patch` groups a whole batch into **one** undo step.

## 10. Deliberately not exposed

| Thing | Why |
| --- | --- |
| Modal dialogs (file chooser, save prompt, message boxes) | a tool call must never block on a UI dialog; the tools use non-interactive paths (`silent=True`, explicit paths) |
| Shell commands, opening terminals, deleting the project folder | nothing an agent needs, and hard to undo |
| The dashboard (create/import/delete projects) | it runs before an editor session exists; project creation stays a human action |
| Interactive editing (painting tiles/images, dragging gizmos) | painting is exposed as data edits (`tile_map_editor_paint`, `image_editor_draw`); gizmo dragging has no headless equivalent, `capture_scene_view` (and its text form `analyze_image`) replaces the observable part |

## 11. Resources (read-only documents)

| URI | Content |
| --- | --- |
| `pygs://editor/capabilities` | this document |
| `pygs://editor/tools` | the live tool list with JSON schemas |
| `pygs://editor/logs` | the newest console lines |
| `pygs://project/info` | project folder, scene, canvas size |
| `pygs://project/config` | `project.pygs` |
| `pygs://project/files` | every project file, grouped by kind |
| `pygs://project/scene-tree` | the object tree of the open scene |
