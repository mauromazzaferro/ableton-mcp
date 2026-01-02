# AbletonMCP/init.py - UPGRADED VERSION
# Enhanced 
from __future__ import absolute_import, print_function, unicode_literals

from _Framework.ControlSurface import ControlSurface
import socket
import json
import threading
import time
import traceback
import random

# Change queue import for Python 2
try:
    import Queue as queue  # Python 2
except ImportError:
    import queue  # Python 3

# Constants for socket communication
DEFAULT_PORT = 9877
HOST = "localhost"

def create_instance(c_instance):
    """Create and return the AbletonMCP script instance"""
    return AbletonMCP(c_instance)

class AbletonMCP(ControlSurface):
    """AbletonMCP Remote Script for Ableton Live - UPGRADED"""
    
    def __init__(self, c_instance):
        """Initialize the control surface"""
        ControlSurface.__init__(self, c_instance)
        self.log_message("AbletonMCP Remote Script initializing (UPGRADED)...")
        
        # Socket server for communication
        self.server = None
        self.client_threads = []
        self.server_thread = None
        self.running = False
        
        # Cache the song reference for easier access
        self._song = self.song()
        
        # Start the socket server
        self.start_server()
        
        self.log_message("AbletonMCP initialized (UPGRADED)")
        
        # Show a message in Ableton
        self.show_message("AbletonMCP UPGRADED: Listening on port " + str(DEFAULT_PORT))
    
    def disconnect(self):
        """Called when Ableton closes or the control surface is removed"""
        self.log_message("AbletonMCP disconnecting...")
        self.running = False
        
        # Stop the server
        if self.server:
            try:
                self.server.close()
            except:
                pass
        
        # Wait for the server thread to exit
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(1.0)
            
        # Clean up any client threads
        for client_thread in self.client_threads[:]:
            if client_thread.is_alive():
                self.log_message("Client thread still alive during disconnect")
        
        ControlSurface.disconnect(self)
        self.log_message("AbletonMCP disconnected")
    
    def start_server(self):
        """Start the socket server in a separate thread"""
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind((HOST, DEFAULT_PORT))
            self.server.listen(5)
            
            self.running = True
            self.server_thread = threading.Thread(target=self._server_thread)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            self.log_message("Server started on port " + str(DEFAULT_PORT))
        except Exception as e:
            self.log_message("Error starting server: " + str(e))
            self.show_message("AbletonMCP: Error starting server - " + str(e))
    
    def _server_thread(self):
        """Server thread implementation - handles client connections"""
        try:
            self.log_message("Server thread started")
            self.server.settimeout(1.0)
            
            while self.running:
                try:
                    client, address = self.server.accept()
                    self.log_message("Connection accepted from " + str(address))
                    self.show_message("AbletonMCP: Client connected")
                    
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client,)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                    self.client_threads.append(client_thread)
                    self.client_threads = [t for t in self.client_threads if t.is_alive()]
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.log_message("Server accept error: " + str(e))
                    time.sleep(0.5)
            
            self.log_message("Server thread stopped")
        except Exception as e:
            self.log_message("Server thread error: " + str(e))
    
    def _handle_client(self, client):
        """Handle communication with a connected client"""
        self.log_message("Client handler started")
        client.settimeout(None)
        buffer = ''
        
        try:
            while self.running:
                try:
                    data = client.recv(8192)
                    
                    if not data:
                        self.log_message("Client disconnected")
                        break
                    
                    try:
                        buffer += data.decode('utf-8')
                    except AttributeError:
                        buffer += data
                    
                    try:
                        command = json.loads(buffer)
                        buffer = ''
                        
                        self.log_message("Received command: " + str(command.get("type", "unknown")))
                        
                        response = self._process_command(command)
                        
                        try:
                            client.sendall(json.dumps(response).encode('utf-8'))
                        except AttributeError:
                            client.sendall(json.dumps(response))
                    except ValueError:
                        continue
                        
                except Exception as e:
                    self.log_message("Error handling client data: " + str(e))
                    self.log_message(traceback.format_exc())
                    
                    error_response = {
                        "status": "error",
                        "message": str(e)
                    }
                    try:
                        client.sendall(json.dumps(error_response).encode('utf-8'))
                    except AttributeError:
                        client.sendall(json.dumps(error_response))
                    except:
                        break
                    
                    if not isinstance(e, ValueError):
                        break
        except Exception as e:
            self.log_message("Error in client handler: " + str(e))
        finally:
            try:
                client.close()
            except:
                pass
            self.log_message("Client handler stopped")
    
    def _process_command(self, command):
        """Process a command from the client and return a response"""
        command_type = command.get("type", "")
        params = command.get("params", {})
        
        response = {
            "status": "success",
            "result": {}
        }
        
        # List of commands that modify Live's state (need main thread)
        modifying_commands = [
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
            # Read-only commands (can run on any thread)
            if command_type == "get_session_info":
                response["result"] = self._get_session_info()
            elif command_type == "get_track_info":
                track_index = params.get("track_index", 0)
                response["result"] = self._get_track_info(track_index)
            elif command_type == "list_clips":
                track_index = params.get("track_index", 0)
                response["result"] = self._list_clips(track_index)
            elif command_type == "get_clip_notes":
                track_index = params.get("track_index", 0)
                clip_index = params.get("clip_index", 0)
                response["result"] = self._get_clip_notes(track_index, clip_index)
            elif command_type == "get_device_parameters":
                track_index = params.get("track_index", 0)
                device_index = params.get("device_index", 0)
                response["result"] = self._get_device_parameters(track_index, device_index)
            elif command_type == "get_browser_tree":
                category_type = params.get("category_type", "all")
                response["result"] = self.get_browser_tree(category_type)
            elif command_type == "get_browser_items_at_path":
                path = params.get("path", "")
                response["result"] = self.get_browser_items_at_path(path)
            elif command_type == "get_browser_item":
                uri = params.get("uri", None)
                path = params.get("path", None)
                response["result"] = self._get_browser_item(uri, path)
            elif command_type == "get_browser_categories":
                category_type = params.get("category_type", "all")
                response["result"] = self._get_browser_categories(category_type)
            elif command_type == "get_browser_items":
                path = params.get("path", "")
                item_type = params.get("item_type", "all")
                response["result"] = self._get_browser_items(path, item_type)
            
            # State-modifying commands (must run on main thread)
            elif command_type in modifying_commands:
                response_queue = queue.Queue()
                
                def main_thread_task():
                    try:
                        result = self._execute_modifying_command(command_type, params)
                        response_queue.put({"status": "success", "result": result})
                    except Exception as e:
                        self.log_message("Error in main thread task: " + str(e))
                        self.log_message(traceback.format_exc())
                        response_queue.put({"status": "error", "message": str(e)})
                
                try:
                    self.schedule_message(0, main_thread_task)
                except AssertionError:
                    main_thread_task()
                
                try:
                    task_response = response_queue.get(timeout=15.0)
                    if task_response.get("status") == "error":
                        response["status"] = "error"
                        response["message"] = task_response.get("message", "Unknown error")
                    else:
                        response["result"] = task_response.get("result", {})
                except queue.Empty:
                    response["status"] = "error"
                    response["message"] = "Timeout waiting for operation to complete"
            else:
                response["status"] = "error"
                response["message"] = "Unknown command: " + command_type
                
        except Exception as e:
            self.log_message("Error processing command: " + str(e))
            self.log_message(traceback.format_exc())
            response["status"] = "error"
            response["message"] = str(e)
        
        return response
    
    def _execute_modifying_command(self, command_type, params):
        """Execute state-modifying commands on the main thread"""
        if command_type == "create_midi_track":
            index = params.get("index", -1)
            return self._create_midi_track(index)
        elif command_type == "set_track_name":
            track_index = params.get("track_index", 0)
            name = params.get("name", "")
            return self._set_track_name(track_index, name)
        elif command_type == "create_clip":
            track_index = params.get("track_index", 0)
            clip_index = params.get("clip_index", 0)
            length = params.get("length", 4.0)
            return self._create_clip(track_index, clip_index, length)
        elif command_type == "add_notes_to_clip":
            track_index = params.get("track_index", 0)
            clip_index = params.get("clip_index", 0)
            notes = params.get("notes", [])
            humanize = params.get("humanize", False)
            return self._add_notes_to_clip(track_index, clip_index, notes, humanize)
        elif command_type == "replace_clip_notes":
            track_index = params.get("track_index", 0)
            clip_index = params.get("clip_index", 0)
            notes = params.get("notes", [])
            humanize = params.get("humanize", False)
            return self._replace_clip_notes(track_index, clip_index, notes, humanize)
        elif command_type == "delete_notes":
            track_index = params.get("track_index", 0)
            clip_index = params.get("clip_index", 0)
            pitch_min = params.get("pitch_min", 0)
            pitch_max = params.get("pitch_max", 127)
            time_start = params.get("time_start", 0.0)
            time_end = params.get("time_end", None)
            return self._delete_notes(track_index, clip_index, pitch_min, pitch_max, time_start, time_end)
        elif command_type == "clear_clip":
            track_index = params.get("track_index", 0)
            clip_index = params.get("clip_index", 0)
            return self._clear_clip(track_index, clip_index)
        elif command_type == "delete_clip":
            track_index = params.get("track_index", 0)
            clip_index = params.get("clip_index", 0)
            return self._delete_clip(track_index, clip_index)
        elif command_type == "duplicate_clip":
            track_index = params.get("track_index", 0)
            clip_index = params.get("clip_index", 0)
            target_slot = params.get("target_slot", None)
            return self._duplicate_clip(track_index, clip_index, target_slot)
        elif command_type == "set_clip_name":
            track_index = params.get("track_index", 0)
            clip_index = params.get("clip_index", 0)
            name = params.get("name", "")
            return self._set_clip_name(track_index, clip_index, name)
        elif command_type == "set_clip_loop":
            track_index = params.get("track_index", 0)
            clip_index = params.get("clip_index", 0)
            loop_start = params.get("loop_start", 0.0)
            loop_end = params.get("loop_end", None)
            return self._set_clip_loop(track_index, clip_index, loop_start, loop_end)
        elif command_type == "set_tempo":
            tempo = params.get("tempo", 120.0)
            return self._set_tempo(tempo)
        elif command_type == "fire_clip":
            track_index = params.get("track_index", 0)
            clip_index = params.get("clip_index", 0)
            return self._fire_clip(track_index, clip_index)
        elif command_type == "stop_clip":
            track_index = params.get("track_index", 0)
            clip_index = params.get("clip_index", 0)
            return self._stop_clip(track_index, clip_index)
        elif command_type == "start_playback":
            return self._start_playback()
        elif command_type == "stop_playback":
            return self._stop_playback()
        elif command_type == "load_browser_item":
            track_index = params.get("track_index", 0)
            item_uri = params.get("item_uri", "")
            return self._load_browser_item(track_index, item_uri)
        elif command_type == "set_track_volume":
            track_index = params.get("track_index", 0)
            volume = params.get("volume", 0.85)
            return self._set_track_volume(track_index, volume)
        elif command_type == "set_track_pan":
            track_index = params.get("track_index", 0)
            pan = params.get("pan", 0.0)
            return self._set_track_pan(track_index, pan)
        elif command_type == "set_track_send":
            track_index = params.get("track_index", 0)
            send_index = params.get("send_index", 0)
            value = params.get("value", 0.0)
            return self._set_track_send(track_index, send_index, value)
        elif command_type == "set_device_param":
            track_index = params.get("track_index", 0)
            device_index = params.get("device_index", 0)
            param_index = params.get("param_index", 0)
            param_name = params.get("param_name", None)
            value = params.get("value", 0.5)
            return self._set_device_param(track_index, device_index, param_index, param_name, value)
        elif command_type == "mute_track":
            track_index = params.get("track_index", 0)
            mute = params.get("mute", True)
            return self._mute_track(track_index, mute)
        elif command_type == "solo_track":
            track_index = params.get("track_index", 0)
            solo = params.get("solo", True)
            return self._solo_track(track_index, solo)
        elif command_type == "arm_track":
            track_index = params.get("track_index", 0)
            arm = params.get("arm", True)
            return self._arm_track(track_index, arm)
        elif command_type == "create_scene":
            index = params.get("index", -1)
            return self._create_scene(index)
        else:
            raise ValueError("Unhandled modifying command: " + command_type)
    
    # ============================================
    # SESSION INFO
    # ============================================
    
    def _get_session_info(self):
        """Get information about the current session"""
        try:
            tracks_info = []
            for i, track in enumerate(self._song.tracks):
                tracks_info.append({
                    "index": i,
                    "name": track.name,
                    "is_midi": track.has_midi_input,
                    "is_audio": track.has_audio_input,
                    "mute": track.mute,
                    "solo": track.solo,
                    "arm": track.arm if hasattr(track, 'arm') else False,
                    "clip_slot_count": len(track.clip_slots),
                    "device_count": len(track.devices)
                })
            
            result = {
                "tempo": self._song.tempo,
                "signature_numerator": self._song.signature_numerator,
                "signature_denominator": self._song.signature_denominator,
                "track_count": len(self._song.tracks),
                "return_track_count": len(self._song.return_tracks),
                "scene_count": len(self._song.scenes),
                "is_playing": self._song.is_playing,
                "tracks": tracks_info,
                "master_track": {
                    "name": "Master",
                    "volume": self._song.master_track.mixer_device.volume.value,
                    "panning": self._song.master_track.mixer_device.panning.value
                }
            }
            return result
        except Exception as e:
            self.log_message("Error getting session info: " + str(e))
            raise
    
    def _get_track_info(self, track_index):
        """Get detailed information about a track"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range: {0} (max: {1})".format(
                    track_index, len(self._song.tracks) - 1))
            
            track = self._song.tracks[track_index]
            
            # Get clip slots info
            clip_slots = []
            for slot_index, slot in enumerate(track.clip_slots):
                clip_info = None
                if slot.has_clip:
                    clip = slot.clip
                    clip_info = {
                        "name": clip.name,
                        "length": clip.length,
                        "is_playing": clip.is_playing,
                        "is_recording": clip.is_recording,
                        "loop_start": clip.loop_start if hasattr(clip, 'loop_start') else 0,
                        "loop_end": clip.loop_end if hasattr(clip, 'loop_end') else clip.length,
                        "is_midi_clip": clip.is_midi_clip if hasattr(clip, 'is_midi_clip') else True
                    }
                
                clip_slots.append({
                    "index": slot_index,
                    "has_clip": slot.has_clip,
                    "clip": clip_info
                })
            
            # Get devices info
            devices = []
            for device_index, device in enumerate(track.devices):
                params = []
                if hasattr(device, 'parameters'):
                    for param_idx, param in enumerate(device.parameters):
                        params.append({
                            "index": param_idx,
                            "name": param.name,
                            "value": param.value,
                            "min": param.min,
                            "max": param.max,
                            "is_enabled": param.is_enabled if hasattr(param, 'is_enabled') else True
                        })
                
                devices.append({
                    "index": device_index,
                    "name": device.name,
                    "class_name": device.class_name,
                    "type": self._get_device_type(device),
                    "is_active": device.is_active if hasattr(device, 'is_active') else True,
                    "parameters": params
                })
            
            # Get sends info
            sends = []
            if hasattr(track.mixer_device, 'sends'):
                for send_idx, send in enumerate(track.mixer_device.sends):
                    sends.append({
                        "index": send_idx,
                        "name": send.name,
                        "value": send.value
                    })
            
            result = {
                "index": track_index,
                "name": track.name,
                "is_audio_track": track.has_audio_input,
                "is_midi_track": track.has_midi_input,
                "mute": track.mute,
                "solo": track.solo,
                "arm": track.arm if hasattr(track, 'arm') else False,
                "volume": track.mixer_device.volume.value,
                "panning": track.mixer_device.panning.value,
                "sends": sends,
                "clip_slots": clip_slots,
                "devices": devices
            }
            return result
        except Exception as e:
            self.log_message("Error getting track info: " + str(e))
            raise
    
    # ============================================
    # CLIP MANAGEMENT
    # ============================================
    
    def _list_clips(self, track_index):
        """List all clips in a track with details"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range: {0}".format(track_index))
            
            track = self._song.tracks[track_index]
            clips = []
            
            for slot_index, slot in enumerate(track.clip_slots):
                if slot.has_clip:
                    clip = slot.clip
                    note_count = 0
                    if hasattr(clip, 'is_midi_clip') and clip.is_midi_clip:
                        try:
                            notes = clip.get_notes(0, 0, clip.length, 128)
                            note_count = len(notes) if notes else 0
                        except:
                            pass
                    
                    clips.append({
                        "slot_index": slot_index,
                        "name": clip.name,
                        "length": clip.length,
                        "is_playing": clip.is_playing,
                        "is_midi_clip": clip.is_midi_clip if hasattr(clip, 'is_midi_clip') else True,
                        "note_count": note_count,
                        "loop_start": clip.loop_start if hasattr(clip, 'loop_start') else 0,
                        "loop_end": clip.loop_end if hasattr(clip, 'loop_end') else clip.length
                    })
            
            return {
                "track_index": track_index,
                "track_name": track.name,
                "clip_count": len(clips),
                "clips": clips
            }
        except Exception as e:
            self.log_message("Error listing clips: " + str(e))
            raise
    
    def _get_clip_notes(self, track_index, clip_index):
        """Get all notes from a clip"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            
            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")
            
            clip_slot = track.clip_slots[clip_index]
            
            if not clip_slot.has_clip:
                raise Exception("No clip in slot {0}".format(clip_index))
            
            clip = clip_slot.clip
            
            if not hasattr(clip, 'is_midi_clip') or not clip.is_midi_clip:
                raise Exception("Clip is not a MIDI clip")
            
            # Get all notes from the clip
            notes = clip.get_notes(0, 0, clip.length, 128)
            
            notes_list = []
            if notes:
                for note in notes:
                    notes_list.append({
                        "pitch": note[0],
                        "start_time": note[1],
                        "duration": note[2],
                        "velocity": note[3],
                        "mute": note[4] if len(note) > 4 else False
                    })
            
            return {
                "track_index": track_index,
                "clip_index": clip_index,
                "clip_name": clip.name,
                "clip_length": clip.length,
                "note_count": len(notes_list),
                "notes": notes_list
            }
        except Exception as e:
            self.log_message("Error getting clip notes: " + str(e))
            raise
    
    def _create_midi_track(self, index):
        """Create a new MIDI track at the specified index"""
        try:
            # Check if we're at track limit (Lite = 8 tracks)
            current_count = len(self._song.tracks)
            
            self._song.create_midi_track(index)
            
            new_track_index = len(self._song.tracks) - 1 if index == -1 else index
            new_track = self._song.tracks[new_track_index]
            
            result = {
                "index": new_track_index,
                "name": new_track.name,
                "total_tracks": len(self._song.tracks)
            }
            return result
        except Exception as e:
            error_msg = str(e)
            if "couldn't create" in error_msg.lower() or "track limit" in error_msg.lower():
                raise Exception("Track limit reached. Ableton Lite supports max 8 tracks. Current: {0}".format(
                    len(self._song.tracks)))
            self.log_message("Error creating MIDI track: " + str(e))
            raise
    
    def _set_track_name(self, track_index, name):
        """Set the name of a track"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            track.name = name
            
            result = {
                "name": track.name
            }
            return result
        except Exception as e:
            self.log_message("Error setting track name: " + str(e))
            raise
    
    def _create_clip(self, track_index, clip_index, length):
        """Create a new MIDI clip in the specified track and clip slot"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range: {0} (available: 0-{1})".format(
                    track_index, len(self._song.tracks) - 1))
            
            track = self._song.tracks[track_index]
            
            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip slot index out of range: {0} (available: 0-{1})".format(
                    clip_index, len(track.clip_slots) - 1))
            
            clip_slot = track.clip_slots[clip_index]
            
            if clip_slot.has_clip:
                raise Exception("Clip slot {0} already has a clip. Use delete_clip first or choose slot {1}".format(
                    clip_index, self._find_empty_slot(track)))
            
            clip_slot.create_clip(length)
            
            result = {
                "name": clip_slot.clip.name,
                "length": clip_slot.clip.length,
                "track_index": track_index,
                "clip_index": clip_index
            }
            return result
        except Exception as e:
            self.log_message("Error creating clip: " + str(e))
            raise
    
    def _find_empty_slot(self, track):
        """Find the first empty clip slot in a track"""
        for i, slot in enumerate(track.clip_slots):
            if not slot.has_clip:
                return i
        return -1
    
    def _delete_clip(self, track_index, clip_index):
        """Delete a clip from a slot"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            
            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")
            
            clip_slot = track.clip_slots[clip_index]
            
            if not clip_slot.has_clip:
                return {"deleted": False, "message": "No clip in slot"}
            
            clip_slot.delete_clip()
            
            return {
                "deleted": True,
                "track_index": track_index,
                "clip_index": clip_index
            }
        except Exception as e:
            self.log_message("Error deleting clip: " + str(e))
            raise
    
    def _clear_clip(self, track_index, clip_index):
        """Clear all notes from a clip (keep the clip)"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            
            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")
            
            clip_slot = track.clip_slots[clip_index]
            
            if not clip_slot.has_clip:
                raise Exception("No clip in slot")
            
            clip = clip_slot.clip
            
            if hasattr(clip, 'is_midi_clip') and clip.is_midi_clip:
                clip.remove_notes(0, 0, clip.length, 128)
            
            return {
                "cleared": True,
                "track_index": track_index,
                "clip_index": clip_index,
                "clip_name": clip.name
            }
        except Exception as e:
            self.log_message("Error clearing clip: " + str(e))
            raise
    
    def _duplicate_clip(self, track_index, clip_index, target_slot):
        """Duplicate a clip to another slot"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            
            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Source clip index out of range")
            
            source_slot = track.clip_slots[clip_index]
            
            if not source_slot.has_clip:
                raise Exception("No clip in source slot")
            
            # Find target slot
            if target_slot is None:
                target_slot = self._find_empty_slot(track)
                if target_slot == -1:
                    raise Exception("No empty clip slots available")
            
            if target_slot < 0 or target_slot >= len(track.clip_slots):
                raise IndexError("Target slot index out of range")
            
            target_slot_obj = track.clip_slots[target_slot]
            
            if target_slot_obj.has_clip:
                raise Exception("Target slot already has a clip")
            
            # Duplicate by copying notes
            source_clip = source_slot.clip
            target_slot_obj.create_clip(source_clip.length)
            target_clip = target_slot_obj.clip
            target_clip.name = source_clip.name + " (copy)"
            
            if hasattr(source_clip, 'is_midi_clip') and source_clip.is_midi_clip:
                notes = source_clip.get_notes(0, 0, source_clip.length, 128)
                if notes:
                    target_clip.set_notes(notes)
            
            return {
                "duplicated": True,
                "source_slot": clip_index,
                "target_slot": target_slot,
                "clip_name": target_clip.name
            }
        except Exception as e:
            self.log_message("Error duplicating clip: " + str(e))
            raise
    
    def _set_clip_loop(self, track_index, clip_index, loop_start, loop_end):
        """Set loop points for a clip"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            
            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")
            
            clip_slot = track.clip_slots[clip_index]
            
            if not clip_slot.has_clip:
                raise Exception("No clip in slot")
            
            clip = clip_slot.clip
            
            if loop_end is None:
                loop_end = clip.length
            
            clip.loop_start = loop_start
            clip.loop_end = loop_end
            
            return {
                "loop_start": clip.loop_start,
                "loop_end": clip.loop_end
            }
        except Exception as e:
            self.log_message("Error setting clip loop: " + str(e))
            raise
    
    # ============================================
    # NOTE MANAGEMENT WITH HUMANIZATION
    # ============================================
    
    def _humanize_notes(self, notes, humanize_config=None):
        """Apply humanization to notes"""
        if humanize_config is None:
            humanize_config = {
                "timing_range_ms": 10,  # ±10ms timing variation
                "velocity_range": 15,   # ±15 velocity variation
                "enabled": True
            }
        
        if not humanize_config.get("enabled", True):
            return notes
        
        timing_range = humanize_config.get("timing_range_ms", 10) / 1000.0  # Convert to beats at ~120 BPM
        timing_range_beats = timing_range * 2  # Rough conversion
        velocity_range = humanize_config.get("velocity_range", 15)
        
        humanized = []
        for note in notes:
            pitch = note.get("pitch", 60)
            start_time = note.get("start_time", 0.0)
            duration = note.get("duration", 0.25)
            velocity = note.get("velocity", 100)
            mute = note.get("mute", False)
            
            # Apply timing offset
            timing_offset = note.get("start_time_offset_ms", None)
            if timing_offset is not None:
                start_time += timing_offset / 1000.0 * 2  # Convert ms to beats
            else:
                # Random humanization
                start_time += random.uniform(-timing_range_beats, timing_range_beats)
            
            # Ensure start_time is not negative
            start_time = max(0.0, start_time)
            
            # Apply velocity variation
            velocity_offset = note.get("velocity_offset", None)
            if velocity_offset is not None:
                velocity += velocity_offset
            else:
                # Random humanization
                velocity += random.randint(-velocity_range, velocity_range)
            
            # Clamp velocity
            velocity = max(1, min(127, velocity))
            
            humanized.append({
                "pitch": pitch,
                "start_time": start_time,
                "duration": duration,
                "velocity": velocity,
                "mute": mute
            })
        
        return humanized
    
    def _add_notes_to_clip(self, track_index, clip_index, notes, humanize=False):
        """Add MIDI notes to a clip (appends to existing notes)"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            
            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")
            
            clip_slot = track.clip_slots[clip_index]
            
            if not clip_slot.has_clip:
                raise Exception("No clip in slot. Create a clip first with create_clip.")
            
            clip = clip_slot.clip
            
            # Apply humanization if requested
            if humanize:
                notes = self._humanize_notes(notes)
            
            # Convert note data to Live's format
            live_notes = []
            for note in notes:
                pitch = note.get("pitch", 60)
                start_time = note.get("start_time", 0.0)
                duration = note.get("duration", 0.25)
                velocity = note.get("velocity", 100)
                mute = note.get("mute", False)
                
                # Validate values
                pitch = max(0, min(127, pitch))
                start_time = max(0.0, start_time)
                duration = max(0.01, duration)
                velocity = max(1, min(127, velocity))
                
                live_notes.append((pitch, start_time, duration, velocity, mute))
            
            # Get existing notes and combine
            existing_notes = list(clip.get_notes(0, 0, clip.length, 128))
            all_notes = existing_notes + live_notes
            
            # Set all notes
            clip.set_notes(tuple(all_notes))
            
            result = {
                "added_count": len(live_notes),
                "total_notes": len(all_notes),
                "clip_name": clip.name
            }
            return result
        except Exception as e:
            self.log_message("Error adding notes to clip: " + str(e))
            raise
    
    def _replace_clip_notes(self, track_index, clip_index, notes, humanize=False):
        """Replace all notes in a clip (clears first, then adds)"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            
            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")
            
            clip_slot = track.clip_slots[clip_index]
            
            if not clip_slot.has_clip:
                raise Exception("No clip in slot. Create a clip first.")
            
            clip = clip_slot.clip
            
            # Apply humanization if requested
            if humanize:
                notes = self._humanize_notes(notes)
            
            # Convert note data to Live's format
            live_notes = []
            for note in notes:
                pitch = note.get("pitch", 60)
                start_time = note.get("start_time", 0.0)
                duration = note.get("duration", 0.25)
                velocity = note.get("velocity", 100)
                mute = note.get("mute", False)
                
                # Validate values
                pitch = max(0, min(127, pitch))
                start_time = max(0.0, start_time)
                duration = max(0.01, duration)
                velocity = max(1, min(127, velocity))
                
                live_notes.append((pitch, start_time, duration, velocity, mute))
            
            # Clear existing notes first
            clip.remove_notes(0, 0, clip.length, 128)
            
            # Set new notes
            clip.set_notes(tuple(live_notes))
            
            result = {
                "replaced": True,
                "note_count": len(live_notes),
                "clip_name": clip.name
            }
            return result
        except Exception as e:
            self.log_message("Error replacing clip notes: " + str(e))
            raise
    
    def _delete_notes(self, track_index, clip_index, pitch_min, pitch_max, time_start, time_end):
        """Delete notes within a pitch and time range"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            
            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")
            
            clip_slot = track.clip_slots[clip_index]
            
            if not clip_slot.has_clip:
                raise Exception("No clip in slot")
            
            clip = clip_slot.clip
            
            if time_end is None:
                time_end = clip.length
            
            # Remove notes in the specified range
            clip.remove_notes(time_start, pitch_min, time_end - time_start, pitch_max - pitch_min + 1)
            
            return {
                "deleted": True,
                "pitch_range": [pitch_min, pitch_max],
                "time_range": [time_start, time_end]
            }
        except Exception as e:
            self.log_message("Error deleting notes: " + str(e))
            raise
    
    def _set_clip_name(self, track_index, clip_index, name):
        """Set the name of a clip"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            
            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")
            
            clip_slot = track.clip_slots[clip_index]
            
            if not clip_slot.has_clip:
                raise Exception("No clip in slot")
            
            clip = clip_slot.clip
            clip.name = name
            
            result = {
                "name": clip.name
            }
            return result
        except Exception as e:
            self.log_message("Error setting clip name: " + str(e))
            raise
    
    # ============================================
    # TRANSPORT CONTROLS
    # ============================================
    
    def _set_tempo(self, tempo):
        """Set the tempo of the session"""
        try:
            tempo = max(20.0, min(999.0, tempo))
            self._song.tempo = tempo
            
            result = {
                "tempo": self._song.tempo
            }
            return result
        except Exception as e:
            self.log_message("Error setting tempo: " + str(e))
            raise
    
    def _fire_clip(self, track_index, clip_index):
        """Fire a clip"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            
            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")
            
            clip_slot = track.clip_slots[clip_index]
            
            if not clip_slot.has_clip:
                raise Exception("No clip in slot")
            
            clip_slot.fire()
            
            result = {
                "fired": True
            }
            return result
        except Exception as e:
            self.log_message("Error firing clip: " + str(e))
            raise
    
    def _stop_clip(self, track_index, clip_index):
        """Stop a clip"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            
            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")
            
            clip_slot = track.clip_slots[clip_index]
            clip_slot.stop()
            
            result = {
                "stopped": True
            }
            return result
        except Exception as e:
            self.log_message("Error stopping clip: " + str(e))
            raise
    
    def _start_playback(self):
        """Start playing the session"""
        try:
            self._song.start_playing()
            
            result = {
                "playing": self._song.is_playing
            }
            return result
        except Exception as e:
            self.log_message("Error starting playback: " + str(e))
            raise
    
    def _stop_playback(self):
        """Stop playing the session"""
        try:
            self._song.stop_playing()
            
            result = {
                "playing": self._song.is_playing
            }
            return result
        except Exception as e:
            self.log_message("Error stopping playback: " + str(e))
            raise
    
    # ============================================
    # MIXER CONTROLS
    # ============================================
    
    def _set_track_volume(self, track_index, volume):
        """Set track volume (0.0 - 1.0)"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            volume = max(0.0, min(1.0, volume))
            track.mixer_device.volume.value = volume
            
            return {
                "track_index": track_index,
                "volume": track.mixer_device.volume.value
            }
        except Exception as e:
            self.log_message("Error setting track volume: " + str(e))
            raise
    
    def _set_track_pan(self, track_index, pan):
        """Set track panning (-1.0 to 1.0)"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            pan = max(-1.0, min(1.0, pan))
            track.mixer_device.panning.value = pan
            
            return {
                "track_index": track_index,
                "pan": track.mixer_device.panning.value
            }
        except Exception as e:
            self.log_message("Error setting track pan: " + str(e))
            raise
    
    def _set_track_send(self, track_index, send_index, value):
        """Set send level for a track (0.0 - 1.0)"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            
            if not hasattr(track.mixer_device, 'sends') or send_index >= len(track.mixer_device.sends):
                raise IndexError("Send index out of range")
            
            value = max(0.0, min(1.0, value))
            track.mixer_device.sends[send_index].value = value
            
            return {
                "track_index": track_index,
                "send_index": send_index,
                "value": track.mixer_device.sends[send_index].value
            }
        except Exception as e:
            self.log_message("Error setting track send: " + str(e))
            raise
    
    def _mute_track(self, track_index, mute):
        """Mute or unmute a track"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            track.mute = mute
            
            return {
                "track_index": track_index,
                "mute": track.mute
            }
        except Exception as e:
            self.log_message("Error muting track: " + str(e))
            raise
    
    def _solo_track(self, track_index, solo):
        """Solo or unsolo a track"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            track.solo = solo
            
            return {
                "track_index": track_index,
                "solo": track.solo
            }
        except Exception as e:
            self.log_message("Error soloing track: " + str(e))
            raise
    
    def _arm_track(self, track_index, arm):
        """Arm or disarm a track for recording"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            
            if hasattr(track, 'arm'):
                track.arm = arm
            
            return {
                "track_index": track_index,
                "arm": track.arm if hasattr(track, 'arm') else False
            }
        except Exception as e:
            self.log_message("Error arming track: " + str(e))
            raise
    
    # ============================================
    # DEVICE PARAMETER CONTROLS
    # ============================================
    
    def _get_device_parameters(self, track_index, device_index):
        """Get all parameters of a device"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            
            if device_index < 0 or device_index >= len(track.devices):
                raise IndexError("Device index out of range")
            
            device = track.devices[device_index]
            params = []
            
            if hasattr(device, 'parameters'):
                for idx, param in enumerate(device.parameters):
                    params.append({
                        "index": idx,
                        "name": param.name,
                        "value": param.value,
                        "min": param.min,
                        "max": param.max,
                        "default": param.default_value if hasattr(param, 'default_value') else None,
                        "is_quantized": param.is_quantized if hasattr(param, 'is_quantized') else False
                    })
            
            return {
                "track_index": track_index,
                "device_index": device_index,
                "device_name": device.name,
                "device_class": device.class_name,
                "parameter_count": len(params),
                "parameters": params
            }
        except Exception as e:
            self.log_message("Error getting device parameters: " + str(e))
            raise
    
    def _set_device_param(self, track_index, device_index, param_index, param_name, value):
        """Set a device parameter by index or name"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            
            if device_index < 0 or device_index >= len(track.devices):
                raise IndexError("Device index out of range")
            
            device = track.devices[device_index]
            
            if not hasattr(device, 'parameters'):
                raise Exception("Device has no parameters")
            
            param = None
            
            # Find by name first if provided
            if param_name:
                for p in device.parameters:
                    if p.name.lower() == param_name.lower():
                        param = p
                        break
                if not param:
                    raise ValueError("Parameter '{0}' not found".format(param_name))
            else:
                # Find by index
                if param_index < 0 or param_index >= len(device.parameters):
                    raise IndexError("Parameter index out of range")
                param = device.parameters[param_index]
            
            # Clamp value to valid range
            value = max(param.min, min(param.max, value))
            param.value = value
            
            return {
                "parameter_name": param.name,
                "value": param.value,
                "device_name": device.name
            }
        except Exception as e:
            self.log_message("Error setting device param: " + str(e))
            raise
    
    # ============================================
    # SCENE MANAGEMENT
    # ============================================
    
    def _create_scene(self, index):
        """Create a new scene"""
        try:
            if index == -1:
                index = len(self._song.scenes)
            
            self._song.create_scene(index)
            
            return {
                "index": index,
                "scene_count": len(self._song.scenes)
            }
        except Exception as e:
            self.log_message("Error creating scene: " + str(e))
            raise
    
    # ============================================
    # BROWSER FUNCTIONS
    # ============================================
    
    def _get_browser_item(self, uri, path):
        """Get a browser item by URI or path"""
        try:
            app = self.application()
            if not app:
                raise RuntimeError("Could not access Live application")
                
            result = {
                "uri": uri,
                "path": path,
                "found": False
            }
            
            if uri:
                item = self._find_browser_item_by_uri(app.browser, uri)
                if item:
                    result["found"] = True
                    result["item"] = {
                        "name": item.name,
                        "is_folder": item.is_folder,
                        "is_device": item.is_device,
                        "is_loadable": item.is_loadable,
                        "uri": item.uri
                    }
                    return result
            
            if path:
                path_parts = path.split("/")
                
                current_item = None
                if path_parts[0].lower() == "instruments":
                    current_item = app.browser.instruments
                elif path_parts[0].lower() == "sounds":
                    current_item = app.browser.sounds
                elif path_parts[0].lower() == "drums":
                    current_item = app.browser.drums
                elif path_parts[0].lower() == "audio_effects":
                    current_item = app.browser.audio_effects
                elif path_parts[0].lower() == "midi_effects":
                    current_item = app.browser.midi_effects
                else:
                    current_item = app.browser.instruments
                    path_parts = ["instruments"] + path_parts
                
                for i in range(1, len(path_parts)):
                    part = path_parts[i]
                    if not part:
                        continue
                    
                    found = False
                    for child in current_item.children:
                        if child.name.lower() == part.lower():
                            current_item = child
                            found = True
                            break
                    
                    if not found:
                        result["error"] = "Path part '{0}' not found".format(part)
                        return result
                
                result["found"] = True
                result["item"] = {
                    "name": current_item.name,
                    "is_folder": current_item.is_folder,
                    "is_device": current_item.is_device,
                    "is_loadable": current_item.is_loadable,
                    "uri": current_item.uri
                }
            
            return result
        except Exception as e:
            self.log_message("Error getting browser item: " + str(e))
            self.log_message(traceback.format_exc())
            raise   
    
    def _load_browser_item(self, track_index, item_uri):
        """Load a browser item onto a track by its URI"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            
            track = self._song.tracks[track_index]
            app = self.application()
            
            item = self._find_browser_item_by_uri(app.browser, item_uri)
            
            if not item:
                raise ValueError("Browser item with URI '{0}' not found".format(item_uri))
            
            self._song.view.selected_track = track
            app.browser.load_item(item)
            
            result = {
                "loaded": True,
                "item_name": item.name,
                "track_name": track.name,
                "uri": item_uri
            }
            return result
        except Exception as e:
            self.log_message("Error loading browser item: {0}".format(str(e)))
            self.log_message(traceback.format_exc())
            raise
    
    def _find_browser_item_by_uri(self, browser_or_item, uri, max_depth=10, current_depth=0):
        """Find a browser item by its URI"""
        try:
            if hasattr(browser_or_item, 'uri') and browser_or_item.uri == uri:
                return browser_or_item
            
            if current_depth >= max_depth:
                return None
            
            if hasattr(browser_or_item, 'instruments'):
                categories = [
                    browser_or_item.instruments,
                    browser_or_item.sounds,
                    browser_or_item.drums,
                    browser_or_item.audio_effects,
                    browser_or_item.midi_effects
                ]
                
                for category in categories:
                    item = self._find_browser_item_by_uri(category, uri, max_depth, current_depth + 1)
                    if item:
                        return item
                
                return None
            
            if hasattr(browser_or_item, 'children') and browser_or_item.children:
                for child in browser_or_item.children:
                    item = self._find_browser_item_by_uri(child, uri, max_depth, current_depth + 1)
                    if item:
                        return item
            
            return None
        except Exception as e:
            self.log_message("Error finding browser item by URI: {0}".format(str(e)))
            return None
    
    def _get_device_type(self, device):
        """Get the type of a device"""
        try:
            if device.can_have_drum_pads:
                return "drum_machine"
            elif device.can_have_chains:
                return "rack"
            elif "instrument" in device.class_display_name.lower():
                return "instrument"
            elif "audio_effect" in device.class_name.lower():
                return "audio_effect"
            elif "midi_effect" in device.class_name.lower():
                return "midi_effect"
            else:
                return "unknown"
        except:
            return "unknown"
    
    def get_browser_tree(self, category_type="all"):
        """Get a simplified tree of browser categories"""
        try:
            app = self.application()
            if not app:
                raise RuntimeError("Could not access Live application")
                
            if not hasattr(app, 'browser') or app.browser is None:
                raise RuntimeError("Browser is not available")
            
            browser_attrs = [attr for attr in dir(app.browser) if not attr.startswith('_')]
            
            result = {
                "type": category_type,
                "categories": [],
                "available_categories": browser_attrs
            }
            
            def process_item(item, depth=0):
                if not item:
                    return None
                
                result = {
                    "name": item.name if hasattr(item, 'name') else "Unknown",
                    "is_folder": hasattr(item, 'children') and bool(item.children),
                    "is_device": hasattr(item, 'is_device') and item.is_device,
                    "is_loadable": hasattr(item, 'is_loadable') and item.is_loadable,
                    "uri": item.uri if hasattr(item, 'uri') else None,
                    "children": []
                }
                
                return result
            
            if (category_type == "all" or category_type == "instruments") and hasattr(app.browser, 'instruments'):
                try:
                    instruments = process_item(app.browser.instruments)
                    if instruments:
                        instruments["name"] = "Instruments"
                        result["categories"].append(instruments)
                except Exception as e:
                    self.log_message("Error processing instruments: {0}".format(str(e)))
            
            if (category_type == "all" or category_type == "sounds") and hasattr(app.browser, 'sounds'):
                try:
                    sounds = process_item(app.browser.sounds)
                    if sounds:
                        sounds["name"] = "Sounds"
                        result["categories"].append(sounds)
                except Exception as e:
                    self.log_message("Error processing sounds: {0}".format(str(e)))
            
            if (category_type == "all" or category_type == "drums") and hasattr(app.browser, 'drums'):
                try:
                    drums = process_item(app.browser.drums)
                    if drums:
                        drums["name"] = "Drums"
                        result["categories"].append(drums)
                except Exception as e:
                    self.log_message("Error processing drums: {0}".format(str(e)))
            
            if (category_type == "all" or category_type == "audio_effects") and hasattr(app.browser, 'audio_effects'):
                try:
                    audio_effects = process_item(app.browser.audio_effects)
                    if audio_effects:
                        audio_effects["name"] = "Audio Effects"
                        result["categories"].append(audio_effects)
                except Exception as e:
                    self.log_message("Error processing audio_effects: {0}".format(str(e)))
            
            if (category_type == "all" or category_type == "midi_effects") and hasattr(app.browser, 'midi_effects'):
                try:
                    midi_effects = process_item(app.browser.midi_effects)
                    if midi_effects:
                        midi_effects["name"] = "MIDI Effects"
                        result["categories"].append(midi_effects)
                except Exception as e:
                    self.log_message("Error processing midi_effects: {0}".format(str(e)))
            
            return result
            
        except Exception as e:
            self.log_message("Error getting browser tree: {0}".format(str(e)))
            self.log_message(traceback.format_exc())
            raise
    
    def get_browser_items_at_path(self, path):
        """Get browser items at a specific path"""
        try:
            app = self.application()
            if not app:
                raise RuntimeError("Could not access Live application")
                
            if not hasattr(app, 'browser') or app.browser is None:
                raise RuntimeError("Browser is not available")
            
            browser_attrs = [attr for attr in dir(app.browser) if not attr.startswith('_')]
                
            path_parts = path.split("/")
            if not path_parts:
                raise ValueError("Invalid path")
            
            root_category = path_parts[0].lower()
            current_item = None
            
            if root_category == "instruments" and hasattr(app.browser, 'instruments'):
                current_item = app.browser.instruments
            elif root_category == "sounds" and hasattr(app.browser, 'sounds'):
                current_item = app.browser.sounds
            elif root_category == "drums" and hasattr(app.browser, 'drums'):
                current_item = app.browser.drums
            elif root_category == "audio_effects" and hasattr(app.browser, 'audio_effects'):
                current_item = app.browser.audio_effects
            elif root_category == "midi_effects" and hasattr(app.browser, 'midi_effects'):
                current_item = app.browser.midi_effects
            else:
                found = False
                for attr in browser_attrs:
                    if attr.lower() == root_category:
                        try:
                            current_item = getattr(app.browser, attr)
                            found = True
                            break
                        except Exception as e:
                            self.log_message("Error accessing browser attribute {0}: {1}".format(attr, str(e)))
                
                if not found:
                    return {
                        "path": path,
                        "error": "Unknown category: {0}".format(root_category),
                        "available_categories": browser_attrs,
                        "items": []
                    }
            
            for i in range(1, len(path_parts)):
                part = path_parts[i]
                if not part:
                    continue
                
                if not hasattr(current_item, 'children'):
                    return {
                        "path": path,
                        "error": "Item at '{0}' has no children".format('/'.join(path_parts[:i])),
                        "items": []
                    }
                
                found = False
                for child in current_item.children:
                    if hasattr(child, 'name') and child.name.lower() == part.lower():
                        current_item = child
                        found = True
                        break
                
                if not found:
                    return {
                        "path": path,
                        "error": "Path part '{0}' not found".format(part),
                        "items": []
                    }
            
            items = []
            if hasattr(current_item, 'children'):
                for child in current_item.children:
                    item_info = {
                        "name": child.name if hasattr(child, 'name') else "Unknown",
                        "is_folder": hasattr(child, 'children') and bool(child.children),
                        "is_device": hasattr(child, 'is_device') and child.is_device,
                        "is_loadable": hasattr(child, 'is_loadable') and child.is_loadable,
                        "uri": child.uri if hasattr(child, 'uri') else None
                    }
                    items.append(item_info)
            
            result = {
                "path": path,
                "name": current_item.name if hasattr(current_item, 'name') else "Unknown",
                "uri": current_item.uri if hasattr(current_item, 'uri') else None,
                "is_folder": hasattr(current_item, 'children') and bool(current_item.children),
                "is_device": hasattr(current_item, 'is_device') and current_item.is_device,
                "is_loadable": hasattr(current_item, 'is_loadable') and current_item.is_loadable,
                "items": items
            }
            
            return result
            
        except Exception as e:
            self.log_message("Error getting browser items at path: {0}".format(str(e)))
            self.log_message(traceback.format_exc())
            raise
