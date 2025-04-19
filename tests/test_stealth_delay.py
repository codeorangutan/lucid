import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import time
from request_cns_test import stealth_delay

def test_stealth_delay_range():
    min_delay = 0.5
    max_delay = 1.5
    start = time.time()
    stealth_delay(min_delay, max_delay)
    elapsed = time.time() - start
    assert min_delay <= elapsed <= max_delay + 0.1, f"Delay {elapsed:.2f}s not in range {min_delay}-{max_delay}s"
