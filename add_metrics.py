import os
import glob

files = [
    "services/ai-brain/main.py",
    "services/auth-service/main.py",
    "services/ticket-service/main.py",
    "services/analytics-service/main.py",
    "services/notification-service/main.py",
    "services/whatsapp-service/main.py",
    "services/voice-agent/api.py"
]

target = """app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)"""

replacement = """app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from shared.utils.metrics import setup_metrics
setup_metrics(app)"""

for f in files:
    if os.path.exists(f):
        with open(f, "r") as file:
            content = file.read()
        if "setup_metrics(app)" not in content:
            if target in content:
                content = content.replace(target, replacement)
                with open(f, "w") as file:
                    file.write(content)
                print(f"Updated {f}")
            else:
                print(f"Target string not found in {f}")
