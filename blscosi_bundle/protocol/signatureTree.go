package protocol

import (
	"strconv"
	"strings"

	"go.dedis.ch/onet/v3/log"
)

func updateResponsesTree(responses, newResponses ResponseMap, nodes int) {
	tree := make(map[int](map[string][]string))
	var maxLevel int
	for level := 1; ; level++ {
		levelTree := make(map[string][]string)
		size := 1 << uint(level)
		for i := 0; i*size < nodes; i++ {
			if i+size/2 >= nodes {
				continue
			}
			var nodesList []string
			for j := 0; j < i+size && j < nodes; j++ {
				nodesList = append(nodesList, strconv.Itoa(j))
			}
			left := strings.Join(nodesList[:size/2], "$")
			right := strings.Join(nodesList[size/2:], "$")
			total := left + "$" + right
			levelTree[total] = []string{left, right}
		}
		tree[level] = levelTree
		if size >= nodes {
			maxLevel = level
			break
		}
	}

	log.Lvlf1("making tree %v", tree)

	for key, response := range newResponses {
		responses[key] = response
	}
	for level := 1; level <= maxLevel; level++ {
		for key, parts := range tree[level] {
			left, ok := responses[parts[0]]
			if !ok {
				continue
			}
			right, ok := responses[parts[1]]
			if !ok {
				continue
			}
			delete(responses, parts[0])
			delete(responses, parts[1])
			responses[key] = left
			responses[key] = right
		}
	}
}
