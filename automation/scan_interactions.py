"""Find likely interaction moments and extract review frames from the full source."""
from pathlib import Path
import json
import cv2
import numpy as np

source = Path(r'C:/Users/bslid.BENJI-PC/Downloads/google_cloud_guide_cropped_top.mp4')
out = Path('automation/interaction_scan')
out.mkdir(parents=True, exist_ok=True)
cap = cv2.VideoCapture(str(source))
fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
samples = []
prev = None
t = 0.0
while t <= duration:
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, frame = cap.read()
    if not ok:
        break
    small = cv2.resize(frame, (320, 166), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    score = 0.0 if prev is None else float(np.mean(cv2.absdiff(gray, prev)))
    samples.append((score, t))
    prev = gray
    t += 0.5
cap.release()

samples.sort(reverse=True)
selected = []
for score, t in samples:
    if all(abs(t - old['time']) > 2.0 for old in selected):
        selected.append({'time': round(t, 2), 'change_score': round(score, 2)})
    if len(selected) >= 24:
        break
selected.sort(key=lambda x: x['time'])
(out / 'interaction_candidates.json').write_text(json.dumps(selected, indent=2), encoding='utf-8')

cap = cv2.VideoCapture(str(source))
tw, th = 640, 332
cols = 3
sheet = np.zeros((8 * (th + 28), cols * tw, 3), dtype=np.uint8)
for i, item in enumerate(selected):
    cap.set(cv2.CAP_PROP_POS_MSEC, item['time'] * 1000)
    ok, frame = cap.read()
    if not ok:
        continue
    frame = cv2.resize(frame, (tw, th), interpolation=cv2.INTER_AREA)
    x, y = (i % cols) * tw, (i // cols) * (th + 28)
    sheet[y:y+th, x:x+tw] = frame
    cv2.putText(sheet, f"{item['time']:06.1f}s  d{item['change_score']:.1f}", (x+8, y+th+20), cv2.FONT_HERSHEY_SIMPLEX, .55, (255,255,255), 1, cv2.LINE_AA)
cap.release()
cv2.imwrite(str(out / 'interaction_candidates.jpg'), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(json.dumps(selected, indent=2))
