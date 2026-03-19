#!/bin/bash

# Deploy payzee Escrow Contract to Testnet

set -e

echo "🚀 Deploying Payzee Escrow Contract to Testnet..."
echo ""

# Configuration
NETWORK="testnet"
ADMIN_SECRET="SAA4UD4Z24NT2VMJ2RYKHANVOCQYGWFG7F2EHB647754WR53JRVFJDCB"
ADMIN_ADDRESS="GAKLIP2APDKAT24GGNCONRYG5TAMNVTAUUDBIYWPO62ZLCDUQ5E56QGI"

# Testnet USDC issuer (Circle)
USDC_ISSUER="GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5"
USDC_CODE="USDC"

echo "📋 Configuration:"
echo "  Network: $NETWORK"
echo "  Admin: $ADMIN_ADDRESS"
echo "  USDC Issuer: $USDC_ISSUER"
echo ""

# Step 1: Build contract
echo "🔨 Building contract..."
soroban contract build
echo "✅ Contract built successfully"
echo ""

# Step 2: Deploy contract
echo "🌐 Deploying contract..."
CONTRACT_ID=$(soroban contract deploy \
  --wasm target/wasm32-unknown-unknown/release/soroban_escrow.wasm \
  --source "$ADMIN_SECRET" \
  --network "$NETWORK")

echo "✅ Contract deployed!"
echo "  Contract ID: $CONTRACT_ID"
echo ""

# Step 3: Wrap USDC asset as Stellar Asset Contract
echo "🔄 Wrapping USDC asset as contract..."
USDC_TOKEN=$(soroban lab token wrap \
  --asset "$USDC_CODE:$USDC_ISSUER" \
  --network "$NETWORK" \
  --source "$ADMIN_SECRET")

echo "✅ USDC token wrapped!"
echo "  Token Contract: $USDC_TOKEN"
echo ""

# Step 4: Initialize contract
echo "⚙️  Initializing contract..."
soroban contract invoke \
  --id "$CONTRACT_ID" \
  --source "$ADMIN_SECRET" \
  --network "$NETWORK" \
  -- initialize \
  --admin "$ADMIN_ADDRESS" \
  --usdc_token "$USDC_TOKEN"

echo "✅ Contract initialized!"
echo ""

# Step 5: Verify initialization
echo "🔍 Verifying deployment..."
STORED_ADMIN=$(soroban contract invoke \
  --id "$CONTRACT_ID" \
  --network "$NETWORK" \
  -- get_admin)

STORED_USDC=$(soroban contract invoke \
  --id "$CONTRACT_ID" \
  --network "$NETWORK" \
  -- get_usdc_token)

echo "✅ Verification complete!"
echo "  Stored Admin: $STORED_ADMIN"
echo "  Stored USDC Token: $STORED_USDC"
echo ""

# Save deployment info
echo "💾 Saving deployment info..."
cat > deployment.json <<EOF
{
  "network": "$NETWORK",
  "contract_id": "$CONTRACT_ID",
  "admin_address": "$ADMIN_ADDRESS",
  "usdc_token": "$USDC_TOKEN",
  "usdc_issuer": "$USDC_ISSUER",
  "deployed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "✅ Deployment info saved to deployment.json"
echo ""

echo "🎉 Deployment complete!"
echo ""
echo "📝 Next steps:"
echo "1. Add CONTRACT_ID to backend .env: STELLAR_ESCROW_CONTRACT=$CONTRACT_ID"
echo "2. Add USDC_TOKEN to backend .env: STELLAR_USDC_TOKEN=$USDC_TOKEN"
echo "3. Update backend to listen for payment_received events"
echo "4. Test deposit: ./scripts/test-deposit.sh"
echo ""
echo "Contract ID: $CONTRACT_ID"
