from pathlib import Path
import json
import cv2
import numpy as np

SOURCE = Path(r'C:/Users/bslid.BENJI-PC/Downloads/google_cloud_guide_cropped_top.mp4')
OUT = Path('automation/analysis')
OUT.mkdir(parents=True, exist_ok=True)
cap = cv2.VideoCapture(str(SOURCE))
fps = cap.get(cv2.CAP_PROP_FPS) or 30
frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
duration = frames / fps
meta = {'source': str(SOURCE), 'fps': fps, 'frames': frames, 'width': w, 'height': h, 'duration': duration}
(OUT / 'metadata.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')

times = list(np.arange(0, duration, 10.0)) + [max(0, duration - 0.1)]
tw = 640
th = round(h * tw / w)
cols = 3
rows = int(np.ceil(len(times) / cols))
sheet = np.zeros((rows * (th + 30), cols * tw, 3), dtype=np.uint8)
for i, t in enumerate(times):
    cap.set(cv2.CAP_PROP_POS_MSEC, float(t * 1000))
    ok, frame = cap.read()
    if not ok:
        continue
    frame = cv2.resize(frame, (tw, th), interpolation=cv2.INTER_AREA)
    x, y = (i % cols) * tw, (i // cols) * (th + 30)
    sheet[y:y+th, x:x+tw] = frame
    cv2.putText(sheet, f'{t:06.1f}s', (x + 8, y + th + 21), cv2.FONT_HERSHEY_SIMPLEX, .55, (255,255,255), 1, cv2.LINE_AA)
cv2.imwrite(str(OUT / 'review_sheet.jpg'), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])
cap.release()
print(json.dumps(meta, indent=2))
