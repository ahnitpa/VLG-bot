1| <img width="234" height="234" alt="202177c614e66ac34ca3324477f4afcd" src="https://github.com/user-attachments/assets/04928022-0d2c-4d49-882b-1173a4013042" />
2| 
3| # VLG Bot
4| 
5| A lightweight Discord bot for server management, entertainment, moderation, music playback, and Gemini AI replies.
6| 
7| This personal hobby project is written in Python and is designed to run as a single-service Discord bot with a small set of core features, simple configuration, and minimal deployment overhead.
8| 
9| ## Overview
10| 
11| VLG Bot provides:
12| 
13| - Discord moderation tools
14| - Basic server utility commands
15| - AFK tracking and inactivity handling
16| - Music playback support
17| - Fun and social commands
18| - SQLite-backed user statistics
19| - Gemini AI replies with optional per-server conversation memory
20| 
21| The bot supports both slash commands and a prefix-based command system using `!v`.
22| 
23| ## Features
24| 
25| ### Moderation and server management
26| 
27| - Kick and ban members
28| - Timeout members
29| - Assign and remove roles
30| - Create categories and channels
31| - Move channels up or down
32| 
33| ### Utility and social features
34| 
35| - Custom status updates
36| - Ping and latency checks
37| - AFK status management
38| - User profile and avatar commands
39| - Random fun commands and mini-game interactions
40| 
41| ### Music
42| 
43| - Music playback via Discord voice channels
44| - FFmpeg integration for audio processing
45| - YouTube media playback through `yt-dlp`
46| 
47| ### Persistence
48| 
49| - SQLite database for user data and inventory-like records
50| - Environment-based configuration
51| 
52| ## Gemini AI replies and server memory
53| 
54| The bot replies when a member mentions it or directly replies to one of its messages. It keeps a **small, server-wide conversation context** so it can follow up on recent AI conversations and asso[...]
55| 
56| Memory scope and safeguards:
57| 
58| - Context is isolated by Discord server and shared across that server's channels; it is never shared with another server.
59| - Only messages that explicitly mention/reply to the bot are retained. The bot does not ingest ordinary server chat or fetch profile details.
60| - The database keeps at most the latest 20 AI exchanges per server, for up to 30 days.
61| - Conversation text is sent to Gemini for inference to answer the request. This is contextual recall, not model training or fine-tuning.
62| - Members can run `/ai-memory-forget` to delete their saved AI exchanges in that server.
63| - A member with Manage Server can run `/ai-memory-clear` to clear the server's saved AI exchanges.
64| 
65| Because memory is shared within a server, let members know before enabling it. For persistence across host restarts, configure `DB_PATH` to a persistent disk/location supported by your host; a tem[...]
66| 
67| ## Project structure
68| 
69| ```text
70| .
71| ├── bot.py               # Main bot entry point and command registration
72| ├── afk.py               # AFK tracking logic
73| ├── fun.py               # Fun and utility commands
74| ├── music.py             # Music commands and playback logic
75| ├── shared.py            # Shared helpers and common bot logic
76| ├── requirements.txt     # Python dependencies
77| ├── Dockerfile           # Docker image definition
78| ├── scripts/
79| │   └── init_db.py       # Initializes the SQLite database
80| ├── bot.db               # Generated SQLite database at runtime
81| └── README.md            # Project documentation
82| ```
83| 
84| ## Requirements
85| 
86| - Python 3.11+
87| - FFmpeg installed and available on `PATH`
88| - A Discord bot token
89| - A Gemini API key for AI replies
90| 
91| ## Installation
92| 
93| Clone the repository:
94| 
95| ```bash
96| git clone https://github.com/ahnitpa/VLG-bot.git
97| cd VLG-bot
98| ```
99| 
100| Create and activate a virtual environment:
101| 
102| ```bash
103| python -m venv .venv
104| source .venv/bin/activate
105| ```
106| 
107| Install dependencies:
108| 
109| ```bash
110| pip install -r requirements.txt
111| ```
112| 
113| Initialize the database if needed:
114| 
115| ```bash
116| python scripts/init_db.py
117| ```
118| 
119| ## Configuration
120| 
121| Set these environment variables in the deployment service:
122| 
123| - `TOKEN`: Discord bot token
124| - `GEMINI_API_KEY`: Gemini API key (keep it secret; never commit it)
125| - `GEMINI_MODEL`: Optional model ID (defaults to `gemini-3.1-flash-lite`)
126| - `DB_PATH`: Optional SQLite file path; use persistent storage if memory should survive restarts
127| - `PORT`: Optional port for the keep-alive web endpoint
128| 
129| In the Discord Developer Portal, enable **Message Content Intent**. The bot also needs permission to view and send messages in the relevant channels.
130| 
131| ## Running the bot
132| 
133| ```bash
134| python bot.py
135| ```
135| 
136| The bot starts the Discord client and a small Flask keep-alive endpoint for hosted environments.
137| 
138| ## Docker
139| 
140| Build the image:
141| 
142| ```bash
143| docker build -t vlg-bot .
144| ```
145| 
146| Run the container:
147| 
148| ```bash
149| docker run --rm -e TOKEN="your_discord_bot_token" -p 8080:8080 vlg-bot
150| ```
151| 
152| ## Command usage
153| 
154| The bot supports both slash commands and the `!v` prefix.
155| 
156| Examples:
157| 
158| ```text
159| !v help
160| !v ping
161| !v afk
162| !v afklist
163| !v rate something
164| !v 8ball question
165| ```
166| 
167| Slash command examples:
168| 
169| ```text
170| /setstatus
171| /coinflip
172| /slap
173| /roast
174| /createchannel
175| /createvoice
176| /movechannel
177| ```
178| 
179| ## Database
180| 
181| The project uses SQLite for user data and basic economy-style tracking. The database is initialized by `scripts/init_db.py`; `DB_PATH` can be used to select a different database location. AI conv[...]
182| 
183| ## Notes
184| 
185| - This is a hobby project and not a large-scale production bot framework.
186| - The codebase is intentionally compact and easy to extend.
187| - Some files may be legacy or duplicate remnants from earlier development iterations.
188| 
189| ## License
190| 
191| This project does not currently include a dedicated license file. That means you will need to ask me for license or a fair agreement.
