from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub

from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types

import time


class OrchestrationController(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # ============================================================
    # APPLICATION PROFILES
    # ============================================================

    APPLICATION_PROFILES = {

        "VIDEO": {
            "priority": 100,
            "bandwidth": "HIGH",
            "latency": "MEDIUM"
        },

        "VOICE": {
            "priority": 200,
            "bandwidth": "LOW",
            "latency": "VERY_LOW"
        },

        "WEB": {
            "priority": 50,
            "bandwidth": "MEDIUM",
            "latency": "MEDIUM"
        },

        "IOT": {
            "priority": 25,
            "bandwidth": "LOW",
            "latency": "HIGH"
        }
    }

    # ============================================================
    # SPANNING TREE FLOOD PORTS
    #
    # These ports form the initial loop-free forwarding tree.
    #
    # S1:
    #   port 1 -> S2
    #   port 2 -> S3
    #
    # S2:
    #   port 1 -> S1
    #   port 2 -> S4
    #   port 3 -> S5
    #   port 4 -> VIDEO client
    #   port 5 -> VOICE client
    #
    # S3:
    #   port 1 -> S1
    #   port 2 -> S6
    #   port 3 -> S7
    #   port 4 -> WEB client
    #   port 5 -> IOT client
    #
    # S4:
    #   port 1 -> S2
    #   port 3 -> VIDEO server
    #
    # S5:
    #   port 1 -> S2
    #   port 3 -> VOICE server
    #
    # S6:
    #   port 1 -> S3
    #   port 3 -> WEB server
    #
    # S7:
    #   port 1 -> S3
    #   port 3 -> IOT server
    #
    # Alternative links:
    #
    #   S4 <-> S6
    #   S5 <-> S7
    #
    # are intentionally excluded from flooding.
    #
    # They remain available for future path orchestration.
    # ============================================================

    FLOOD_PORTS = {

        1: [1, 2],

        2: [1, 2, 3, 4, 5],

        3: [1, 2, 3, 4, 5],

        4: [1, 3],

        5: [1, 3],

        6: [1, 3],

        7: [1, 3]
    }

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def __init__(self, *args, **kwargs):

        super(
            OrchestrationController,
            self
        ).__init__(*args, **kwargs)

        self.datapaths = {}

        self.mac_to_port = {}

        self.port_stats = {}

        self.previous_port_stats = {}

        self.monitor_thread = hub.spawn(
            self.monitor
        )

        self.logger.info("")
        self.logger.info(
            "=============================================="
        )
        self.logger.info(
            " APPLICATION-AWARE SDN ORCHESTRATOR"
        )
        self.logger.info(
            "=============================================="
        )
        self.logger.info(
            "Controller : RYU"
        )
        self.logger.info(
            "Protocol   : OpenFlow 1.3"
        )
        self.logger.info(
            "Forwarding : LOOP-FREE MAC LEARNING"
        )
        self.logger.info(
            "Telemetry  : ENABLED"
        )
        self.logger.info(
            "Applications: VIDEO / VOICE / WEB / IOT"
        )
        self.logger.info(
            "Alternative paths: ENABLED"
        )
        self.logger.info(
            "=============================================="
        )
        self.logger.info("")

    # ============================================================
    # ADD FLOW
    # ============================================================

    def add_flow(
        self,
        datapath,
        priority,
        match,
        actions,
        idle_timeout=0,
        hard_timeout=0
    ):

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout
        )

        datapath.send_msg(mod)

    # ============================================================
    # SWITCH FEATURES
    # ============================================================

    @set_ev_cls(
        ofp_event.EventOFPSwitchFeatures,
        CONFIG_DISPATCHER
    )
    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath

        dpid = datapath.id

        self.datapaths[dpid] = datapath

        self.mac_to_port.setdefault(
            dpid,
            {}
        )

        self.port_stats.setdefault(
            dpid,
            {}
        )

        self.previous_port_stats.setdefault(
            dpid,
            {}
        )

        self.logger.info(
            "Switch connected: ID=%s",
            dpid
        )

        parser = datapath.ofproto_parser

        ofproto = datapath.ofproto

        # --------------------------------------------------------
        # TABLE MISS
        # --------------------------------------------------------

        match = parser.OFPMatch()

        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]

        self.add_flow(
            datapath,
            0,
            match,
            actions
        )

    # ============================================================
    # SWITCH STATE
    # ============================================================

    @set_ev_cls(
        ofp_event.EventOFPStateChange,
        [MAIN_DISPATCHER, DEAD_DISPATCHER]
    )
    def state_change_handler(self, ev):

        datapath = ev.datapath

        if ev.state == MAIN_DISPATCHER:

            self.datapaths[
                datapath.id
            ] = datapath

        elif ev.state == DEAD_DISPATCHER:

            self.datapaths.pop(
                datapath.id,
                None
            )

    # ============================================================
    # PACKET IN
    # ============================================================

    @set_ev_cls(
        ofp_event.EventOFPPacketIn,
        MAIN_DISPATCHER
    )
    def packet_in_handler(self, ev):

        msg = ev.msg

        datapath = msg.datapath

        dpid = datapath.id

        parser = datapath.ofproto_parser

        ofproto = datapath.ofproto

        in_port = msg.match[
            "in_port"
        ]

        pkt = packet.Packet(
            msg.data
        )

        eth = pkt.get_protocol(
            ethernet.ethernet
        )

        if eth is None:
            return

        # --------------------------------------------------------
        # Ignore LLDP
        # --------------------------------------------------------

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src = eth.src

        dst = eth.dst

        # --------------------------------------------------------
        # Learn source MAC
        # --------------------------------------------------------

        self.mac_to_port[
            dpid
        ][src] = in_port

        self.logger.info(
            "PACKET S%s | %s -> %s | port=%s",
            dpid,
            src,
            dst,
            in_port
        )

        # --------------------------------------------------------
        # Known destination
        # --------------------------------------------------------

        if dst in self.mac_to_port[
            dpid
        ]:

            out_port = self.mac_to_port[
                dpid
            ][dst]

            actions = [
                parser.OFPActionOutput(
                    out_port
                )
            ]

            match = parser.OFPMatch(
                in_port=in_port,
                eth_dst=dst
            )

            self.add_flow(
                datapath,
                10,
                match,
                actions,
                idle_timeout=60
            )

            self.logger.info(
                "LEARNED FLOW S%s | "
                "%s -> port %s",
                dpid,
                dst,
                out_port
            )

        # --------------------------------------------------------
        # Unknown destination
        #
        # Use only the loop-free spanning-tree ports.
        # --------------------------------------------------------

        else:

            flood_ports = self.FLOOD_PORTS.get(
                dpid,
                []
            )

            output_ports = [
                port
                for port in flood_ports
                if port != in_port
            ]

            actions = []

            for port in output_ports:

                actions.append(
                    parser.OFPActionOutput(
                        port
                    )
                )

            self.logger.info(
                "UNKNOWN %s on S%s | "
                "TREE FLOOD ports=%s",
                dst,
                dpid,
                output_ports
            )

        # --------------------------------------------------------
        # Send packet
        # --------------------------------------------------------

        data = None

        if msg.buffer_id == ofproto.OFP_NO_BUFFER:

            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )

        datapath.send_msg(
            out
        )

    # ============================================================
    # TELEMETRY MONITOR
    # ============================================================

    def monitor(self):

        while True:

            for datapath in list(
                self.datapaths.values()
            ):

                self.request_port_stats(
                    datapath
                )

            hub.sleep(5)

    # ============================================================
    # REQUEST PORT STATS
    # ============================================================

    def request_port_stats(
        self,
        datapath
    ):

        parser = datapath.ofproto_parser

        request = parser.OFPPortStatsRequest(
            datapath,
            0
        )

        datapath.send_msg(
            request
        )

    # ============================================================
    # PORT STATISTICS
    # ============================================================

    @set_ev_cls(
        ofp_event.EventOFPPortStatsReply,
        MAIN_DISPATCHER
    )
    def port_stats_reply_handler(
        self,
        ev
    ):

        datapath = ev.msg.datapath

        dpid = datapath.id

        current_time = time.time()

        self.port_stats.setdefault(
            dpid,
            {}
        )

        self.previous_port_stats.setdefault(
            dpid,
            {}
        )

        for stat in ev.msg.body:

            port = stat.port_no

            if port >= datapath.ofproto.OFPP_MAX:
                continue

            previous = (
                self.previous_port_stats[
                    dpid
                ].get(port)
            )

            rx_mbps = 0.0

            tx_mbps = 0.0

            if previous:

                elapsed = (
                    current_time
                    -
                    previous["time"]
                )

                if elapsed > 0:

                    rx_delta = (
                        stat.rx_bytes
                        -
                        previous["rx_bytes"]
                    )

                    tx_delta = (
                        stat.tx_bytes
                        -
                        previous["tx_bytes"]
                    )

                    rx_mbps = (
                        max(0, rx_delta)
                        * 8
                        / elapsed
                        / 1000000
                    )

                    tx_mbps = (
                        max(0, tx_delta)
                        * 8
                        / elapsed
                        / 1000000
                    )

            current = {

                "rx_bytes":
                    stat.rx_bytes,

                "tx_bytes":
                    stat.tx_bytes,

                "rx_packets":
                    stat.rx_packets,

                "tx_packets":
                    stat.tx_packets,

                "rx_dropped":
                    stat.rx_dropped,

                "tx_dropped":
                    stat.tx_dropped,

                "rx_mbps":
                    rx_mbps,

                "tx_mbps":
                    tx_mbps,

                "time":
                    current_time
            }

            self.port_stats[
                dpid
            ][port] = current

            self.previous_port_stats[
                dpid
            ][port] = current.copy()

        self.logger.info(
            "Telemetry collected from S%s",
            dpid
        )

    # ============================================================
    # APPLICATION PROFILE
    # ============================================================

    def get_application_profile(
        self,
        application
    ):

        return self.APPLICATION_PROFILES.get(
            application,
            self.APPLICATION_PROFILES["WEB"]
        )
