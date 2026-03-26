"""Test Soroban contract integration with backend."""
import asyncio
import time
from stellar_sdk import Keypair, Network, Server, TransactionBuilder
from stellar_sdk.soroban_rpc import SorobanServer
from src.config import Settings

config = Settings()

CONTRACT_ID = config.stellar_escrow_contract
USDC_TOKEN = config.stellar_usdc_token


async def test_deposit_and_listen():
    """Test making a deposit and listening for the event."""
    
    print("🧪 Testing Soroban Integration\n")
    print(f"Contract: {CONTRACT_ID}")
    print(f"USDC Token: {USDC_TOKEN}\n")
    
    # Step 1: Get latest ledger before deposit
    soroban_server = SorobanServer("https://soroban-testnet.stellar.org:443")
    
    try:
        latest_ledger_response = soroban_server.get_latest_ledger()
        start_ledger = latest_ledger_response.sequence
        print(f"📊 Starting from ledger: {start_ledger}\n")
    except Exception as e:
        print(f"❌ Error getting latest ledger: {e}")
        return
    
    # Step 2: Make a deposit using CLI (simulated - user would do this via extension)
    print("📝 To test, run this command in another terminal:\n")
    session_id = f"backend_test_{int(time.time())}"
    
    deposit_cmd = f"""
cd "/Users/rizwan/Documents/Projects/payzee/soroban-escrow"
soroban contract invoke \\
  --id {CONTRACT_ID} \\
  --source-account admin \\
  --network testnet \\
  --send=yes \\
  -- deposit \\
  --user GAKLIP2APDKAT24GGNCONRYG5TAMNVTAUUDBIYWPO62ZLCDUQ5E56QGI \\
  --amount 50000000 \\
  --session_id {session_id}
"""
    
    print(deposit_cmd)
    print(f"\n⏳ Waiting 30 seconds for you to run the deposit command...")
    print(f"Session ID to use: {session_id}\n")
    
    await asyncio.sleep(30)
    
    # Step 3: Poll for events
    print("\n🔍 Polling for PaymentReceived events...\n")
    
    try:
        # Get events from the start ledger
        events_response = soroban_server.get_events(
            start_ledger=start_ledger,
            filters=[{
                "type": "contract",
                "contractIds": [CONTRACT_ID],
            }],
            limit=10
        )
        
        print(f"📨 Found {len(events_response.events)} total events\n")
        
        payment_events = []
        for event in events_response.events:
            # Parse event topics
            if hasattr(event, 'value') and hasattr(event, 'topic'):
                topics = event.topic
                
                # Check if this is a payment_received event
                if topics and len(topics) > 0:
                    first_topic = topics[0]
                    if hasattr(first_topic, 'symbol') and first_topic.symbol == 'payment_received':
                        payment_events.append(event)
                        
                        print(f"✅ PaymentReceived Event Found!")
                        print(f"   Ledger: {event.ledger}")
                        print(f"   Contract: {event.contract_id}")
                        
                        # Parse event data
                        event_data = event.value
                        if hasattr(event_data, 'map'):
                            data_map = {item.key.symbol: item.val for item in event_data.map}
                            
                            user = data_map.get('user')
                            amount = data_map.get('amount')
                            event_session_id = data_map.get('session_id')
                            timestamp = data_map.get('timestamp')
                            
                            if user:
                                print(f"   User: {user.address if hasattr(user, 'address') else user}")
                            if amount:
                                amount_value = amount.i128 if hasattr(amount, 'i128') else amount
                                amount_usdc = amount_value / 10000000  # Convert to USDC
                                print(f"   Amount: {amount_value} stroops ({amount_usdc} USDC)")
                            if event_session_id:
                                sess_id = event_session_id.string if hasattr(event_session_id, 'string') else event_session_id
                                print(f"   Session ID: {sess_id}")
                            if timestamp:
                                ts = timestamp.u64 if hasattr(timestamp, 'u64') else timestamp
                                print(f"   Timestamp: {ts}")
                            
                            print("\n📋 Backend would now:")
                            print(f"   1. Create virtual card for {amount_usdc} USD")
                            print(f"   2. Apply 5% buffer → ${amount_usdc * 1.05:.2f} limit")
                            print(f"   3. Link card to session: {sess_id}")
                            print(f"   4. Store user address for refunds")
                            print()
        
        if not payment_events:
            print("⚠️  No PaymentReceived events found.")
            print("   Make sure you ran the deposit command above.\n")
        else:
            print(f"\n✅ Successfully detected {len(payment_events)} payment event(s)!")
            print("🎉 Backend integration test PASSED!\n")
            
    except Exception as e:
        print(f"❌ Error polling events: {e}\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_deposit_and_listen())
