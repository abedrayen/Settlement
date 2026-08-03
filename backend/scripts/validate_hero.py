# Validate EV formula (no database required)
from __future__ import annotations

balance = 5597.50
p_app = 0.78
p_accept = 0.64
p_fulfill = 0.85
optimal_rr = 0.60

settlement = balance * optimal_rr
ev = p_app * p_accept * p_fulfill * settlement
expected = 1425.0
assert abs(ev - expected) < 1.0, f"EV mismatch: {ev}"
print(f"EV formula validated: £{ev:,.2f} = PoAPP x PoA x PoF x (Balance x RR)")
