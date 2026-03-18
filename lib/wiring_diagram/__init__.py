"""Physical wiring diagram generation library.

Use this module when generating complex physical wiring diagrams
(many switches, servers, and cables). Import it in your script:

    import sys
    sys.path.insert(0, '/home/user/code/drawio_infra_py/lib')

    from wiring_diagram import Diagram, nid, edge_style, port_style

    # Color palette: red, orange, yellow, lime, green, teal, cyan,
    #   blue, navy, indigo, purple, magenta, pink, brown, gray, dark
    # Line styles: solid, dashed, dotted, dash-dot, long, short

    E_10G = edge_style("orange", width=2)
    E_MGT = edge_style("cyan", width=1.5, line="dotted")
    P_SFP = port_style("red")

    D = Diagram(page_w=3200, page_h=780, route_y_min=130, route_y_max=458)
    # add shapes, queue cables via D.add_edge()
    D.legend([("10G Data", E_10G), ("Mgmt", E_MGT)])
    D.save("output.drawio")  # flush_edges() is called automatically

Routers:
    - NaiveRouter:    1 edge = 1 lane (simple)
    - LeftEdgeRouter: lane compression + barycenter crossing minimisation
    - ObstacleRouter: LeftEdgeRouter + vertical detours around device boxes
                      (X/Y concentric fan-out, strict-interior detection)
"""

from .styles import (
    PALETTE, LINE_STYLES, edge_style, port_style,
    PORT_BLUE, PORT_NAVY, PORT_GREEN, PORT_RED, PORT_GRAY,
    EDGE_BLUE, EDGE_NAVY, EDGE_GREEN, EDGE_RED, EDGE_ACCENT,
    BG_YELLOW, BG_GREEN, BG_PURPLE, BG_RED, BG_BLUE, BG_GRAY,
    CARD_STYLE, CTRL_STYLE, SFP_STYLE,
)
from .ids import nid, reset_ids
from .diagram import Diagram
from .routing import Router, NaiveRouter, LeftEdgeRouter, ObstacleRouter
from .graph import Topology

__all__ = [
    "Diagram", "nid", "reset_ids",
    "Router", "NaiveRouter", "LeftEdgeRouter", "ObstacleRouter",
    "Topology",
    "PALETTE", "LINE_STYLES", "edge_style", "port_style",
    "PORT_BLUE", "PORT_NAVY", "PORT_GREEN", "PORT_RED", "PORT_GRAY",
    "EDGE_BLUE", "EDGE_NAVY", "EDGE_GREEN", "EDGE_RED", "EDGE_ACCENT",
    "BG_YELLOW", "BG_GREEN", "BG_PURPLE", "BG_RED", "BG_BLUE", "BG_GRAY",
    "CARD_STYLE", "CTRL_STYLE", "SFP_STYLE",
]
