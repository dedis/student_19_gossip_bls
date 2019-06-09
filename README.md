# BLS Cosigning via a Gossip Protocol

The aim of this semester project is to build a gossip protocol for building collective signatures.


## Install and run

```
env GO111MODULE=on go get github.com/dedis/student_19_gossip_bls
```

Navigate to `student_19_gossip_bls/blscosi_bundle/blscosi_bundle/`.

```
env GO111MODULE=on go install
```

Navigate to `student_19_gossip_bls/conode/`.

```
env GO111MODULE=on go build
./runnodes.sh -n 6 -v 1
```

In a test folder in a second terminal:

```
date > date
blscosi_bundle sign -o sig.json date
blscosi_bundle verify -o sig.json date
```


## Run a simulation

Navigate to `student_19_gossip_bls/blscosi_bundle/simulation_bundle/`.

```
env GO111MODULE=on go install
simulation_bundle local.toml
```
