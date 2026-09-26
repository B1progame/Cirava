"""Resolve automation template for this project.

Run from Resolve's Fusion Console or external scripting environment after
enabling Resolve external scripting. It creates a project, imports the master,
creates a 1920x1080/30 timeline, and saves a .drp archive.
"""
from pathlib import Path
import sys

MASTER = str(Path('exports/Google_Cloud_Setup_Professional_Final.mp4').resolve())
PROJECT_NAME = 'Google Cloud Setup – Professional Tutorial'
PROJECT_FILE = str(Path('exports/Google_Cloud_Setup_Professional_Final.drp').resolve())

def main():
    import DaVinciResolveScript as dvr
    resolve = dvr.scriptapp('Resolve')
    if not resolve:
        raise RuntimeError('Resolve scripting API is unavailable. Enable External scripting > Local.')
    pm = resolve.GetProjectManager()
    project = pm.CreateProject(PROJECT_NAME) or pm.GetCurrentProject()
    if not project:
        raise RuntimeError('Could not create or access the Resolve project')
    media_pool = project.GetMediaPool()
    items = media_pool.ImportMedia([MASTER])
    if not items:
        raise RuntimeError('Could not import the rendered master')
    timeline = media_pool.CreateTimelineFromClips('Google Cloud Setup – Master', items)
    if not timeline:
        raise RuntimeError('Could not create timeline')
    project.SetCurrentTimeline(timeline)
    # Save a portable Resolve project archive.
    if not pm.ExportProject(PROJECT_NAME, PROJECT_FILE):
        raise RuntimeError('Resolve did not export the project archive')
    print(PROJECT_FILE)

if __name__ == '__main__':
    main()
