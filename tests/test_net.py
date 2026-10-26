import http.server
import io
import json
import os
import threading
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import TempHome, test_port

from cos import cli, core, daemon, net

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# Invented, and none of it may come out the other end: documentation addresses (RFC 5737,
# RFC 7042), a made-up network and an employer-ish VPN.
GATEWAY, MAC, SSID, VPN = "192.0.2.1", "00:00:5e:00:53:01", "ExampleNet", "Example Corp VPN"
ROUTE = """   route to: default
destination: default
       mask: default
    gateway: %s
  interface: en0
      flags: <UP,GATEWAY,DONE,STATIC,PRCLONING,GLOBAL>
""" % GATEWAY
PORTS = """
Hardware Port: Ethernet Adapter (en2)
Device: en2
Ethernet Address: 00:00:5e:00:53:02

Hardware Port: Wi-Fi
Device: en0
Ethernet Address: %s
""" % MAC
NC = """Available network connection services in the current set (*=enabled):
* (Disconnected)   0F0F0F0F-0000-4000-8000-000000000001 VPN (com.example.vpn) "%s"   [VPN:com.example.vpn]
""" % VPN
ARP = "? (%s) at 0:0:5e:0:53:1 on en0 ifscope [ethernet]\n" % GATEWAY
ARP_GONE = "? (%s) at (incomplete) on en0 ifscope [ethernet]\n" % GATEWAY
# The JXA never asks for these, but if CoreWLAN ever volunteered them they'd still be dropped.
WIFI = json.dumps({"power": True, "rssi": "-48", "noise": "-95", "tx": 1200, "channel": "37", "band": "3",
                   "width": "4", "phy": "6", "ssid": SSID, "bssid": MAC})


class FakeMac:
    def __init__(self, arp=ARP, nc=NC, wifi=WIFI):
        self.out = {"route": ROUTE, "networksetup": PORTS, "scutil": nc, "arp": arp, "osascript": wifi}
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        return core.Result(0, self.out.get(cmd[0], ""), "")


def checked(mac=None, internet=None, dns=40):
    mac = mac or FakeMac()
    internet = internet or {"resolved": True, "ok": True, "ms": 24, "portal": False}
    with mock.patch.object(net.core, "run", mac), mock.patch.object(net, "probe_dns", return_value=dns), \
            mock.patch.object(net, "probe_internet", return_value=internet):
        return net.check()


class TestNet(TempHome):
    def test_the_wifi_script_asks_for_nothing_identifying(self):
        script = net.WIFI_JXA.lower()
        for word in ("ssid", "bssid", "hardwareaddress", "countrycode", "scan", "configuration", "profile",
                     "cached", "network", "name"):
            self.assertNotIn(word, script)
        self.assertNotIn("%", net.WIFI_JXA, "nothing is ever filled in")
        w = net.parse_wifi(WIFI)
        self.assertEqual(set(w), set(net.WIFI_KEYS) | {"joined"})
        self.assertEqual((w["rssi"], w["band"], w["joined"]), (-48, 3, True))
        self.assertIsNone(net.parse_wifi("execution error: Error: ReferenceError (-2700)"))
        self.assertFalse(net.parse_wifi('{"power": true, "rssi": 0}')["joined"])

    def test_nothing_identifying_reaches_the_output(self):
        r = checked(FakeMac(nc=NC.replace("(Disconnected)", "(Connected)")))
        with redirect_stdout(io.StringIO()) as out:
            net.render(r)
        for text in (out.getvalue(), json.dumps(r)):
            for secret in (GATEWAY, MAC, "00:00:5e", "0:0:5e", SSID, VPN, "com.example", "en0", "en2"):
                self.assertNotIn(secret, text)
        self.assertTrue(r["vpn"])
        self.assertEqual(r["via"], "wifi")
        self.assertEqual(core.read_journal(days=1), [], "a check leaves no trace")

    def test_a_check_sends_nothing_to_the_local_network(self):
        # A ping to the router trips macOS's Local Network privacy (and maybe its alert);
        # the ARP table answers "has the router been there?" without sending a packet.
        mac = FakeMac()
        r = checked(mac)
        self.assertEqual((r["level"], r["verdict"]), ("ok", "Network looks fine."))
        self.assertEqual(r["router"], {"seen": True})
        self.assertEqual([c for c in mac.calls if c[0] == "arp"], [["arp", "-n", GATEWAY]])
        used = {c[0] for c in mac.calls}
        self.assertEqual(used, {"route", "networksetup", "scutil", "arp", "osascript", "ifconfig"})
        self.assertEqual(checked(FakeMac(arp=ARP_GONE))["router"], {"seen": False})

    def test_through_a_vpn_the_router_isnt_pinged(self):
        mac = FakeMac()
        mac.out["route"] = ROUTE.replace("en0", "utun4")
        r = checked(mac)
        self.assertEqual((r["via"], r["vpn"], r["router"]), ("vpn", True, None))
        self.assertEqual(r["verdict"], "Network looks fine, through a VPN.")

    def test_parsers(self):
        self.assertEqual(net.parse_route(ROUTE), (GATEWAY, "en0"))
        self.assertEqual(net.parse_route(""), (None, None))
        ports = net.parse_ports(PORTS)
        self.assertEqual(ports, {"en2": "Ethernet Adapter (en2)", "en0": "Wi-Fi"})
        self.assertEqual([net.link_kind(i, ports) for i in ("en0", "en2", "utun3", "bridge0", None)],
                         ["wifi", "ethernet", "vpn", "other", None])
        self.assertFalse(net.vpn_connected(NC))
        self.assertFalse(net.parse_arp("%s (%s) -- no entry" % (GATEWAY, GATEWAY)))
        self.assertIsNone(net.probe_router("link#12"), "only an address is ever looked up")

    def test_verdicts(self):
        fine = {"connected": True, "via": "wifi", "vpn": False, "dns_ms": 40,
                "wifi": {"power": True, "joined": True, "rssi": -50, "noise": -95},
                "router": {"seen": True},
                "internet": {"resolved": True, "ok": True, "ms": 25, "portal": False}}

        def case(**change):
            r = dict(fine)
            for k, v in change.items():
                r[k] = dict(r[k], **v) if isinstance(v, dict) and isinstance(r.get(k), dict) else v
            return net.verdict(r)

        cases = [
            (case(connected=False, wifi={"power": False, "joined": False}), "bad", "Wi-Fi is off"),
            (case(connected=False, wifi={"joined": False}), "bad", "Not connected to any network"),
            (case(connected=False), "bad", "hasn't given this Mac an address"),
            (case(internet=None, dns_ms=None), "bad", "DNS isn't answering"),
            (case(via="vpn", vpn=True, ethernet=True, wifi={"rssi": -80}), "ok", "Network looks fine, through a VPN."),
            (case(via="vpn", vpn=True, ethernet=False, wifi={"rssi": -80}), "warn", "weak"),
            (case(internet={"portal": True}), "bad", "sign-in page"),
            (case(internet={"resolved": False, "ok": False}), "bad", "DNS isn't answering"),
            (case(internet={"ok": False}), "bad", "past your network"),
            (case(internet={"ok": False}, router={"seen": False}), "bad", "restarting the router"),
            (case(internet={"ok": False}, router=None, vpn=True), "bad", "A VPN is on"),
            (case(wifi={"rssi": -78}), "warn", "weak (-78 dBm)"),
            (case(wifi={"rssi": -66, "noise": -80}), "warn", "noisy"),
            (case(internet={"ms": 420}, vpn=True), "warn", "the internet is slow (420 ms)"),
            (case(dns_ms=1500), "warn", "DNS is slow"),
            (case(router={"seen": False}), "ok", "Network looks fine."),
            (case(internet=None), "unknown", "Can't tell"),
            (case(via="ethernet", wifi={"rssi": -85}), "ok", "Network looks fine."),
        ]
        for (level, text), want_level, want in cases:
            self.assertEqual(level, want_level, text)
            self.assertIn(want, text)
        self.assertIn("A VPN is on", [t for (_, t), _, w in cases if w == "the internet is slow (420 ms)"][0])

    def test_a_probe_that_hangs_doesnt_hold_the_check(self):
        t = time.monotonic()
        got = net._parallel({"slow": lambda: time.sleep(2) or "late", "fast": lambda: "here",
                             "broken": lambda: 1 / 0}, budget=0.3)
        self.assertLess(time.monotonic() - t, 1.5)
        self.assertEqual(got, {"slow": None, "fast": "here", "broken": None})

    def test_the_portal_probe_never_follows_a_redirect(self):
        replies = {"/ok": (200, b"<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>"),
                   "/login": (302, b"")}

        class Portal(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                code, body = replies[self.path]
                self.send_response(code)
                if code == 302:
                    self.send_header("Location", "http://login.example/")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", test_port()), Portal)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        port = server.server_address[1]
        ok = net.probe_internet("127.0.0.1", "/ok", port=port)
        self.assertEqual((ok["ok"], ok["portal"]), (True, False))
        self.assertEqual(net.probe_internet("127.0.0.1", "/login", port=port)["portal"], True)

    def test_speed_keeps_only_throughput_and_responsiveness(self):
        out = json.dumps({"dl_throughput": 412345678, "ul_throughput": 38123456, "responsiveness": 1234,
                          "interface_name": "en0", "test_endpoint": "edge.example", "os_version": "x"})
        self.assertEqual(net.parse_speed(out), {"down_mbps": 412.3, "up_mbps": 38.1, "rpm": 1234})
        with mock.patch.object(net.core, "run", return_value=core.Result(0, out, "")), \
                redirect_stdout(io.StringIO()) as shown:
            self.assertEqual(net.speed(as_json=False), 0)
        self.assertIn("412.3 Mbps down", shown.getvalue())
        self.assertIn("real data", shown.getvalue(), "it says what it costs before it runs")
        entry = core.read_journal(days=1)[-1]
        self.assertIn("speed test", entry["msg"])
        self.assertNotIn("en0", json.dumps(entry))
        with mock.patch.object(net.core, "run", return_value=core.Result(1, "", "offline")), \
                redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            net.speed(as_json=True)


class TestNetReview(TempHome):
    """An independent review of 0010's code (night of 26 October): each finding, kept fixed."""

    def test_an_ipv6_only_network_is_connected(self):
        mac = FakeMac()
        mac.out["route"] = ""

        def run(cmd, **kw):
            if cmd[:4] == ["route", "-n", "get", "-inet6"]:
                return core.Result(0, "   route to: default\n  interface: en0\n", "")
            return mac(cmd, **kw)
        r = checked(run)
        self.assertTrue(r["connected"])
        self.assertEqual(r["via"], "wifi")

    def test_a_portal_that_hijacks_dns_is_reported_without_connecting(self):
        with mock.patch.object(net, "addresses", return_value=["10.1.2.3"]), \
                mock.patch.object(net.http.client, "HTTPConnection", side_effect=AssertionError("connected")):
            self.assertEqual(net.probe_internet(), {"resolved": True, "ok": False, "portal": True})

    def test_ipv4_goes_first(self):
        infos = [(net.socket.AF_INET6, 1, 6, "", ("2001:db8::1", 80, 0, 0)), (net.socket.AF_INET6, 1, 6, "", ("2001:db8::2", 80, 0, 0)),
                 (net.socket.AF_INET, 1, 6, "", ("192.0.2.10", 80)), (net.socket.AF_INET, 1, 6, "", ("192.0.2.11", 80))]
        with mock.patch.object(net.socket, "getaddrinfo", return_value=infos):
            self.assertEqual(net.addresses("captive.apple.com", 80)[:2], ["192.0.2.10", "2001:db8::1"])

    def test_no_answer_from_arp_is_unknown(self):
        with mock.patch.object(net.core, "run", return_value=core.Result(124, "", "")):
            self.assertEqual(net.probe_router(GATEWAY), {"seen": None})
        r = {"connected": True, "via": "wifi", "vpn": False, "dns_ms": 30, "router": {"seen": None},
             "wifi": {"power": True, "joined": True, "rssi": -50, "noise": -95},
             "internet": {"resolved": True, "ok": False}}
        self.assertNotIn("restarting the router", net.verdict(r)[1])

    def test_ethernet_is_read_from_ifconfig_status_only(self):
        out = "en2: flags=8863<UP>\n\tether 00:00:5e:00:53:02\n\tstatus: active\nen0: flags=8863<UP>\n\tstatus: active\n"
        self.assertTrue(net.ethernet_active(out, {"en2": "Ethernet Adapter (en2)", "en0": "Wi-Fi"}))
        self.assertFalse(net.ethernet_active(out.replace("status: active\nen0", "status: inactive\nen0"),
                                             {"en2": "Ethernet Adapter (en2)", "en0": "Wi-Fi"}))

    def test_missing_wifi_numbers_arent_printed_as_none(self):
        r = {"level": "ok", "verdict": "Network looks fine.", "via": "wifi", "vpn": False, "dns_ms": 20,
             "router": {"seen": True}, "internet": {"resolved": True, "ok": True, "ms": 10, "portal": False},
             "wifi": {"power": True, "joined": True, "rssi": -50, "noise": None, "tx": None, "band": 3,
                      "channel": 0, "width": 0, "phy": 0}}
        with redirect_stdout(io.StringIO()) as out:
            net.render(r)
        self.assertNotIn("None", out.getvalue())


class TestSpeedIsAsked(TempHome):
    def cos(self, *args):
        with redirect_stdout(io.StringIO()):
            return cli.main(list(args))

    def test_never_from_a_background_job_and_only_written_so_the_ask_rule_sees_it(self):
        os.environ["CLAUDE_OS_DAEMON"] = "morning"
        try:
            with self.assertRaises(SystemExit) as cm:
                self.cos("net", "--speed")
            self.assertEqual(cm.exception.code, 3)
        finally:
            del os.environ["CLAUDE_OS_DAEMON"]
        with self.assertRaises(SystemExit) as cm:
            self.cos("net", "--json", "--speed")
        self.assertEqual(cm.exception.code, 2)
        with open(os.path.join(ROOT, ".claude", "settings.json")) as f:
            asks = json.load(f)["permissions"]["ask"]
        for prefix in ("bin/cos", "./bin/cos", "cos"):
            self.assertIn("Bash(%s net --speed*)" % prefix, asks)
            self.assertIn("Bash(%s net --speed*)" % prefix, daemon.ALWAYS_DENIED)


if __name__ == "__main__":
    unittest.main()
