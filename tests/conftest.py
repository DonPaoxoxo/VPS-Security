import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "services", "api"))
sys.path.insert(0, os.path.join(ROOT, "agents", "linux"))
sys.path.insert(0, os.path.join(ROOT, "services", "worker"))

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
