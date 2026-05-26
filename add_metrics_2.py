import os

files = ["services/auth-service/main.py", "services/ticket-service/main.py"]

for f in files:
    if os.path.exists(f):
        with open(f, "r") as file:
            content = file.read()
        if "setup_metrics(app)" not in content:
            target = "allow_headers=[\"*\"],\n)"
            replacement = "allow_headers=[\"*\"],\n)\n\nfrom shared.utils.metrics import setup_metrics\nsetup_metrics(app)"
            content = content.replace(target, replacement)
            with open(f, "w") as file:
                file.write(content)
            print(f"Updated {f}")
