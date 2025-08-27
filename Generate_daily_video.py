# Generate an anime-style "fight" short (original motion graphics)
# Saves: ./out/video.mp4
#
# Optional: upload to YouTube if secrets are set:
#   YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN

import os, random, datetime, math
import numpy as np
from moviepy.editor import (
    ColorClip, TextClip, CompositeVideoClip, VideoClip, vfx, AudioClip
)

W, H = 720, 1280    # vertical 9:16
FPS = 24
DUR = 12            # seconds
OUT_DIR = "out"
OUT_PATH = os.path.join(OUT_DIR, "video.mp4")

# ---------- Visual helpers ----------

def speedlines_clip(duration=4, density=14, angle_deg=-25, speed=600, opacity=0.35):
    """Procedural diagonal speed lines."""
    angle = math.radians(angle_deg)
    dx = math.cos(angle); dy = math.sin(angle)
    period = W // density
    thickness = max(1, period // 3)

    def make_frame(t):
        # move the pattern over time
        shift = int(speed * t)
        img = np.zeros((H, W, 3), dtype=np.uint8)

        # draw diagonal white streaks
        for y in range(H):
            for x in range(0, W, period):
                # diagonal index
                xi = int(x + dx * y + shift) % period
                if xi < thickness:
                    img[y, x:x+thickness] = 255
        return img

    clip = VideoClip(make_frame, duration=duration).set_fps(FPS)
    return clip.set_opacity(opacity)

def flash_clip(duration=0.1):
    return ColorClip(size=(W, H), color=(255,255,255), duration=duration)

def shake_pos(intensity=10):
    """Return a position function to shake a layer."""
    def pos(t):
        rng = random.Random(int(t*1000)+42)
        return (rng.randint(-intensity,intensity),
                rng.randint(-intensity,intensity))
    return pos

# ---------- Audio helpers ----------

def tone(freq, dur, vol=0.2):
    """Sine tone AudioClip."""
    return AudioClip(lambda t: vol*np.sin(2*np.pi*freq*t), duration=dur, fps=44100)

def whoosh(dur=0.3):
    return AudioClip(lambda t: 0.25*np.sin(2*np.pi*(80+220*t**2)*t), duration=dur, fps=44100)

def thump(dur=0.18):
    return AudioClip(lambda t: 0.35*np.sin(2*np.pi*(60*(1-t))*t)*np.exp(-6*t), duration=dur, fps=44100)

# ---------- Build the video ----------

def build_video():
    os.makedirs(OUT_DIR, exist_ok=True)

    bg = ColorClip((W,H), color=(10,10,18), duration=DUR)

    fighters = [
        ("KAZE", "#ff3b3b"), ("RYU", "#35f0ff"), ("AKIRA", "#ffd23b"),
        ("SHIN", "#b05cff"), ("YUMI", "#7bff7b"), ("REI", "#ff7be7")
    ]
    left, right = random.sample(fighters, 2)

    # Title card
    title = TextClip(
        f"ANIME FIGHT – {datetime.date.today().strftime('%b %d')}",
        fontsize=60, color="white", font="DejaVu-Sans", size=(W-60,None), method="caption"
    ).set_position("center").set_duration(1.5).fx(vfx.fadein, 0.2).fx(vfx.fadeout,0.2)

    # Versus intro
    left_txt = TextClip(left[0], fontsize=110, color=left[1],
                        font="DejaVu-Sans-Oblique").set_duration(2.5)
    right_txt = TextClip(right[0], fontsize=110, color=right[1],
                         font="DejaVu-Sans-Oblique").set_duration(2.5)

    left_clip = left_txt.set_position(lambda t: (-W+int( W*1.2*t),  H*0.25)).set_start(1.5)
    right_clip= right_txt.set_position(lambda t: ( W-int( W*1.2*t), H*0.65)).set_start(1.5)

    vs = TextClip("VS", fontsize=140, color="white", font="DejaVu-Sans").set_duration(2.5)\
         .set_position("center").set_start(1.6)

    # Action section with shakes, lines, flashes
    action_bg = ColorClip((W,H), color=(15,8,24), duration=7).set_start(3.2)
    lines1 = speedlines_clip(2.5, density=16, angle_deg=-20, speed=500).set_start(3.2)
    lines2 = speedlines_clip(2.5, density=18, angle_deg=20,  speed=600, opacity=0.25).set_start(5.7)

    impact_times = [3.6, 4.2, 5.1, 6.0, 6.9, 7.8, 8.6, 9.2]
    flashes = [flash_clip(0.08).set_start(t) for t in impact_times]

    # Big “slashes”
    slash = TextClip("/", fontsize=500, color="white", font="DejaVu-Sans")\
            .set_duration(0.25).set_start(4.9).set_position(shake_pos(20)).fx(vfx.resize, width=600)
    slash2= slash.set_start(7.2).fx(vfx.mirror_x)

    # Audio track
    audio = whoosh(0.35).set_start(1.55)
    for t in impact_times:
        audio = audio.set_audio(audio.audio_fadeout(0.0)).fx( lambda c: c ) # keep reference
        audio = audio.set_duration(max(audio.duration, t+0.2))
        audio = audio.audio_fadeout(0.0).fx(lambda c: c)  # no-op, ensure chaining
        audio = audio.set_audio(audio)
        audio = audio.set_audio( (audio + thump(0.2).set_start(t)).volumex(1) )

    # Final composite
    comp = CompositeVideoClip(
        [bg, title, left_clip, right_clip, vs,
         action_bg, lines1, lines2, slash, slash2] + flashes,
        size=(W,H)
    ).set_fps(FPS)

    # Simple constant background tone so the video isn’t silent
    base_tone = tone(440, DUR, vol=0.03)
    comp = comp.set_audio(base_tone)

    print("Rendering video...")
    comp.write_videofile(OUT_PATH, fps=FPS, codec="libx264", audio_codec="aac", threads=4, preset="medium")
    print(f"Saved: {OUT_PATH}")
    return OUT_PATH

# ---------- Optional: upload to YouTube ----------

def maybe_upload_to_youtube(video_path):
    cid  = os.getenv("YT_CLIENT_ID")
    csec = os.getenv("YT_CLIENT_SECRET")
    rtok = os.getenv("YT_REFRESH_TOKEN")
    if not (cid and csec and rtok):
        print("YouTube secrets not set. Skipping upload.")
        return

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds = Credentials(
            None,
            refresh_token=rtok,
            client_id=cid,
            client_secret=csec,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        yt = build("youtube", "v3", credentials=creds)
        today = datetime.date.today().strftime("%b %d, %Y")
        title = f"AI Anime Fight • {today}"
        desc = "Auto-generated anime-style motion graphic. #anime #shorts"
        body = {
            "snippet": {
                "title": title,
                "description": desc,
                "categoryId": "24",
                "tags": ["anime", "fight", "motion graphics", "shorts"]
            },
            "status": {"privacyStatus": "public"}
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=False)
        print("Uploading to YouTube...")
        resp = yt.videos().insert(part="snippet,status", body=body, media_body=media).execute()
        print(f"Uploaded: https://www.youtube.com/watch?v={resp['id']}")
    except Exception as e:
        print("YouTube upload failed:", e)

def main():
    path = build_video()
    maybe_upload_to_youtube(path)

if __name__ == "__main__":
    main()
