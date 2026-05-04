## 2025-05-02 - SSRF Protection Requires Global IP Check
**Vulnerability:** The application's SSRF protection in `backend/main.py` verified IPs against private, loopback, multicast, reserved, and link-local ranges, but failed to block `0.0.0.0`, `::`, or shared network IPs (e.g. `100.64.0.1`), allowing an attacker to bypass the proxy.
**Learning:** `ipaddress.is_private` does not cover all unroutable or internal IPs in Python. Specifically, `0.0.0.0` has `is_unspecified = True` and is not considered private or reserved.
**Prevention:** When validating IP addresses for SSRF prevention, enforce `ip_obj.is_global` (to guarantee public routability) and explicitly reject `ip_obj.is_unspecified`.
