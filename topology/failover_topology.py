from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink


def create_topology():

    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink
    )

    info("*** Adding RYU controller\n")

    controller = net.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6633
    )

    info("*** Adding switches\n")

    s1 = net.addSwitch(
        "s1",
        protocols="OpenFlow13"
    )

    s2 = net.addSwitch(
        "s2",
        protocols="OpenFlow13"
    )

    s3 = net.addSwitch(
        "s3",
        protocols="OpenFlow13"
    )

    info("*** Adding client and servers\n")

    client = net.addHost(
        "client",
        ip="10.0.0.1/24",
        mac="00:00:00:00:00:01"
    )

    server1 = net.addHost(
        "server1",
        ip="10.0.0.2/24",
        mac="00:00:00:00:00:02"
    )

    server2 = net.addHost(
        "server2",
        ip="10.0.0.3/24",
        mac="00:00:00:00:00:03"
    )

    info("*** Creating links\n")

    # Client -> S1
    net.addLink(
        client,
        s1
    )

    # S1 -> S2
    net.addLink(
        s1,
        s2
    )

    # S1 -> S3
    net.addLink(
        s1,
        s3
    )

    # S2 -> Primary Server
    net.addLink(
        s2,
        server1
    )

    # S3 -> Backup Server
    net.addLink(
        s3,
        server2
    )

    info("*** Starting network\n")

    net.build()

    controller.start()

    s1.start([controller])
    s2.start([controller])
    s3.start([controller])

    info("*** Network started successfully\n")

    CLI(net)

    net.stop()


if __name__ == "__main__":

    setLogLevel("info")

    create_topology()
