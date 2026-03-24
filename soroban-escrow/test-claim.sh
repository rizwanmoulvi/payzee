#!/bin/bash

# Test claim from payzee Escrow Contract

set -e

if [ -z "$1" ]; then
    echo "Usage: ./test-claim.sh <session_id>"
    exit 1
fi

SESSION_ID="$1"

# Load deployment info
if [ ! -f deployment.json ]; then
    echo "❌ deployment.json not found. Run ./deploy.sh first."
    exit 1
fi

CONTRACT_ID=$(jq -r '.contract_id' deployment.json)
ADMIN_SECRET="SAA4UD4Z24NT2VMJ2RYKHANVOCQYGWFG7F2EHB647754WR53JRVFJDCB"
ADMIN_ADDRESS="GAKLIP2APDKAT24GGNCONRYG5TAMNVTAUUDBIYWPO62ZLCDUQ5E56QGI"

echo "🧪 Testing Claim for Session: $SESSION_ID"
echo ""

# Step 1: Get deposit details
echo "📋 Getting deposit details..."
DEPOSIT=$(soroban contract invoke \
  --id "$CONTRACT_ID" \
  --network testnet \
  -- get_deposit \
  --session_id "$SESSION_ID")

echo "$DEPOSIT"
echo ""

# Step 2: Make claim
echo "💰 Claiming USDC..."
soroban contract invoke \
  --id "$CONTRACT_ID" \
  --network testnet \
  --source "$ADMIN_SECRET" \
  -- claim \
  --session_id "$SESSION_ID"

echo "✅ Claim successful!"
echo ""

# Step 3: Verify claim
echo "🔍 Verifying claim..."
UPDATED_DEPOSIT=$(soroban contract invoke \
  --id "$CONTRACT_ID" \
  --network testnet \
  -- get_deposit \
  --session_id "$SESSION_ID")

echo "$UPDATED_DEPOSIT"
echo ""

echo "🎉 Claim test complete!"
