#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import datetime
import signal
import select
import re
import json
import tty
import termios

# Configuration
STATE_FILE = ".encode_h265_resume.json"
LOG_FILE = f"encode_h265_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Global states
ffmpeg_process = None
caffeinate_process = None
quit_requested = False
was_quit = False
dry_run = False
list_output = None

def log(message, mode="a"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_msg = str(message).replace('\r', '').replace('\n', ' ')
    formatted_msg = f"[{timestamp}] {clean_msg}"
    print(message)
    try:
        with open(LOG_FILE, mode) as f:
            f.write(formatted_msg + "\n")
    except:
        pass

def get_video_info(file_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,codec_type,r_frame_rate:format=duration", "-of", "json", file_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0: raise Exception("ffprobe failed")
    data = json.loads(result.stdout)
    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    duration = float(data.get("format", {}).get("duration", 0))
    fps_raw = video_stream.get("r_frame_rate", "25/1")
    try:
        num, den = map(int, fps_raw.split("/"))
        fps = num / den if den != 0 else 25
    except: fps = 25
    return {
        "codec": video_stream.get("codec_name"), 
        "total_frames": max(1, int(duration * fps)),
        "fps": fps,
        "duration": duration
    }

def show_progress_bar(current, total, is_resuming=False):
    width = 40
    percent = min(100, int(current * 100 / total))
    filled = int(percent * width / 100)
    bar = "=" * filled + "-" * (width - filled)
    prefix = "[RESUMING] " if is_resuming else ""
    sys.stdout.write(f"\r{prefix}[{bar}] {percent}% ({current}/{total} frames)")
    sys.stdout.flush()

def save_state(file_path, frame):
    state = {"file": file_path, "frame": frame, "timestamp": time.time()}
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            return None
    return None

def clear_state():
    if os.path.exists(STATE_FILE):
        try: os.remove(STATE_FILE)
        except: pass

def cleanup(sig=None, frame=None):
    global quit_requested, was_quit, ffmpeg_process, caffeinate_process
    quit_requested = True
    was_quit = True
    if ffmpeg_process:
        try: ffmpeg_process.terminate()
        except: pass
    if caffeinate_process:
        try: caffeinate_process.terminate()
        except: pass

def main():
    global ffmpeg_process, caffeinate_process, quit_requested, was_quit, dry_run, list_output
    
    # Check for --dry-run argument
    if "--dry-run" in sys.argv:
        dry_run = True
        sys.argv.remove("--dry-run")
    
    # Check for --list argument
    if "--list" in sys.argv:
        list_output = "files_to_convert.txt"
        sys.argv.remove("--list")
    
    try: caffeinate_process = subprocess.Popen(["caffeinate", "-i"])
    except: pass

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    log("==========================================", mode="w")
    log("H.265 Encoding Script" + (" [DRY RUN]" if dry_run else "") + (" [LIST MODE]" if list_output else ""))
    log("Controls: P/Space=Pause & Resume, Q=Quit & Clean")
    log("==========================================")

    resume_data = load_state()
    video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm')
    files = [f for f in sorted(os.listdir(".")) if f.lower().endswith(video_extensions) and "_h265_mp3.mp4" not in f]
    
    files_to_convert = []
    
    if resume_data and resume_data["file"] in files:
        print(f"\nFound partial work for: {resume_data['file']}")
        try:
            choice = input("Resume from frame {}? (Y/n): ".format(resume_data["frame"])).lower()
            if choice == 'n':
                clear_state()
                resume_data = None
        except EOFError:
            resume_data = None
    else:
        resume_data = None

    for file_path in files:
        if quit_requested: break
        
        output_path = file_path.rsplit(".", 1)[0] + "_h265_mp3.mp4"
        try: 
            info = get_video_info(file_path)
            log(f"File: {file_path} | Codec: {info['codec']} | Duration: {info['duration']}s")
        except Exception as e:
            log(f"Skipping {file_path}: Error getting info: {e}")
            continue

        if info["codec"] == "hevc" and not resume_data:
            log(f"Skipping {file_path}: Already HEVC")
            continue

        if os.path.exists(output_path) and not resume_data:
            try:
                out_info = get_video_info(output_path)
                if out_info["codec"] == "hevc":
                    log(f"Skipping {file_path}: Output {output_path} already exists and is HEVC")
                    continue
            except:
                pass
        
        files_to_convert.append(file_path)

        start_frame = 0
        if resume_data and resume_data["file"] == file_path:
            start_frame = resume_data["frame"]
            log(f"\nResuming: {file_path} at frame {start_frame}")
        else:
            log(f"\nProcessing: {file_path}")

        cmd = ["ffmpeg", "-nostdin"]
        if start_frame > 0:
            seek_time = start_frame / info["fps"]
            cmd.extend(["-ss", str(seek_time)])
        
        cmd.extend([
            "-i", file_path,
            "-c:v", "libx265", "-x265-params", "ctu=32:max-tu-size=16:pools=16", "-c:a", "libmp3lame", "-q:a", "4",
            "-y", output_path
        ])
        
        if dry_run:
            log(f"[DRY RUN] Would execute: {' '.join(cmd)}")
            resume_data = None
            continue
        
        if list_output:
            resume_data = None
            continue
        
        ffmpeg_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=0)

        frame_pattern = re.compile(r"frame=\s*(\d+)")
        last_frame_seen = start_frame
        line_buf = ""
        
        fd = sys.stdin.fileno()
        is_tty = os.isatty(fd)
        if is_tty:
            old_settings = termios.tcgetattr(fd)
            tty.setraw(fd)
        
        try:
            while True:
                sources = [ffmpeg_process.stdout]
                if is_tty: sources.append(sys.stdin)
                
                r, _, _ = select.select(sources, [], [], 0.1)
                
                for s in r:
                    if s == sys.stdin:
                        char = sys.stdin.read(1).lower()
                        if char == 'q':
                            was_quit = True
                            quit_requested = True
                            ffmpeg_process.terminate()
                        elif char == 'p' or char == ' ':
                            save_state(file_path, last_frame_seen)
                            quit_requested = True
                            ffmpeg_process.terminate()
                    
                    elif s == ffmpeg_process.stdout:
                        char = ffmpeg_process.stdout.read(1)
                        if not char: break
                        line_buf += char
                        if char in ('\r', '\n'):
                            match = frame_pattern.search(line_buf)
                            if match:
                                current_rel_frame = int(match.group(1))
                                last_frame_seen = start_frame + current_rel_frame
                                show_progress_bar(last_frame_seen, info["total_frames"], is_resuming=(start_frame > 0))
                            line_buf = ""
                
                if ffmpeg_process.poll() is not None or quit_requested:
                    break
        finally:
            if is_tty:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            print("")

        if quit_requested:
            if was_quit:
                log("\n[QUIT] Cleaning up and exiting...")
                clear_state()
                if os.path.exists(output_path):
                    try: os.remove(output_path)
                    except: pass
            else:
                log(f"\n[PAUSED] Progress saved for {file_path}. Exiting.")
            break

        if ffmpeg_process.returncode == 0:
            log("✓ Success")
            os.remove(file_path)
            os.rename(output_path, file_path)
            clear_state()
            resume_data = None
        else:
            if not was_quit and not os.path.exists(STATE_FILE):
                log("✗ Failed")
                if os.path.exists(output_path):
                    try: os.remove(output_path)
                    except: pass
        
        ffmpeg_process = None

    # Write file list if requested
    if list_output and files_to_convert:
        try:
            with open(list_output, "w") as f:
                for file in files_to_convert:
                    full_path = os.path.abspath(file)
                    f.write(full_path + "\n")
            log(f"\nFile list saved to: {list_output}")
        except Exception as e:
            log(f"Error writing file list: {e}")

    if caffeinate_process: caffeinate_process.terminate()

if __name__ == "__main__":
    main()