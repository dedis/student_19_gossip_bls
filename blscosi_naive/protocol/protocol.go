// Package protocol implements the BLS protocol using a main protocol and multiple
// subprotocols, one for each substree.
package protocol

import (
	"errors"
	"fmt"
	"math/rand"
	"sync"
	"time"

	"go.dedis.ch/kyber/v3"
	"go.dedis.ch/kyber/v3/pairing"
	"go.dedis.ch/kyber/v3/sign/bls"
	"go.dedis.ch/kyber/v3/sign/cosi"
	"go.dedis.ch/onet/v3"
	"go.dedis.ch/onet/v3/log"
)

const defaultTimeout = 10 * time.Second
const gossipTick = 100 * time.Millisecond

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
// This protocol should only exist on the root node.
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

	// internodes channel
	RumorsChan chan RumorMessage
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

	err := c.RegisterChannels(&c.RumorsChan)
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

	protocolTimeout := time.After(3500 * time.Millisecond)

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
		// If we aren't root, we don't know what the message is.
		err := p.trySign(responses)
		if err != nil {
			return err
		}
	}

	log.Lvlf3("Gossip protocol started at node %v", p.ServerIdentity())

	ticker := time.NewTicker(gossipTick)
	for {
		done := false
		select {
		case rumor := <-p.RumorsChan:
			updateResponses(responses, rumor.ResponseMap)
			log.Lvlf5("Incoming rumor, %d known, %d needed, root %v", len(responses), len(p.Roster().List), p.IsRoot())
			if p.IsRoot() && len(responses) == len(p.Roster().List) {
				// We've got all the signatures.
				done = true
			}
			if len(p.Msg) == 0 && len(rumor.Msg) > 0 {
				p.Msg = rumor.Msg[:]
				// Add own signature.
				err := p.trySign(responses)
				if err != nil {
					return err
				}
			}
		case <-ticker.C:
			log.Lvl5("Outgoing rumor")
			p.sendRumor(responses)
		case <-protocolTimeout:
			done = true
		}
		if done {
			break
		}
	}
	log.Lvl5("Done with gossiping")

	if !p.IsRoot() {
		return nil
	}

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

	p.FinalSignature <- append(signature, finalMask.Mask()...)
	log.Lvlf3("%v created final signature %x with mask %b", p.ServerIdentity(), signature, finalMask.Mask())
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

// sendRumor sends the given signatures to a random peer.
func (p *BlsCosi) sendRumor(responses ResponseMap) {
	// Get a random node except self.
	self := p.TreeNode()
	root := p.Root()
	allNodes := append(root.Children, root)

	numPeers := len(allNodes) - 1
	if numPeers <= 0 {
		log.Lvl1("no other nodes in the roster")
		return
	}

	selfIndex := -1
	for i, node := range allNodes {
		if node.Equal(self) {
			selfIndex = i
			break
		}
	}
	if selfIndex == -1 {
		log.Lvl1("couldn't find outselves in the roster")
		numPeers++
	}

	index := rand.Intn(numPeers)
	if index >= selfIndex {
		index++
	}

	log.Lvlf5("chose %d, maximum %d", index, len(allNodes)-1)
	target := allNodes[index]
	p.SendTo(target, &Rumor{responses, p.Msg})
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
