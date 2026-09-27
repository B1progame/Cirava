# Follow and control transfers

Open **Transfers** to see current and recent work. Each active transfer shows its state, progress, elapsed time, and estimated time remaining. The overall panel combines progress across the queue; a single file may be moving while the queue's total also includes files that have not started yet. Toasts announce when work is queued, begins, or advances to the next queued item.

## What the status means

- **Starting transfer**: Cirava is preparing the transfer or contacting Drive.
- **Transferring**: bytes are moving. Speed, transferred size, and ETA update as data arrives.
- **Paused**: Cirava has stopped sending or receiving until you resume.
- **Retrying**: a request failed temporarily and Cirava is waiting before trying again.
- **Completed** or **Failed**: the transfer reached a final state. Open the transfer details or History for the result.

Zero bytes per second at startup does not necessarily mean a transfer is stuck. Check whether the status changes from Starting transfer, and look for a retry or error message. If it stays unchanged, see [Troubleshooting](Troubleshooting).

## Pause, resume, or cancel

Use the controls in the transfer panel to pause or resume uploads and downloads. Cancel stops the selected transfer work; it does not delete the local source file or remove an already uploaded Drive file. A cancelled item can be retried later from Transfers when the app offers that action.

Download controls take effect while data is streaming, between received blocks. If a download is paused, its live speed drops to zero until you resume. Cancelling stops the transfer; it does not remove a partially downloaded file unless Cirava's cleanup for that transfer succeeds.

## Keep transfers running in the background

Closing the window hides Cirava in the Windows notification area while it remains running. If a transfer is active, Cirava shows a notice that it continues in the background. Open the Cirava tray icon to reopen the app.

The tray menu includes **Open Cirava**, an **Open page** submenu for Home, Drive, Transfers, History, Scan & repeat, Diagnostics, Settings, and About, plus controls to pause active transfers, resume paused transfers, stop active transfers, and exit Cirava. Stopping from the tray asks for confirmation. Choosing **Exit Cirava** ends the app, so transfers cannot continue after exit.
