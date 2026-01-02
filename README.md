# AbletonMCP - UPGRADED 🎹

**Enhanced Ableton Live MCP (Model Context Protocol) for AI-driven music production**

This is an upgraded version of [ahujasid/ableton-mcp](https://github.com/ahujasid/ableton-mcp) with additional features specifically designed for creating professional melodic techno tracks (Tale Of Us / Afterlife style).

## New Features ✨

### Clip Management
- **`list_clips`** - List all clips in a track with details (name, length, note count)
- **`delete_clip`** - Delete a clip from a slot
- **`clear_clip`** - Clear all notes from a clip (keep the clip)
- **`duplicate_clip`** - Duplicate a clip to another slot
- **`set_clip_loop`** - Set loop points for a clip
- **`get_clip_notes`** - Get all MIDI notes from a clip

### Note Management with Humanization
- **`add_notes_to_clip`** - Add notes to a clip (now with humanization support)
- **`replace_clip_notes`** - Replace all notes in a clip atomically
- **`delete_notes`** - Delete notes within pitch/time range
- **Humanization options:**
  - `humanize: true` - Apply random timing (±10ms) and velocity (±15) variation
  - `start_time_offset_ms` - Per-note timing offset in milliseconds
  - `velocity_offset` - Per-note velocity adjustment

### Mixer Controls
- **`set_track_volume`** - Set track volume (0.0-1.0)
- **`set_track_pan`** - Set track pan (-1.0 to 1.0)
- **`set_track_send`** - Set send levels (for reverb/delay)
- **`mute_track`** / **`solo_track`** / **`arm_track`** - Track state controls

### Device Parameter Control
- **`get_device_parameters`** - Get all parameters of a device
- **`set_device_param`** - Set device parameters by index or name

### Enhanced Session Info
- **`get_session_info`** - Now returns full track list with clip counts, device counts
- **`get_track_info`** - Now includes sends, detailed device parameters

### Scene Management
- **`create_scene`** - Create new scenes for arrangement

## Installation

### 1. Install the Remote Script in Ableton

Copy the `AbletonMCP_Remote_Script` folder to your Ableton MIDI Remote Scripts folder:

**Windows:**
```
C:\Users\[Username]\Documents\Ableton\User Library\Remote Scripts\
```

**macOS:**
```
/Users/[Username]/Music/Ableton/User Library/Remote Scripts/
```

Then in Ableton Live:
1. Go to **Preferences → Link, Tempo & MIDI**
2. Under **Control Surface**, select **AbletonMCP**
3. You should see "AbletonMCP UPGRADED: Listening on port 9877" message

### 2. Install the MCP Server

```bash
cd MCP_Server
pip install -e .
```

Or with uv:
```bash
uv pip install -e .
```

### 3. Configure your MCP client (Cursor, Claude, etc.)

Add to your MCP config:
```json
{
  "mcpServers": {
    "AbletonMCP": {
      "command": "python",
      "args": ["-m", "MCP_Server.server"],
      "cwd": "/path/to/ableton-mcp-upgraded"
    }
  }
}
```

## Usage Examples

### Create a humanized kick pattern
```python
# Create a 4-bar kick pattern with humanization
notes = []
for beat in range(16):  # 16 beats = 4 bars
    notes.append({
        "pitch": 36,  # C1 kick
        "start_time": beat,
        "duration": 0.25,
        "velocity": 100
    })

add_notes_to_clip(track_index=0, clip_index=0, notes=notes, humanize=True)
```

### Create a rolling bass line
```python
# Sub bass with slight timing variation
notes = [
    {"pitch": 33, "start_time": 0.0, "duration": 3.5, "velocity": 90, "start_time_offset_ms": 3},
    {"pitch": 33, "start_time": 4.0, "duration": 3.5, "velocity": 88, "start_time_offset_ms": -2},
    {"pitch": 35, "start_time": 8.0, "duration": 3.5, "velocity": 92, "start_time_offset_ms": 5},
    {"pitch": 33, "start_time": 12.0, "duration": 3.5, "velocity": 87, "start_time_offset_ms": -3},
]

replace_clip_notes(track_index=1, clip_index=0, notes=notes)
```

### Set up reverb send
```python
# Create return track with reverb, then set send level
set_track_send(track_index=0, send_index=0, value=0.3)  # 30% to Send A
```

## MIDI Note Reference

### Drums (General MIDI)
| Note | Pitch | Description |
|------|-------|-------------|
| C1   | 36    | Kick |
| D1   | 38    | Snare |
| F#1  | 42    | Closed Hi-Hat |
| A#1  | 46    | Open Hi-Hat |
| E1   | 40    | Rim/Clap |
| C#1  | 37    | Side Stick |

### Common Keys for Melodic Techno
| Key | Root Note | Scale |
|-----|-----------|-------|
| Am  | A (57)    | Natural Minor |
| Dm  | D (50)    | Natural Minor |
| Em  | E (52)    | Natural Minor |

## Clip Lengths (in beats at 4/4)

| Beats | Bars | Use |
|-------|------|-----|
| 4     | 1    | Single bar loop |
| 16    | 4    | Short phrase |
| 32    | 8    | Standard phrase |
| 64    | 16   | Intro/Outro |
| 128   | 32   | Full section |

## Limitations

- **Ableton Live Lite:** Maximum 8 tracks
- **Automation:** Clip automation not yet supported (use device parameters instead)
- **Audio clips:** Only MIDI clips are fully supported

## Credits

Based on [ahujasid/ableton-mcp](https://github.com/ahujasid/ableton-mcp)

Upgraded for melodic techno production workflows.
