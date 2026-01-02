# AbletonMCP Server - UPGRADED VERSION
# Enhanced for Tale Of Us / Afterlife melodic techno production
from mcp.server.fastmcp import FastMCP, Context
import socket
import json
import logging
from dataclasses import dataclass
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, List, Union, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AbletonMCPServer")

@dataclass
class AbletonConnection:
    host: str
    port: int
    sock: socket.socket = None
    
    def connect(self) -> bool:
        """Connect to the Ableton Remote Script socket server"""
        if self.sock:
            return True
            
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logger.info(f"Connected to Ableton at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Ableton: {str(e)}")
            self.sock = None
            return False
    
    def disconnect(self):
        """Disconnect from the Ableton Remote Script"""
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                logger.error(f"Error disconnecting from Ableton: {str(e)}")
            finally:
                self.sock = None

    def receive_full_response(self, sock, buffer_size=8192):
        """Receive the complete response, potentially in multiple chunks"""
        chunks = []
        sock.settimeout(20.0)  # Increased timeout for complex operations
        
        try:
            while True:
                try:
                    chunk = sock.recv(buffer_size)
                    if not chunk:
                        if not chunks:
                            raise Exception("Connection closed before receiving any data")
                        break
                    
                    chunks.append(chunk)
                    
                    try:
                        data = b''.join(chunks)
                        json.loads(data.decode('utf-8'))
                        logger.info(f"Received complete response ({len(data)} bytes)")
                        return data
                    except json.JSONDecodeError:
                        continue
                except socket.timeout:
                    logger.warning("Socket timeout during chunked receive")
                    break
                except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
                    logger.error(f"Socket connection error during receive: {str(e)}")
                    raise
        except Exception as e:
            logger.error(f"Error during receive: {str(e)}")
            raise
            
        if chunks:
            data = b''.join(chunks)
            logger.info(f"Returning data after receive completion ({len(data)} bytes)")
            try:
                json.loads(data.decode('utf-8'))
                return data
            except json.JSONDecodeError:
                raise Exception("Incomplete JSON response received")
        else:
            raise Exception("No data received")

    def send_command(self, command_type: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a command to Ableton and return the response"""
        if not self.sock and not self.connect():
            raise ConnectionError("Not connected to Ableton")
        
        command = {
            "type": command_type,
            "params": params or {}
        }
        
        is_modifying_command = command_type in [
            "create_midi_track", "create_audio_track", "set_track_name",
            "create_clip", "add_notes_to_clip", "set_clip_name",
            "set_tempo", "fire_clip", "stop_clip", "set_device_parameter",
            "start_playback", "stop_playback", "load_instrument_or_effect",
            "load_browser_item",
            # NEW COMMANDS
            "delete_clip", "clear_clip", "replace_clip_notes", "delete_notes",
            "set_track_volume", "set_track_pan", "set_track_send",
            "set_device_param", "mute_track", "solo_track", "arm_track",
            "duplicate_clip", "set_clip_loop", "create_scene"
        ]
        
        try:
            logger.info(f"Sending command: {command_type} with params: {params}")
            
            self.sock.sendall(json.dumps(command).encode('utf-8'))
            logger.info(f"Command sent, waiting for response...")
            
            if is_modifying_command:
                import time
                time.sleep(0.1)
            
            timeout = 20.0 if is_modifying_command else 15.0
            self.sock.settimeout(timeout)
            
            response_data = self.receive_full_response(self.sock)
            logger.info(f"Received {len(response_data)} bytes of data")
            
            response = json.loads(response_data.decode('utf-8'))
            logger.info(f"Response parsed, status: {response.get('status', 'unknown')}")
            
            if response.get("status") == "error":
                logger.error(f"Ableton error: {response.get('message')}")
                raise Exception(response.get("message", "Unknown error from Ableton"))
            
            if is_modifying_command:
                import time
                time.sleep(0.1)
            
            return response.get("result", {})
        except socket.timeout:
            logger.error("Socket timeout while waiting for response from Ableton")
            self.sock = None
            raise Exception("Timeout waiting for Ableton response")
        except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
            logger.error(f"Socket connection error: {str(e)}")
            self.sock = None
            raise Exception(f"Connection to Ableton lost: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Ableton: {str(e)}")
            if 'response_data' in locals() and response_data:
                logger.error(f"Raw response (first 200 bytes): {response_data[:200]}")
            self.sock = None
            raise Exception(f"Invalid response from Ableton: {str(e)}")
        except Exception as e:
            logger.error(f"Error communicating with Ableton: {str(e)}")
            self.sock = None
            raise Exception(f"Communication error with Ableton: {str(e)}")

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage server startup and shutdown lifecycle"""
    try:
        logger.info("AbletonMCP UPGRADED server starting up")
        
        try:
            ableton = get_ableton_connection()
            logger.info("Successfully connected to Ableton on startup")
        except Exception as e:
            logger.warning(f"Could not connect to Ableton on startup: {str(e)}")
            logger.warning("Make sure the Ableton Remote Script is running")
        
        yield {}
    finally:
        global _ableton_connection
        if _ableton_connection:
            logger.info("Disconnecting from Ableton on shutdown")
            _ableton_connection.disconnect()
            _ableton_connection = None
        logger.info("AbletonMCP server shut down")

# Create the MCP server with lifespan support
mcp = FastMCP(
    "AbletonMCP",
    description="Ableton Live integration through MCP - UPGRADED for melodic techno production",
    lifespan=server_lifespan
)

# Global connection for resources
_ableton_connection = None

def get_ableton_connection():
    """Get or create a persistent Ableton connection"""
    global _ableton_connection
    
    if _ableton_connection is not None:
        try:
            _ableton_connection.sock.settimeout(1.0)
            _ableton_connection.sock.sendall(b'')
            return _ableton_connection
        except Exception as e:
            logger.warning(f"Existing connection is no longer valid: {str(e)}")
            try:
                _ableton_connection.disconnect()
            except:
                pass
            _ableton_connection = None
    
    if _ableton_connection is None:
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Connecting to Ableton (attempt {attempt}/{max_attempts})...")
                _ableton_connection = AbletonConnection(host="localhost", port=9877)
                if _ableton_connection.connect():
                    logger.info("Created new persistent connection to Ableton")
                    
                    try:
                        _ableton_connection.send_command("get_session_info")
                        logger.info("Connection validated successfully")
                        return _ableton_connection
                    except Exception as e:
                        logger.error(f"Connection validation failed: {str(e)}")
                        _ableton_connection.disconnect()
                        _ableton_connection = None
                else:
                    _ableton_connection = None
            except Exception as e:
                logger.error(f"Connection attempt {attempt} failed: {str(e)}")
                if _ableton_connection:
                    _ableton_connection.disconnect()
                    _ableton_connection = None
            
            if attempt < max_attempts:
                import time
                time.sleep(1.0)
        
        if _ableton_connection is None:
            logger.error("Failed to connect to Ableton after multiple attempts")
            raise Exception("Could not connect to Ableton. Make sure the Remote Script is running.")
    
    return _ableton_connection


# ============================================
# SESSION INFO TOOLS
# ============================================

@mcp.tool()
def get_session_info(ctx: Context) -> str:
    """Get detailed information about the current Ableton session including all tracks, tempo, and playing state."""
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("get_session_info")
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error getting session info from Ableton: {str(e)}")
        return f"Error getting session info: {str(e)}"

@mcp.tool()
def get_track_info(ctx: Context, track_index: int) -> str:
    """
    Get detailed information about a specific track including clips, devices, and mixer settings.
    
    Parameters:
    - track_index: The index of the track (0-based)
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("get_track_info", {"track_index": track_index})
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error getting track info from Ableton: {str(e)}")
        return f"Error getting track info: {str(e)}"


# ============================================
# TRACK MANAGEMENT TOOLS
# ============================================

@mcp.tool()
def create_midi_track(ctx: Context, index: int = -1) -> str:
    """
    Create a new MIDI track in the Ableton session.
    
    Parameters:
    - index: The index to insert the track at (-1 = end of list)
    
    Note: Ableton Lite has a maximum of 8 tracks.
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("create_midi_track", {"index": index})
        return f"Created new MIDI track '{result.get('name', 'unknown')}' at index {result.get('index')}. Total tracks: {result.get('total_tracks')}"
    except Exception as e:
        logger.error(f"Error creating MIDI track: {str(e)}")
        return f"Error creating MIDI track: {str(e)}"

@mcp.tool()
def set_track_name(ctx: Context, track_index: int, name: str) -> str:
    """
    Set the name of a track.
    
    Parameters:
    - track_index: The index of the track to rename
    - name: The new name for the track
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("set_track_name", {"track_index": track_index, "name": name})
        return f"Renamed track to: {result.get('name', name)}"
    except Exception as e:
        logger.error(f"Error setting track name: {str(e)}")
        return f"Error setting track name: {str(e)}"

@mcp.tool()
def mute_track(ctx: Context, track_index: int, mute: bool = True) -> str:
    """
    Mute or unmute a track.
    
    Parameters:
    - track_index: The index of the track
    - mute: True to mute, False to unmute
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("mute_track", {"track_index": track_index, "mute": mute})
        return f"Track {track_index} {'muted' if result.get('mute') else 'unmuted'}"
    except Exception as e:
        logger.error(f"Error muting track: {str(e)}")
        return f"Error muting track: {str(e)}"

@mcp.tool()
def solo_track(ctx: Context, track_index: int, solo: bool = True) -> str:
    """
    Solo or unsolo a track.
    
    Parameters:
    - track_index: The index of the track
    - solo: True to solo, False to unsolo
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("solo_track", {"track_index": track_index, "solo": solo})
        return f"Track {track_index} {'soloed' if result.get('solo') else 'unsoloed'}"
    except Exception as e:
        logger.error(f"Error soloing track: {str(e)}")
        return f"Error soloing track: {str(e)}"

@mcp.tool()
def arm_track(ctx: Context, track_index: int, arm: bool = True) -> str:
    """
    Arm or disarm a track for recording.
    
    Parameters:
    - track_index: The index of the track
    - arm: True to arm, False to disarm
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("arm_track", {"track_index": track_index, "arm": arm})
        return f"Track {track_index} {'armed' if result.get('arm') else 'disarmed'}"
    except Exception as e:
        logger.error(f"Error arming track: {str(e)}")
        return f"Error arming track: {str(e)}"


# ============================================
# CLIP MANAGEMENT TOOLS
# ============================================

@mcp.tool()
def list_clips(ctx: Context, track_index: int) -> str:
    """
    List all clips in a track with their details (name, length, note count).
    
    Parameters:
    - track_index: The index of the track
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("list_clips", {"track_index": track_index})
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error listing clips: {str(e)}")
        return f"Error listing clips: {str(e)}"

@mcp.tool()
def create_clip(ctx: Context, track_index: int, clip_index: int, length: float = 4.0) -> str:
    """
    Create a new MIDI clip in the specified track and clip slot.
    
    Parameters:
    - track_index: The index of the track to create the clip in
    - clip_index: The index of the clip slot to create the clip in
    - length: The length of the clip in beats (default: 4.0)
    
    Common lengths:
    - 4 beats = 1 bar
    - 16 beats = 4 bars
    - 32 beats = 8 bars (good for phrases)
    - 64 beats = 16 bars (intro/outro)
    - 128 beats = 32 bars (full section)
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("create_clip", {
            "track_index": track_index, 
            "clip_index": clip_index, 
            "length": length
        })
        return f"Created new clip at track {track_index}, slot {clip_index} with length {length} beats"
    except Exception as e:
        logger.error(f"Error creating clip: {str(e)}")
        return f"Error creating clip: {str(e)}"

@mcp.tool()
def delete_clip(ctx: Context, track_index: int, clip_index: int) -> str:
    """
    Delete a clip from a clip slot.
    
    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("delete_clip", {
            "track_index": track_index,
            "clip_index": clip_index
        })
        if result.get("deleted"):
            return f"Deleted clip at track {track_index}, slot {clip_index}"
        else:
            return f"No clip to delete at track {track_index}, slot {clip_index}"
    except Exception as e:
        logger.error(f"Error deleting clip: {str(e)}")
        return f"Error deleting clip: {str(e)}"

@mcp.tool()
def clear_clip(ctx: Context, track_index: int, clip_index: int) -> str:
    """
    Clear all notes from a clip (keeps the clip, removes notes).
    
    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("clear_clip", {
            "track_index": track_index,
            "clip_index": clip_index
        })
        return f"Cleared all notes from clip '{result.get('clip_name')}'"
    except Exception as e:
        logger.error(f"Error clearing clip: {str(e)}")
        return f"Error clearing clip: {str(e)}"

@mcp.tool()
def duplicate_clip(ctx: Context, track_index: int, clip_index: int, target_slot: int = None) -> str:
    """
    Duplicate a clip to another slot.
    
    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the source clip slot
    - target_slot: The target slot index (None = first empty slot)
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("duplicate_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "target_slot": target_slot
        })
        return f"Duplicated clip to slot {result.get('target_slot')}: '{result.get('clip_name')}'"
    except Exception as e:
        logger.error(f"Error duplicating clip: {str(e)}")
        return f"Error duplicating clip: {str(e)}"

@mcp.tool()
def set_clip_name(ctx: Context, track_index: int, clip_index: int, name: str) -> str:
    """
    Set the name of a clip.
    
    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - name: The new name for the clip
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_name", {
            "track_index": track_index,
            "clip_index": clip_index,
            "name": name
        })
        return f"Renamed clip at track {track_index}, slot {clip_index} to '{name}'"
    except Exception as e:
        logger.error(f"Error setting clip name: {str(e)}")
        return f"Error setting clip name: {str(e)}"

@mcp.tool()
def set_clip_loop(ctx: Context, track_index: int, clip_index: int, loop_start: float = 0.0, loop_end: float = None) -> str:
    """
    Set loop points for a clip.
    
    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot
    - loop_start: Loop start point in beats (default: 0)
    - loop_end: Loop end point in beats (None = clip length)
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_loop", {
            "track_index": track_index,
            "clip_index": clip_index,
            "loop_start": loop_start,
            "loop_end": loop_end
        })
        return f"Set loop points: {result.get('loop_start')} - {result.get('loop_end')} beats"
    except Exception as e:
        logger.error(f"Error setting clip loop: {str(e)}")
        return f"Error setting clip loop: {str(e)}"


# ============================================
# NOTE MANAGEMENT TOOLS (WITH HUMANIZATION)
# ============================================

@mcp.tool()
def get_clip_notes(ctx: Context, track_index: int, clip_index: int) -> str:
    """
    Get all MIDI notes from a clip.
    
    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot
    
    Returns a list of notes with pitch, start_time, duration, velocity.
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("get_clip_notes", {
            "track_index": track_index,
            "clip_index": clip_index
        })
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error getting clip notes: {str(e)}")
        return f"Error getting clip notes: {str(e)}"

@mcp.tool()
def add_notes_to_clip(
    ctx: Context, 
    track_index: int, 
    clip_index: int, 
    notes: List[Dict[str, Union[int, float, bool]]],
    humanize: bool = False
) -> str:
    """
    Add MIDI notes to a clip (appends to existing notes).
    
    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - notes: List of note dictionaries with:
        - pitch: MIDI note number (0-127, 60=C4)
        - start_time: Start position in beats
        - duration: Note length in beats
        - velocity: Note velocity (1-127)
        - mute: Whether note is muted (optional, default False)
        - start_time_offset_ms: Timing offset in milliseconds for humanization (optional)
        - velocity_offset: Velocity adjustment for humanization (optional)
    - humanize: Whether to apply random humanization (timing ±10ms, velocity ±15)
    
    Common MIDI pitches:
    - Kick: 36 (C1)
    - Snare: 38 (D1)
    - Closed HH: 42 (F#1)
    - Open HH: 46 (A#1)
    - Bass notes: 24-48 (C0-C3)
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
            "humanize": humanize
        })
        return f"Added {result.get('added_count')} notes to clip '{result.get('clip_name')}' (total: {result.get('total_notes')})"
    except Exception as e:
        logger.error(f"Error adding notes to clip: {str(e)}")
        return f"Error adding notes to clip: {str(e)}"

@mcp.tool()
def replace_clip_notes(
    ctx: Context, 
    track_index: int, 
    clip_index: int, 
    notes: List[Dict[str, Union[int, float, bool]]],
    humanize: bool = False
) -> str:
    """
    Replace all notes in a clip (clears existing notes first, then adds new ones).
    
    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - notes: List of note dictionaries (same format as add_notes_to_clip)
    - humanize: Whether to apply random humanization
    
    Use this when you want to completely replace the clip content.
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("replace_clip_notes", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
            "humanize": humanize
        })
        return f"Replaced clip '{result.get('clip_name')}' with {result.get('note_count')} notes"
    except Exception as e:
        logger.error(f"Error replacing clip notes: {str(e)}")
        return f"Error replacing clip notes: {str(e)}"

@mcp.tool()
def delete_notes(
    ctx: Context,
    track_index: int,
    clip_index: int,
    pitch_min: int = 0,
    pitch_max: int = 127,
    time_start: float = 0.0,
    time_end: float = None
) -> str:
    """
    Delete notes within a pitch and time range.
    
    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot
    - pitch_min: Minimum pitch to delete (default: 0)
    - pitch_max: Maximum pitch to delete (default: 127)
    - time_start: Start time in beats (default: 0)
    - time_end: End time in beats (None = clip end)
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("delete_notes", {
            "track_index": track_index,
            "clip_index": clip_index,
            "pitch_min": pitch_min,
            "pitch_max": pitch_max,
            "time_start": time_start,
            "time_end": time_end
        })
        return f"Deleted notes in pitch range {pitch_min}-{pitch_max}, time range {time_start}-{result.get('time_range', [0, 0])[1]}"
    except Exception as e:
        logger.error(f"Error deleting notes: {str(e)}")
        return f"Error deleting notes: {str(e)}"


# ============================================
# MIXER CONTROL TOOLS
# ============================================

@mcp.tool()
def set_track_volume(ctx: Context, track_index: int, volume: float) -> str:
    """
    Set the volume of a track.
    
    Parameters:
    - track_index: The index of the track
    - volume: Volume level (0.0 to 1.0, where 0.85 is roughly 0dB)
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("set_track_volume", {
            "track_index": track_index,
            "volume": volume
        })
        return f"Set track {track_index} volume to {result.get('volume')}"
    except Exception as e:
        logger.error(f"Error setting track volume: {str(e)}")
        return f"Error setting track volume: {str(e)}"

@mcp.tool()
def set_track_pan(ctx: Context, track_index: int, pan: float) -> str:
    """
    Set the panning of a track.
    
    Parameters:
    - track_index: The index of the track
    - pan: Pan position (-1.0 = full left, 0.0 = center, 1.0 = full right)
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("set_track_pan", {
            "track_index": track_index,
            "pan": pan
        })
        return f"Set track {track_index} pan to {result.get('pan')}"
    except Exception as e:
        logger.error(f"Error setting track pan: {str(e)}")
        return f"Error setting track pan: {str(e)}"

@mcp.tool()
def set_track_send(ctx: Context, track_index: int, send_index: int, value: float) -> str:
    """
    Set a send level for a track (for reverb/delay sends).
    
    Parameters:
    - track_index: The index of the track
    - send_index: The index of the send (0 = Send A, 1 = Send B, etc.)
    - value: Send level (0.0 to 1.0)
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("set_track_send", {
            "track_index": track_index,
            "send_index": send_index,
            "value": value
        })
        return f"Set track {track_index} send {send_index} to {result.get('value')}"
    except Exception as e:
        logger.error(f"Error setting track send: {str(e)}")
        return f"Error setting track send: {str(e)}"


# ============================================
# DEVICE PARAMETER TOOLS
# ============================================

@mcp.tool()
def get_device_parameters(ctx: Context, track_index: int, device_index: int) -> str:
    """
    Get all parameters of a device on a track.
    
    Parameters:
    - track_index: The index of the track
    - device_index: The index of the device on the track
    
    Returns a list of all parameters with their current values and ranges.
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("get_device_parameters", {
            "track_index": track_index,
            "device_index": device_index
        })
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error getting device parameters: {str(e)}")
        return f"Error getting device parameters: {str(e)}"

@mcp.tool()
def set_device_param(
    ctx: Context,
    track_index: int,
    device_index: int,
    value: float,
    param_index: int = None,
    param_name: str = None
) -> str:
    """
    Set a device parameter by index or name.
    
    Parameters:
    - track_index: The index of the track
    - device_index: The index of the device on the track
    - value: The new value for the parameter
    - param_index: The index of the parameter (if not using param_name)
    - param_name: The name of the parameter (alternative to param_index)
    
    Use get_device_parameters first to see available parameters.
    """
    try:
        ableton = get_ableton_connection()
        params = {
            "track_index": track_index,
            "device_index": device_index,
            "value": value
        }
        if param_name:
            params["param_name"] = param_name
        if param_index is not None:
            params["param_index"] = param_index
            
        result = ableton.send_command("set_device_param", params)
        return f"Set '{result.get('parameter_name')}' to {result.get('value')} on device '{result.get('device_name')}'"
    except Exception as e:
        logger.error(f"Error setting device parameter: {str(e)}")
        return f"Error setting device parameter: {str(e)}"


# ============================================
# TRANSPORT CONTROLS
# ============================================

@mcp.tool()
def set_tempo(ctx: Context, tempo: float) -> str:
    """
    Set the tempo of the Ableton session.
    
    Parameters:
    - tempo: The new tempo in BPM (20-999)
    
    Common tempos for melodic techno: 120-123 BPM
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("set_tempo", {"tempo": tempo})
        return f"Set tempo to {result.get('tempo', tempo)} BPM"
    except Exception as e:
        logger.error(f"Error setting tempo: {str(e)}")
        return f"Error setting tempo: {str(e)}"

@mcp.tool()
def fire_clip(ctx: Context, track_index: int, clip_index: int) -> str:
    """
    Start playing a clip.
    
    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("fire_clip", {
            "track_index": track_index,
            "clip_index": clip_index
        })
        return f"Started playing clip at track {track_index}, slot {clip_index}"
    except Exception as e:
        logger.error(f"Error firing clip: {str(e)}")
        return f"Error firing clip: {str(e)}"

@mcp.tool()
def stop_clip(ctx: Context, track_index: int, clip_index: int) -> str:
    """
    Stop playing a clip.
    
    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("stop_clip", {
            "track_index": track_index,
            "clip_index": clip_index
        })
        return f"Stopped clip at track {track_index}, slot {clip_index}"
    except Exception as e:
        logger.error(f"Error stopping clip: {str(e)}")
        return f"Error stopping clip: {str(e)}"

@mcp.tool()
def start_playback(ctx: Context) -> str:
    """Start playing the Ableton session."""
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("start_playback")
        return "Started playback"
    except Exception as e:
        logger.error(f"Error starting playback: {str(e)}")
        return f"Error starting playback: {str(e)}"

@mcp.tool()
def stop_playback(ctx: Context) -> str:
    """Stop playing the Ableton session."""
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("stop_playback")
        return "Stopped playback"
    except Exception as e:
        logger.error(f"Error stopping playback: {str(e)}")
        return f"Error stopping playback: {str(e)}"


# ============================================
# SCENE MANAGEMENT
# ============================================

@mcp.tool()
def create_scene(ctx: Context, index: int = -1) -> str:
    """
    Create a new scene.
    
    Parameters:
    - index: The index to insert the scene at (-1 = end)
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("create_scene", {"index": index})
        return f"Created scene at index {result.get('index')}. Total scenes: {result.get('scene_count')}"
    except Exception as e:
        logger.error(f"Error creating scene: {str(e)}")
        return f"Error creating scene: {str(e)}"


# ============================================
# BROWSER AND INSTRUMENT LOADING
# ============================================

@mcp.tool()
def load_instrument_or_effect(ctx: Context, track_index: int, uri: str) -> str:
    """
    Load an instrument or effect onto a track using its URI.
    
    Parameters:
    - track_index: The index of the track to load the instrument on
    - uri: The URI of the instrument or effect to load
    
    Use get_browser_items_at_path to find available instruments and their URIs.
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("load_browser_item", {
            "track_index": track_index,
            "item_uri": uri
        })
        
        if result.get("loaded", False):
            return f"Loaded '{result.get('item_name')}' on track '{result.get('track_name')}'"
        else:
            return f"Failed to load instrument with URI '{uri}'"
    except Exception as e:
        logger.error(f"Error loading instrument by URI: {str(e)}")
        return f"Error loading instrument by URI: {str(e)}"

@mcp.tool()
def get_browser_tree(ctx: Context, category_type: str = "all") -> str:
    """
    Get a hierarchical tree of browser categories from Ableton.
    
    Parameters:
    - category_type: Type of categories to get ('all', 'instruments', 'sounds', 'drums', 'audio_effects', 'midi_effects')
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("get_browser_tree", {
            "category_type": category_type
        })
        
        if "available_categories" in result and len(result.get("categories", [])) == 0:
            available_cats = result.get("available_categories", [])
            return (f"No categories found for '{category_type}'. "
                   f"Available browser categories: {', '.join(available_cats)}")
        
        total_folders = result.get("total_folders", 0)
        formatted_output = f"Browser tree for '{category_type}':\n\n"
        
        def format_tree(item, indent=0):
            output = ""
            if item:
                prefix = "  " * indent
                name = item.get("name", "Unknown")
                is_loadable = item.get("is_loadable", False)
                uri = item.get("uri", "")
                
                output += f"{prefix}• {name}"
                if is_loadable:
                    output += " [loadable]"
                if uri:
                    output += f"\n{prefix}  URI: {uri}"
                output += "\n"
                
                for child in item.get("children", []):
                    output += format_tree(child, indent + 1)
            return output
        
        for category in result.get("categories", []):
            formatted_output += format_tree(category)
            formatted_output += "\n"
        
        return formatted_output
    except Exception as e:
        error_msg = str(e)
        if "Browser is not available" in error_msg:
            return f"Error: The Ableton browser is not available. Make sure Ableton Live is fully loaded."
        elif "Could not access Live application" in error_msg:
            return f"Error: Could not access the Ableton Live application."
        else:
            logger.error(f"Error getting browser tree: {error_msg}")
            return f"Error getting browser tree: {error_msg}"

@mcp.tool()
def get_browser_items_at_path(ctx: Context, path: str) -> str:
    """
    Get browser items at a specific path in Ableton's browser.
    
    Parameters:
    - path: Path in the format "category/folder/subfolder"
            where category is one of: instruments, sounds, drums, audio_effects, midi_effects
    
    Examples:
    - "instruments" - list all instrument categories
    - "sounds/Bass" - list bass sounds
    - "drums/Drum Rack" - list drum racks
    """
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("get_browser_items_at_path", {
            "path": path
        })
        
        if "error" in result and "available_categories" in result:
            error = result.get("error", "")
            available_cats = result.get("available_categories", [])
            return (f"Error: {error}\n"
                   f"Available browser categories: {', '.join(available_cats)}")
        
        return json.dumps(result, indent=2)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error getting browser items at path: {error_msg}")
        return f"Error getting browser items at path: {error_msg}"

@mcp.tool()
def load_drum_kit(ctx: Context, track_index: int, rack_uri: str, kit_path: str) -> str:
    """
    Load a drum rack and then load a specific drum kit into it.
    
    Parameters:
    - track_index: The index of the track to load on
    - rack_uri: The URI of the drum rack to load
    - kit_path: Path to the drum kit inside the browser
    """
    try:
        ableton = get_ableton_connection()
        
        result = ableton.send_command("load_browser_item", {
            "track_index": track_index,
            "item_uri": rack_uri
        })
        
        if not result.get("loaded", False):
            return f"Failed to load drum rack with URI '{rack_uri}'"
        
        kit_result = ableton.send_command("get_browser_items_at_path", {
            "path": kit_path
        })
        
        if "error" in kit_result:
            return f"Loaded drum rack but failed to find drum kit: {kit_result.get('error')}"
        
        kit_items = kit_result.get("items", [])
        loadable_kits = [item for item in kit_items if item.get("is_loadable", False)]
        
        if not loadable_kits:
            return f"Loaded drum rack but no loadable drum kits found at '{kit_path}'"
        
        kit_uri = loadable_kits[0].get("uri")
        load_result = ableton.send_command("load_browser_item", {
            "track_index": track_index,
            "item_uri": kit_uri
        })
        
        return f"Loaded drum rack and kit '{loadable_kits[0].get('name')}' on track {track_index}"
    except Exception as e:
        logger.error(f"Error loading drum kit: {str(e)}")
        return f"Error loading drum kit: {str(e)}"


# ============================================
# MAIN EXECUTION
# ============================================

def main():
    """Run the MCP server"""
    mcp.run()

if __name__ == "__main__":
    main()
