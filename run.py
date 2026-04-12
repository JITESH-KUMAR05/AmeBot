"""
run.py — Azure App Service entry point.

WHY THIS EXISTS:
  Azure's Oryx build engine extracts the app to a dynamic /tmp/<hash>/ path.
  Simple 'cd Backend' in the startup command fails because the CWD at startup
  is unpredictable. Using __file__ gives the absolute path of THIS script
  regardless of CWD, so Backend/ is found reliably every time.

STARTUP COMMAND (set in Azure Portal):
  python run.py
"""

import sys
import os

# Resolve Backend/ relative to this script's absolute location.
# Works whether app is at /home/site/wwwroot OR /tmp/<oryx-hash>/.
base_dir    = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(base_dir, "Backend")

# Change CWD so relative paths in config.py work (e.g. "data/faiss_index")
os.chdir(backend_dir)

# Add Backend to sys.path so all internal imports work
# (config, retriever, chat, session, models)
sys.path.insert(0, backend_dir)

import uvicorn

uvicorn.run(
    "main:app",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
)
