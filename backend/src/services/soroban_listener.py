"""
Soroban Event Listener Service

Polls the Stellar Soroban RPC for PaymentReceived events from the escrow contract.
When a payment is detected, it triggers card creation via the Lithic API.
"""
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime

from stellar_sdk import SorobanServer, scval, xdr
from .config import settings

logger = logging.getLogger(__name__)


class SorobanEventListener:
    """Listens for Soroban contract events and processes payments."""
    
    def __init__(self):
        self.server = SorobanServer(settings.stellar_rpc_url)
        self.contract_id = settings.stellar_escrow_contract
        self.last_processed_ledger = None
        self.is_running = False
        
    async def start(self):
        """Start the event listener loop."""
        logger.info(f"Starting Soroban event listener for contract {self.contract_id}")
        self.is_running = True
        
        # Get starting ledger
        ledger_resp = await asyncio.to_thread(self.server.get_latest_ledger)
        self.last_processed_ledger = ledger_resp.sequence
        logger.info(f"Starting from ledger {self.last_processed_ledger}")
        
        while self.is_running:
            try:
                await self._poll_events()
                await asyncio.sleep(5)  # Poll every 5 seconds
            except Exception as e:
                logger.error(f"Error polling events: {e}", exc_info=True)
                await asyncio.sleep(10)  # Back off on error
    
    async def stop(self):
        """Stop the event listener."""
        logger.info("Stopping Soroban event listener")
        self.is_running = False
    
    async def _poll_events(self):
        """Poll for new events since last processed ledger."""
        # Get current ledger
        ledger_resp = await asyncio.to_thread(self.server.get_latest_ledger)
        current_ledger = ledger_resp.sequence
        
        if current_ledger <= self.last_processed_ledger:
            return  # No new ledgers
        
        # Get events from last processed to current
        events_resp = await asyncio.to_thread(
            self.server.get_events,
            start_ledger=self.last_processed_ledger + 1,
            filters=[{
                "type": "contract",
                "contractIds": [self.contract_id],
            }],
            limit=100
        )
        
        logger.info(f"Polled ledgers {self.last_processed_ledger + 1} to {current_ledger}, found {len(events_resp.events)} events")
        
        for event in events_resp.events:
            await self._process_event(event)
        
        self.last_processed_ledger = current_ledger
    
    async def _process_event(self, event):
        """Process a single Soroban event."""
        try:
            # Decode topic to get event name
            if not event.topic or len(event.topic) == 0:
                return
            
            topic_xdr = xdr.SCVal.from_xdr(event.topic[0])
            event_name = scval.to_symbol(topic_xdr)
            
            if event_name == "payment_received":
                await self._handle_payment_received(event)
            elif event_name == "payment_claimed":
                logger.info(f"Payment claimed event on ledger {event.ledger}")
        
        except Exception as e:
            logger.error(f"Error processing event: {e}", exc_info=True)
    
    async def _handle_payment_received(self, event):
        """Handle a payment_received event by creating a virtual card."""
        try:
            # Decode event value
            value_xdr = xdr.SCVal.from_xdr(event.value)
            value_map = scval.to_map(value_xdr)
            
            # Extract payment details
            amount_stroops = value_map.get("amount", 0)
            session_id = value_map.get("session_id", "")
            user_address = value_map.get("user", "")
            timestamp = value_map.get("timestamp", 0)
            
            amount_usdc = amount_stroops / 10_000_000  # Convert from stroops
            
            logger.info(
                f"Payment received: {amount_usdc} USDC from {user_address[:8]}... "
                f"(session: {session_id}, ledger: {event.ledger})"
            )
            
            # Create virtual card with Lithic
            card_data = await self._create_virtual_card(
                amount_usdc=amount_usdc,
                session_id=session_id,
                user_address=user_address,
                stellar_ledger=event.ledger
            )
            
            logger.info(f"Created card {card_data['token']} for session {session_id}")
        
        except Exception as e:
            logger.error(f"Error handling payment_received: {e}", exc_info=True)
    
    async def _create_virtual_card(
        self,
        amount_usdc: float,
        session_id: str,
        user_address: str,
        stellar_ledger: int
    ) -> Dict:
        """
        Create a virtual card via Lithic API.
        
        Returns the created card data including token.
        """
        from .lithic_client import lithic_client
        
        # Create card with Lithic
        card = await asyncio.to_thread(
            lithic_client.cards.create,
            type="SINGLE_USE",
            spend_limit=int(amount_usdc * 100),  # Convert to cents
            spend_limit_duration="TRANSACTION",
            state="OPEN",
            memo=f"Session: {session_id}, Ledger: {stellar_ledger}"
        )
        
        #TODO: Store card details in database
        # - session_id
        # - user_address
        # - card_token
        # - amount_usdc
        # - stellar_ledger
        # - created_at
        # - status
        
        return {
            "token": card.token,
            "last_four": card.last_four,
            "created": card.created,
            "state": card.state,
            "session_id": session_id,
            "amount_usdc": amount_usdc
        }


# Global instance
event_listener = SorobanEventListener()


async def start_event_listener():
    """Start the global event listener."""
    await event_listener.start()


async def stop_event_listener():
    """Stop the global event listener."""
    await event_listener.stop()
