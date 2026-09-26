# Project Prompt — Desktop UI, Installer, First-Run Setup, Google Login and Transfer Experience

Create the complete desktop user interface and user experience for a high-performance Google Drive upload/download application.

This prompt focuses ONLY on:

* installer
* application shell
* first-run setup
* Google configuration guide
* Google login
* home screen
* drag-and-drop selection
* upload planning
* download planning
* Drive explorer
* transfer progress experience
* animations
* settings
* About screen
* application updates
* error UX
* responsive desktop behavior
* visual consistency

The actual high-performance Google Drive transfer engine is implemented separately.

The result must feel like a polished modern desktop application, not a Python utility with a web page attached.

---

# 1. Technology

Use this architecture:

```text
React
TypeScript
Vite
        │
        ▼
Python application backend
        │
        ├── Google authentication
        ├── Google Drive API
        ├── transfer engine
        ├── settings
        ├── updater
        └── local application state

Desktop container:
pywebview or another mature Python-native WebView solution
```

Preferred:

```text
Frontend:
React + TypeScript + Vite

Backend:
Python 3.12+

Desktop shell:
pywebview

Python communication:
local API/event bridge

Packaging:
PyInstaller or equivalent

Installer:
Windows installer with proper Start Menu entry,
uninstaller and application icon
```

Do NOT make the user manually start:

```text
python main.py
npm run dev
uvicorn
```

in the production application.

The finished application must install and behave like a normal desktop application.

---

# 2. Visual identity

The application should have its own identity.

Do NOT simply clone Google Drive.

Take inspiration from:

* modern macOS applications
* Windows 11
* Arc
* Linear
* Raycast
* modern cloud storage clients
* modern AI applications

The interface should feel:

```text
light
smooth
clean
slightly futuristic
premium
soft
friendly
fast
```

Avoid:

```text
heavy borders
pure black backgrounds
huge amounts of gray
cheap neon
extreme glassmorphism
overly rounded everything
UI clutter
Bootstrap-looking components
```

---

# 3. Core color direction

Primary background palette:

```text
very light blue
soft cyan
frosted white
slightly lavender highlights
subtle warm white
```

Example visual direction:

```text
#F7FBFF
#EEF7FF
#E4F3FF
#DDF7F6
#F4F0FF
```

These are inspiration values only.

Create a proper design token system rather than scattering hardcoded colors throughout the code.

Dynamic accent colors may include:

```text
blue
cyan
soft purple
very subtle peach
```

Colors should remain light.

---

# 4. Dynamic background

Several important screens should use a dynamic animated background.

It should look like soft diffused light moving underneath a translucent surface.

Imagine:

```text
large blurred blob
+
another slow gradient
+
soft radial light
+
very subtle grain
```

Movement must be slow and elegant.

NOT:

```text
gaming RGB
fast moving gradient
rainbow animation
particle explosion
```

Example:

```text
╭──────────────────────────────────────────╮
│                                          │
│        ~ soft blue glow ~                │
│                                          │
│                   ~ cyan glow ~          │
│                                          │
│      ~ subtle lavender light ~           │
│                                          │
╰──────────────────────────────────────────╯
```

Use GPU-friendly CSS.

Prefer:

```text
transform
opacity
filter
```

Avoid constantly repainting enormous complex DOM structures.

Support:

```text
prefers-reduced-motion
```

---

# 5. Typography

Use a modern neutral interface font.

Prefer the native system font stack where possible.

Typography hierarchy:

```text
Hero title
32–44 px

Screen title
26–32 px

Section title
18–22 px

Normal UI
14–16 px

Metadata
12–13 px
```

Use font weight rather than excessive font-size changes.

Avoid extremely bold typography.

---

# 6. Installer

Create a proper Windows installer.

Installer should contain:

```text
application logo

application name

version

install location

create Start Menu shortcut

optional desktop shortcut

launch application after installation
```

The installer must bundle everything required to run the application.

The user should NOT need to separately install:

```text
Python
Node.js
npm
pip
Vite
Visual Studio
```

---

# 7. First launch detection

When the application starts, determine:

```text
has_app_been_initialized?
```

Persist this locally.

Possible state:

```json
{
  "firstRunComplete": false
}
```

If:

```text
firstRunComplete == false
```

launch the onboarding experience automatically.

Do not show the normal application first.

---

# 8. First-run background

The first-run screen should use the dynamic light background.

Example:

```text
┌──────────────────────────────────────────────┐
│                                              │
│     soft moving light background             │
│                                              │
│        ╭──────────────────────────╮          │
│        │                          │          │
│        │   Setup your Drive       │          │
│        │                          │          │
│        │        Continue →        │          │
│        │                          │          │
│        ╰──────────────────────────╯          │
│                                              │
└──────────────────────────────────────────────┘
```

The setup window should appear to float over the background.

---

# 9. Floating setup guide

Create a floating setup wizard.

Visual style:

```text
rounded but not exaggerated
soft shadow
semi-translucent
high readability
large screenshots
clear instructions
step indicator
```

Example:

```text
╭─────────────────────────────────────────────────╮
│ Setup Google Drive                       2 / 6   │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │                                             │ │
│ │         CURRENT GOOGLE SCREENSHOT           │ │
│ │                                             │ │
│ │             ◉ highlighted area             │ │
│ │                                             │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ Create an OAuth desktop application.            │
│                                                 │
│ Click "Create credentials" and choose the       │
│ currently documented desktop application       │
│ option.                                         │
│                                                 │
│ ← Back                         Continue →        │
╰─────────────────────────────────────────────────╯
```

---

# 10. Do not use stale setup screenshots

Before implementing the onboarding guide, research the CURRENT Google setup process.

Use:

* browser automation
* browser inspection
* computer vision
* current official Google documentation

to verify the current interface.

Navigate the current Google Cloud Console setup flow and capture screenshots for the onboarding wizard.

Use computer vision or manual inspection to identify the important controls.

Add annotations such as:

```text
highlight rectangle
arrow
numbered marker
soft spotlight
```

The wizard screenshots must match the current Google interface as closely as practical.

Do not rely on old screenshots found in random tutorials.

---

# 11. Ask the developer/user when necessary

Browser automation may encounter:

```text
Google sign-in
2FA
CAPTCHA
account-selection screen
organization restriction
billing warning
security confirmation
```

Never attempt to bypass these.

Pause the screenshot-gathering process at that point and ask me to complete the human-authentication step.

After I complete it, continue gathering screenshots.

---

# 12. Setup wizard steps

The exact labels must be verified against Google's current official documentation.

The wizard will roughly cover:

```text
1. Create/select Google Cloud project

2. Enable Google Drive API

3. Configure OAuth consent / branding if required

4. Configure application audience if required

5. Create OAuth client

6. Choose the correct desktop/native application type

7. Obtain required OAuth configuration

8. Return to this application

9. Enter/import configuration

10. Validate configuration
```

Do not assume these labels remain unchanged.

Research them before implementation.

---

# 13. Interactive setup steps

The wizard must not just display a giant block of instructions.

Each page explains ONE thing.

Example:

```text
Step 3

Enable Google Drive API

[ screenshot ]

1. Open APIs & Services
2. Search for Google Drive API
3. Open it
4. Press Enable

[ Open Google Cloud Console ]

← Back                I've done this →
```

---

# 14. Deep links

Where appropriate, include buttons like:

```text
Open Google Cloud Console

Open Google Drive API page

Open OAuth configuration

Open official documentation
```

Use current official URLs.

Do not hardcode undocumented URLs that could break unnecessarily.

---

# 15. Setup data entry

Eventually show configuration fields.

Example:

```text
Google configuration

Client ID
[______________________________________]

Additional configuration
[______________________________________]

                         Test configuration
```

Only request fields actually required by the chosen implementation.

Do not ask for unnecessary secrets.

---

# 16. Configuration validation

When the user presses:

```text
Test configuration
```

perform real validation.

Do NOT simply check whether fields are non-empty.

Validation stages could display:

```text
✓ Configuration format

✓ OAuth endpoint reachable

✓ Google authorization available

✓ Token exchange configuration

✓ Drive API reachable

✓ Required permissions available
```

Show progress sequentially.

Example:

```text
Testing Google configuration...

✓ Client configuration
✓ OAuth authorization
✓ Drive API connection
✓ File metadata test

Everything looks good.
```

---

# 17. Validation failure

When validation fails, explain exactly which step failed.

Bad:

```text
Authentication error.
```

Good:

```text
Google Drive API could not be accessed.

Your OAuth login worked, but Drive API access returned:

403 — API not enabled

Open your Google Cloud project and enable Google Drive API.

[Show me how]
```

The:

```text
Show me how
```

button should reopen the relevant wizard step.

---

# 18. Complete setup

Once validation succeeds:

```text
Everything is ready
```

Show a subtle completion animation.

Then store:

```text
firstRunComplete = true
```

Transition smoothly to the login page.

Do not abruptly reload the entire window.

---

# 19. Login hero screen

After initial setup, show the main login hero page when no Google account is authenticated.

This should be one of the strongest visual screens.

Example layout:

```text
┌────────────────────────────────────────────────┐
│                                                │
│             moving soft background             │
│                                                │
│             Transfer your files.               │
│             Without the waiting.               │
│                                                │
│     Fast resumable Google Drive transfers      │
│                                                │
│           ╭──────────────────────╮             │
│           │  G  Sign in Google  │             │
│           ╰──────────────────────╯             │
│                                                │
│               Setup settings                   │
│                                                │
└────────────────────────────────────────────────┘
```

---

# 20. Login card

Place authentication inside a floating card.

Card:

```text
soft translucent background
subtle border
large blur behind it
soft shadow
```

Google login button should look clean and familiar but should not impersonate Google.

Example:

```text
╭────────────────────────────╮
│  G   Continue with Google  │
╰────────────────────────────╯
```

---

# 21. Google OAuth UX

Clicking Google login:

```text
button press
↓
small loading animation
↓
system browser opens
↓
Google OAuth
↓
application receives callback
↓
browser may show "You may return to the app"
↓
application becomes active
```

During authentication the app displays:

```text
Waiting for Google...

Complete sign-in in your browser.
```

Include:

```text
Open browser again
Cancel
```

---

# 22. Login success transition

Do not instantly switch screens.

Animate:

```text
Google login card
↓
success check
↓
card subtly shrinks/fades
↓
dynamic background shifts
↓
main application slides/fades in
```

Target duration:

```text
400–700 ms
```

Keep it smooth, not theatrical.

---

# 23. Application shell

After login, show the main application.

Use a persistent left sidebar.

Example:

```text
┌───────────────┬──────────────────────────────────┐
│               │                                  │
│   App logo    │                                  │
│               │                                  │
│   Home        │                                  │
│   Drive       │                                  │
│   Upload      │                                  │
│   Download    │                                  │
│   Transfers   │                                  │
│   History     │                                  │
│               │                                  │
│───────────────│                                  │
│   Settings    │                                  │
│   About       │                                  │
│               │                                  │
└───────────────┴──────────────────────────────────┘
```

---

# 24. Sidebar behavior

Sidebar width approximately:

```text
220–260 px
```

Use:

```text
icon
label
active indicator
```

Selected page should use a soft pill/background.

Do not put every element into its own visible rectangle.

The sidebar should feel visually quiet.

---

# 25. Sidebar footer

Bottom area:

```text
Google account avatar

Account name

email address

connection status
```

Click opens compact account menu:

```text
Drive account
Switch account
Sign out
Settings
```

---

# 26. Home page

Home is minimal.

The central focus is the upload/download action.

Center:

```text
               ◌
             ╭───╮
             │ + │
             ╰───╯

       Drop files or folders

            or click +
```

---

# 27. Pulsing plus control

Create a large central circular plus button.

It should have:

```text
subtle pulse
soft outer ring
very subtle glow
```

NOT a constant distracting animation.

Example:

```text
           ·  ·
       ·           ·

           ╭─────╮
           │  +  │
           ╰─────╯

       ·           ·
           ·  ·
```

Pulse approximately every few seconds.

On hover:

```text
slightly enlarge
outer ring becomes clearer
background becomes brighter
```

---

# 28. Plus menu

Clicking the plus opens:

```text
Upload files
Upload folder

Download from Drive

Open Drive browser
```

Use an animated contextual menu.

---

# 29. Drag and drop

Allow dropping:

```text
one file
multiple files
one folder
multiple folders
mixed selection
```

onto the home area.

When files enter the window, transform the screen into a drop zone.

Example:

```text
┌───────────────────────────────────────────────┐
│                                               │
│             Drop to add files                 │
│                                               │
│                   ↓                           │
│                                               │
└───────────────────────────────────────────────┘
```

Use a soft scale and background change.

---

# 30. Upload planner

After choosing files/folders, do NOT immediately upload.

Open:

```text
Upload Planner
```

This page lets the user decide exactly where everything should go.

---

# 31. Upload Planner layout

Use three main areas:

```text
┌─────────────────────────────────────────────────────┐
│ Upload 12 items                ETA ~ 3m 24s  Upload │
├───────────────┬─────────────────────┬───────────────┤
│               │                     │               │
│ Local items   │ Google Drive        │ Plan/details  │
│               │                     │               │
│ file.zip      │ My Drive            │ Destination   │
│ photos/       │ ├─ School           │ /School       │
│ video.mp4     │ ├─ Projects         │               │
│               │ └─ Backup           │ 18.2 GB       │
│               │                     │               │
└───────────────┴─────────────────────┴───────────────┘
```

---

# 32. Own Google Drive explorer

Create your own file explorer interface using Drive data.

It should behave like a native file manager.

Support:

```text
breadcrumbs

folder tree

file list

search

sorting

multi-selection

double click folder

back/forward

refresh

new folder

details

list/grid mode
```

Do not embed the Google Drive website.

---

# 33. Explorer breadcrumbs

Example:

```text
My Drive  >  School  >  Music  >  Presentation
```

Breadcrumb segments should be clickable.

Animate folder transitions subtly.

---

# 34. File rows

Example:

```text
Name                  Type        Size      Modified

📁 Presentation       Folder                Today
📄 notes.docx         Document    820 KB    Yesterday
🎬 video.mp4          Video       4.2 GB    Monday
```

Support sorting by:

```text
name
size
date
type
```

---

# 35. Assigning destinations

User can choose:

```text
All selected files → one Drive folder
```

or individual destinations:

```text
video.mp4      → Videos
school.zip     → School/Backup
photos/        → Photos/2026
```

Allow drag-and-drop assignment.

---

# 36. File planning visualization

When assigning files, show their destinations visually.

Example:

```text
video.mp4
    ↓
My Drive / Videos

SchoolProject/
    ↓
My Drive / School / Projects
```

---

# 37. Transfer prediction

Before starting, calculate an estimated duration.

Display:

```text
18.6 GB
Estimated upload speed: 812 Mbps
Estimated completion: ~3m 04s
```

The prediction should use:

```text
recent benchmark data
current connection
file sizes
number of files
API overhead
historical performance
```

Label uncertain estimates appropriately.

Example:

```text
Estimated: 3–4 minutes
```

rather than fake precision.

---

# 38. Hold-to-upload button

Top-right:

```text
Hold to Upload
```

This is a special interaction.

Normal:

```text
╭──────────────────────────╮
│       Hold to Upload     │
╰──────────────────────────╯
```

On press:

```text
button starts filling
```

Example:

```text
0%
▓░░░░░░░░░

50%
▓▓▓▓▓░░░░░

100%
▓▓▓▓▓▓▓▓▓▓
```

Hold approximately:

```text
700–1000 ms
```

When complete:

```text
small haptic-like visual response
icon changes to arrow/check
transfer starts
```

If released early:

```text
progress smoothly reverses
```

---

# 39. Accessibility for hold interaction

Do not make holding the ONLY possible way to initiate transfer.

Provide either:

```text
keyboard equivalent
```

or a setting:

```text
Require hold to start transfer
```

Users requiring reduced interaction can use normal activation.

---

# 40. Upload transition

When upload starts:

```text
planner interface
↓
subtle blur
↓
cards move/fade away
↓
sidebar recedes
↓
full-screen transfer experience appears
```

This screen temporarily takes visual priority over the normal application shell.

---

# 41. Full transfer mode

The upload/download screen should visually block the main sidebar.

Not by destroying it.

Instead:

```text
sidebar fades/slides behind transfer layer
```

Transfer experience occupies the entire application content.

---

# 42. Transfer background

Use a richer version of the dynamic background.

Upload:

```text
blue
cyan
slight violet
```

Download:

```text
cyan
blue
very subtle green
```

Keep both visually related.

---

# 43. Main progress area

Center:

```text
Uploading

18.4 GB / 24.1 GB

███████████████████░░░░░░

812 Mbps

~58 seconds remaining
```

Progress bar should animate continuously but accurately.

No fake movement.

---

# 44. Transfer animation

Add a custom animated illustration representing the transfer process.

The illustration should look like a simplified Drive-style file explorer.

Example:

```text
╭──────────────────────────────────────────╮
│ My Drive                                 │
│                                          │
│ 📁 School                                │
│ 📁 Videos                                │
│ 📁 Projects                              │
│                                          │
│      📄 Project.zip                      │
│           ↘                              │
│             📁 Projects                  │
╰──────────────────────────────────────────╯
```

---

# 45. Animated virtual cursor

Inside this visualization only, use a stylized cursor.

It is NOT the user's real cursor.

The virtual cursor visually demonstrates:

```text
file selected
↓
file dragged
↓
destination folder highlights
↓
file drops
↓
upload progresses
```

Example:

```text
        ↖ virtual cursor

Project.zip
     │
     └──────────────► Projects/
```

---

# 46. Virtual explorer represents actual transfer plan

The visualization must not randomly animate fake folders.

It should represent the user's actual planned structure.

Example:

User chose:

```text
Video.mp4
→ School/Media

Project.zip
→ Projects/2026
```

Then the visualization should show those paths.

---

# 47. Per-file upload progress

Each animated file has its own progress.

Example:

```text
Project.zip

████████████░░░░░░░░
63%
```

Another:

```text
Video.mp4

██████░░░░░░░░░░░░░░
31%
```

Completed:

```text
✓ notes.pdf
```

---

# 48. Collapsible transfer visualization

The visualization should normally be compact.

Include an arrow button.

Collapsed:

```text
Uploading
████████████████░░░
72%

                        ⌄
```

Expanded:

```text
Uploading
████████████████░░░
72%

                        ⌃

╭─────────────────────────────╮
│ transfer visualization      │
│                             │
│ virtual explorer            │
│ file animations             │
│ file progress               │
╰─────────────────────────────╯
```

---

# 49. Arrow animation

When expanded:

```text
arrow rotates 180°
```

Use:

```text
spring-like rotation
content height animation
opacity fade
small translate motion
```

Avoid instantly appearing content.

Suggested transition:

```text
250–400 ms
```

---

# 50. Expanded animation sequence

When opening:

```text
arrow rotates
↓
container grows
↓
background softly appears
↓
Drive explorer fades upward
↓
files fade in
↓
virtual cursor appears
```

When closing, reverse gracefully.

---

# 51. Transfer information

Also display:

```text
current speed

average speed

peak speed

remaining data

ETA

files completed

files remaining

active transfers
```

Example:

```text
824 Mbps

Average        791 Mbps
Peak           901 Mbps
Remaining      6.2 GB
Files          5 / 12
```

---

# 52. Pause controls

Actions:

```text
Pause
Cancel
Background
```

Background returns to the normal app while transfer continues.

Sidebar gets a transfer indicator:

```text
Transfers   ● 2
```

---

# 53. Transfer mini indicator

When transfer is in background:

top or sidebar area can show:

```text
↑ 812 Mbps
72%
```

Clicking returns to full transfer mode.

---

# 54. Upload complete

Completion experience:

```text
progress reaches 100%
↓
progress becomes checkmark
↓
background subtly changes
↓
small success motion
```

Show:

```text
Upload complete

24.1 GB
12 files
3m 18s

Average speed
781 Mbps
```

Actions:

```text
Open in Drive
Upload more
Done
```

---

# 55. Download flow

Downloading should mirror uploading.

Flow:

```text
Drive Explorer
↓
select files/folders
↓
Download Planner
↓
choose local destination
↓
see estimated size/time
↓
Hold to Download
↓
full transfer mode
```

---

# 56. Download Planner

Layout:

```text
Drive files
+
destination path
+
file conflict handling
+
space available
+
estimated duration
```

Example:

```text
Download to

C:\Users\Benji\Downloads

Available space
612 GB

Download size
84.3 GB

Estimated time
~14 minutes
```

---

# 57. Download animation

Use the same visual language but reverse direction.

Example:

```text
Google Drive file
        ↓
virtual cursor selects it
        ↓
animated movement toward
local folder
        ↓
local file fills
```

---

# 58. Transfers page

Create dedicated transfer management page.

Tabs:

```text
Active
Queued
Completed
Failed
```

Rows/cards:

```text
Project.zip

Upload
12.4 / 18.8 GB
66%

702 Mbps

Pause
Cancel
```

---

# 59. History page

Show previous operations.

Example:

```text
Today

Project.zip
Uploaded
18.8 GB
3m 10s

Video.mp4
Downloaded
7.3 GB
1m 04s
```

Allow:

```text
clear history
reveal local file
open Drive location
retry
```

---

# 60. Settings screen

Sections:

```text
General

Transfers

Network

Google account

Appearance

Updates

Advanced
```

---

# 61. General settings

Options:

```text
Launch at startup

Continue unfinished transfers

Show notifications

Confirm cancellation

Start minimized
```

---

# 62. Transfer settings

Expose:

```text
Automatic optimization

Upload mode

Download mode

Bandwidth limits

Concurrent files

Advanced chunk configuration
```

Advanced options should be collapsed by default.

---

# 63. Appearance settings

Support:

```text
Light

Dark

System
```

Primary visual design is light mode.

Dark mode should be designed properly rather than simply inverting colors.

Also:

```text
Reduce motion

Disable animated background

Compact mode
```

---

# 64. About screen

Create a polished About page.

Example:

```text
[ App Logo ]

App Name

Version 1.0.0

High-performance Google Drive transfers.

Created by:
[YOUR NAME]
```

---

# 65. Google affiliation notice

Clearly display:

```text
This application is an independent project
and is not affiliated with, endorsed by,
or sponsored by Google LLC.
```

Do not visually imply official Google ownership.

---

# 66. About technical information

Include:

```text
App version

Python version if useful

transfer engine version

database version

update channel
```

Actions:

```text
Check for updates

Open project website

Licenses

Privacy

Diagnostics
```

---

# 67. Real application updater

Implement actual version checking.

Suggested model:

```text
Application
↓
fetch signed update manifest
↓
compare semantic version
↓
show update
↓
download installer/package
↓
verify checksum/signature
↓
apply update
↓
restart
```

---

# 68. Update UI

Example:

```text
Update available

Version 1.4.0

• Faster large-file downloads
• Improved upload recovery
• New Drive explorer

48 MB

[Later]        [Update]
```

Display real release notes.

---

# 69. Automatic update settings

Options:

```text
Automatically check for updates

Automatically download updates

Install when application closes

Update channel:
Stable
Beta
```

Default:

```text
Stable
```

---

# 70. Python dependency updates

DO NOT run:

```text
pip install --upgrade
```

for random dependencies every application startup.

For production builds, Python libraries are part of the packaged application.

When dependencies change:

```text
release new application version
↓
updater installs updated package
```

This prevents:

```text
dependency incompatibility
broken environments
supply-chain problems
administrator permission problems
different installations behaving differently
```

---

# 71. Development dependency updater

A developer-only mode may provide:

```text
Check Python dependencies
```

using the project's locked dependency file.

Never expose this as the normal production updater.

---

# 72. Update failure

If application update fails:

```text
Update could not be installed.

Your current version is unchanged.

[Retry]
[View details]
```

Never leave the installation half-updated.

---

# 73. Startup update check

Startup flow:

```text
launch
↓
load local UI immediately
↓
check update asynchronously
↓
continue application
```

Do NOT block application startup for a long network update check.

Only interrupt when:

```text
critical update
```

is explicitly required.

---

# 74. Startup state machine

Implement clear application states:

```text
STARTING

↓ first-ever run?

SETUP

↓ configured but not authenticated?

LOGIN

↓ authenticated?

HOME
```

Example:

```text
if !configured:
    show_setup()

elif !authenticated:
    show_login()

else:
    show_home()
```

---

# 75. Splash screen

If startup requires more than a brief moment, use a tiny splash screen.

Example:

```text
[logo]

App Name

Starting…
```

Maximum visual complexity should be low.

Do not show a splash screen unnecessarily if startup is almost instant.

---

# 76. Error UX

Errors should appear as structured cards/toasts.

Example:

```text
Upload paused

Your network connection was lost.

We'll continue automatically once you're online.
```

Avoid:

```text
Exception: requests.exceptions...
```

unless user expands:

```text
Technical details
```

---

# 77. Toast system

Use small status toasts for:

```text
Folder created

Link copied

Transfer paused

Upload resumed

Update downloaded
```

Toast stack should not cover important controls.

---

# 78. Confirmation modals

Use modals only for destructive actions.

Examples:

```text
Cancel 84 GB upload?

Remove account?

Clear transfer history?
```

Do not use confirmation dialogs for every normal action.

---

# 79. Motion system

Define consistent motion tokens.

For example:

```text
fast
120–160 ms

normal
200–280 ms

slow
350–500 ms
```

Use consistent easing.

Preferred:

```text
ease-out
spring-like curves
```

Avoid:

```text
linear UI transitions
1-second button animations
huge bouncing
```

---

# 80. Page transitions

Changing sidebar page:

```text
old content:
fade 100%
→ 0%
translate Y 0 → 4px

new content:
fade 0%
→ 100%
translate Y 6px → 0
```

Keep page changes quick.

---

# 81. Shared element transitions

Where practical:

```text
file selected on Home
```

may visually become:

```text
file card in Upload Planner
```

Use this sparingly.

---

# 82. Hover behavior

Interactive elements should react subtly.

Buttons:

```text
1–2 px translate
slight brightness
```

Rows:

```text
soft background
```

Cards:

```text
slightly stronger shadow
```

No exaggerated 3D tilt.

---

# 83. Keyboard navigation

Support:

```text
Tab
Shift+Tab
Enter
Escape
Arrow keys
Ctrl+A
Ctrl+F
Delete where appropriate
```

Drive explorer should be usable primarily through keyboard as well.

---

# 84. Accessibility

Requirements:

```text
semantic labels

visible keyboard focus

reasonable contrast

screen-reader accessible controls

reduced motion support

no information represented only by color
```

---

# 85. Window behavior

Support normal desktop resizing.

Recommended minimum:

```text
1100 × 700
```

Ideal:

```text
1400 × 850+
```

On narrower windows:

```text
sidebar may become icon-only
secondary inspector may collapse
```

Do not let the layout overflow horizontally.

---

# 86. Native title bar

Prefer a clean custom title-bar experience only if it can remain fully functional.

Required:

```text
drag region

minimize

maximize

close

double click maximize
```

Do not break normal Windows window behavior for visual appearance.

---

# 87. Performance

UI must remain smooth while transferring huge files.

Never send thousands of transfer events per second into React.

Backend should provide throttled UI updates.

Target UI updates around:

```text
5–10 progress updates/second
```

Use efficient state selectors so updating one transfer does not rerender the entire application.

---

# 88. React architecture

Use reusable components.

Example:

```text
AppShell

Sidebar

TitleBar

DynamicBackground

GlassPanel

DriveExplorer

Breadcrumbs

FileTable

FileTree

TransferCard

TransferProgress

TransferVisualization

VirtualCursor

SetupWizard

SetupScreenshot

GoogleLoginCard

Toast

Modal

UpdaterDialog
```

---

# 89. State architecture

Separate:

```text
authentication state

setup state

Drive state

transfer state

UI state

settings state

update state
```

Do not create one enormous global state object.

---

# 90. Design tokens

Create central tokens for:

```text
colors

spacing

radius

shadow

typography

animation durations

easing

z-index
```

Example:

```text
radius.sm
radius.md
radius.lg

space.1
space.2
space.3

motion.fast
motion.normal
motion.slow
```

---

# 91. Component consistency

One button type should not have 15 unrelated visual designs.

Define:

```text
PrimaryButton

SecondaryButton

GhostButton

DangerButton

IconButton
```

Use them consistently.

---

# 92. Loading skeletons

When loading Drive content, use skeletons.

Example:

```text
███████████     █████
██████████████  ███
████████         █████
```

Do not show an empty page and then suddenly populate it.

---

# 93. Empty states

Example Drive folder empty:

```text
This folder is empty

Drop files here
or

[Upload]
```

History empty:

```text
No transfers yet.

Your completed transfers will appear here.
```

---

# 94. First-start complete flow

The entire first-run experience should work like this:

```text
Installer finishes

↓ Launch

Dynamic setup screen

↓ Continue

Interactive Google setup guide

↓ screenshots + guidance

Configuration entry

↓ Test

Real validation

↓ Success

Login hero

↓ Continue with Google

System browser OAuth

↓ Success

Home

↓ Drop file

Upload Planner

↓ choose Drive destination

ETA shown

↓ Hold to Upload

Full transfer experience

↓ Completed

Home / Drive / Transfers
```

---

# 95. Normal startup flow

After everything is configured:

```text
launch app

↓ authenticated?

YES
↓
Home

NO
↓
Login hero
```

Do not force the user through setup again.

---

# 96. Setup can be reopened

Settings should contain:

```text
Google configuration

Run setup guide again
```

This reopens the wizard without destroying existing configuration unless the user explicitly changes it.

---

# 97. Developer screenshot workflow

Before completing the onboarding wizard:

1. Open the current official Google configuration pages using browser automation.

2. Gather screenshots of every relevant step.

3. Use computer vision to determine useful annotation locations.

4. Crop screenshots to only the relevant browser content.

5. Blur/redact:

   * email addresses
   * project identifiers
   * credentials
   * personal account data

6. Add reusable annotation metadata rather than baking instructions directly into the screenshots where possible.

Example:

```json
{
  "image": "oauth-create-client.webp",
  "annotations": [
    {
      "type": "spotlight",
      "x": 0.74,
      "y": 0.28,
      "width": 0.18,
      "height": 0.07
    }
  ]
}
```

This allows annotations to scale responsively.

---

# 98. Screenshot freshness

Include metadata:

```text
capturedAt
googleUiVersion if identifiable
wizardStep
```

Make screenshots easy to replace when Google changes the Cloud Console interface.

Do not scatter hardcoded screenshot imports throughout the UI.

---

# 99. Final visual polish pass

Before considering the UI finished:

check every screen for:

```text
spacing consistency

alignment

button hierarchy

typography hierarchy

focus states

empty states

loading states

errors

very long filenames

very deep folders

large file counts

high DPI monitors

125% Windows scaling

150% Windows scaling

light mode

dark mode

reduced motion
```

---

# 100. Final acceptance criteria

Do not consider the UI finished until ALL of these work:

```text
installer works

application launches normally

first-launch detection works

setup guide appears only when appropriate

setup guide contains current screenshots

Google configuration can be entered

configuration is actually validated

Google OAuth login works

login hero is polished

Home page works

drag-and-drop works

file picker works

folder picker works

Drive explorer works

Upload Planner works

Download Planner works

destination assignment works

transfer ETA appears

Hold to Upload works

Hold to Download works

transfer full-screen mode works

sidebar blocking transition works

transfer visualization works

per-file progress works

virtual cursor visualization works

expand/collapse animation works

background transfers work

Transfers page works

History page works

Settings works

About works

Google affiliation disclaimer exists

application updater works

failed update safely rolls back

application can restart successfully

UI remains responsive during transfers
```

---

# Final design objective

The application should feel as though these ideas were combined:

```text
modern cloud storage client
+
premium desktop file manager
+
high-performance transfer manager
+
clean modern onboarding
+
soft futuristic interface
```

The experience should communicate:

```text
drop file
choose destination
know how long it will take
start
watch it happen
done
```

without exposing technical complexity unless the user deliberately opens advanced controls.

The first-run experience should make a complicated Google API setup understandable through an interactive visual tutorial rather than expecting the user to read documentation.

The transfer experience should be visually interesting enough that uploading or downloading a large file feels like an intentional part of the product, while every animation remains tied to real transfer state instead of displaying fake progress.

Build the whole UI as a coherent product rather than a collection of individually styled pages.
