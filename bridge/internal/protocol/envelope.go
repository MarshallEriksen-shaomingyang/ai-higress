package protocol

import (
	"encoding/json"
	"errors"
	"strings"
)

type Envelope struct {
	V             int             `json:"v"`
	Type          string          `json:"type"`
	AgentID       string          `json:"agent_id,omitempty"`
	ReqID         string          `json:"req_id,omitempty"`
	ConnSessionID string          `json:"conn_session_id,omitempty"`
	Seq           int64           `json:"seq,omitempty"`
	Ts            int64           `json:"ts,omitempty"`
	Payload       json.RawMessage `json:"payload,omitempty"`
}

func (e Envelope) ValidateBasic() error {
	if e.V <= 0 {
		return errors.New("invalid envelope: v must be > 0")
	}
	if strings.TrimSpace(e.Type) == "" {
		return errors.New("invalid envelope: type is required")
	}
	return nil
}

func DecodeEnvelope(data []byte) (*Envelope, error) {
	var env Envelope
	if err := json.Unmarshal(data, &env); err != nil {
		return nil, err
	}
	if err := env.ValidateBasic(); err != nil {
		return nil, err
	}
	return &env, nil
}

func EncodeEnvelope(env Envelope) ([]byte, error) {
	if err := env.ValidateBasic(); err != nil {
		return nil, err
	}
	return json.Marshal(env)
}
