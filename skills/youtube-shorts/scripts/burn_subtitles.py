import os
import subprocess
import sys
from pathlib import Path

def burn(mp4_path, srt_path, out_path):
    mp4_path = Path(mp4_path).resolve()
    srt_path = Path(srt_path).resolve()
    out_path = Path(out_path).resolve()
    
    # We change directory to the folder containing srt_path
    # to avoid ffmpeg Windows path escaping issues for subtitles filter
    original_cwd = os.getcwd()
    work_dir = srt_path.parent
    os.chdir(work_dir)
    
    # ffmpeg expects filename in subtitles filter
    srt_filename = srt_path.name
    # Escaping single quotes in filename just in case
    srt_filename_escaped = srt_filename.replace("'", "'\\''")
    
    cmd = [
        "ffmpeg", "-y",
        "-i", str(mp4_path),
        "-vf", f"subtitles='{srt_filename_escaped}'",
        "-c:v", "libx264", "-crf", "20",
        "-c:a", "copy",
        str(out_path)
    ]
    print(f"Running command: {' '.join(cmd)}")
    rc = subprocess.call(cmd)
    os.chdir(original_cwd)
    return rc

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python burn_subtitles.py <input_mp4> <input_srt> <output_mp4>")
        sys.exit(1)
    
    input_mp4 = sys.argv[1]
    input_srt = sys.argv[2]
    output_mp4 = sys.argv[3]
    
    rc = burn(input_mp4, input_srt, output_mp4)
    sys.exit(rc)
