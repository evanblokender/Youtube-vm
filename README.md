╔══════════════════════════════════════════════════════════════════════════════════╗
║        YouTube Chat Controls VirtualBox VM — Arch Linux Chaos Mode             ║
║                        COMPLETE SETUP TUTORIAL                                  ║
╚══════════════════════════════════════════════════════════════════════════════════╝

This tutorial walks you through everything you need to get the bot running.
Estimated setup time: 45–90 minutes if you're following along carefully.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 1: SYSTEM REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Host Machine Requirements:
  • OS: Windows 10/11, Ubuntu 20.04+, or macOS 12+
  • RAM: Minimum 8GB (16GB recommended — 4GB for VM + rest for host)
  • CPU: 4+ cores with VT-x/AMD-V virtualization enabled in BIOS
  • Storage: 30GB+ free space
  • Internet: Stable upload for streaming (5+ Mbps recommended)

Software Required:
  • Python 3.11 or newer
  • Oracle VirtualBox 7.0+
  • OBS Studio (for streaming the VM to YouTube)
  • A YouTube channel with Live Streaming enabled


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 2: INSTALL SYSTEM DEPENDENCIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 2A — Install Python 3.11+

  Windows:
    Download from https://python.org → check "Add to PATH" during install
    Verify: open Command Prompt → python --version

  Ubuntu/Debian:
    sudo apt update
    sudo apt install python3.11 python3.11-pip python3.11-venv

  macOS:
    brew install python@3.11


STEP 2B — Install VirtualBox

  Windows/macOS:
    Download from https://www.virtualbox.org/wiki/Downloads
    Install with default options
    
  Ubuntu:
    sudo apt install virtualbox virtualbox-ext-pack

  After install, verify VBoxManage is accessible:
    Windows: Add "C:\Program Files\Oracle\VirtualBox" to your PATH environment variable
    Linux/Mac: Should work automatically
    
    Test: Open terminal → VBoxManage --version
    Expected output: 7.x.x (any version number)


STEP 2C — Install OBS Studio

  Download from https://obsproject.com
  This is used to capture the VM window and stream it to YouTube.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 3: SET UP THE VIRTUAL MACHINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 3A — Download the Arch Linux ISO

  Go to: https://archlinux.org/download/
  Download the latest ISO (archlinux-YYYY.MM.DD-x86_64.iso)
  Save it somewhere you'll remember, e.g.: C:\ISOs\archlinux.iso


STEP 3B — Create the Virtual Machine

  Open VirtualBox → Click "New"

  Settings to use:
    Name:          ArchLinuxChaos         ← IMPORTANT: must match config.json vm_name
    Type:          Linux
    Version:       Arch Linux (64-bit)
    RAM:           2048 MB (2GB minimum, 4096 recommended)
    CPU:           2 cores
    Hard Disk:     Create new VDI, Dynamically allocated, 20GB
    
  After creating VM, go to Settings:
  
  System → Processor:
    Enable "PAE/NX"
    
  System → Acceleration:
    Enable VT-x/AMD-V (should be on by default)
    
  Display:
    Video Memory: 128MB
    Graphics Controller: VMSVGA
    Enable 3D Acceleration: OFF (causes issues in headless mode)
    
  Storage:
    Click the empty optical drive
    Click the disc icon → "Choose a disk file"
    Select your downloaded Arch Linux ISO
    
  Network:
    Adapter 1: NAT (lets the VM access the internet through your host)


STEP 3C — Boot and Verify (optional test)

  Start the VM from VirtualBox GUI.
  You should see the Arch Linux boot menu.
  This confirms the ISO loaded correctly.
  Close the VM window (Power off) — the bot will start it headlessly later.


STEP 3D — Create a Safe Snapshot (CRITICAL)

  Start the VM → wait for it to boot to the Arch Linux prompt
  Then from VirtualBox main window:
    Machine → Take Snapshot
    Name: SafeBase
    Description: Clean Arch ISO boot state
    Click OK
    
  Power off the VM.
  
  This snapshot is what !revert restores. Every time the stream gets too chaotic
  or the VM breaks, the bot can snap back to this clean state instantly.

  From command line you can also do:
    VBoxManage snapshot "ArchLinuxChaos" take "SafeBase" --description "Clean state"


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 4: SET UP YOUTUBE API ACCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You need TWO things from Google:
  1. An API Key (for reading public data like live chat)
  2. OAuth2 credentials (for posting messages as your channel)

STEP 4A — Create a Google Cloud Project

  1. Go to: https://console.cloud.google.com/
  2. Click "Select a project" → "New Project"
  3. Name it: "ArchChaosBot" (anything works)
  4. Click "Create"
  5. Make sure this new project is selected at the top


STEP 4B — Enable YouTube Data API v3

  1. In Google Cloud Console, go to "APIs & Services" → Library
  2. Search for "YouTube Data API v3"
  3. Click it → Click "Enable"


STEP 4C — Create an API Key

  1. Go to "APIs & Services" → "Credentials"
  2. Click "+ CREATE CREDENTIALS" → "API Key"
  3. Copy the key shown — this is your youtube_api_key
  4. (Optional but recommended) Click "Restrict Key":
     API restrictions → YouTube Data API v3


STEP 4D — Create OAuth2 Desktop Credentials

  1. Still on Credentials page
  2. Click "+ CREATE CREDENTIALS" → "OAuth client ID"
  3. If prompted to configure consent screen:
     - Choose "External"
     - Fill in App name: "ArchChaosBot"
     - Add your email as developer contact
     - Save and continue through all steps
     - On Scopes page, click "Add or Remove Scopes"
     - Search for "youtube" and add:
         .../auth/youtube
         .../auth/youtube.force-ssl
     - Save → Back to Dashboard
  4. Now create the OAuth client:
     Application type: Desktop app
     Name: ArchChaosBot Desktop
     Click Create
  5. Download the JSON file (client_secrets.json)
     Save it to your archstream project folder

  You should now have:
    youtube_api_key:      AIzaSy... (from Step 4C)
    youtube_client_id:    12345-abc.apps.googleusercontent.com
    youtube_client_secret: GOCSPX-...


STEP 4E — Get Your Refresh Token

  This lets the bot post messages as your YouTube channel.

  In your terminal, navigate to the archstream folder:
    cd path/to/archstream

  Run the token helper:
    python get_token.py

  A browser window will open. Sign in with the YouTube account you want
  the bot to post from. Grant the permissions requested.

  After authorizing, the script prints:
    Refresh Token: 1//0gAB...

  Copy that refresh token. You'll need it in config.json.


STEP 4F — Find Your Channel ID
  Channel ID:
    Go to YouTube Studio → Settings → Channel
    Or visit: https://www.youtube.com/account_advanced
    It looks like: UCxxxxxxxxxxxxxxxxxxxxx


STEP 4G — Find Your Live Chat ID

Live Chat ID:
Edit getchat_id.py and add the same api key that is in your config.json.
now run python getchat_id.py enter the link to your stream. EG: "https://www.youtube.com/watch?v=123h4" now you will get that id! put that in config.json


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 5: INSTALL THE BOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 5A — Place the bot files

  Copy the entire archstream/ folder to wherever you want to run it.
  Suggested location:
    Windows: C:\archstream\
    Linux:   ~/archstream/

  Your folder structure should look like:
    archstream/
    ├── main.py
    ├── config.json
    ├── requirements.txt
    ├── get_token.py
    ├── getchat_id.py
    ├── core/
    │   ├── bot.py
    │   ├── vm_controller.py
    │   ├── user_db.py
    │   ├── vote_system.py
    │   └── rate_limiter.py
    ├── commands/
    │   ├── parser.py
    │   └── executor.py
    ├── api/
    │   └── youtube_chat.py
    └── utils/
        └── config.py


STEP 5B — Create a virtual environment (recommended)

  Windows:
    cd C:\archstream
    python -m venv venv
    venv\Scripts\activate

  Linux/macOS:
    cd ~/archstream
    python3 -m venv venv
    source venv/bin/activate

  You should see (venv) in your terminal prompt.


STEP 5C — Install Python dependencies

  pip install -r requirements.txt

  This installs:
    • aiohttp          — async HTTP for YouTube API calls
    • google-auth-oauthlib — OAuth2 flow helper


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 6: CONFIGURE THE BOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Open config.json in a text editor and fill in your values:

  {
    "youtube_api_key":      "AIzaSy...",           ← From Step 4C
    "youtube_channel_id":   "UCxxxxxxxxxxxxxxx",    ← Your channel ID
    "youtube_client_id":    "12345-abc.apps...",    ← From Step 4D
    "youtube_client_secret": "GOCSPX-...",          ← From Step 4D
    "youtube_refresh_token": "1//0gAB...",          ← From Step 4E
    "youtube_live_chat_id": "",                     ← Leave blank (auto-detected)

    "vm_name": "ArchLinuxChaos",                    ← MUST match your VM name exactly
    "snapshot_name": "SafeBase",                    ← MUST match snapshot you created

    "admin_user_ids": ["YOUR_CHANNEL_ID_HERE"],     ← Your channel ID for admin access
    ...
  }

Key settings to consider tuning:
  
  user_cooldown: 3.0        How many seconds between commands per user
                            Lower = more responsive, higher = less spam
                            Recommended: 2.0–5.0
  
  vote_duration: 20         Seconds for voting window on major commands
                            Recommended: 15–30
  
  type_max_length: 100      Max characters for !type command
                            Lower = safer (prevents huge command injections)
  
  mouse_max_delta: 300      Max pixels mouse can move per command
                            Lower = less chaos with mouse moves
  
  queue_max_size: 50        How many commands can be queued at once
                            Prevents flooding during spikes


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 7: SET UP OBS FOR STREAMING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OBS Stream Setup:
  1. Open OBS → Settings → Stream
  2. Service: YouTube - RTMPS
  3. Connect Account (or use Stream Key)
  4. Settings → Output:
     Encoder: x264 or NVENC (if you have Nvidia GPU)
     Bitrate: 4500–6000 Kbps for 1080p30
  5. Settings → Video:
     Base Resolution: 1920x1080
     Output Resolution: 1920x1080
     FPS: 30
  6. Click "Start Streaming" when ready


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 8: START YOUR FIRST STREAM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 8A — Start a YouTube Livestream

  1. Go to YouTube Studio → Go Live (or youtube.com/webcam)
  2. Choose "Stream" method
  3. Set title: "YouTube Chat Controls Arch Linux Install! Type !help"
  4. Set privacy to Public
  5. Start the stream

  IMPORTANT: The bot looks for an ACTIVE livestream on your channel.
  The stream MUST be live before you start the bot.


STEP 8B — Start the Bot

  Terminal 1 (keep this open):
    cd path/to/archstream
    source venv/bin/activate    (Linux/Mac)
    venv\Scripts\activate       (Windows)
    python main.py

  You should see:
    [INFO] Connecting to YouTube Live Chat...
    [INFO] Connected to live chat: Lc.xxxxxxxx
    [INFO] Checking VM state...
    [INFO] VM 'ArchLinuxChaos' started (headless)
    [INFO] Chat loop started
    [INFO] Execution loop started

 NOW IN THE LOG TERMINAL SCROLL UP YOU WILL SEE A IP ADD THAT AS A BROWSER SOURCE IN OBS!!! TOO SEE THE CHAT AND EXECUTED COMMANDS!


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 9: COMMON ISSUES & TROUBLESHOOTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ISSUE: "Could not find live chat ID"
  • Make sure a livestream is ACTIVE (not scheduled, not ended)
  • Make sure youtube_channel_id is correct
  • Try manually getting the chat ID:
    Visit: https://www.googleapis.com/youtube/v3/liveBroadcasts?part=snippet&broadcastStatus=active&key=YOUR_API_KEY&mine=true
    Find liveChatId in the response and paste it into config.json

ISSUE: "Token refresh failed"
  • Re-run: python get_token.py
  • Make sure your OAuth consent screen has the correct scopes
  • Check client_id and client_secret are correct

ISSUE: "VBoxManage not found"
  • Windows: Add VirtualBox to PATH
    System Properties → Environment Variables → Path → Add:
    C:\Program Files\Oracle\VirtualBox
  • Test: open new terminal → VBoxManage --version

ISSUE: VM won't start / "VERR_VMX_NO_VMX"
  • Enable virtualization in BIOS:
    Restart PC → Enter BIOS (Del/F2/F12 during boot)
    Look for "Intel VT-x", "AMD-V", or "SVM Mode" → Enable it
    Save and exit

ISSUE: Commands work but nothing happens in VM
  • Make sure the VM is actually running: VBoxManage list runningvms
  • Make sure the VM name in config matches exactly (case-sensitive on Linux)
  • Try running a command manually:
    VBoxManage controlvm "ArchLinuxChaos" keyboardputstring "hello"

ISSUE: Bot posts messages but chat doesn't respond to commands
  • Check logs for parse errors
  • Make sure commands start with ! (e.g., !type hello)
  • Check user_cooldown isn't too high

ISSUE: "403 Forbidden" on chat poll
  • Your API key may not have YouTube Data API v3 enabled
  • Or the key is restricted to wrong APIs
  • Go to Google Cloud Console → Credentials → check your key

ISSUE: Messages not sending / "quotaExceeded"
  • YouTube API has a daily quota of 10,000 units
  • Each message sent costs ~50 units (~200 messages/day for free tier)
  • To increase: request quota increase in Google Cloud Console
  • Or reduce bot responses (set more to public=False in executor.py)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 10: OPTIONAL ENHANCEMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RUNNING AS A SERVICE (Linux — keeps running after terminal closes)

  Create: /etc/systemd/system/archchaos.service
  
    [Unit]
    Description=Arch Linux Chaos Bot
    After=network.target

    [Service]
    User=yourusername
    WorkingDirectory=/home/yourusername/archstream
    ExecStart=/home/yourusername/archstream/venv/bin/python main.py
    Restart=on-failure
    RestartSec=10

    [Install]
    WantedBy=multi-user.target

  Then:
    sudo systemctl daemon-reload
    sudo systemctl enable archchaos
    sudo systemctl start archchaos
    sudo systemctl status archchaos


AUTO-RESTART ON VM CRASH

  The bot will attempt to restart the VM if a command fails because the VM
  isn't running. For extra safety, add a watchdog cron:
  
    */5 * * * * VBoxManage showvminfo "ArchLinuxChaos" | grep -q "running" || VBoxManage startvm "ArchLinuxChaos" --type headless


SCHEDULED AUTO-REVERT (Resets every N hours)

  Add to your main.py or run as separate cron:
    Every 2 hours: run !revert to restore the SafeBase snapshot
    This keeps the stream fresh and prevents the VM from getting
    permanently broken by trolls.


OVERLAYS IN OBS

  Add a Text source in OBS showing latest commands.
  Use a webhook or file-write in bot.py to update a local text file,
  then OBS reads it as a Text (GDI+) source.

  Example: In executor.py, after each command:
    with open("data/last_command.txt", "w") as f:
        f.write(f"Last: {cmd.name} by {user_display}")


CHAT COMMAND DISPLAY OVERLAY

  Simple HTML overlay for OBS (Browser Source):
  Create a file: overlay.html
  Use JavaScript to poll data/last_command.txt and display it.
  Add as Browser Source in OBS → file:///path/to/overlay.html


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 11: COMMAND REFERENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
USER COMMANDS (!type = typing into VM)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • !type <text>      → Types text inside VM
  • !mouse <x> <y>    → Moves mouse relative to current position
  • !click [left/right] → Simulates mouse click
  • !vote <command>    → Starts a vote for dangerous commands (revert, shutdown)
  • !help              → Shows this help message


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADMIN COMMANDS (!vote overrides, etc.)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • !revert            → Restores snapshot SafeBase
  • !shutdown          → Gracefully shuts down VM
  • !restart           → Restarts the VM
  • !kill <user>        → Removes a user from voting (admin only)
  • !set <param> <val> → Adjust bot parameters on the fly (admin only)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VOTE SYSTEM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • Dangerous commands require votes
  • Default: 50% of active users in chat must vote
  • Admins can override votes
  • Vote duration and thresholds are configurable in config.json


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 12: SAFETY WARNINGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • The VM runs with root privileges inside Arch Linux. Be careful with commands.
  • Do not install unsafe packages or scripts inside the VM.
  • Use snapshots for quick recovery.
  • User input is untrusted; bot sanitizes input for keyboard/mouse, but extreme
    commands may still crash the VM.
  • Always test new features in a separate test VM before going live.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 13: CONTACT & SUPPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • GitHub: https://github.com/evanblokender/Youtube-vm
  • Issues: https://github.com/evanblokender/Youtube-vm/issues
