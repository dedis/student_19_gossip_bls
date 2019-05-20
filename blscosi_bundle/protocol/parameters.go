package protocol

import (
	"time"
)

// Parameters holds a set of parameters, mainly for simulation purposes
type Parameters struct {
	GossipTick    time.Duration // periodic interval
	RumorPeers    int           // number of peers that a rumor message is sent to
	ShutdownPeers int           // number of peers that the shutdown message is sent to
	TreeMode      bool          // aggregate messages wherever possible
}

// DefaultParams returns a set of default parameters
func DefaultParams() Parameters {
	return Parameters{
		GossipTick:    100 * time.Millisecond,
		RumorPeers:    2,
		ShutdownPeers: 2,
		TreeMode:      true,
	}
}
