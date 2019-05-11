package protocol

import (
	"go.dedis.ch/kyber/v3"
	"go.dedis.ch/kyber/v3/pairing"
	"go.dedis.ch/kyber/v3/sign/cosi"
)

// makeAggregateResponse takes many signatures and masks to aggregate them
// into one signature and one mask.
func makeAggregateResponse(suite pairing.Suite, publics []kyber.Point, responses ResponseMap) (*Response, error) {
	finalMask, err := cosi.NewMask(suite.(cosi.Suite), publics, nil)
	if err != nil {
		return nil, err
	}
	finalSignature := suite.G1().Point()

	aggMask := finalMask.Mask()
	for _, res := range responses {
		if res == nil || len(res.Signature) == 0 {
			continue
		}

		sig, err := res.Signature.Point(suite)
		if err != nil {
			return nil, err
		}
		finalSignature = finalSignature.Add(finalSignature, sig)

		aggMask, err = cosi.AggregateMasks(aggMask, res.Mask)
		if err != nil {
			return nil, err
		}
	}

	err = finalMask.SetMask(aggMask)
	if err != nil {
		return nil, err
	}

	sig, err := finalSignature.MarshalBinary()
	if err != nil {
		return nil, err
	}

	return &Response{Signature: sig, Mask: finalMask.Mask()}, nil
}
