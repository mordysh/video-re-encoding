#!/usr/bin/env python3

import os
import subprocess
import glob

def convert_mp4_to_wav():
    mp4_files = glob.glob("*.mp4")
    
    if not mp4_files:
        print("No MP4 files found in the current directory.")
        return
    
    print(f"Found {len(mp4_files)} MP4 file(s). Starting conversion...")
    
    for input_file in sorted(mp4_files):
        output_file = os.path.splitext(input_file)[0] + ".wav"
        
        cmd = ["ffmpeg", "-i", input_file, "-vn", "-ac", "1", "-ar", "16000", output_file]
        
        print(f"Converting: {input_file} -> {output_file}")
        
        try:
            subprocess.run(cmd, check=True)
            print(f"Successfully converted: {output_file}\n")
        except subprocess.CalledProcessError as e:
            print(f"Error converting {input_file}: {e}\n")

if __name__ == "__main__":
    convert_mp4_to_wav()
