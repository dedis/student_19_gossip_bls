package protocol

import (
	"errors"
	"fmt"

	"go.dedis.ch/kyber/v3"
	"go.dedis.ch/kyber/v3/pairing"
	"go.dedis.ch/kyber/v3/sign"
	"go.dedis.ch/kyber/v3/sign/bdn"
	"go.dedis.ch/onet/v3"
	"go.dedis.ch/onet/v3/log"
	"go.dedis.ch/onet/v3/network"
)

// DefaultProtocolName can be used from other packages to refer to this protocol.
// If this name is used, then the suite used to verify signatures must be
// the default cothority.Suite.
const DefaultProtocolName = "bundleCoSiDefault"

func init() {
	network.RegisterMessages(&Rumor{}, &Shutdown{}, &Response{}, &Stop{})
}

// ResponseMap is the container used to store responses coming from the children
type ResponseMap map[string]*Response

// BlsSignature contains the message and its aggregated signature
type BlsSignature []byte

// GetMask creates and returns the mask associated with the signature. If
// no mask has been appended, mask with every bit enabled is assumed
func (sig BlsSignature) GetMask(suite pairing.Suite, publics []kyber.Point) (*sign.Mask, error) {
	mask, err := sign.NewMask(suite, publics, nil)
	if err != nil {
		return nil, err
	}

	lenCom := suite.G1().PointLen()
	if len(sig) < lenCom {
		return nil, errors.New("signature too short to get mask")
	}

	err = mask.SetMask(sig[lenCom:])
	if err != nil {
		return nil, err
	}

	return mask, nil
}

func (sig BlsSignature) RawSignature(suite pairing.Suite) ([]byte, error) {
	lenCom := suite.G1().PointLen()
	if len(sig) < lenCom {
		return nil, errors.New("signature too short")
	}
	return sig[:lenCom], nil
}

// Point creates the point associated with the signature in G1
func (sig BlsSignature) Point(suite pairing.Suite) (kyber.Point, error) {
	pointSig := suite.G1().Point()

	if err := pointSig.UnmarshalBinary(sig); err != nil {
		return nil, err
	}

	return pointSig, nil
}

// VerifyAggregate checks the signature over the message using the public keys and a default policy
func (sig BlsSignature) VerifyAggregate(suite pairing.Suite, msg []byte, publics []kyber.Point) error {
	policy := sign.NewThresholdPolicy(DefaultThreshold(len(publics)))
	return sig.VerifyAggregateWithPolicy(suite, msg, publics, policy)
}

// VerifyAggregateWithPolicy checks the signature over the message using the given public keys and policy
func (sig BlsSignature) VerifyAggregateWithPolicy(suite pairing.Suite, msg []byte, publics []kyber.Point, policy sign.Policy) error {
	if len(publics) == 0 {
		return errors.New("no public keys provided")
	}
	if msg == nil {
		return errors.New("no message provided")
	}

	rawSig, err := sig.RawSignature(suite)
	if err != nil {
		return err
	}

	// Unpack the participation mask
	mask, err := sig.GetMask(suite, publics)
	if err != nil {
		return err
	}

	log.Lvlf5("Verifying against %v", rawSig)

	// get the aggregate public key
	aggKey, err := bdn.AggregatePublicKeys(suite, mask)
	if err != nil {
		return err
	}

	err = bdn.Verify(suite, aggKey, msg, rawSig)
	if err != nil {
		return fmt.Errorf("didn't get a valid signature: %s", err)
	}

	log.Lvl3("Signature verified and is correct!")
	log.Lvl3("m.CountEnabled():", mask.CountEnabled())

	if !policy.Check(mask) {
		return errors.New("the policy is not fulfilled")
	}

	return nil
}

// Rumor is a struct that can be sent in the gossip protocol
type Rumor struct {
	ResponseMap ResponseMap
	Msg         []byte
}

// RumorMessage just contains a Rumor and the data necessary to identify and
// process the message in the onet framework.
type RumorMessage struct {
	*onet.TreeNode
	Rumor
}

// Shutdown is a struct that can be sent in the gossip protocol
// A valid shutdown message must contain a proof that the root has seen a valid
// final signature. This is to prevent faked shutdown messages that take down the
// gossip protocol. Thus the shutdown message contains the final signature,
// which in turn is signed by root.
type Shutdown struct {
	FinalCoSignature BlsSignature
	RootSig          []byte
}

// ShutdownMessage just contains a Shutdown and the data necessary to identify
// and process the message in the onet framework.
type ShutdownMessage struct {
	*onet.TreeNode
	Shutdown
}

// Response is the blscosi response message
type Response struct {
	Signature BlsSignature
	Mask      []byte
}

// Refusal is the signed refusal response from a given node
type Refusal struct {
	Signature []byte
}

// StructRefusal contains the refusal and the treenode that sent it
type StructRefusal struct {
	*onet.TreeNode
	Refusal
}

// Stop is a message used to instruct a node to stop its protocol
type Stop struct{}

// StructStop is a wrapper around Stop for it to work with onet
type StructStop struct {
	*onet.TreeNode
	Stop
}
