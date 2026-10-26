"""cos net — is it the Wi-Fi, the router, or the internet? (decision 0010)

`cos net` takes a few seconds and sends almost nothing. All at once, it reads the Wi-Fi
signal (CoreWLAN, through one fixed JXA script), asks the ARP table whether the router has
answered lately, looks up a name nobody has asked for before (so a cache can't answer for
DNS), and fetches Apple's captive-portal page; then it gives one plain verdict.

It sends nothing to the local network. Even a ping to the router is a local network
operation: macOS's Local Network privacy blocks it ("No route to host") for any app but
Terminal, and may ask the human first. Reading the ARP table sends no packets. `cos net --speed` runs macOS's own networkQuality: about 20
seconds and real data, so only when the human asks, never from a background job.

It never reads or keeps the network's name, a hardware address, nearby networks, the country
code or DNS search domains, and never prints an address or a VPN's name (they often name an
employer). The router's address is used to find its ARP entry and dropped.
"""

import http.client
import ipaddress
import json
import re
import socket
import threading
import time
import uuid

from . import core

# The whole Wi-Fi read: eight properties of the current connection, with nothing filled in.
# It never asks for anything Location guards or that identifies a network (test_net checks).
WIFI_JXA = ('ObjC.import("CoreWLAN");'
            'var i = $.CWWiFiClient.sharedWiFiClient.interface;'
            'var c = i.isNil() ? null : i.wlanChannel;'
            'var ch = function (k) { return c === null || c.isNil() ? 0 : c[k]; };'
            'i.isNil() ? "{}" : JSON.stringify({power: i.powerOn, rssi: i.rssiValue, noise: i.noiseMeasurement,'
            ' tx: i.transmitRate, channel: ch("channelNumber"), band: ch("channelBand"),'
            ' width: ch("channelWidth"), phy: i.activePHYMode})')
WIFI_KEYS = ("power", "rssi", "noise", "tx", "channel", "band", "width", "phy")
BANDS = {1: "2.4 GHz", 2: "5 GHz", 3: "6 GHz"}
WIDTHS = {1: 20, 2: 40, 3: 80, 4: 160, 5: 320}
PHYS = {1: "802.11a", 2: "802.11b", 3: "802.11g", 4: "Wi-Fi 4", 5: "Wi-Fi 5", 6: "Wi-Fi 6", 7: "Wi-Fi 7"}

PORTAL = ("captive.apple.com", "/hotspot-detect.html")  # what macOS itself asks to spot sign-in pages
BUDGET = 5  # seconds for all the probes together
WEAK_DBM, NOISY_SNR = -72, 20
SLOW_INTERNET_MS, SLOW_DNS_MS = 250, 800
SPEED = ["networkQuality", "-c", "-M", "30"]


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def parse_wifi(out):
    """The JXA's JSON, keeping only WIFI_KEYS; None when there's no Wi-Fi (or the read failed)."""
    try:
        raw = json.loads(out or "")
    except ValueError:
        return None
    if not isinstance(raw, dict) or not raw:
        return None
    w = {k: _int(raw.get(k)) for k in WIFI_KEYS if k != "power"}
    w["power"] = raw.get("power") in (True, 1, "1", "true")
    w["joined"] = bool(w["rssi"])
    return w


def parse_route(out):
    """(gateway, interface) of the default route; either may be None."""
    gw = re.search(r"^\s*gateway:\s*(\S+)", out or "", re.M)
    iface = re.search(r"^\s*interface:\s*(\S+)", out or "", re.M)
    return (gw.group(1) if gw else None), (iface.group(1) if iface else None)


def parse_ports(out):
    """{device: hardware port} from `networksetup -listallhardwareports`, addresses skipped."""
    ports, port = {}, None
    for line in (out or "").splitlines():
        if line.startswith("Hardware Port:"):
            port = line.split(":", 1)[1].strip()
        elif line.startswith("Device:") and port:
            ports[line.split(":", 1)[1].strip()] = port
    return ports


def link_kind(iface, ports):
    if not iface:
        return None
    if iface.startswith(("utun", "ipsec", "ppp", "tun", "tap")):
        return "vpn"
    port = ports.get(iface, "")
    if "Wi-Fi" in port or "AirPort" in port:
        return "wifi"
    if "iPhone" in port or "iPad" in port:
        return "phone"
    if "Ethernet" in port or "LAN" in port:
        return "ethernet"
    return "other"


def vpn_connected(nc_out):
    """`scutil --nc list`: only whether some service says Connected; names are never read.
    (utun interfaces alone prove nothing: macOS keeps several up with every VPN off.)"""
    return "(Connected)" in (nc_out or "")


def parse_arp(out):
    """Whether `arp -n <router>` shows a complete entry, i.e. the router answered on the link
    within the last 20 minutes or so. Yes or no only; its hardware address is never kept."""
    return bool(re.search(r"\) at [0-9a-f]{1,2}(:[0-9a-f]{1,2}){5}\b", out or ""))


def probe_wifi():
    r = core.run(["osascript", "-l", "JavaScript", "-e", WIFI_JXA], timeout=3)
    return parse_wifi(r.out) if r.ok else None


def probe_router(gateway):
    if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", gateway or ""):
        return None
    out = core.run(["arp", "-n", gateway], timeout=2).out
    return {"seen": parse_arp(out) if out.strip() else None}  # no answer from arp is unknown


def probe_dns():
    """Milliseconds to look up a name that has never been asked for, so no cache answers.
    It doesn't exist; the answer "no such name" still takes the resolver's full round trip."""
    t = time.monotonic()
    try:
        socket.getaddrinfo("cos-%s.apple.com" % uuid.uuid4().hex[:12], 80)
    except OSError:
        pass
    return round((time.monotonic() - t) * 1000)


def addresses(host, port):
    """What a name resolves to, one IPv4 and one IPv6 first: a broken IPv6 path (a VPN that
    drops it, say) shouldn't spend the whole budget before IPv4 gets a turn."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    v4 = [i[4][0] for i in infos if i[0] == socket.AF_INET]
    v6 = [i[4][0] for i in infos if i[0] == socket.AF_INET6]
    out = []
    for a in v4[:1] + v6[:1] + v4[1:] + v6[1:]:
        if a not in out:
            out.append(a)
    return out


def _local(address):
    ip = ipaddress.ip_address(address.split("%")[0])
    return not (ip.is_global or ip.is_loopback)


def probe_internet(host=PORTAL[0], path=PORTAL[1], timeout=2, port=80):
    """Apple's captive-portal page: reachable at all, how fast it connects, and whether
    something answered in its place (a sign-in page). Redirects are never followed, and a
    name that resolves to a local address is a sign-in page hijacking DNS: it's reported
    without connecting, since that connection would be a local network operation."""
    try:
        addrs = addresses(host, port)
    except OSError:
        return {"resolved": False, "ok": False}
    if addrs and all(_local(a) for a in addrs):
        return {"resolved": True, "ok": False, "portal": True}
    for a in [a for a in addrs if not _local(a)][:2]:
        conn = http.client.HTTPConnection("[%s]" % a if ":" in a else a, port, timeout=timeout)
        try:
            t = time.monotonic()
            conn.connect()
            ms = round((time.monotonic() - t) * 1000)
            conn.request("GET", path, headers={"Host": host})
            resp = conn.getresponse()
            body = resp.read(4096).decode("utf-8", "replace")
        except (OSError, http.client.HTTPException):
            continue
        finally:
            conn.close()
        return {"resolved": True, "ok": True, "ms": ms, "portal": resp.status != 200 or "Success" not in body}
    return {"resolved": True, "ok": False}


def ethernet_active(ifconfig_out, ports):
    """Is any wired port up? `ifconfig`'s blocks, read for "status: active" only."""
    wired = {d for d, port in ports.items() if link_kind(d, {d: port}) == "ethernet"}
    active, current = set(), None
    for line in (ifconfig_out or "").splitlines():
        if line and not line[0].isspace():
            current = line.split(":", 1)[0]
        elif current in wired and "status: active" in line:
            active.add(current)
    return bool(active)


def _parallel(jobs, budget):
    """Run the probes at once; whatever hasn't answered within the budget counts as None.
    (A lookup can block for 30 s when DNS is broken, which is exactly when this runs.)"""
    got = {}

    def go(key, fn):
        try:
            got[key] = fn()
        except Exception:  # a probe must never take the whole check down
            got[key] = None

    threads = [threading.Thread(target=go, args=item, daemon=True) for item in jobs.items()]
    for t in threads:
        t.start()
    deadline = time.monotonic() + budget
    for t in threads:
        t.join(max(0, deadline - time.monotonic()))
    return {k: got.get(k) for k in jobs}


def check():
    gateway, iface = parse_route(core.run(["route", "-n", "get", "default"], timeout=2).out)
    if not iface:  # an IPv6-only network has no IPv4 default route
        iface = parse_route(core.run(["route", "-n", "get", "-inet6", "default"], timeout=2).out)[1]
        gateway = None
    tunnel = link_kind(iface, {}) == "vpn"
    got = _parallel({
        "wifi": probe_wifi,
        # Through a VPN, the "gateway" is the VPN's own end, not the router.
        "router": lambda: None if tunnel else probe_router(gateway),
        "dns_ms": probe_dns,
        "internet": probe_internet,
        "ports": lambda: parse_ports(core.run(["networksetup", "-listallhardwareports"], timeout=3).out),
        "nc": lambda: core.run(["scutil", "--nc", "list"], timeout=3).out,
        "ifconfig": lambda: core.run(["ifconfig"], timeout=3).out,
    }, BUDGET)
    ports = got.pop("ports") or {}
    via = link_kind(iface, ports)
    r = dict(got, via=via, vpn=via == "vpn" or vpn_connected(got.pop("nc")),
             ethernet=ethernet_active(got.pop("ifconfig"), ports),
             connected=bool(iface) or bool((got.get("internet") or {}).get("ok")))
    r.pop("nc", None)
    r.pop("ifconfig", None)
    r["level"], r["verdict"] = verdict(r)
    return r


def verdict(r):
    """(level, one line): the single likeliest cause, or that it looks fine, or can't tell."""
    w, router, net, dns = r.get("wifi") or {}, r.get("router"), r.get("internet") or {}, r.get("dns_ms")
    # Under a VPN, the tunnel runs over Wi-Fi only when no cable is plugged in and active.
    on_wifi = bool(w.get("joined")) and (r.get("via") == "wifi" or (r.get("via") == "vpn" and not r.get("ethernet")))
    seen = router["seen"] if router else None
    vpn = " A VPN is on, and it may be the bottleneck." if r.get("vpn") else ""
    if not r.get("connected"):
        if w and not w.get("power"):
            return "bad", "Not connected: Wi-Fi is off and there's no cable."
        if w.get("joined"):
            return "bad", ("Wi-Fi is joined, but the router hasn't given this Mac an address: turn Wi-Fi off "
                           "and on, or restart the router.")
        return "bad", "Not connected to any network."
    if net.get("portal"):
        return "bad", "A sign-in page is waiting (a captive portal): open any website to log in."
    if not net and dns is None:
        return "bad", "DNS isn't answering: looking up a name took more than %d seconds." % BUDGET
    if net and not net.get("resolved"):
        return "bad", "Connected, but names don't resolve: DNS isn't answering."
    if net and not net.get("ok"):
        if seen:
            return "bad", ("Your Mac reaches the router, but the internet doesn't answer: the trouble is likely "
                           "past your network (the router's own connection, or the provider)." + vpn)
        if seen is False:
            return "bad", "Neither the internet nor the router is answering: try restarting the router."
        return "bad", "The internet isn't answering." + vpn
    if on_wifi and w.get("rssi") and w["rssi"] < WEAK_DBM:
        return "warn", "Wi-Fi signal is weak (%d dBm): move closer to the router, or away from walls and metal." % w["rssi"]
    if on_wifi and w.get("rssi") and w.get("noise") and w["rssi"] - w["noise"] < NOISY_SNR:
        return "warn", ("Wi-Fi is noisy (the signal is only %d dB above the noise): another channel or band may help."
                        % (w["rssi"] - w["noise"]))
    if net.get("ms") and net["ms"] > SLOW_INTERNET_MS:
        if on_wifi:
            return "warn", ("The Wi-Fi signal is fine but the internet is slow (%d ms): the provider, or "
                            "something on the network using it." % net["ms"] + vpn)
        return "warn", "The internet is slow to answer (%d ms)." % net["ms"] + vpn
    if dns and dns > SLOW_DNS_MS:
        return "warn", "DNS is slow (%d ms): every new site waits that long before it starts loading." % dns
    if net.get("ok"):
        return "ok", "Network looks fine" + (", through a VPN." if r.get("vpn") else ".")
    return "unknown", "Can't tell: the checks didn't finish in time."


def _signal(rssi):
    return "strong" if rssi >= -60 else "good" if rssi >= -70 else "weak" if rssi >= -80 else "very weak"


def summary(r):
    """What the desktop's Network card shows (0010, amended): the verdict and a few numbers,
    nothing that names the network, the router or the Mac. Kept nowhere."""
    w, net = r.get("wifi") or {}, r.get("internet") or {}
    joined = bool(w.get("joined"))
    return {"level": r.get("level"), "verdict": r.get("verdict"), "via": r.get("via"), "vpn": bool(r.get("vpn")),
            "signal_dbm": w.get("rssi") if joined else None, "signal": _signal(w["rssi"]) if joined and w.get("rssi") else None,
            "link_mbps": w.get("tx") if joined else None, "dns_ms": r.get("dns_ms"),
            "internet_ms": net.get("ms") if net.get("ok") else None, "portal": bool(net.get("portal"))}


def render(r):
    mark = {"ok": "✓", "warn": "!", "bad": "✗"}.get(r["level"], "?")
    print("%s %s" % (mark, r["verdict"]))
    w = r.get("wifi") or {}
    via = {"wifi": "Wi-Fi", "ethernet": "Ethernet", "vpn": "a VPN", "phone": "iPhone or iPad", "other": "another link"}
    if r.get("via"):
        print("  via        %s" % via[r["via"]])
    if w.get("joined"):
        bits = [BANDS.get(w["band"]), "channel %d" % w["channel"] if w.get("channel") else None,
                "%d MHz" % WIDTHS[w["width"]] if w.get("width") in WIDTHS else None, PHYS.get(w["phy"])]
        print("  Wi-Fi      %s" % ", ".join(b for b in bits if b))
        extra = ([", noise %d dBm" % w["noise"]] if w.get("noise") else []) + \
                ([" · %d Mbps link" % w["tx"]] if w.get("tx") else [])
        print("  signal     %d dBm (%s)%s" % (w["rssi"], _signal(w["rssi"]), "".join(extra)))
    elif w and not w.get("power"):
        print("  Wi-Fi      off")
    router = r.get("router")
    if router:
        print("  router     %s" % {True: "answering", False: "not seen lately"}.get(router["seen"], "couldn't check"))
    net = r.get("internet")
    if net and net.get("ok"):
        print("  internet   %d ms to Apple%s" % (net["ms"], " · a sign-in page answered instead" if net["portal"] else ""))
    elif net:
        print("  internet   %s" % ("names don't resolve" if not net["resolved"] else "no answer"))
    if r.get("dns_ms") is not None:
        print("  DNS        %d ms for a fresh lookup" % r["dns_ms"])
    print("  VPN        %s" % ("on" if r.get("vpn") else "off"))
    print("\nSlow anyway? `cos net --speed` measures throughput (about 20 seconds; it uses data).")


def parse_speed(out):
    """networkQuality -c: throughput and responsiveness only; the rest (interface, server,
    OS version…) is dropped."""
    try:
        raw = json.loads(out or "")
    except ValueError:
        return None
    if not isinstance(raw, dict):
        return None

    def mbps(key):
        v = raw.get(key)
        return round(v / 1e6, 1) if isinstance(v, (int, float)) else None

    rpm = raw.get("responsiveness", raw.get("dl_responsiveness"))
    return {"down_mbps": mbps("dl_throughput"), "up_mbps": mbps("ul_throughput"),
            "rpm": int(rpm) if isinstance(rpm, (int, float)) else None}


def _feel(rpm):
    return "laggy for calls and games" if rpm < 200 else "fine for most things" if rpm < 800 else "snappy"


def speed(as_json):
    if not as_json:
        print("Measuring with macOS's networkQuality: about 20 seconds, and it moves real data "
              "(a few hundred MB on a fast line)…", flush=True)
    s = parse_speed(core.run(SPEED, timeout=45).out)
    if not s or s["down_mbps"] is None:
        core.journal("action", "network speed test failed")
        core.die("the speed test didn't finish (offline, or networkQuality couldn't reach Apple's servers)")
    core.journal("action", "ran a network speed test: %s Mbps down, %s up" % (s["down_mbps"], s["up_mbps"]), **s)

    def show(s):
        print("↓ %s Mbps down · ↑ %s Mbps up" % (s["down_mbps"], s["up_mbps"]))
        if s["rpm"] is not None:
            print("  responsiveness %d RPM: %s" % (s["rpm"], _feel(s["rpm"])))
    core.emit(s, as_json, show)
    return 0


def main(args):
    if args.speed:
        return speed(args.json)
    r = check()
    core.emit(r, args.json, render)
    return 0
