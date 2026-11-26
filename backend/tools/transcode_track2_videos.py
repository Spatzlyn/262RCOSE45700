"""Make browser-playable copies of the Track 2 source videos (no backend imports; runs on the host).

AI Hub 597 MP4s are MPEG-4 Part 2 ('mp4v') with the moov atom at the end: Chrome/Edge/Safari cannot play
them in <video>. This writes H.264 (yuv420p) + faststart copies, keeping every frame and the 15 fps timing
so decision_time_s = frame_index / fps still points at the same frame. Originals are never modified.

  python3 backend/tools/transcode_track2_videos.py --store /data/backend-store --video-root /data/aihub_597/2.Validation
Output: <store>/track2/videos_h264/<clip_id>.mp4 and manifest.json (hashes, ffmpeg version, checks).
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def probe(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                          "stream=codec_name,width,height,r_frame_rate,nb_read_frames:format=start_time",
                          "-of", "json", str(p)], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    s = d["streams"][0]
    return {"codec": s["codec_name"], "width": s["width"], "height": s["height"], "fps": s["r_frame_rate"],
            "frames": int(s["nb_read_frames"]), "start_time": float(d.get("format", {}).get("start_time", 0) or 0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--video-root", required=True)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    store = Path(a.store)
    items = [json.loads(x) for x in (store / "track2" / "items.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    clips = {i["clip_id"]: i["video_relpath"] for i in items}
    out_dir = store / "track2" / "videos_h264"
    out_dir.mkdir(parents=True, exist_ok=True)
    version = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    manifest = {"ffmpeg": version, "params": "libx264 -crf 18 -preset medium -pix_fmt yuv420p -fps_mode passthrough "
                                           "-movflags +faststart -an", "clips": {}}
    for clip, rel in sorted(clips.items()):
        src = Path(a.video_root) / rel
        dst = out_dir / f"{clip}.mp4"
        if not dst.exists() or a.force:
            tmp = dst.with_suffix(".tmp.mp4")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-map", "0:v:0", "-c:v", "libx264",
                            "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-fps_mode", "passthrough",
                            "-movflags", "+faststart", "-an", str(tmp)], check=True)
            tmp.replace(dst)
        ps, pd = probe(src), probe(dst)
        ok = (ps["frames"] == pd["frames"] and ps["fps"] == pd["fps"]
              and (ps["width"], ps["height"]) == (pd["width"], pd["height"]))
        manifest["clips"][clip] = {"source": rel, "source_sha256": sha(src), "output_sha256": sha(dst),
                                   "source_probe": ps, "output_probe": pd, "frames_fps_size_preserved": ok}
        print(clip, "OK" if ok else "MISMATCH", ps, "->", pd)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    if not all(c["frames_fps_size_preserved"] for c in manifest["clips"].values()):
        raise SystemExit("frame count / fps / size changed for at least one clip")


if __name__ == "__main__":
    main()
