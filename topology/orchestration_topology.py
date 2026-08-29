from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink


def create_topology():

    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=False
    )

    info("\n")
    info("============================================\n")
    info(" APPLICATION-AWARE SDN NETWORK\n")
    info(" RESOURCE ORCHESTRATION TESTBED\n")
    info("============================================\n")

    # ============================================================
    # RYU CONTROLLER
    # ============================================================

    info("*** Adding RYU controller\n")

    controller = net.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6633
    )

    # ============================================================
    # SWITCHES
    # ============================================================

    info("*** Adding switches\n")

    s1 = net.addSwitch("s1", protocols="OpenFlow13")
    s2 = net.addSwitch("s2", protocols="OpenFlow13")
    s3 = net.addSwitch("s3", protocols="OpenFlow13")
    s4 = net.addSwitch("s4", protocols="OpenFlow13")
    s5 = net.addSwitch("s5", protocols="OpenFlow13")
    s6 = net.addSwitch("s6", protocols="OpenFlow13")
    s7 = net.addSwitch("s7", protocols="OpenFlow13")

    # ============================================================
    # APPLICATION CLIENTS
    # ============================================================

    info("*** Adding application clients\n")

    vcli = net.addHost(
        "vcli",
        ip="10.0.1.10/24",
        mac="00:00:00:00:01:10"
    )

    vocli = net.addHost(
        "vocli",
        ip="10.0.2.10/24",
        mac="00:00:00:00:02:10"
    )

    wcli = net.addHost(
        "wcli",
        ip="10.0.3.10/24",
        mac="00:00:00:00:03:10"
    )

    icli = net.addHost(
        "icli",
        ip="10.0.4.10/24",
        mac="00:00:00:00:04:10"
    )

    # ============================================================
    # SERVICE INSTANCES
    # ============================================================

    info("*** Adding service instances\n")

    vserv = net.addHost(
        "vserv",
        ip="10.0.1.100/24",
        mac="00:00:00:00:11:00"
    )

    voserv = net.addHost(
        "voserv",
        ip="10.0.2.100/24",
        mac="00:00:00:00:12:00"
    )

    wserv = net.addHost(
        "wserv",
        ip="10.0.3.100/24",
        mac="00:00:00:00:13:00"
    )

    iserv = net.addHost(
        "iserv",
        ip="10.0.4.100/24",
        mac="00:00:00:00:14:00"
    )

    # ============================================================
    # CORE NETWORK
    #
    #              S1
    #             /  \
    #           S2    S3
    #          /  \  /  \
    #        S4   S5 S6   S7
    #         \    / \    /
    #          \  /   \  /
    #
    # S4 <-> S6 and S5 <-> S7 are alternative paths.
    #
    # ============================================================

    info("*** Creating core network links\n")

    # ------------------------------------------------------------
    # Core links
    # ------------------------------------------------------------

    net.addLink(
        s1,
        s2,
        cls=TCLink,
        bw=100,
        delay="5ms"
    )

    net.addLink(
        s1,
        s3,
        cls=TCLink,
        bw=100,
        delay="5ms"
    )

    net.addLink(
        s2,
        s4,
        cls=TCLink,
        bw=100,
        delay="5ms"
    )

    net.addLink(
        s2,
        s5,
        cls=TCLink,
        bw=50,
        delay="10ms"
    )

    net.addLink(
        s3,
        s6,
        cls=TCLink,
        bw=100,
        delay="5ms"
    )

    net.addLink(
        s3,
        s7,
        cls=TCLink,
        bw=50,
        delay="10ms"
    )

    # ------------------------------------------------------------
    # Alternative paths
    # ------------------------------------------------------------

    net.addLink(
        s4,
        s6,
        cls=TCLink,
        bw=30,
        delay="20ms"
    )

    net.addLink(
        s5,
        s7,
        cls=TCLink,
        bw=30,
        delay="20ms"
    )

    # ============================================================
    # APPLICATION CLIENT CONNECTIONS
    # ============================================================

    info("*** Connecting application clients\n")

    # Video
    net.addLink(
        vcli,
        s2,
        cls=TCLink,
        bw=100,
        delay="5ms"
    )

    # Voice
    net.addLink(
        vocli,
        s2,
        cls=TCLink,
        bw=30,
        delay="2ms"
    )

    # Web
    net.addLink(
        wcli,
        s3,
        cls=TCLink,
        bw=50,
        delay="5ms"
    )

    # IoT
    net.addLink(
        icli,
        s3,
        cls=TCLink,
        bw=30,
        delay="10ms"
    )

    # ============================================================
    # SERVICE CONNECTIONS
    # ============================================================

    info("*** Connecting service instances\n")

    # Video server
    net.addLink(
        s4,
        vserv,
        cls=TCLink,
        bw=100,
        delay="5ms"
    )

    # Voice server
    net.addLink(
        s5,
        voserv,
        cls=TCLink,
        bw=30,
        delay="2ms"
    )

    # Web server
    net.addLink(
        s6,
        wserv,
        cls=TCLink,
        bw=50,
        delay="5ms"
    )

    # IoT server
    net.addLink(
        s7,
        iserv,
        cls=TCLink,
        bw=30,
        delay="10ms"
    )

    # ============================================================
    # BUILD
    # ============================================================

    info("*** Building network\n")

    net.build()

    # ============================================================
    # START CONTROLLER
    # ============================================================

    info("*** Connecting to RYU controller\n")

    controller.start()

    # ============================================================
    # START SWITCHES
    # ============================================================

    info("*** Starting switches\n")

    s1.start([controller])
    s2.start([controller])
    s3.start([controller])
    s4.start([controller])
    s5.start([controller])
    s6.start([controller])
    s7.start([controller])

    # ============================================================
    # SUCCESS MESSAGE
    # ============================================================

    info("\n")
    info("============================================\n")
    info(" NETWORK STARTED SUCCESSFULLY\n")
    info("============================================\n")

    info(" Application paths:\n")
    info("   VIDEO  : vcli  -> vserv\n")
    info("   VOICE  : vocli -> voserv\n")
    info("   WEB    : wcli  -> wserv\n")
    info("   IOT    : icli  -> iserv\n")

    info("\n")
    info(" Resource constraints:\n")
    info("   VIDEO  : 100 Mbps\n")
    info("   VOICE  : 30 Mbps\n")
    info("   WEB    : 50 Mbps\n")
    info("   IOT    : 30 Mbps\n")

    info("\n")
    info(" Alternative paths:\n")
    info("   S4 <-> S6 : 30 Mbps / 20 ms\n")
    info("   S5 <-> S7 : 30 Mbps / 20 ms\n")

    info("============================================\n")
    info("\n")

    CLI(net)

    # ============================================================
    # CLEAN SHUTDOWN
    # ============================================================

    info("*** Stopping network\n")

    net.stop()


if __name__ == "__main__":

    setLogLevel("info")

    create_topology()
