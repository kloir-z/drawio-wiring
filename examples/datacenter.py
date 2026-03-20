#!/usr/bin/env python3
"""Example: large datacenter physical wiring diagram.

24 devices across 4 layers, 100 cables (97 routed + 3 StackWise).
Uses Topology API with ObstacleRouter for automatic layout.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from wiring_diagram import Topology, ObstacleRouter
from wiring_diagram import (
    BG_YELLOW, BG_GREEN, BG_PURPLE, BG_BLUE,
    PORT_BLUE, PORT_GREEN, PORT_RED, PORT_GRAY,
)

OUT = os.path.join(os.path.dirname(__file__), "datacenter.drawio")

# -- Edge styles ---------------------------------------------------------------
# Solid lines (data paths)
E_CORE  = "strokeColor=#b85450;strokeWidth=3;"               # Red: Core uplinks
E_SVC   = "strokeColor=#FF8000;strokeWidth=2;"               # Orange: Svc → Storage
E_ACC   = "strokeColor=#0070C0;strokeWidth=2;"               # Blue: Dist → Access
E_DATA  = "strokeColor=#6a9f3c;strokeWidth=2;"               # Green: Svc → Server NIC
E_VM    = "strokeColor=#00897B;strokeWidth=2;"               # Teal: Svc → VM Host
E_STACK = "strokeColor=#888888;strokeWidth=2;dashed=1;"      # Grey dashed: StackWise
# Fine dotted lines (management/OOB)
_DOT    = "dashed=1;dashPattern=1 2;"
E_MGMT  = f"strokeColor=#9673a6;strokeWidth=1.5;{_DOT}"     # Purple dotted: Mgmt/BMC

# -- Port styles ---------------------------------------------------------------
P_UP   = PORT_RED
P_DOWN = PORT_BLUE
P_SRV  = PORT_GREEN
P_MGMT = PORT_GRAY


# ==============================================================================
# Topology  (24 devices)
# ==============================================================================
T = Topology()

# -- Layer 0: Core switches (2) -----------------------------------------------
#   8 downlinks each
for i in range(1, 3):
    T.add_device(
        f"core{i}", label=f"Core-SW-{i}", style=BG_PURPLE, layer=0,
        ports=[("u1", P_UP), ("u2", P_UP)]
              + [(f"d{n}", P_DOWN) for n in range(1, 9)])

# -- Layer 1: Distribution (2) + Service (2) ----------------------------------
#   Dist: 7 downlinks each
for i in range(1, 3):
    T.add_device(
        f"dist{i}", label=f"Dist-SW-{i}", style=BG_YELLOW, layer=1,
        ports=[("u1", P_UP), ("u2", P_UP)]
              + [(f"d{n}", P_DOWN) for n in range(1, 8)])

#   Svc: 21 downlinks each
for i in range(1, 3):
    T.add_device(
        f"svc{i}", label=f"Svc-SW-{i}", style=BG_YELLOW, layer=1,
        ports=[("u1", P_UP), ("u2", P_UP)]
              + [(f"d{n}", P_DOWN) for n in range(1, 22)])

# -- Layer 2: Access (4) + Management (2) -------------------------------------
#   Access: 3 downlinks each
for i in range(1, 5):
    T.add_device(
        f"acc{i}", label=f"Access-{i}", style=BG_GREEN, layer=2,
        ports=[("u1", P_UP), ("u2", P_UP),
               ("d1", P_DOWN), ("d2", P_DOWN), ("d3", P_DOWN)])

#   Mgmt: 8 downlinks each
for i in range(1, 3):
    T.add_device(
        f"mgmt{i}", label=f"Mgmt-SW-{i}", style=BG_GREEN, layer=2,
        ports=[("u1", P_UP)]
              + [(f"d{n}", P_MGMT) for n in range(1, 9)])

# -- Layer 3: Storage (3) + Server (4) + VM Host (3) + Auth (2) ---------------
#   Storage: iSCSI(2) + NFS(2) + Mgmt(1) = 5 ports
for i in range(1, 4):
    suffix = chr(ord('A') + i - 1)
    T.add_device(f"stor{i}", label=f"Storage-{suffix}", style=BG_BLUE,
                 layer=3, cards=[
                     ("iSCSI", [("e0a", False, P_SRV), ("e0b", False, P_SRV)]),
                     ("NFS",   [("e1a", False, P_SRV), ("e1b", False, P_SRV)]),
                     ("Mgmt",  [("m1",  False, P_MGMT)]),
                 ])

#   Server: OCP(2) + PCIe1(2) + PCIe2(2) + BMC(1) = 7 ports
for i in range(1, 5):
    T.add_device(f"srv{i}", label=f"Server-{i}", style=BG_BLUE,
                 layer=3, cards=[
                     ("OCP",   [("ocp1", False, P_SRV), ("ocp2", False, P_SRV)]),
                     ("PCIe1", [("p1a",  False, P_SRV), ("p1b",  False, P_SRV)]),
                     ("PCIe2", [("p2a",  False, P_SRV), ("p2b",  False, P_SRV)]),
                     ("BMC", [("mgmt", False, P_MGMT)]),
                 ])

#   VM Host: OCP(2) + PCIe1(2) + PCIe2(2) + PCIe3(2) + BMC(1) = 9 ports
for i in range(1, 4):
    T.add_device(f"vmh{i}", label=f"VM-Host-{i}", style=BG_BLUE,
                 layer=3, cards=[
                     ("OCP",   [("ocp1", False, P_SRV), ("ocp2", False, P_SRV)]),
                     ("PCIe1", [("p1a",  False, P_SRV), ("p1b",  False, P_SRV)]),
                     ("PCIe2", [("p2a",  False, P_SRV), ("p2b",  False, P_SRV)]),
                     ("PCIe3", [("p3a",  False, P_SRV), ("p3b",  False, P_SRV)]),
                     ("BMC", [("mgmt", False, P_MGMT)]),
                 ])

#   Auth: NIC1(2) + NIC2(2) + BMC(1) = 5 ports
for i in range(1, 3):
    T.add_device(
        f"auth{i}", label=f"Auth-{i}", style=BG_BLUE, layer=3,
        cards=[
            ("NIC1",  [("eth1", False, P_SRV), ("eth2", False, P_SRV)]),
            ("NIC2",  [("eth3", False, P_SRV), ("eth4", False, P_SRV)]),
            ("BMC", [("mgmt", False, P_MGMT)]),
        ])


# ==============================================================================
# Cables  (97 routed cables + 3 StackWise = 100 total)
#
# Port allocation tracked per device to guarantee no duplicates.
# ==============================================================================

# -- Core → Dist: 4 cables (red) ------------------------------------------------
# core1.d1→dist1.u1  core1.d2→dist2.u1  core2.d1→dist1.u2  core2.d2→dist2.u2
T.add_cable("core1", "d1", "dist1", "u1", style=E_CORE)
T.add_cable("core1", "d2", "dist2", "u1", style=E_CORE)
T.add_cable("core2", "d1", "dist1", "u2", style=E_CORE)
T.add_cable("core2", "d2", "dist2", "u2", style=E_CORE)

# -- Core → Svc: 4 cables (red) -------------------------------------------------
# core1.d3→svc1.u1  core1.d4→svc2.u1  core2.d3→svc1.u2  core2.d4→svc2.u2
T.add_cable("core1", "d3", "svc1", "u1", style=E_CORE)
T.add_cable("core1", "d4", "svc2", "u1", style=E_CORE)
T.add_cable("core2", "d3", "svc1", "u2", style=E_CORE)
T.add_cable("core2", "d4", "svc2", "u2", style=E_CORE)

# -- Core → Mgmt uplink: 2 cables (red) -----------------------------------------
# core1.d5→mgmt1.u1  core2.d5→mgmt2.u1
T.add_cable("core1", "d5", "mgmt1", "u1", style=E_CORE)
T.add_cable("core2", "d5", "mgmt2", "u1", style=E_CORE)

# -- Core → Server PCIe2: 4 cables (red) ----------------------------------------
# core1.d6→srv1.p2a  core2.d6→srv2.p2a  core1.d7→srv3.p2a  core2.d7→srv4.p2a
T.add_cable("core1", "d6", "srv1", "p2a", style=E_CORE)
T.add_cable("core2", "d6", "srv2", "p2a", style=E_CORE)
T.add_cable("core1", "d7", "srv3", "p2a", style=E_CORE)
T.add_cable("core2", "d7", "srv4", "p2a", style=E_CORE)

# -- Core → VM Host PCIe2: 2 cables (red) ---------------------------------------
# core1.d8→vmh1.p2a  core2.d8→vmh2.p2a
T.add_cable("core1", "d8", "vmh1", "p2a", style=E_CORE)
T.add_cable("core2", "d8", "vmh2", "p2a", style=E_CORE)

# -- Dist → Access: 8 cables (blue, dual-homed) ---------------------------------
for n, acc in enumerate(["acc1", "acc2", "acc3", "acc4"], 1):
    T.add_cable("dist1", f"d{n}", acc, "u1", style=E_ACC)
    T.add_cable("dist2", f"d{n}", acc, "u2", style=E_ACC)

# -- Dist → Server PCIe2: 4 cables (blue) ---------------------------------------
# dist1.d5→srv1.p2b  dist2.d5→srv2.p2b  dist1.d6→srv3.p2b  dist2.d6→srv4.p2b
T.add_cable("dist1", "d5", "srv1", "p2b", style=E_ACC)
T.add_cable("dist2", "d5", "srv2", "p2b", style=E_ACC)
T.add_cable("dist1", "d6", "srv3", "p2b", style=E_ACC)
T.add_cable("dist2", "d6", "srv4", "p2b", style=E_ACC)

# -- Dist → VM Host PCIe1: 2 cables (blue) --------------------------------------
# dist1.d7→vmh2.p1b  dist2.d7→vmh3.p2b
T.add_cable("dist1", "d7", "vmh2", "p1b", style=E_ACC)
T.add_cable("dist2", "d7", "vmh3", "p2b", style=E_ACC)

# -- Svc → Storage iSCSI: 6 cables (orange) -------------------------------------
# svc1.d1→stor1.e0a  svc1.d2→stor2.e0a  svc1.d3→stor3.e0a
# svc2.d1→stor1.e0b  svc2.d2→stor2.e0b  svc2.d3→stor3.e0b
T.add_cable("svc1", "d1", "stor1", "e0a", style=E_SVC)
T.add_cable("svc1", "d2", "stor2", "e0a", style=E_SVC)
T.add_cable("svc1", "d3", "stor3", "e0a", style=E_SVC)
T.add_cable("svc2", "d1", "stor1", "e0b", style=E_SVC)
T.add_cable("svc2", "d2", "stor2", "e0b", style=E_SVC)
T.add_cable("svc2", "d3", "stor3", "e0b", style=E_SVC)

# -- Svc → Storage NFS: 6 cables (orange) ---------------------------------------
# svc1.d4→stor1.e1a  svc1.d5→stor2.e1a  svc1.d6→stor3.e1a
# svc2.d4→stor1.e1b  svc2.d5→stor2.e1b  svc2.d6→stor3.e1b
T.add_cable("svc1", "d4", "stor1", "e1a", style=E_SVC)
T.add_cable("svc1", "d5", "stor2", "e1a", style=E_SVC)
T.add_cable("svc1", "d6", "stor3", "e1a", style=E_SVC)
T.add_cable("svc2", "d4", "stor1", "e1b", style=E_SVC)
T.add_cable("svc2", "d5", "stor2", "e1b", style=E_SVC)
T.add_cable("svc2", "d6", "stor3", "e1b", style=E_SVC)

# -- Svc → Server OCP: 8 cables (green) -----------------------------------------
# svc1.d7→srv1.ocp1  svc2.d7→srv1.ocp2  svc1.d8→srv2.ocp1  svc2.d8→srv2.ocp2
# svc1.d9→srv3.ocp1  svc2.d9→srv3.ocp2  svc1.d10→srv4.ocp1 svc2.d10→srv4.ocp2
for i in range(1, 5):
    T.add_cable("svc1", f"d{6+i}", f"srv{i}", "ocp1", style=E_DATA)
    T.add_cable("svc2", f"d{6+i}", f"srv{i}", "ocp2", style=E_DATA)

# -- Svc → Server PCIe1: 8 cables (green) ---------------------------------------
# svc1.d11→srv1.p1a  svc2.d11→srv1.p1b  ... svc1.d14→srv4.p1a  svc2.d14→srv4.p1b
for i in range(1, 5):
    T.add_cable("svc1", f"d{10+i}", f"srv{i}", "p1a", style=E_DATA)
    T.add_cable("svc2", f"d{10+i}", f"srv{i}", "p1b", style=E_DATA)

# -- Svc → VM Host OCP: 6 cables (teal) -----------------------------------------
# svc1.d15→vmh1.ocp1  svc2.d15→vmh1.ocp2
# svc1.d16→vmh2.ocp1  svc2.d16→vmh2.ocp2
T.add_cable("svc1", "d15", "vmh1", "ocp1", style=E_VM)
T.add_cable("svc2", "d15", "vmh1", "ocp2", style=E_VM)
T.add_cable("svc1", "d16", "vmh2", "ocp1", style=E_VM)
T.add_cable("svc2", "d16", "vmh2", "ocp2", style=E_VM)

# -- Svc → VM Host OCP + PCIe1: 5 cables (teal) ---------------------------------
T.add_cable("svc1", "d17", "vmh3", "ocp1", style=E_VM)
T.add_cable("svc2", "d17", "vmh3", "ocp2", style=E_VM)
T.add_cable("svc1", "d18", "vmh1", "p3a", style=E_VM)
T.add_cable("svc2", "d18", "vmh2", "p3a", style=E_VM)
T.add_cable("svc1", "d19", "vmh3", "p3a", style=E_VM)

# -- Access → Auth NIC1: 4 cables (blue) ----------------------------------------
# acc1.d1→auth1.eth1  acc2.d1→auth1.eth2  acc3.d1→auth2.eth1  acc4.d1→auth2.eth2
T.add_cable("acc1", "d1", "auth1", "eth1", style=E_ACC)
T.add_cable("acc2", "d1", "auth1", "eth2", style=E_ACC)
T.add_cable("acc3", "d1", "auth2", "eth1", style=E_ACC)
T.add_cable("acc4", "d1", "auth2", "eth2", style=E_ACC)

# -- Access → VM Host PCIe1: 4 cables (teal) ------------------------------------
# acc1.d2→vmh1.p1a  acc2.d2→vmh2.p1a  acc3.d2→vmh3.p1a  acc4.d2→vmh3.p1b
T.add_cable("acc1", "d2", "vmh1", "p1a", style=E_VM)
T.add_cable("acc2", "d2", "vmh2", "p1a", style=E_VM)
T.add_cable("acc3", "d2", "vmh3", "p1a", style=E_VM)
T.add_cable("acc4", "d2", "vmh3", "p1b", style=E_VM)

# -- Access → Auth NIC2: 4 cables (green) ---------------------------------------
# acc1.d3→auth1.eth3  acc2.d3→auth1.eth4  acc3.d3→auth2.eth3  acc4.d3→auth2.eth4
T.add_cable("acc1", "d3", "auth1", "eth3", style=E_DATA)
T.add_cable("acc2", "d3", "auth1", "eth4", style=E_DATA)
T.add_cable("acc3", "d3", "auth2", "eth3", style=E_DATA)
T.add_cable("acc4", "d3", "auth2", "eth4", style=E_DATA)

# -- Mgmt1 → Storage OOB: 3 cables (purple dotted) ------------------------------
T.add_cable("mgmt1", "d1", "stor1", "m1", style=E_MGMT)
T.add_cable("mgmt1", "d2", "stor2", "m1", style=E_MGMT)
T.add_cable("mgmt1", "d3", "stor3", "m1", style=E_MGMT)

# -- Mgmt1 → Server BMC: 4 cables (purple dotted) -----------------------------
for i in range(1, 5):
    T.add_cable("mgmt1", f"d{3+i}", f"srv{i}", "mgmt", style=E_MGMT)

# -- Mgmt1 → Auth BMC: 1 cable (purple dotted) --------------------------------
T.add_cable("mgmt1", "d8", "auth1", "mgmt", style=E_MGMT)

# -- Mgmt2 → VM Host BMC: 3 cables (purple dotted) ----------------------------
for i in range(1, 4):
    T.add_cable("mgmt2", f"d{i}", f"vmh{i}", "mgmt", style=E_MGMT)

# -- Mgmt2 → Auth BMC: 1 cable (purple dotted) --------------------------------
T.add_cable("mgmt2", "d4", "auth2", "mgmt", style=E_MGMT)

# -- Mgmt2 → VM Host PCIe3: 3 cables (purple dotted) ----------------------------
T.add_cable("mgmt2", "d5", "vmh1", "p3b", style=E_MGMT)
T.add_cable("mgmt2", "d6", "vmh2", "p3b", style=E_MGMT)
T.add_cable("mgmt2", "d7", "vmh3", "p3b", style=E_MGMT)

# -- Mgmt2 → VM Host backup: 1 cable (purple dotted) ----------------------------
T.add_cable("mgmt2", "d8", "vmh3", "p2a", style=E_MGMT)

# -- Svc → VM Host PCIe remaining: 2 cables (teal) ------------------------------
T.add_cable("svc1", "d21", "vmh1", "p2b", style=E_VM)
T.add_cable("svc2", "d21", "vmh2", "p2b", style=E_VM)

# -- StackWise links (3) --------------------------------------------------------
T.add_simple_link("core1", "core2", "StackWise", E_STACK)
T.add_simple_link("dist1", "dist2", "StackWise", E_STACK)
T.add_simple_link("svc1",  "svc2",  "StackWise", E_STACK)


# ==============================================================================
# Layout & Save
# ==============================================================================
D = T.to_diagram(router=ObstacleRouter(), layer_gap=220, device_gap=25,
                 cable_layers=True)
D.save(OUT)
print(f"Saved: {OUT}")
