"""
Test script to simulate the complete Buffer & Refund flow.

This demonstrates:
1. Creating a card with user's Stellar address
2. Simulating a webhook from Lithic
3. Calculating and logging refund details

Note: Actual Stellar refund will fail without:
- Platform secret key configured
- Platform account funded with USDC
- User account existing on Stellar network
"""
import requests
import json

API_URL = "http://127.0.0.1:8000"
API_KEY = "sk_stellar_pay_dev_b03352ef1d68164c675023b82538ea3d1d1902f69bc408b7"

# Test user's Stellar address (generated for testing)
TEST_USER_STELLAR_ADDRESS = "GBVUGAQ44K3JNIUE4ARPFQP26V7L2YU24XLZ543G2UTF4D24TWMB4FMV"

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def create_test_card():
    """Step 1: Create a card with user's Stellar address"""
    print_section("STEP 1: Create Card with 5% Buffer")
    
    payload = {
        "stellar_transaction_id": "WEBHOOK_TEST_001",
        "user_stellar_address": TEST_USER_STELLAR_ADDRESS,
        "amount_cents": 10000,  # $100.00
        "merchant_name": "Amazon"
    }
    
    response = requests.post(
        f"{API_URL}/api/v1/cards/create",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        },
        json=payload
    )
    
    card = response.json()
    
    print(f"Card Created:")
    print(f"  ID: {card['id']}")
    print(f"  Stellar TX: {card['stellar_transaction_id']}")
    print(f"  User Address: {TEST_USER_STELLAR_ADDRESS[:10]}...{TEST_USER_STELLAR_ADDRESS[-6:]}")
    print(f"  Amount: ${card['amount_cents']/100:.2f}")
    print(f"  Spend Limit: ${card['spend_limit_cents']/100:.2f} (5% buffer)")
    print(f"  Buffer: ${(card['spend_limit_cents'] - card['amount_cents'])/100:.2f}")
    print(f"\nCard Details:")
    print(f"  Token: {card['card']['token']}")
    print(f"  Last 4: {card['card']['last_four']}")
    print(f"  State: {card['card']['state']}")
    
    return card

def simulate_webhook(card_token, actual_charge_cents):
    """Step 2: Simulate Lithic webhook for transaction.settled"""
    print_section("STEP 2: Simulate Lithic Webhook")
    
    webhook_payload = {
        "event_type": "transaction.settled",
        "card_token": card_token,
        "amount": actual_charge_cents,  # Actual merchant charge
        "token": "tx_webhook_test_001"
    }
    
    print(f"Webhook Event:")
    print(f"  Event: transaction.settled")
    print(f"  Card Token: {card_token}")
    print(f"  Merchant Charged: ${actual_charge_cents/100:.2f}")
    print(f"\nNOTE: Webhook signature verification will be skipped (no LITHIC_WEBHOOK_SECRET)")
    
    response = requests.post(
        f"{API_URL}/webhooks/lithic",
        headers={"Content-Type": "application/json"},
        json=webhook_payload
    )
    
    result = response.json()
    
    print(f"\nWebhook Response:")
    print(json.dumps(result, indent=2))
    
    return result

def get_card_details(card_id):
    """Step 3: Check final card state"""
    print_section("STEP 3: Verify Card State")
    
    response = requests.get(
        f"{API_URL}/api/v1/cards/{card_id}",
        headers={"X-API-Key": API_KEY}
    )
    
    card = response.json()
    
    print(f"Final Card State:")
    print(f"  Original Amount: ${card['amount_cents']/100:.2f}")
    print(f"  Spend Limit: ${card['spend_limit_cents']/100:.2f}")
    print(f"  Card Token: {card['card']['token']}")
    
    return card

def run_scenario(scenario_name, amount_cents, actual_charge_cents):
    """Run a complete test scenario"""
    print(f"\n\n{'#'*60}")
    print(f"# SCENARIO: {scenario_name}")
    print(f"{'#'*60}")
    
    # Create card
    card = create_test_card()
    
    # Simulate webhook
    result = simulate_webhook(card['card']['token'], actual_charge_cents)
    
    # Get final state
    final_card = get_card_details(card['id'])
    
    # Summary
    print_section("SUMMARY")
    spend_limit = card['spend_limit_cents']
    refund = spend_limit - actual_charge_cents
    
    print(f"Scenario: {scenario_name}")
    print(f"  User authorized: {spend_limit/100:.2f} USDC")
    print(f"  Merchant charged: ${actual_charge_cents/100:.2f}")
    print(f"  Unused buffer: ${refund/100:.2f}")
    print(f"  Refund status: {result.get('status', 'unknown')}")
    
    if refund > 0:
        print(f"\n✅ SUCCESS: ${refund/100:.2f} should be refunded to user")
    elif refund == 0:
        print(f"\n✅ EXACT MATCH: No refund needed")
    else:
        print(f"\n❌ OVER LIMIT: Would have been declined")
    
    return card, result

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  BUFFER & REFUND FLOW TEST")
    print("="*60)
    
    # Scenario 1: Merchant charges less than limit (typical)
    run_scenario(
        "Typical E-Commerce Purchase",
        amount_cents=10000,     # $100 item
        actual_charge_cents=10240  # $102.40 (with tax)
    )
    
    print("\n\n" + "="*60)
    print("NOTE: Stellar refund will fail without:")
    print("  - STELLAR_PLATFORM_SECRET configured in .env")
    print("  - Platform account funded with USDC")
    print("  - User account existing on Stellar network")
    print("="*60)
