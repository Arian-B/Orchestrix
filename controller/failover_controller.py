import time

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub

from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import arp
from ryu.lib.packet import ether_types


class ResourceOrchestrationController(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # ============================================================
    # APPLICATIONS
    # ============================================================

    APPLICATIONS = {

        "VIDEO": {
            "client_ip": "10.0.1.10",
            "server_ip": "10.0.1.100",
            "client_mac": "00:00:00:00:01:10",
            "server_mac": "00:00:00:00:11:00",
            "bandwidth": 100,
            "latency": 5
        },

        "VOICE": {
            "client_ip": "10.0.2.10",
            "server_ip": "10.0.2.100",
            "client_mac": "00:00:00:00:02:10",
            "server_mac": "00:00:00:00:12:00",
            "bandwidth": 30,
            "latency": 10
        },

        "WEB": {
            "client_ip": "10.0.3.10",
            "server_ip": "10.0.3.100",
            "client_mac": "00:00:00:00:03:10",
            "server_mac": "00:00:00:00:13:00",
            "bandwidth": 50,
            "latency": 5
        },

        "IOT": {
            "client_ip": "10.0.4.10",
            "server_ip": "10.0.4.100",
            "client_mac": "00:00:00:00:04:10",
            "server_mac": "00:00:00:00:14:00",
            "bandwidth": 30,
            "latency": 10
        }
    }

    # ============================================================
    # STATIC HOST LOCATIONS
    # ============================================================

    HOST_LOCATION = {

        "00:00:00:00:01:10": (2, 4),
        "00:00:00:00:11:00": (4, 3),

        "00:00:00:00:02:10": (2, 5),
        "00:00:00:00:12:00": (5, 3),

        "00:00:00:00:03:10": (3, 4),
        "00:00:00:00:13:00": (6, 3),

        "00:00:00:00:04:10": (3, 5),
        "00:00:00:00:14:00": (7, 3)
    }

    # ============================================================
    # APPLICATION PATHS
    #
    # Each application receives a deterministic loop-free path.
    #
    # VIDEO:
    # S2 -> S4
    #
    # VOICE:
    # S2 -> S5
    #
    # WEB:
    # S3 -> S6
    #
    # IOT:
    # S3 -> S7
    #
    # The cross-links S4-S6 and S5-S7 remain available for future
    # dynamic path orchestration.
    # ============================================================

    PATHS = {

        "VIDEO": [
            (2, 4),
            (4, 2)
        ],

        "VOICE": [
            (2, 5),
            (5, 2)
        ],

        "WEB": [
            (3, 6),
            (6, 3)
        ],

        "IOT": [
            (3, 7),
            (7, 3)
        ]
    }

    # ============================================================
    # CANDIDATE PATHS FOR RESOURCE ORCHESTRATION
    # ============================================================
    #
    # Each path is represented as a sequence of switch-to-switch
    # links. These paths are evaluated by the orchestration engine.
    #
    # The existing PATHS dictionary remains unchanged and continues
    # to provide the currently active forwarding paths.
    # ============================================================

    CANDIDATE_PATHS = {

        "VIDEO": [

            # Current direct path
            [
                (2, 4)
            ],

            # Alternative path through the core
            [
                (2, 1),
                (1, 3),
                (3, 6),
                (6, 4)
            ]
        ],

        "VOICE": [

            # Current direct path
            [
                (2, 5)
            ],

            # Alternative path through the core
            [
                (2, 1),
                (1, 3),
                (3, 7),
                (7, 5)
            ]
        ],

        "WEB": [

            # Current direct path
            [
                (3, 6)
            ],

            # Alternative path through the core
            [
                (3, 1),
                (1, 2),
                (2, 4),
                (4, 6)
            ]
        ],

        "IOT": [

            # Current direct path
            [
                (3, 7)
            ],

            # Alternative path through the core
            [
                (3, 1),
                (1, 2),
                (2, 5),
                (5, 7)
            ]
        ]
    }

    # ============================================================
    # HOST PORTS
    # ============================================================

    HOST_PORTS = {

        2: {
            "00:00:00:00:01:10": 4,
            "00:00:00:00:02:10": 5
        },

        3: {
            "00:00:00:00:03:10": 4,
            "00:00:00:00:04:10": 5
        },

        4: {
            "00:00:00:00:11:00": 3
        },

        5: {
            "00:00:00:00:12:00": 3
        },

        6: {
            "00:00:00:00:13:00": 3
        },

        7: {
            "00:00:00:00:14:00": 3
        }
    }

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def __init__(self, *args, **kwargs):

        super(
            ResourceOrchestrationController,
            self
        ).__init__(*args, **kwargs)

        self.datapaths = {}

        self.port_stats = {}

        self.previous_stats = {}

        # Currently selected path for each application.
        self.active_paths = {}

        self.monitor_thread = hub.spawn(
            self.monitor_network
        )

        self.logger.info("")
        self.logger.info(
            "=================================================="
        )
        self.logger.info(
            " APPLICATION-AWARE SDN RESOURCE ORCHESTRATOR"
        )
        self.logger.info(
            "=================================================="
        )
        self.logger.info(
            " Loop-free forwarding      : ENABLED"
        )
        self.logger.info(
            " Application profiles      : ENABLED"
        )
        self.logger.info(
            " Resource monitoring       : ENABLED"
        )
        self.logger.info(
            " Traffic measurement       : ENABLED"
        )
        self.logger.info(
            " Policy engine             : ENABLED"
        )
        self.logger.info(
            " Alternative paths         : AVAILABLE"
        )
        self.logger.info(
            "=================================================="
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
        idle_timeout=0
    ):

        parser = datapath.ofproto_parser

        ofproto = datapath.ofproto

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions,
            idle_timeout=idle_timeout
        )

        datapath.send_msg(flow_mod)

    # ============================================================
    # SWITCH CONNECTION
    # ============================================================

    @set_ev_cls(
        ofp_event.EventOFPSwitchFeatures,
        CONFIG_DISPATCHER
    )
    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath

        dpid = datapath.id

        self.datapaths[dpid] = datapath

        self.logger.info(
            "Switch connected: S%s",
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
            priority=0,
            match=match,
            actions=actions
        )

        # --------------------------------------------------------
        # INSTALL APPLICATION PATHS
        # --------------------------------------------------------

        if len(self.datapaths) == 7:

            self.logger.info(
                ""
            )

            self.logger.info(
                "=================================================="
            )

            self.logger.info(
                "ALL SWITCHES CONNECTED"
            )

            self.install_application_paths()

            self.logger.info(
                "LOOP-FREE APPLICATION FORWARDING INSTALLED"
            )

            self.logger.info(
                "RESOURCE ORCHESTRATION ENGINE READY"
            )

            self.logger.info(
                "=================================================="
            )

    # ============================================================
    # INSTALL APPLICATION PATHS
    # ============================================================

    def install_application_paths(self):

        for name, config in self.APPLICATIONS.items():

            client_mac = config["client_mac"]

            server_mac = config["server_mac"]

            path = self.PATHS[name]

            self.logger.info(
                "[PATH] %s : %s -> %s",
                name,
                config["client_ip"],
                config["server_ip"]
            )

            # ----------------------------------------------------
            # CLIENT -> SERVER
            # ----------------------------------------------------

            for src_switch, dst_switch in path:

                if src_switch not in self.datapaths:
                    continue

                datapath = self.datapaths[src_switch]

                parser = datapath.ofproto_parser

                # Determine output port.

                out_port = self.get_inter_switch_port(
                    src_switch,
                    dst_switch
                )

                if out_port is None:
                    continue

                match = parser.OFPMatch(
                    eth_dst=server_mac
                )

                actions = [
                    parser.OFPActionOutput(
                        out_port
                    )
                ]

                self.add_flow(
                    datapath,
                    priority=100,
                    match=match,
                    actions=actions
                )

            # ----------------------------------------------------
            # SERVER -> CLIENT
            # ----------------------------------------------------

            reverse_path = list(
                reversed(path)
            )

            for src_switch, dst_switch in reverse_path:

                if src_switch not in self.datapaths:
                    continue

                datapath = self.datapaths[src_switch]

                parser = datapath.ofproto_parser

                out_port = self.get_inter_switch_port(
                    src_switch,
                    dst_switch
                )

                if out_port is None:
                    continue

                match = parser.OFPMatch(
                    eth_dst=client_mac
                )

                actions = [
                    parser.OFPActionOutput(
                        out_port
                    )
                ]

                self.add_flow(
                    datapath,
                    priority=100,
                    match=match,
                    actions=actions
                )

            # ----------------------------------------------------
            # HOST-SIDE FLOWS
            # ----------------------------------------------------

            self.install_host_flow(
                name,
                client_mac,
                server_mac
            )

    # ============================================================
    # INSTALL DYNAMIC APPLICATION PATH
    # ============================================================
    #
    # Installs the currently selected orchestration path using
    # higher-priority OpenFlow rules.
    #
    # The original priority-100 static rules remain underneath
    # these priority-200 rules as a safety fallback.
    # ============================================================

    def install_dynamic_application_path(
        self,
        application,
        path
    ):

        if application not in self.APPLICATIONS:

            return False

        if not path:

            return False

        config = self.APPLICATIONS[
            application
        ]

        client_mac = config["client_mac"]

        server_mac = config["server_mac"]

        installed = 0

        path_string = " -> ".join(
            str(src)
            for src, dst in path
        )

        if path:

            path_string += " -> " + str(
                path[-1][1]
            )

        self.logger.info(
            "[FLOW] %s | Installing selected path | %s",
            application,
            path_string
        )

        # --------------------------------------------------------
        # CLIENT -> SERVER
        # --------------------------------------------------------

        for src_switch, dst_switch in path:

            datapath = self.datapaths.get(
                src_switch
            )

            if datapath is None:

                continue

            out_port = self.get_inter_switch_port(
                src_switch,
                dst_switch
            )

            if out_port is None:

                self.logger.warning(
                    "[FLOW] %s | No port for S%s -> S%s",
                    application,
                    src_switch,
                    dst_switch
                )

                continue

            parser = datapath.ofproto_parser

            match = parser.OFPMatch(
                eth_dst=server_mac
            )

            actions = [
                parser.OFPActionOutput(
                    out_port
                )
            ]

            self.add_flow(
                datapath,
                priority=200,
                match=match,
                actions=actions
            )

            self.logger.info(
                "[FLOW] %s | S%s -> S%s | port=%s | SERVER",
                application,
                src_switch,
                dst_switch,
                out_port
            )

            installed += 1

        # --------------------------------------------------------
        # SERVER -> CLIENT
        # --------------------------------------------------------

        reverse_path = [
            (dst, src)
            for src, dst in reversed(path)
        ]

        for src_switch, dst_switch in reverse_path:

            datapath = self.datapaths.get(
                src_switch
            )

            if datapath is None:

                continue

            out_port = self.get_inter_switch_port(
                src_switch,
                dst_switch
            )

            if out_port is None:

                self.logger.warning(
                    "[FLOW] %s | No reverse port for "
                    "S%s -> S%s",
                    application,
                    src_switch,
                    dst_switch
                )

                continue

            parser = datapath.ofproto_parser

            match = parser.OFPMatch(
                eth_dst=client_mac
            )

            actions = [
                parser.OFPActionOutput(
                    out_port
                )
            ]

            self.add_flow(
                datapath,
                priority=200,
                match=match,
                actions=actions
            )

            self.logger.info(
                "[FLOW] %s | S%s -> S%s | port=%s | CLIENT",
                application,
                src_switch,
                dst_switch,
                out_port
            )

            installed += 1

        if installed == 0:

            self.logger.warning(
                "[FLOW] %s | No dynamic rules installed",
                application
            )

            return False

        self.logger.info(
            "[FLOW] %s | Dynamic path installed | Rules=%d",
            application,
            installed
        )

        return True

    # ============================================================
    # INSTALL HOST FLOWS
    # ============================================================

    def install_host_flow(
        self,
        application,
        client_mac,
        server_mac
    ):

        config = self.APPLICATIONS[
            application
        ]

        client_location = self.HOST_LOCATION[
            client_mac
        ]

        server_location = self.HOST_LOCATION[
            server_mac
        ]

        client_switch = client_location[0]

        client_port = client_location[1]

        server_switch = server_location[0]

        server_port = server_location[1]

        # --------------------------------------------------------
        # CLIENT SWITCH -> CLIENT
        # --------------------------------------------------------

        if client_switch in self.datapaths:

            datapath = self.datapaths[
                client_switch
            ]

            parser = datapath.ofproto_parser

            match = parser.OFPMatch(
                eth_dst=client_mac
            )

            actions = [
                parser.OFPActionOutput(
                    client_port
                )
            ]

            self.add_flow(
                datapath,
                priority=100,
                match=match,
                actions=actions
            )

        # --------------------------------------------------------
        # SERVER SWITCH -> SERVER
        # --------------------------------------------------------

        if server_switch in self.datapaths:

            datapath = self.datapaths[
                server_switch
            ]

            parser = datapath.ofproto_parser

            match = parser.OFPMatch(
                eth_dst=server_mac
            )

            actions = [
                parser.OFPActionOutput(
                    server_port
                )
            ]

            self.add_flow(
                datapath,
                priority=100,
                match=match,
                actions=actions
            )

    # ============================================================
    # INTER-SWITCH PORT MAP
    # ============================================================

    def get_inter_switch_port(
        self,
        src,
        dst
    ):

        ports = {

            (1, 2): 1,
            (2, 1): 1,

            (1, 3): 2,
            (3, 1): 1,

            (2, 4): 2,
            (4, 2): 1,

            (2, 5): 3,
            (5, 2): 1,

            (3, 6): 2,
            (6, 3): 1,

            (3, 7): 3,
            (7, 3): 1,

            (4, 6): 2,
            (6, 4): 2,

            (5, 7): 2,
            (7, 5): 2
        }

        return ports.get(
            (src, dst)
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

        # Ignore LLDP.

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:

            return

        # --------------------------------------------------------
        # ARP
        # --------------------------------------------------------

        arp_pkt = pkt.get_protocol(
            arp.arp
        )

        if arp_pkt is not None:

            self.handle_arp(
                datapath,
                in_port,
                arp_pkt,
                eth,
                msg
            )

            return

        # --------------------------------------------------------
        # UNKNOWN TRAFFIC
        # --------------------------------------------------------

        # Do NOT flood through the cyclic topology.
        #
        # Instead, send unknown packets back to controller and
        # allow application-specific flows to handle traffic.

        self.logger.debug(
            "Unknown packet on S%s port %s",
            dpid,
            in_port
        )

    # ============================================================
    # ARP HANDLER
    # ============================================================

    def handle_arp(
        self,
        datapath,
        in_port,
        arp_pkt,
        eth,
        msg
    ):

        target_ip = arp_pkt.dst_ip

        source_ip = arp_pkt.src_ip

        target_mac = None

        target_switch = None

        target_port = None

        # --------------------------------------------------------
        # FIND TARGET HOST
        # --------------------------------------------------------

        for config in self.APPLICATIONS.values():

            if target_ip == config["client_ip"]:

                target_mac = config["client_mac"]

                location = self.HOST_LOCATION[
                    target_mac
                ]

                target_switch = location[0]

                target_port = location[1]

                break

            if target_ip == config["server_ip"]:

                target_mac = config["server_mac"]

                location = self.HOST_LOCATION[
                    target_mac
                ]

                target_switch = location[0]

                target_port = location[1]

                break

        if target_mac is None:

            return

        # --------------------------------------------------------
        # SAME SWITCH
        # --------------------------------------------------------

        if datapath.id == target_switch:

            parser = datapath.ofproto_parser

            actions = [
                parser.OFPActionOutput(
                    target_port
                )
            ]

            out = parser.OFPPacketOut(
                datapath=datapath,
                buffer_id=msg.buffer_id,
                in_port=in_port,
                actions=actions,
                data=msg.data
            )

            datapath.send_msg(
                out
            )

            return

        # --------------------------------------------------------
        # DETERMINE APPLICATION
        # --------------------------------------------------------

        application = None

        for name, config in self.APPLICATIONS.items():

            if (
                source_ip == config["client_ip"]
                and
                target_ip == config["server_ip"]
            ):

                application = name

            elif (
                source_ip == config["server_ip"]
                and
                target_ip == config["client_ip"]
            ):

                application = name

        if application is None:

            return

        # --------------------------------------------------------
        # FOLLOW APPLICATION PATH
        # --------------------------------------------------------

        # Use the currently selected resource-aware path.
        # Fall back to the original deterministic path if the
        # orchestration engine has not selected one yet.
        path = self.active_paths.get(
            application,
            self.PATHS[application]
        )

        next_switch = None

        for src, dst in path:

            if src == datapath.id:

                next_switch = dst

                break

        if next_switch is None:

            reverse_path = list(
                reversed(path)
            )

            for src, dst in reverse_path:

                if src == datapath.id:

                    next_switch = dst

                    break

        if next_switch is None:

            return

        out_port = self.get_inter_switch_port(
            datapath.id,
            next_switch
        )

        if out_port is None:

            return

        parser = datapath.ofproto_parser

        actions = [
            parser.OFPActionOutput(
                out_port
            )
        ]

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=msg.data
        )

        datapath.send_msg(
            out
        )

    # ============================================================
    # RESOURCE MONITOR
    # ============================================================

    def monitor_network(self):

        while True:

            for datapath in list(
                self.datapaths.values()
            ):

                self.request_port_stats(
                    datapath
                )

            # Evaluate the latest measured resource state.
            self.evaluate_resource_state()

            # Evaluate candidate paths using the latest
            # resource measurements.
            self.evaluate_candidate_paths()

            hub.sleep(5)

    # ============================================================
    # PORT STATISTICS REQUEST
    # ============================================================

    def request_port_stats(
        self,
        datapath
    ):

        parser = datapath.ofproto_parser

        ofproto = datapath.ofproto

        request = parser.OFPPortStatsRequest(
            datapath,
            0,
            ofproto.OFPP_ANY
        )

        datapath.send_msg(
            request
        )

    # ============================================================
    # PORT STATISTICS REPLY
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

        now = time.time()

        for stat in ev.msg.body:

            port = stat.port_no

            if port >= 0xff00:

                continue

            key = (
                dpid,
                port
            )

            current_rx_bytes = stat.rx_bytes
            current_tx_bytes = stat.tx_bytes

            current_packets = (
                stat.rx_packets +
                stat.tx_packets
            )

            previous = self.previous_stats.get(
                key
            )

            if previous is None:

                self.previous_stats[key] = {

                    "rx_bytes": current_rx_bytes,

                    "tx_bytes": current_tx_bytes,

                    "packets": current_packets,

                    "time": now
                }

                continue

            time_delta = (
                now -
                previous["time"]
            )

            if time_delta <= 0:

                continue

            rx_delta = (
                current_rx_bytes -
                previous["rx_bytes"]
            )

            tx_delta = (
                current_tx_bytes -
                previous["tx_bytes"]
            )

            packet_delta = (
                current_packets -
                previous["packets"]
            )

            if rx_delta < 0:
                rx_delta = 0

            if tx_delta < 0:
                tx_delta = 0

            if packet_delta < 0:
                packet_delta = 0

            rx_mbps = (
                rx_delta *
                8 /
                time_delta /
                1_000_000
            )

            tx_mbps = (
                tx_delta *
                8 /
                time_delta /
                1_000_000
            )

            # Use the heavier traffic direction as the
            # link utilization measurement.
            mbps = max(
                rx_mbps,
                tx_mbps
            )

            self.port_stats[key] = {

                "bytes": (
                    current_rx_bytes +
                    current_tx_bytes
                ),

                "rx_mbps": rx_mbps,

                "tx_mbps": tx_mbps,

                "packets": current_packets,

                "mbps": mbps,

                "timestamp": now
            }

            self.previous_stats[key] = {

                "rx_bytes": current_rx_bytes,

                "tx_bytes": current_tx_bytes,

                "packets": current_packets,

                "time": now
            }

            # Only display meaningful traffic.

            if mbps > 1.0:

                self.logger.info(
                    "[RESOURCE] "
                    "S%s port %s | "
                    "Traffic %.2f Mbps | "
                    "Packets %d",
                    dpid,
                    port,
                    mbps,
                    packet_delta
                )

    # ============================================================
    # APPLICATION POLICY
    # ============================================================

    def evaluate_application(
        self,
        application
    ):

        if application not in self.APPLICATIONS:

            return

        config = self.APPLICATIONS[
            application
        ]

        self.logger.info(
            "[POLICY] %s | "
            "Bandwidth=%d Mbps | "
            "Latency=%d ms",
            application,
            config["bandwidth"],
            config["latency"]
        )

    # ============================================================
    # RESOURCE UTILIZATION
    # ============================================================

    def get_port_utilization(
        self,
        dpid,
        port
    ):

        key = (
            dpid,
            port
        )

        stats = self.port_stats.get(
            key
        )

        if stats is None:

            return 0.0

        return stats.get(
            "mbps",
            0.0
        )

    # ============================================================
    # PHASE 2: RESOURCE-AWARE PATH SCORING
    # ============================================================
    #
    # Physical topology information.
    #
    # Each entry maps:
    #
    #     source switch -> destination switch -> source port
    #
    # This allows the controller to translate a candidate path
    # into real OpenFlow port statistics.
    # ============================================================

    LINK_PORTS = {

        (1, 2): 1,
        (2, 1): 1,

        (1, 3): 2,
        (3, 1): 1,

        (2, 4): 2,
        (4, 2): 1,

        (2, 5): 3,
        (5, 2): 1,

        (3, 6): 2,
        (6, 3): 1,

        (3, 7): 3,
        (7, 3): 1,

        (4, 6): 2,
        (6, 4): 2,

        (5, 7): 2,
        (7, 5): 2
    }

    # ============================================================
    # RESOURCE CONGESTION THRESHOLDS
    # ============================================================
    #
    # Utilization is calculated as:
    #
    #     measured traffic / link capacity
    #
    # 0.00 - 0.69  -> NORMAL
    # 0.70 - 0.89  -> WARNING
    # 0.90+        -> CONGESTED
    # ============================================================

    CONGESTION_WARNING = 0.70

    CONGESTION_THRESHOLD = 0.90

    LINK_CAPACITY = {

        # Core links
        (1, 2): 100,
        (2, 1): 100,

        (1, 3): 100,
        (3, 1): 100,

        (2, 4): 100,
        (4, 2): 100,

        (2, 5): 50,
        (5, 2): 50,

        (3, 6): 100,
        (6, 3): 100,

        (3, 7): 50,
        (7, 3): 50,

        # Alternative paths
        (4, 6): 30,
        (6, 4): 30,

        (5, 7): 30,
        (7, 5): 30
    }

    LINK_LATENCY = {

        (1, 2): 5,
        (2, 1): 5,

        (1, 3): 5,
        (3, 1): 5,

        (2, 4): 5,
        (4, 2): 5,

        (2, 5): 10,
        (5, 2): 10,

        (3, 6): 5,
        (6, 3): 5,

        (3, 7): 10,
        (7, 3): 10,

        (4, 6): 20,
        (6, 4): 20,

        (5, 7): 20,
        (7, 5): 20
    }

    def get_path_metrics(
        self,
        path
    ):

        if not path:

            return {
                "bandwidth": 0.0,
                "utilization": 1.0,
                "latency": 0.0,
                "feasible": False
            }

        bottleneck_bandwidth = float("inf")

        maximum_utilization = 0.0

        total_latency = 0.0

        feasible = True

        for src, dst in path:

            port = self.LINK_PORTS.get(
                (src, dst)
            )

            capacity = self.LINK_CAPACITY.get(
                (src, port),
                100
            )

            utilization_mbps = self.get_port_utilization(
                src,
                port
            )

            utilization = (
                utilization_mbps /
                capacity
            )

            available_bandwidth = max(
                0.0,
                capacity - utilization_mbps
            )

            bottleneck_bandwidth = min(
                bottleneck_bandwidth,
                available_bandwidth
            )

            maximum_utilization = max(
                maximum_utilization,
                utilization
            )

            total_latency += self.LINK_LATENCY.get(
                (src, dst),
                10
            )

            if utilization >= 1.0:

                feasible = False

        if bottleneck_bandwidth == float("inf"):

            bottleneck_bandwidth = 0.0

        return {

            "bandwidth": bottleneck_bandwidth,

            "utilization": maximum_utilization,

            "latency": total_latency,

            "feasible": feasible
        }

    def score_path(
        self,
        application,
        path
    ):

        if application not in self.APPLICATIONS:

            return None

        config = self.APPLICATIONS[
            application
        ]

        metrics = self.get_path_metrics(
            path
        )

        required_bandwidth = config[
            "bandwidth"
        ]

        required_latency = config[
            "latency"
        ]

        available_bandwidth = metrics[
            "bandwidth"
        ]

        utilization = metrics[
            "utilization"
        ]

        latency = metrics[
            "latency"
        ]

        # --------------------------------------------------------
        # BANDWIDTH SCORE
        # --------------------------------------------------------
        #
        # A path that cannot satisfy the application's bandwidth
        # requirement receives zero bandwidth score.
        # --------------------------------------------------------

        if required_bandwidth <= 0:

            bandwidth_score = 1.0

        else:

            bandwidth_score = min(
                available_bandwidth /
                required_bandwidth,
                1.0
            )

        # --------------------------------------------------------
        # UTILIZATION SCORE
        # --------------------------------------------------------

        utilization_score = max(
            0.0,
            1.0 - utilization
        )

        # --------------------------------------------------------
        # LATENCY SCORE
        # --------------------------------------------------------

        if required_latency <= 0:

            latency_score = 1.0

        elif latency <= required_latency:

            latency_score = 1.0

        else:

            latency_score = max(
                0.0,
                required_latency /
                latency
            )

        # --------------------------------------------------------
        # FINAL SCORE
        # --------------------------------------------------------
        #
        # Bandwidth receives the highest weight because the
        # project is primarily resource-oriented.
        #
        # Utilization is the second-most important factor.
        #
        # Latency remains important for real-time applications.
        # --------------------------------------------------------

        score = (
            0.50 * bandwidth_score +
            0.30 * utilization_score +
            0.20 * latency_score
        ) * 100.0

        # Penalize paths that are currently unable to satisfy
        # their basic resource requirement.
        if available_bandwidth < required_bandwidth:

            score *= 0.50

        return {

            "score": score,

            "bandwidth": available_bandwidth,

            "utilization": utilization,

            "latency": latency,

            "feasible": metrics[
                "feasible"
            ],

            "bandwidth_score": bandwidth_score,

            "utilization_score": utilization_score,

            "latency_score": latency_score
        }

    def select_best_path(
        self,
        application
    ):

        candidates = self.CANDIDATE_PATHS.get(
            application,
            []
        )

        if not candidates:

            return None

        best_path = None

        best_result = None

        for path in candidates:

            result = self.score_path(
                application,
                path
            )

            if result is None:

                continue

            if (
                best_result is None or
                result["score"] >
                best_result["score"]
            ):

                best_path = path

                best_result = result

        return {

            "path": best_path,

            "metrics": best_result
        }

    def evaluate_candidate_paths(self):

        for application in self.CANDIDATE_PATHS:

            result = self.select_best_path(
                application
            )

            if result is None:

                continue

            path = result["path"]

            metrics = result["metrics"]

            if path is None:

                continue

            # ----------------------------------------------------
            # Build readable path representation.
            # ----------------------------------------------------

            path_string = " -> ".join(
                str(src)
                for src, dst in path
            )

            path_string += " -> " + str(
                path[-1][1]
            )

            previous_path = self.active_paths.get(
                application
            )

            # ----------------------------------------------------
            # First decision for this application.
            # ----------------------------------------------------

            if previous_path is None:

                self.active_paths[
                    application
                ] = path

                self.logger.info(
                    "[ORCHESTRATION] %s | "
                    "SELECTED INITIAL PATH | "
                    "Path=%s | "
                    "Score=%.2f | "
                    "Available=%.2f Mbps | "
                    "Utilization=%.1f%% | "
                    "Latency=%d ms",
                    application,
                    path_string,
                    metrics["score"],
                    metrics["bandwidth"],
                    metrics["utilization"] * 100,
                    metrics["latency"]
                )

                continue

            # ----------------------------------------------------
            # Evaluate the currently active path.
            # ----------------------------------------------------

            current_result = self.score_path(
                application,
                previous_path
            )

            if current_result is None:

                continue

            current_score = current_result["score"]

            score_improvement = (
                metrics["score"] -
                current_score
            )

            current_congested = (
                current_result["utilization"] >= 0.80
            )

            # ----------------------------------------------------
            # Anti-flapping policy.
            #
            # A path change requires either:
            #
            # 1. Current path is congested and the new path
            #    provides a better score, OR
            #
            # 2. New path is at least 15 points better.
            # ----------------------------------------------------

            should_switch = (

                path != previous_path
                and
                (
                    (
                        current_congested
                        and
                        metrics["score"] > current_score
                    )
                    or
                    score_improvement >= 15.0
                )
            )

            if not should_switch:

                self.logger.info(
                    "[ORCHESTRATION] %s | "
                    "ACTIVE PATH RETAINED | "
                    "Path=%s | "
                    "CurrentScore=%.2f | "
                    "BestScore=%.2f | "
                    "Improvement=%.2f",
                    application,
                    path_string,
                    current_score,
                    metrics["score"],
                    score_improvement
                )

                continue

            # ----------------------------------------------------
            # Compare selected path with current path.
            # ----------------------------------------------------

            if path != previous_path:

                old_string = " -> ".join(
                    str(src)
                    for src, dst in previous_path
                )

                old_string += " -> " + str(
                    previous_path[-1][1]
                )

                self.logger.info(
                    "[ORCHESTRATION] %s | "
                    "PATH CHANGE DETECTED | "
                    "Old=%s | New=%s | "
                    "Score=%.2f",
                    application,
                    old_string,
                    path_string,
                    metrics["score"]
                )

                # Install the newly selected path into the
                # OpenFlow switches.
                installed = self.install_dynamic_application_path(
                    application,
                    path
                )

                if installed:

                    self.active_paths[
                        application
                    ] = path

                    self.logger.info(
                        "[ORCHESTRATION] %s | "
                        "ACTIVE PATH UPDATED | "
                        "Path=%s",
                        application,
                        path_string
                    )

                else:

                    self.logger.warning(
                        "[ORCHESTRATION] %s | "
                        "Dynamic path installation failed. "
                        "Keeping previous active path.",
                        application
                    )

            else:

                self.logger.info(
                    "[ORCHESTRATION] %s | "
                    "ACTIVE PATH=%s | "
                    "Score=%.2f | "
                    "Available=%.2f Mbps | "
                    "Utilization=%.1f%% | "
                    "Latency=%d ms",
                    application,
                    path_string,
                    metrics["score"],
                    metrics["bandwidth"],
                    metrics["utilization"] * 100,
                    metrics["latency"]
                )

    def get_link_capacity(self, dpid, port):

        return self.LINK_CAPACITY.get(
            (dpid, port),
            100
        )

    def get_congestion_state(self, dpid, port):

        utilization = (
            self.get_port_utilization(
                dpid,
                port
            )
            /
            self.get_link_capacity(
                dpid,
                port
            )
        )

        if utilization >= self.CONGESTION_THRESHOLD:

            return "CONGESTED"

        if utilization >= self.CONGESTION_WARNING:

            return "WARNING"

        return "NORMAL"

    def evaluate_resource_state(self):

        for (dpid, port), stats in list(
            self.port_stats.items()
        ):

            mbps = stats.get(
                "mbps",
                0.0
            )

            capacity = self.get_link_capacity(
                dpid,
                port
            )

            utilization = (
                mbps / capacity
            )

            state = self.get_congestion_state(
                dpid,
                port
            )

            if mbps > 1.0:

                self.logger.info(
                    "[ORCHESTRATION] "
                    "S%s port %s | "
                    "%.2f / %d Mbps | "
                    "Utilization %.1f%% | "
                    "State=%s",
                    dpid,
                    port,
                    mbps,
                    capacity,
                    utilization * 100,
                    state
                )

