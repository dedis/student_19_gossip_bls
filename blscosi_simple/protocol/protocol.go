// Package protocol implements the BLS protocol using a main protocol and multiple
// subprotocols, one for each substree.
package protocol

import (
	"errors"
	"fmt"
	"math/rand"
	"sync"
	"time"

	"go.dedis.ch/kyber/sign/bls"
	"go.dedis.ch/kyber/v3"
	"go.dedis.ch/kyber/v3/pairing"
	"go.dedis.ch/kyber/v3/sign/cosi"
	"go.dedis.ch/onet"
	"go.dedis.ch/onet/v3/log"
)

const defaultTimeout = 10 * time.Second
const shutdownAfter = 11 * time.Second // finally truly shutdown the protocol
const gossipTick = 100 * time.Millisecond

const rumorPeers = 2    // number of peers that a rumor message is sent to
const shutdownPeers = 2 // number of peers that the shutdown message is sent to

// VerificationFn is called on every node. Where msg is the message that is
// co-signed and the data is additional data for verification.
type VerificationFn func(msg, data []byte) bool

// init is done at startup. It defines every messages that is handled by the network
// and registers the protocols.
func init() {
	GlobalRegisterDefaultProtocols()
}

// BlsCosi holds the parameters of the protocol.
// It also defines a channel that will receive the final signature.
// This protocol exists on all nodes.
type BlsCosi struct {
	*onet.TreeNodeInstance
	Msg  []byte
	Data []byte
	// Timeout is not a global timeout for the protocol, but a timeout used
	// for waiting for responses.
	Timeout        time.Duration
	Threshold      int
	FinalSignature chan BlsSignature // final signature that is sent back to client

	stoppedOnce    sync.Once
	startChan      chan bool
	verificationFn VerificationFn
	suite          *pairing.SuiteBn256

	// internodes channels
	RumorsChan   chan RumorMessage
	ShutdownChan chan ShutdownMessage
}

// NewDefaultProtocol is the default protocol function used for registration
// with an always-true verification.
// Called by GlobalRegisterDefaultProtocols
func NewDefaultProtocol(n *onet.TreeNodeInstance) (onet.ProtocolInstance, error) {
	vf := func(a, b []byte) bool { return true }
	return NewBlsCosi(n, vf, pairing.NewSuiteBn256())
}

// GlobalRegisterDefaultProtocols is used to register the protocols before use,
// most likely in an init function.
func GlobalRegisterDefaultProtocols() {
	onet.GlobalProtocolRegister(DefaultProtocolName, NewDefaultProtocol)
}

// DefaultThreshold computes the minimal threshold authorized using
// the formula 3f+1
func DefaultThreshold(n int) int {
	f := (n - 1) / 3
	return n - f
}

// NewBlsCosi method is used to define the blscosi protocol.
func NewBlsCosi(n *onet.TreeNodeInstance, vf VerificationFn, suite *pairing.SuiteBn256) (onet.ProtocolInstance, error) {
	nNodes := len(n.Roster().List)
	c := &BlsCosi{
		TreeNodeInstance: n,
		FinalSignature:   make(chan BlsSignature, 1),
		Timeout:          defaultTimeout,
		Threshold:        DefaultThreshold(nNodes),
		startChan:        make(chan bool, 1),
		verificationFn:   vf,
		suite:            suite,
	}

	err := c.RegisterChannels(&c.RumorsChan, &c.ShutdownChan)
	if err != nil {
		return nil, errors.New("couldn't register channels: " + err.Error())
	}

	return c, nil
}

// Shutdown stops the protocol
func (p *BlsCosi) Shutdown() error {
	p.stoppedOnce.Do(func() {
		close(p.startChan)
		close(p.FinalSignature)
	})
	return nil
}

// Dispatch is the main method of the protocol for all nodes.
func (p *BlsCosi) Dispatch() error {
	defer p.Done()

	protocolTimeout := time.After(shutdownAfter)

	// responses is a map where we collect all signatures.
	responses := make(ResponseMap)

	// The root must wait for Start() to have been called.
	if p.IsRoot() {
		select {
		case _, ok := <-p.startChan:
			if !ok {
				return errors.New("protocol finished prematurely")
			}
		case <-time.After(time.Second):
			return errors.New("timeout, did you forget to call Start?")
		}

		// Add own signature.
		// If we aren't root, we don't yet know what the message is.
		err := p.trySign(responses)
		if err != nil {
			return err
		}
	}

	log.Lvlf3("Gossip protocol started at node %v", p.ServerIdentity())

	ticker := time.NewTicker(gossipTick)

	var shutdownStruct Shutdown

	// When `shutdown` is true, we'll initiate a "soft shutdown": the protocol
	// stays alive here on this node, but no more rumor messages are sent.
	shutdown := false
	done := false
	for !shutdown {
		select {
		case rumor := <-p.RumorsChan:
			updateResponses(responses, rumor.ResponseMap)
			log.Lvlf5("Incoming rumor, %d known, %d needed, is-root %v",
				len(responses), p.Threshold, p.IsRoot())
			if p.IsRoot() && len(responses) >= p.Threshold {
				// We've got all the signatures.
				shutdown = true
			}

			if len(p.Msg) == 0 && len(rumor.Msg) > 0 {
				p.Msg = rumor.Msg[:]
				// Add own signature.
				err := p.trySign(responses)
				if err != nil {
					return err
				}
			}
		case shutdownMsg := <-p.ShutdownChan:
			log.Lvl5("Received shutdown")
			if err := p.verifyShutdown(shutdownMsg); err == nil {
				shutdownStruct = shutdownMsg.Shutdown
				shutdown = true
			} else {
				log.Lvl1("Got spoofed shutdown:", err)
				// Don't take any action
			}
		case <-ticker.C:
			log.Lvl5("Outgoing rumor")
			p.sendRumors(responses)
		case <-protocolTimeout:
			shutdown = true
			done = true
		}
	}
	log.Lvl5("Done with gossiping")
	ticker.Stop()

	if p.IsRoot() {
		log.Lvl3(p.ServerIdentity().Address, "collected all signature responses")

		// generate root signature
		signaturePoint, finalMask, err := p.generateSignature(responses)
		if err != nil {
			return err
		}

		signature, err := signaturePoint.MarshalBinary()
		if err != nil {
			return err
		}

		finalSig := append(signature, finalMask.Mask()...)
		p.FinalSignature <- finalSig
		log.Lvlf3("%v created final signature %x with mask %b", p.ServerIdentity(), signature, finalMask.Mask())

		// Sign shutdown message
		rootSig, err := bls.Sign(p.suite, p.Private(), finalSig)
		if err != nil {
			return err
		}
		shutdownStruct = Shutdown{finalSig, rootSig}
	}

	p.sendShutdowns(shutdownStruct)

	// We respond to every non-shutdown message with a shutdown message, to
	// ensure that all nodes will shut down eventually. This is also the reason
	// why we don't immediately do a hard shutdown.
	for !done {
		select {
		case rumor := <-p.RumorsChan:
			sender := rumor.TreeNode
			log.Lvl5("Responding to rumor with shutdown", sender.Equal(p.TreeNode()))
			p.sendShutdown(sender, shutdownStruct)
		case <-p.ShutdownChan:
			// ignore
		case <-protocolTimeout:
			done = true
		}
	}
	log.Lvl5("Done with the whole protocol")

	return nil
}

func (p *BlsCosi) trySign(responses ResponseMap) error {
	if p.verificationFn(p.Msg, p.Data) {
		own, err := p.makeResponse()
		if err != nil {
			return err
		}
		responses[p.Public().String()] = own
		log.Lvlf4("Node %v signed", p.ServerIdentity())
	} else {
		log.Lvlf4("Node %v refused to sign", p.ServerIdentity())
	}
	return nil
}

// sendRumors sends a rumor message to some peers.
func (p *BlsCosi) sendRumors(responses ResponseMap) {
	targets, err := p.getRandomPeers(shutdownPeers)
	if err != nil {
		log.Lvl1("Couldn't get random peers:", err)
		return
	}
	log.Lvl5("Sending rumors")
	for _, target := range targets {
		p.sendRumor(target, responses)
	}
}

// sendRumor sends the given signatures to a random peer.
func (p *BlsCosi) sendRumor(target *onet.TreeNode, responses ResponseMap) {
	p.SendTo(target, &Rumor{responses, p.Msg})
}

// sendShutdowns sends a shutdown message to some random peers.
func (p *BlsCosi) sendShutdowns(shutdown Shutdown) {
	targets, err := p.getRandomPeers(shutdownPeers)
	if err != nil {
		log.Lvl1("Couldn't get random peers:", err)
		return
	}
	log.Lvl5("Sending shutdowns")
	for _, target := range targets {
		p.sendShutdown(target, shutdown)
	}
}

// sendShutdown sends a shutdown message to a single peer.
func (p *BlsCosi) sendShutdown(target *onet.TreeNode, shutdown Shutdown) {
	p.SendTo(target, &shutdown)
}

// verifyShutdown verifies the legitimacy of a shutdown message.
func (p *BlsCosi) verifyShutdown(msg ShutdownMessage) error {
	rootPublic := p.Publics()[:1]
	finalSig := msg.FinalCoSignature

	// verify final signature
	err := msg.FinalCoSignature.Verify(p.suite, p.Msg, p.Publics())
	if err != nil {
		return err
	}

	// verify root signature of final signature
	return msg.RootSig.Verify(p.suite, finalSig, rootPublic)
}

// getRandomPeers returns a slice of random peers (not including self).
func (p *BlsCosi) getRandomPeers(numTargets int) ([]*onet.TreeNode, error) {
	self := p.TreeNode()
	root := p.Root()
	allNodes := append(root.Children, root)

	numPeers := len(allNodes) - 1

	selfIndex := len(allNodes)
	for i, node := range allNodes {
		if node.Equal(self) {
			selfIndex = i
			break
		}
	}
	if selfIndex == len(allNodes) {
		log.Lvl1("couldn't find outselves in the roster")
		numPeers++
	}

	if numPeers < numTargets {
		return nil, errors.New("not enough nodes in the roster")
	}

	var results []*onet.TreeNode
	for i := 0; i < numTargets; i++ {
		index := rand.Intn(numPeers)
		if index >= selfIndex {
			index++
		}
		results = append(results, allNodes[index])
	}

	return results, nil
}

// getRandomPeer returns a random peer (not including self).
func (p *BlsCosi) getRandomPeer() (*onet.TreeNode, error) {
	peers, err := p.getRandomPeers(1)
	if err != nil {
		return nil, err
	}
	return peers[0], nil
}

// Start is done only by root and starts the protocol.
// It also verifies that the protocol has been correctly parameterized.
func (p *BlsCosi) Start() error {
	err := p.checkIntegrity()
	if err != nil {
		p.Done()
		return err
	}

	log.Lvlf3("Starting BLS CoSi on %v", p.ServerIdentity())
	p.startChan <- true
	return nil
}

// checkIntegrity checks if the protocol has been instantiated with
// correct parameters
func (p *BlsCosi) checkIntegrity() error {
	if p.Msg == nil {
		return fmt.Errorf("no proposal msg specified")
	}
	if p.CreateProtocol == nil {
		return fmt.Errorf("no create protocol function specified")
	}
	if p.verificationFn == nil {
		return fmt.Errorf("verification function cannot be nil")
	}
	if p.Timeout < 500*time.Microsecond {
		return fmt.Errorf("unrealistic timeout")
	}
	if p.Threshold > p.Tree().Size() {
		return fmt.Errorf("threshold (%d) bigger than number of nodes (%d)", p.Threshold, p.Tree().Size())
	}
	if p.Threshold < 1 {
		return fmt.Errorf("threshold of %d smaller than one node", p.Threshold)
	}

	return nil
}

// checkFailureThreshold returns true when the number of failures
// is above the threshold
func (p *BlsCosi) checkFailureThreshold(numFailure int) bool {
	return numFailure > len(p.Roster().List)-p.Threshold
}

// generateSignature aggregates all the signatures in responses.
// Also aggregates the bitmasks.
func (p *BlsCosi) generateSignature(responses ResponseMap) (kyber.Point, *cosi.Mask, error) {
	for k, r := range responses {
		log.Lvlf5("generating signature from %v %v", k, r)
	}

	// Aggregate all signatures
	response, err := makeAggregateResponse(p.suite, p.Publics(), responses)
	if err != nil {
		log.Lvlf3("%v failed to create aggregate signature", p.ServerIdentity())
		return nil, nil, err
	}
	log.Lvlf5("generated signature %v", response)

	//create final aggregated mask
	finalMask, err := cosi.NewMask(p.suite, p.Publics(), nil)
	if err != nil {
		return nil, nil, err
	}
	err = finalMask.SetMask(response.Mask)
	if err != nil {
		return nil, nil, err
	}

	finalSignature, err := response.Signature.Point(p.suite)
	if err != nil {
		return nil, nil, err
	}
	log.Lvlf3("%v is done aggregating signatures with total of %d signatures", p.ServerIdentity(), finalMask.CountEnabled())

	return finalSignature, finalMask, err
}

// Sign the message and pack it with the mask as a response
func (p *BlsCosi) makeResponse() (*Response, error) {
	mask, err := cosi.NewMask(p.suite, p.Publics(), p.Public())
	log.Lvlf1("%v pk %v pk %v", p.Publics(), p.Public(), p.Msg)
	if err != nil {
		log.Error(err)
		return nil, err
	}

	sig, err := bls.Sign(p.suite, p.Private(), p.Msg)
	if err != nil {
		return nil, err
	}

	return &Response{
		Mask:      mask.Mask(),
		Signature: sig,
	}, nil
}

// updateResponses updates the first map with the content from the second map.
func updateResponses(responses ResponseMap, newResponses ResponseMap) {
	for key, response := range newResponses {
		responses[key] = response
	}
}
