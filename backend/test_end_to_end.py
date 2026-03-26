"""
End-to-End Integration Test
============================
Tests the complete flow:
1. User deposits USDC to Soroban contract
2. Backend detects PaymentReceived event
3. Backend creates virtual card via Lithic
4. Merchant payment simulation
"""
import time
import sys
from datetime import datetime
from stellar_sdk import SorobanServer, xdr, StrKey
from src.config import Settings
from src.lithic_client import lithic_client

config = Settings()

def print_step(step, message):
    """Print formatted step."""
    print(f"\n{'='*70}")
    print(f"STEP {step}: {message}")
    print('='*70)

def print_success(message):
    """Print success message."""
    print(f"✅ {message}")

def print_error(message):
    """Print error message."""
    print(f"❌ {message}")

def print_info(message):
    """Print info message."""
    print(f"ℹ️  {message}")

# Test parameters
SESSION_ID = f"e2e_test_{int(time.time())}"
DEPOSIT_AMOUNT = 5_000_000  # 0.5 USDC in stroops
CARD_LIMIT_CENTS = 50  # $0.50 limit

print("\n" + "="*70)
print("🧪 END-TO-END INTEGRATION TEST")
print("="*70)
print(f"Session ID: {SESSION_ID}")
print(f"Deposit Amount: {DEPOSIT_AMOUNT / 10_000_000} USDC")
print(f"Card Limit: ${CARD_LIMIT_CENTS / 100}")
print("="*70)

# ============================================================================
# STEP 1: Make Deposit to Soroban Contract
# ============================================================================
print_step(1, "DEPOSIT USDC TO SOROBAN CONTRACT")

print_info(f"Contract: {config.stellar_escrow_contract}")
print_info("Making deposit via Soroban CLI...")
print_info("(User should run deposit command manually or we can verify existing)")

# For this test, we'll assume the user has already made a deposit
# In production, this would be triggered by the frontend
input("\n⏸️  Press Enter after making a deposit with session_id: " + SESSION_ID)

# ============================================================================
# STEP 2: Detect Event from Soroban RPC
# ============================================================================
print_step(2, "BACKEND DETECTS PAYMENT EVENT")

server = SorobanServer(config.stellar_rpc_url)
contract_id = config.stellar_escrow_contract

print_info("Polling Soroban RPC for events...")

# Get recent events
ledger_resp = server.get_latest_ledger()
current_ledger = ledger_resp.sequence
start_ledger = current_ledger - 50  # Look back 50 ledgers

events_resp = server.get_events(
    start_ledger=start_ledger,
    filters=[{
        "type": "contract",
        "contractIds": [contract_id],
    }],
    limit=20
)

print_info(f"Found {len(events_resp.events)} total events")

# Find our payment event
payment_found = False
payment_data = None

for event in events_resp.events:
    if not event.topic or len(event.topic) == 0:
        continue
    
    # Decode topic
    topic_xdr = xdr.SCVal.from_xdr(event.topic[0])
    event_name = topic_xdr.sym.sc_symbol.decode()
    
    if event_name == "payment_received":
        # Decode value
        value_xdr = xdr.SCVal.from_xdr(event.value)
        data_map = {}
        for item in value_xdr.map.sc_map:
            key = item.key.sym.sc_symbol.decode()
            data_map[key] = item.val
        
        # Extract session_id
        session_id = data_map["session_id"].str.sc_string.decode()
        
        if session_id == SESSION_ID:
            # Extract all fields
            amount_hi = int(data_map["amount"].i128.hi.int64)
            amount_lo = int(data_map["amount"].i128.lo.uint64)
            amount = (amount_hi << 64) | amount_lo
            
            user_account = data_map["user"].address.account_id.account_id.ed25519.uint256
            user_address = StrKey.encode_ed25519_public_key(user_account)
            
            timestamp = int(data_map["timestamp"].u64.uint64)
            
            payment_data = {
                "session_id": session_id,
                "amount_stroops": amount,
                "amount_usdc": amount / 10_000_000,
                "user": user_address,
                "timestamp": timestamp,
                "ledger": event.ledger,
                "ledger_time": event.ledger_close_at
            }
            payment_found = True
            break

if payment_found:
    print_success(f"Payment event detected!")
    print(f"   Session: {payment_data['session_id']}")
    print(f"   Amount: {payment_data['amount_usdc']} USDC")
    print(f"   User: {payment_data['user'][:8]}...{payment_data['user'][-8:]}")
    print(f"   Ledger: {payment_data['ledger']}")
    print(f"   Time: {payment_data['ledger_time']}")
else:
    print_error(f"Payment event not found for session {SESSION_ID}")
    print_info("Make sure you deposited with the correct session_id")
    sys.exit(1)

# ============================================================================
# STEP 3: Create Virtual Card via Lithic
# ============================================================================
print_step(3, "CREATE VIRTUAL CARD VIA LITHIC")

print_info("Creating single-use virtual card...")

try:
    # Create card
    card = lithic_client.cards.create(
        type="SINGLE_USE",
        spend_limit=CARD_LIMIT_CENTS,
        spend_limit_duration="TRANSACTION",
        state="OPEN",
        memo=f"Session: {SESSION_ID}, USDC: {payment_data['amount_usdc']}"
    )
    
    print_success("Virtual card created!")
    print(f"   Card Token: {card.token}")
    print(f"   Last 4 Digits: {card.last_four}")
    print(f"   CVV: {card.cvv}")
    print(f"   Expiry: {card.exp_month}/{card.exp_year}")
    print(f"   State: {card.state}")
    print(f"   Spend Limit: ${CARD_LIMIT_CENTS / 100}")
    print(f"   Created: {card.created}")
    
    card_data = {
        "token": card.token,
        "pan": card.pan,
        "cvv": card.cvv,
        "exp_month": card.exp_month,
        "exp_year": card.exp_year,
        "last_four": card.last_four,
        "state": card.state,
        "spend_limit": CARD_LIMIT_CENTS
    }
    
except Exception as e:
    print_error(f"Card creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# STEP 4: Verify Card Details
# ============================================================================
print_step(4, "VERIFY CARD DETAILS")

print_info("Retrieving card details from Lithic...")

try:
    # Get card details
    card_details = lithic_client.cards.retrieve(card.token)
    
    print_success("Card verified!")
    print(f"   PAN: {card_details.pan[:4]}...{card_details.pan[-4:]}")
    print(f"   CVV: {card_details.cvv}")
    print(f"   State: {card_details.state}")
    print(f"   Available Spend: ${card_details.spend_limit / 100}")
    
except Exception as e:
    print_error(f"Card verification failed: {e}")
    sys.exit(1)

# ============================================================================
# STEP 5: Display Full Card for Merchant Payment
# ============================================================================
print_step(5, "CARD READY FOR MERCHANT PAYMENT")

print("\n" + "="*70)
print("💳 VIRTUAL CARD DETAILS")
print("="*70)
print(f"Card Number:  {card_data['pan']}")
print(f"CVV:          {card_data['cvv']}")
print(f"Expiry:       {card_data['exp_month']:02d}/{card_data['exp_year']}")
print(f"Limit:        ${card_data['spend_limit'] / 100}")
print("="*70)
print("\nℹ️  Use these details to make a test payment to a merchant")
print("ℹ️  The card is SINGLE_USE and will close after first transaction")

# ============================================================================
# STEP 6: Monitor for Transaction
# ============================================================================
print_step(6, "MONITOR FOR TRANSACTION")

print_info("Waiting for merchant transaction...")
print_info("Make a payment using the card details above")
print_info("(Or skip this step with Ctrl+C)")

try:
    # Poll for transactions
    for i in range(30):  # Poll for 30 seconds
        time.sleep(1)
        
        # Get card transactions
        transactions = lithic_client.transactions.list(
            card_token=card.token,
            page_size=10
        )
        
        if len(transactions.data) > 0:
            print_success("Transaction detected!")
            
            for txn in transactions.data:
                print(f"\n   Transaction: {txn.token}")
                print(f"   Amount: ${txn.amount / 100}")
                print(f"   Merchant: {txn.merchant.descriptor}")
                print(f"   Status: {txn.status}")
                print(f"   Result: {txn.result}")
                print(f"   Created: {txn.created}")
            
            break
        
        if i % 5 == 0:
            print(f"   Waiting... ({i}s elapsed)")
    
    else:
        print_info("No transaction detected within 30 seconds")
        print_info("You can still use the card details to make a payment")

except KeyboardInterrupt:
    print_info("\nSkipping transaction monitoring")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*70)
print("📊 END-TO-END TEST SUMMARY")
print("="*70)
print_success(f"Payment Detected: {payment_data['amount_usdc']} USDC")
print_success(f"Card Created: {card_data['last_four']}")
print_success(f"Card Limit: ${card_data['spend_limit'] / 100}")
print_success("Integration: Soroban → Backend → Lithic ✅")
print("="*70)

print("\n🎉 END-TO-END TEST COMPLETE!")
print("\nNEXT STEPS:")
print("1. Use the card details to make a test merchant payment")
print("2. Verify transaction appears in Lithic dashboard")
print("3. Check that card state changes to CLOSED after use")
print("4. Test the claim() function to return USDC to admin")
print("="*70 + "\n")
