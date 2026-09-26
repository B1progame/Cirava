from pathlib import Path
import json
import cv2
import numpy as np

SOURCE = Path('public/cirava-guide.mp4')
OUT = Path('automation/analysis')
OUT.mkdir(parents=True, exist_ok=True)

cap = cv2.VideoCapture(str(SOURCE))
fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
duration = frames / fps if fps else 0

metadata = {
    'source': str(SOURCE.resolve()),
    'fps': fps,
    'frames': frames,
    'width': width,
    'height': height,
    'duration_seconds': duration,
}
(OUT / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')

# Uniform review sheet: one frame every ~5 seconds, labelled with timecode.
sample_count = max(1, int(np.ceil(duration / 5.0)))
thumb_w = 480
thumb_h = round(height * thumb_w / width) if width else 270
cols = 3
rows = int(np.ceil(sample_count / cols))
sheet = np.zeros((rows * (thumb_h + 32), cols * thumb_w, 3), dtype=np.uint8)

for i in range(sample_count):
    t = min(duration, i * 5.0)
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, frame = cap.read()
    if not ok:
        continue
    frame = cv2.resize(frame, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)
    x = (i % cols) * thumb_w
    y = (i // cols) * (thumb_h + 32)
    sheet[y:y+thumb_h, x:x+thumb_w] = frame
    cv2.putText(sheet, f'{t:06.1f}s', (x + 8, y + thumb_h + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

cv2.imwrite(str(OUT / 'uniform_review_sheet.jpg'), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])

# Full-size keyframes for privacy and UI inspection.
for t in [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 25.5]:
    cap.set(cv2.CAP_PROP_POS_MSEC, min(t, duration) * 1000)
    ok, frame = cap.read()
    if ok:
        cv2.imwrite(str(OUT / f'keyframe_{t:04.1f}s.jpg'), frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 94])

# Detect substantial visual changes at one-second cadence for an initial cut map.
changes = []
prev = None
t = 0.0
while t <= duration:
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, frame = cap.read()
    if not ok:
        break
    small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    if prev is not None:
        score = float(np.mean(cv2.absdiff(gray, prev)))
        if score >= 18.0:
            changes.append({'time_seconds': round(t, 2), 'score': round(score, 2)})
    prev = gray
    t += 1.0

(OUT / 'scene_changes.json').write_text(json.dumps(changes, indent=2), encoding='utf-8')
cap.release()
print(json.dumps(metadata, indent=2))
print(f'analysis_frames={sample_count} scene_changes={len(changes)}')
