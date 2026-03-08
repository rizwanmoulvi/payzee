"""Simple event detection test."""
from stellar_sdk import SorobanServer, scval, xdr

server = SorobanServer("https://soroban-testnet.stellar.org:443")
contract = "CCF2PJC3K4U6QMY6CBIN4QPVXOI6UPKDJA57RTPXWS2O5CQX3CGGKXTY"

# Get current ledger
ledger_resp = server.get_latest_ledger()
current = ledger_resp.sequence
start = current - 100

# Get events
events = server.get_events(
    start_ledger=start,
    filters=[{"type": "contract", "contractIds": [contract]}],
    limit=10
)

print(f"Found {len(events.events)} events\n")

for event in events.events:
    # Parse topic
    topic_xdr = xdr.SCVal.from_xdr(event.topic[0])
    event_name = topic_xdr.sym.sc_symbol.decode()  # Read the symbol bytes
    
    if event_name == "payment_received":
        print("✅ Payment Received!")
        print(f"   Ledger: {event.ledger}")
        print(f"   Time: {event.ledger_close_at}")
        
        # Parse value
        value_xdr = xdr.SCVal.from_xdr(event.value)
        data_map = {}
        for item in value_xdr.map.sc_map:
            key = item.key.sym.sc_symbol.decode()
            data_map[key] = item.val
        
        # Extract values from SCVal objects
        amount_hi = int(data_map["amount"].i128.hi.int64)
        amount_lo = int(data_map["amount"].i128.lo.uint64)
        amount = (amount_hi << 64) | amount_lo  # Combine hi and lo parts
        
        session_id = data_map["session_id"].str.sc_string.decode()
        user_account = data_map["user"].address.account_id.account_id.ed25519.uint256
        
        from stellar_sdk import StrKey
        user = StrKey.encode_ed25519_public_key(user_account)
        
        print(f"   Amount: {amount / 10000000} USDC")
        print(f"   Session: {session_id}")
        print(f"   User: {user[:8]}...{user[-8:]}")
        print()
