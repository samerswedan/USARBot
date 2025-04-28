# Shared in‑memory state between robot code and Flask UI
import multiprocessing as mp

_manager          = mp.Manager()
robot_state       = _manager.dict()      # pose, battery, etc.
detections_queue  = _manager.list()      # survivor / hazard events
command_queue     = _manager.Queue()     # UI → robot commands

# Some helpers
def push_detection(det): detections_queue.append(det)
def pop_command(block=True, timeout=None):
    try:  return command_queue.get(block, timeout)
    except: return None
def send_command(cmd): command_queue.put(cmd)
