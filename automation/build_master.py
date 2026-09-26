"""Build a conservative tutorial master from the supplied recording.

The supplied recording already contains the intended five-step visual language,
so this script preserves the UI and timing and only adds clean edge fades.
The source is never overwritten.
"""
from pathlib import Path
import json
import shutil
import cv2
import numpy as np

SOURCE = Path('public/cirava-guide.mp4')
WORK = Path('project/source')
EXPORTS = Path('exports')
WORK.mkdir(parents=True, exist_ok=True)
EXPORTS.mkdir(parents=True, exist_ok=True)

working_copy = WORK / SOURCE.name
if not working_copy.exists():
    shutil.copy2(SOURCE, working_copy)

out_path = EXPORTS / 'Google_Cloud_Setup_Professional_Final.mp4'
cap = cv2.VideoCapture(str(SOURCE))
fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# MPEG-4 Part 2 is broadly available in OpenCV's Windows build.
writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*'mp4v'),
                         fps, (width, height))
if not writer.isOpened():
    raise RuntimeError('Could not open MP4 writer')

fade_frames = max(1, round(fps * 0.35))
written = 0
while True:
    ok, frame = cap.read()
    if not ok:
        break
    idx = written
    if idx < fade_frames:
        alpha = (idx + 1) / fade_frames
        frame = cv2.convertScaleAbs(frame, alpha=alpha, beta=255 * (1 - alpha))
    elif idx >= frame_count - fade_frames:
        alpha = (frame_count - idx) / fade_frames
        frame = cv2.convertScaleAbs(frame, alpha=alpha, beta=255 * (1 - alpha))
    writer.write(frame)
    written += 1

cap.release()
writer.release()

manifest = {
    'source': str(SOURCE.resolve()),
    'working_copy': str(working_copy.resolve()),
    'master': str(out_path.resolve()),
    'width': width,
    'height': height,
    'fps': fps,
    'frames': written,
    'duration_seconds': written / fps,
    'edit_note': 'Original five-step recording preserved; 0.35s white edge fades only.',
}
(EXPORTS / 'master_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps(manifest, indent=2))
