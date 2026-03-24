#!/bin/bash

# Test deposit to payzee Escrow Contract

set -e

# Load deployment info
if [ ! -f deployment.json ]; then
    echo "❌ deployment.json not found. Run ./deploy.sh first."
    exit 1
fi

CONTRACT_ID=$(jq -r '.contract_id' deployment.json)
USDC_TOKEN=$(jq -r '.usdc_token' deployment.json)

# Test user credentials (in production, this would be the end user)
USER_SECRET="SAA4UD4Z24NT2VMJ2RYKHANVOCQYGWFG7F2EHB647754WR53JRVFJDCB"
USER_ADDRESS="GAKLIP2APDKAT24GGNCONRYG5TAMNVTAUUDBIYWPO62ZLCDUQ5E56QGI"

# Test parameters
AMOUNT=10000000  # 100 USDC (7 decimals)
SESSION_ID="test_session_$(date +%s)"

echo "🧪 Testing payzee Escrow Contract"
echo ""
echo "📋 Test Configuration:"
echo "  Contract: $CONTRACT_ID"
echo "  USDC Token: $USDC_TOKEN"
echo "  User: $USER_ADDRESS"
echo "  Amount: $AMOUNT (100 USDC)"
echo "  Session ID: $SESSION_ID"
echo ""

# Step 1: Check user's USDC balance
echo "💰 Checking user's USDC balance..."
BALANCE=$(soroban contract invoke \
  --id "$USDC_TOKEN" \
  --network testnet \
  -- balance \
  --id "$USER_ADDRESS" || echo "0")

echo "  Current balance: $BALANCE"
echo ""

# Step 2: If balance is 0, try to mint some test USDC (if admin)
if [ "$BALANCE" == "0" ]; then
    echo "⚠️  User has no USDC. Attempting to mint test tokens..."
    
    # Try to mint (will fail if not admin, which is expected)
    soroban contract invoke \
      --id "$USDC_TOKEN" \
      --network testnet \
      --source "$USER_SECRET" \
      -- mint \
      --to "$USER_ADDRESS" \
      --amount 100000000 || echo "  (Minting failed - expected if not token admin)"
    
    echo ""
fi

# Step 3: Approve contract to spend USDC
echo "✅ Approving contract to spend USDC..."
soroban contract invoke \
  --id "$USDC_TOKEN" \
  --network testnet \
  --source "$USER_SECRET" \
  -- approve \
  --from "$USER_ADDRESS" \
  --spender "$CONTRACT_ID" \
  --amount "$AMOUNT" \
  --expiration_ledger 999999

echo "✅ Approval granted"
echo ""

# Step 4: Make deposit
echo "💳 Making deposit..."
soroban contract invoke \
  --id "$CONTRACT_ID" \
  --network testnet \
  --source "$USER_SECRET" \
  -- deposit \
  --user "$USER_ADDRESS" \
  --amount "$AMOUNT" \
  --session_id "$SESSION_ID"

echo "✅ Deposit successful!"
echo ""

# Step 5: Verify deposit
echo "🔍 Verifying deposit..."
DEPOSIT=$(soroban contract invoke \
  --id "$CONTRACT_ID" \
  --network testnet \
  -- get_deposit \
  --session_id "$SESSION_ID")

echo "✅ Deposit verified!"
echo "$DEPOSIT"
echo ""

# Step 6: Check all deposits
echo "📊 All deposits:"
ALL_DEPOSITS=$(soroban contract invoke \
  --id "$CONTRACT_ID" \
  --network testnet \
  -- get_all_deposits)

echo "$ALL_DEPOSITS"
echo ""

echo "🎉 Test complete!"
echo ""
echo "Next steps:"
echo "1. Check backend logs for payment_received event"
echo "2. Verify virtual card was created"
echo "3. Test claim: ./scripts/test-claim.sh $SESSION_ID"
