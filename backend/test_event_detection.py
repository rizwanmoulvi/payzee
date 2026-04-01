"""Quick test: Make a deposit and check if backend can read the event."""
import time
from stellar_sdk import SorobanServer, scval, xdr
from src.config import Settings

config = Settings()

CONTRACT_ID = config.stellar_escrow_contract
print(f"\n🧪 Testing Soroban Event Detection\n")
print(f"Contract: {CONTRACT_ID}\n")

# Get current ledger
soroban_server = SorobanServer("https://soroban-testnet.stellar.org:443")

def decode_xdr_value(xdr_str):
    """Decode XDR encoded SCVal."""
    try:
        sc_val = xdr.SCVal.from_xdr(xdr_str)
        return sc_val
    except Exception as e:
        print(f"Error decoding XDR: {e}")
        return None

try:
    latest_ledger_response = soroban_server.get_latest_ledger()
    current_ledger = latest_ledger_response.sequence
    print(f"Current ledger: {current_ledger}")
    
    # Look back 100 ledgers for recent events
    start_ledger = current_ledger - 100
    
    print(f"Searching from ledger {start_ledger} to {current_ledger}...\n")
    
    # Get events
    events_response = soroban_server.get_events(
        start_ledger=start_ledger,
        filters=[{
            "type": "contract",
            "contractIds": [CONTRACT_ID],
        }],
        limit=20
    )
    
    print(f"📨 Found {len(events_response.events)} events\n")
    
    payment_count = 0
    claim_count = 0
    
    for event in events_response.events:
        # Decode topic to check event name
        if event.topic and len(event.topic) > 0:
            topic_val = decode_xdr_value(event.topic[0])
            
            if topic_val and hasattr(topic_val, 'sym'):
                # SCSymbol has sc_symbol attribute which is bytes
                event_name = topic_val.sym.sc_symbol.decode() if hasattr(topic_val.sym, 'sc_symbol') else str(topic_val.sym)
                
                if event_name == 'payment_received':
                    payment_count += 1
                    print(f"✅ PaymentReceived Event #{payment_count}")
                    print(f"   Ledger: {event.ledger}")
                    print(f"   Time: {event.ledger_close_at}")
                    
                    # Decode the value
                    value_decoded = decode_xdr_value(event.value)
                    
                    if value_decoded and hasattr(value_decoded, 'map'):
                        data_map = {}
                        for item in value_decoded.map.sc_map:
                            key_sym = item.key.sym.sc_symbol.decode()
                            data_map[key_sym] = item.val
                        
                        if 'amount' in data_map:
                            # Use scval helper to convert
                            amount = scval.to_int128(data_map['amount'])
                            amount_usdc = amount / 10000000
                            print(f"   Amount: {amount_usdc} USDC")
                        
                        if 'session_id' in data_map:
                            session_id = scval.to_string(data_map['session_id'])
                            print(f"   Session: {session_id}")
                        
                        if 'user' in data_map:
                            user = scval.to_address(data_map['user'])
                            print(f"   User: {user[:8]}...{user[-8:]}")
                    
                    print()
                
                elif event_name == 'payment_claimed':
                    claim_count += 1
                    print(f"💰 PaymentClaimed Event #{claim_count}")
                    print(f"   Ledger: {event.ledger}")
                    print()
    
    print(f"\n📊 Summary:")
    print(f"   Payment events: {payment_count}")
    print(f"   Claim events: {claim_count}")
    
    if payment_count > 0:
        print(f"\n✅ Backend can successfully read Soroban events!")
        print(f"🎉 Integration test PASSED!\n")
    else:
        print(f"\n⚠️  No recent payment events found.")
        print(f"   Try making a deposit to test event detection.\n")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
