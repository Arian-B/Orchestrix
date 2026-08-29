# Orchestrix

<p align="center">
  <img src="docs/orchestrix-banner.png" alt="Orchestrix Banner" width="100%">
</p>

<p align="center">
  <strong>Application-Aware SDN Resource and Traffic Orchestration Framework</strong>
</p>

<p align="center">
  <em>Intelligent network resource monitoring, path evaluation, dynamic traffic orchestration, and resilient forwarding built on Software-Defined Networking.</em>
</p>

---

## Overview

**Orchestrix** is an application-aware Software-Defined Networking (SDN) framework designed to monitor network resources, evaluate application-specific traffic requirements, score available forwarding paths, and dynamically adapt traffic flows according to current network conditions.

The project combines centralized SDN control with resource-aware decision making. Rather than treating all network traffic identically, Orchestrix models different application classes and evaluates their requirements in terms of bandwidth, latency, and network utilization.

The current implementation is built around **Ryu**, **OpenFlow 1.3**, **Open vSwitch**, and **Mininet**, providing a programmable network environment in which traffic conditions can be generated, measured, analyzed, and acted upon by the controller.

The long-term objective of Orchestrix is to evolve from a research-oriented SDN orchestration prototype into a complete intelligent network management platform incorporating resilient failover, policy-driven Quality of Service, telemetry analytics, APIs, visualization, and an interactive management interface.

---

## Core Objectives

- Monitor network traffic and resource utilization continuously.
- Model network behavior at the application level.
- Associate applications with bandwidth and latency requirements.
- Detect congestion and classify resource utilization states.
- Maintain multiple candidate forwarding paths.
- Evaluate paths using measurable network conditions.
- Select forwarding paths dynamically according to resource availability.
- Install selected paths through OpenFlow rules.
- Preserve loop-free forwarding behavior in a topology containing redundant links.
- Provide a foundation for automatic server and link failover.
- Provide telemetry suitable for experimentation, analysis, and future visualization.
- Establish an extensible architecture for future policy engines and network automation.

---

## Current Capabilities

### Application-Aware Network Modeling

The controller defines application profiles with characteristics including:

- Client IP address
- Server IP address
- Client MAC address
- Server MAC address
- Required bandwidth
- Latency requirement

Current application profiles:

| Application | Bandwidth Requirement | Latency Requirement |
|---|---:|---:|
| VIDEO | 100 Mbps | 5 ms |
| VOICE | 30 Mbps | 10 ms |
| WEB | 50 Mbps | 5 ms |
| IOT | 30 Mbps | 10 ms |

This allows network decisions to be associated with application requirements rather than being based solely on destination addresses.

### Resource Telemetry

Orchestrix periodically requests OpenFlow port statistics from connected switches.

The controller measures:

- Received bytes
- Transmitted bytes
- Packet counts
- Traffic rate
- Port utilization
- Available bandwidth

Traffic rate is derived from byte counters over time, allowing the controller to observe changing network conditions rather than relying exclusively on static topology information.

### Congestion Detection

Measured traffic is compared against configured link capacities.

| Utilization | State |
|---:|---|
| 0%–69% | NORMAL |
| 70%–89% | WARNING |
| 90%+ | CONGESTED |

This provides the resource orchestration layer with an operational representation of network health.

### Candidate Path Evaluation

Each application can have multiple candidate forwarding paths.

For example, VIDEO has the direct path:

```text
S2 → S4
```

and an alternative path:

```text
S2 → S1 → S3 → S6 → S4
```

The controller evaluates paths using:

- Available bandwidth
- Maximum link utilization
- Link capacity
- End-to-end path latency
- Path feasibility

### Dynamic Path Selection

The orchestration engine maintains an active path for each application.

When network conditions change, the controller evaluates candidate paths and determines whether another path provides a sufficiently better option.

When a path change is justified, Orchestrix dynamically installs higher-priority OpenFlow forwarding rules corresponding to the selected path.

The original static forwarding rules remain underneath these dynamic rules as a lower-priority fallback.

```text
Dynamic orchestration rules
          |
          v
Static application forwarding
          |
          v
Controller handling
```

### Dynamic OpenFlow Rule Installation

Selected paths are translated into OpenFlow forwarding rules.

Example:

```text
VIDEO

Client
  |
 S2
  |
 S1
  |
 S3
  |
 S6
  |
 S4
  |
Server
```

The controller installs forwarding rules for both directions:

```text
Client → Server
Server → Client
```

### Loop-Free Forwarding

The topology contains redundant links to support alternate routing.

Orchestrix uses explicit application paths and controlled forwarding rules rather than unrestricted flooding, providing path diversity without sacrificing deterministic forwarding behavior.

---

## Architecture

At a high level, Orchestrix follows a centralized SDN architecture.

```text
                    +----------------------+
                    |      Orchestrix      |
                    |   SDN Controller     |
                    +----------+-----------+
                               |
                         OpenFlow 1.3
                               |
        +----------------------+----------------------+
        |                      |                      |
      +---+                  +---+                  +---+
      | S1|------------------| S2|------------------| S4|
      +---+                  +---+                  +---+
        |                      |                      |
        |                      |                      |
      +---+                  +---+                  +---+
      | S3|------------------| S5|                  | S6|
      +---+                  +---+                  +---+
        |                                              |
       S7-----------------------------------------------+

                    Mininet / Open vSwitch
```

The architecture consists of four logical layers.

### 1. Network Emulation Layer

Mininet provides the virtualized network environment.

Open vSwitch instances represent the programmable switches.

### 2. Control Layer

Ryu acts as the SDN controller framework and communicates with switches using OpenFlow 1.3.

### 3. Orchestration Layer

The Orchestrix controller performs:

- Resource monitoring
- Congestion analysis
- Application classification
- Candidate path evaluation
- Path scoring
- Path selection
- Dynamic forwarding rule installation

### 4. Application and Service Layer

Client and server instances generate application-specific traffic through the Mininet topology.

---

## Repository Structure

```text
Orchestrix/
│
├── controller/
│   ├── failover_controller.py
│   └── orchestration_controller.py
│
├── dashboard/
├── data/
├── docs/
├── documentation/
├── policies/
├── results/
├── screenshots/
│
├── scripts/
│   ├── cleanup.sh
│   ├── start_controller.sh
│   └── start_network.sh
│
├── servers/
│   ├── primary/
│   └── backup/
│
├── telemetry/
├── tests/
│
├── tools/
│   └── ryu/
│
├── topology/
│   ├── failover_topology.py
│   └── orchestration_topology.py
│
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

The `tools/ryu` directory is intentionally excluded from the Orchestrix Git repository because it is maintained as a separate Git repository.

Python virtual environments and runtime logs are also excluded from version control.

---

## Technology Stack

| Component | Technology |
|---|---|
| SDN Framework | Ryu |
| Southbound Protocol | OpenFlow 1.3 |
| Virtual Switch | Open vSwitch |
| Network Emulator | Mininet |
| Programming Language | Python |
| Traffic Generation | iPerf / iPerf3 |
| Operating Environment | Linux / WSL |
| Version Control | Git |
| Repository Hosting | GitHub |

---

## Running the Current Testbed

The current implementation is designed to operate in a Linux or WSL environment with the required SDN dependencies installed.

### 1. Enter the project

```bash
cd /mnt/d/Coding/Orchestrix
```

### 2. Activate the Ryu environment

```bash
source ryu-venv/bin/activate
```

### 3. Start the controller

```bash
ryu-manager controller/failover_controller.py
```

A successful controller startup reports the initialization of the Orchestrix resource orchestration engine and subsequently reports connected switches.

Expected initialization includes:

```text
APPLICATION-AWARE SDN RESOURCE ORCHESTRATOR

Loop-free forwarding      : ENABLED
Application profiles      : ENABLED
Resource monitoring       : ENABLED
Traffic measurement       : ENABLED
Policy engine             : ENABLED
Alternative paths         : AVAILABLE
```

### 4. Start the Mininet topology

In another terminal:

```bash
cd /mnt/d/Coding/Orchestrix
sudo python3 topology/orchestration_topology.py
```

The topology creates the application clients, service instances, switches, and inter-switch links used by the orchestration experiments.

### 5. Generate application traffic

Traffic can be generated from the Mininet CLI using the configured client and server hosts.

For example:

```text
mininet> vserv iperf -s
```

and from the corresponding client:

```text
mininet> vcli iperf -c 10.0.1.100
```

The resulting traffic should be visible through the controller's resource telemetry.

---

## Observability

Orchestrix exposes its current state primarily through controller logs.

### Resource telemetry

```text
[RESOURCE] S4 port 1 | Traffic 96.10 Mbps | Packets 9199
```

### Resource state

```text
[ORCHESTRATION] S4 port 1 |
96.10 / 100 Mbps |
Utilization 96.1% |
State=CONGESTED
```

### Path scoring

```text
[PATH-SCORE] VIDEO |
Path=2 -> 1 -> 3 -> 6 -> 4 |
Score=82.86 |
Available=30.00 Mbps |
Utilization=0.0% |
Latency=35 ms
```

### Dynamic path change

```text
[ORCHESTRATION] VIDEO |
PATH CHANGE DETECTED |
Old=2 -> 4 |
New=2 -> 1 -> 3 -> 6 -> 4
```

### Dynamic rule installation

```text
[FLOW] VIDEO |
Dynamic path installed |
Rules=8
```

These events provide a transparent view of the controller's decision-making process and form the basis for future telemetry visualization.

---

## Design Philosophy

Orchestrix is built around the principle that network orchestration should be **resource-aware, application-aware, and adaptive**.

Traditional forwarding approaches generally focus on connectivity: determine where a packet needs to go and forward it toward the destination.

Orchestrix introduces another dimension:

> The best path is not necessarily the shortest path. It is the path that best satisfies the application's requirements under the network's current conditions.

A path that is optimal under low utilization may become unsuitable during congestion. Conversely, a longer path may become preferable when the direct route approaches its capacity limit.

This makes network state an active input to forwarding decisions.

---

## Current Limitations

The current baseline is intentionally focused on establishing the orchestration core.

The following areas remain under active development:

- Automatic physical link failure detection
- Server health monitoring
- Primary-to-backup server failover
- Stateful service recovery
- More sophisticated QoS enforcement
- Advanced policy constraints
- Persistent telemetry storage
- Historical analytics
- REST API
- Real-time dashboard
- Network topology visualization
- Experiment automation
- Formal performance evaluation
- Production-oriented deployment support

These are planned extensions rather than claims of functionality already implemented in the current baseline.

---

## Development Roadmap

### Phase I — SDN Orchestration Core

- [x] Application profiles
- [x] Static application paths
- [x] Resource telemetry
- [x] Traffic measurement
- [x] Congestion classification
- [x] Candidate path modeling
- [x] Path scoring
- [x] Dynamic path selection
- [x] Dynamic OpenFlow rule installation
- [x] Active path tracking

### Phase II — Resilience and Failover

- [ ] Link failure detection
- [ ] Switch failure handling
- [ ] Server health monitoring
- [ ] Primary server failure detection
- [ ] Automatic backup server activation
- [ ] Service recovery
- [ ] Failback and recovery policies

### Phase III — Advanced Resource Orchestration

- [ ] Application-level QoS enforcement
- [ ] Bandwidth reservation
- [ ] Priority-aware path selection
- [ ] Latency-aware optimization
- [ ] Multi-constraint path scoring
- [ ] Policy-driven orchestration
- [ ] Resource prediction

### Phase IV — Observability and Analytics

- [ ] Persistent telemetry storage
- [ ] Historical traffic analysis
- [ ] Performance metrics
- [ ] Experiment result generation
- [ ] Automated benchmarking
- [ ] Network health analytics

### Phase V — Management Platform

- [ ] REST API
- [ ] Real-time orchestration dashboard
- [ ] Interactive topology visualization
- [ ] Application monitoring
- [ ] Path visualization
- [ ] Resource utilization graphs
- [ ] Failure and recovery event timeline
- [ ] Configuration management

### Phase VI — Intelligent Network Automation

- [ ] Predictive congestion detection
- [ ] Adaptive resource allocation
- [ ] Policy optimization
- [ ] Machine-learning-assisted path selection
- [ ] Automated experiment orchestration
- [ ] Intelligent network planning

---

## Project Status

**Current status: Active development**

The current Orchestrix baseline demonstrates an operational application-aware SDN orchestration pipeline:

```text
Application Requirements
          |
          v
Network Telemetry
          |
          v
Resource Measurement
          |
          v
Congestion Analysis
          |
          v
Candidate Path Evaluation
          |
          v
Path Scoring
          |
          v
Dynamic Path Selection
          |
          v
OpenFlow Rule Installation
          |
          v
Adaptive Forwarding
```

The project is positioned to extend this orchestration pipeline toward resilient failover, richer QoS policies, persistent telemetry, and a full management interface.

---

## Contributing

Orchestrix is currently maintained as an active development project.

Future contributions should preserve the project's architectural separation between:

- Network topology
- SDN control logic
- Resource telemetry
- Orchestration policies
- Application services
- Experiment data
- Visualization and management

Changes should be tested against the Mininet/Ryu environment before being merged into the main branch.

---

## License

Orchestrix is distributed under the **MIT License**.

See the `LICENSE` file for the complete license text.

---

## Author

**Arian Bhattacharjee**

Computer Science and Engineering

Orchestrix is developed as an ongoing SDN research and engineering project focused on intelligent resource-aware network orchestration.

---

## Acknowledgements

The project builds upon the open-source SDN ecosystem provided by Ryu, OpenFlow, Open vSwitch, and Mininet.

Their respective technologies provide the programmable control, switching, and network emulation foundations on which Orchestrix is being developed.

---

<p align="center">
  <strong>Orchestrix</strong><br>
  <em>Observe. Evaluate. Orchestrate. Adapt.</em>
</p>
