import subprocess
import sys
import os
import time
import logging
from health_server import start_health_server
import asyncio
import threading

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("combined_runner.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CombinedRunner")

if sys.platform == "win32":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def log_reader(pipe, prefix):
    with pipe:
        for line in iter(pipe.readline, b''):
            decoded_line = line.decode('utf-8', errors='replace').strip()
            if decoded_line:
                print(f"[{prefix}] {decoded_line}")

def run_bot(name, command, cwd):
    """Starts a bot process and reads its logs."""
    logger.info(f"📡 Starting {name}...")
    
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    proc = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )
    
    # Start threads to read stdout and stderr
    threading.Thread(target=log_reader, args=(proc.stdout, name), daemon=True).start()
    threading.Thread(target=log_reader, args=(proc.stderr, f"{name}-ERR"), daemon=True).start()
    
    return proc

async def main():
    # 1. Start Health Server (Render needs this)
    asyncio.create_task(start_health_server())
    
    logger.info("🚀 Starting Combined Runner (4-Bot Mode)...")
    
    # Define bots
    bots_config = [
        {"name": "SignalBot", "cmd": [sys.executable, "main.py"], "cwd": os.getcwd()},
        {"name": "GreenBot",  "cmd": [sys.executable, "main.py"], "cwd": os.path.join(os.getcwd(), "green_bot")},
        {"name": "Bot3",      "cmd": [sys.executable, "main.py"], "cwd": os.path.join(os.getcwd(), "bot3")},
        {"name": "Bot4",      "cmd": [sys.executable, "main.py"], "cwd": os.path.join(os.getcwd(), "bot4")},
    ]
    
    running_bots = {}
    
    for config in bots_config:
        proc = run_bot(config["name"], config["cmd"], config["cwd"])
        running_bots[config["name"]] = {"proc": proc, "config": config}
    
    logger.info(f"✅ All {len(bots_config)} bots are running.")
    
    try:
        while True:
            for name, data in list(running_bots.items()):
                proc = data["proc"]
                if proc.poll() is not None:
                    logger.error(f"❌ {name} died with code {proc.returncode}. Restarting in 5s...")
                    await asyncio.sleep(5)
                    new_proc = run_bot(name, data["config"]["cmd"], data["config"]["cwd"])
                    running_bots[name]["proc"] = new_proc
                    
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        logger.info("Stopping bots...")
        for name, data in running_bots.items():
            data["proc"].terminate()
        logger.info("All bots stopped.")

if __name__ == "__main__":
    asyncio.run(main())
