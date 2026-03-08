"""Lithic API service wrapper for card creation and transaction simulation."""
from typing import Any, Dict, Optional

import requests
from lithic import Lithic

from ..config import settings


class LithicService:
    """
    Service wrapper for Lithic card operations.
    
    Provides methods for:
    - Creating virtual cards (SINGLE_USE or MERCHANT_LOCKED)
    - Simulating authorization transactions
    - Simulating clearing/settlement
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> None:
        """
        Initialize Lithic service.
        
        Args:
            api_key: Lithic API key (defaults to settings)
            environment: 'sandbox' or 'production' (defaults to settings)
        """
        self.api_key = api_key or settings.lithic_api_key
        self.environment = environment or settings.lithic_environment
        
        # Allow initialization without API key for testing/development
        # Actual API calls will fail if not configured
        self.client = None
        if self.api_key:
            self.client = Lithic(
                api_key=self.api_key,
                environment=self.environment,
            )

    def create_virtual_card(
        self,
        memo: Optional[str] = None,
        card_type: str = "SINGLE_USE",
        spend_limit_cents: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a SINGLE_USE card in Lithic with spend limit (Buffer & Refund strategy).
        
        SINGLE_USE cards are closed upon first successful authorization and can 
        only be used once. After the first transaction, additional purchases will 
        be declined, but the card will remain available to process refunds.
        
        Production Strategy:
        - Set spend_limit 5% higher than requested amount
        - Prevents failures from tax, shipping, fees added at checkout
        - Unused buffer is "trapped" in closed card after first charge
        - Backend webhook handler refunds unused buffer to Stellar wallet
        
        Args:
            memo: Optional memo to attach to the card (e.g., Stellar tx ID)
            card_type: Card type - SINGLE_USE (default) or MERCHANT_LOCKED
            spend_limit_cents: Maximum amount in cents that can be charged to this card.
                             Should include 5% buffer (e.g., $100 item → $105 limit)
            
        Returns:
            Dictionary with card details including:
            - token: Lithic card token
            - last_four: Last 4 digits
            - exp_month: Expiration month
            - exp_year: Expiration year
            - state: Card state (OPEN, CLOSED, etc.)
            - pan: Full card number (sandbox only)
            - cvv: CVV code (sandbox only)
        """
        if not self.client:
            raise ValueError("Lithic API key not configured")
        
        # Build card creation parameters
        create_params = {
            "type": "SINGLE_USE",
            "memo": memo or "payzee Single-Use Card",
        }
        
        # Add spend limit if specified
        if spend_limit_cents is not None:
            create_params["spend_limit"] = spend_limit_cents
            create_params["spend_limit_duration"] = "TRANSACTION"  # Limit applies per transaction
        
        card = self.client.cards.create(**create_params)
        
        # Convert Lithic response to dict
        return {
            "token": getattr(card, "token", None),
            "last_four": getattr(card, "last_four", None),
            "exp_month": getattr(card, "exp_month", None),
            "exp_year": getattr(card, "exp_year", None),
            "state": getattr(card, "state", None),
            # Sandbox provides these for testing
            "pan": getattr(card, "pan", None),
            "cvv": getattr(card, "cvv", None),
        }

    def simulate_authorization(
        self,
        pan: str,
        amount_cents: int,
        descriptor: str,
        mcc: str = "5999",
        merchant_currency: str = "USD",
    ) -> Dict[str, Any]:
        """
        Simulate a card authorization transaction.
        
        Args:
            pan: Card primary account number (full card number)
            amount_cents: Amount in minor currency units (cents)
            descriptor: Merchant descriptor (name shown on statement)
            mcc: Merchant Category Code (default: 5999 - Miscellaneous)
            merchant_currency: Currency code (default: USD)
            
        Returns:
            Dictionary with:
        if not self.client:
            raise ValueError("Lithic API key not configured")
        
            - token: Transaction token
            - debugging_request_id: Debug ID for tracking
        """
        transaction = self.client.transactions.simulate_authorization(
            pan=pan,
            amount=amount_cents,
            merchant_amount=amount_cents,
            descriptor=descriptor,
            mcc=mcc,
            merchant_currency=merchant_currency,
        )
        
        return {
            "token": getattr(transaction, "token", None),
            "debugging_request_id": getattr(transaction, "debugging_request_id", None),
        }

    def simulate_clearing(
        self,
        transaction_token: str,
        amount_cents: int,
    ) -> Dict[str, Any]:
        """
        Simulate transaction clearing/settlement.
        
        Args:
            transaction_token: Authorization transaction token
            amount_cents: Amount to clear in cents
            
        Returns:
            Dictionary with:
            - debugging_request_id: Debug ID for tracking
            - Other clearing details
        """
        if not self.client:
            raise ValueError("Lithic API key not configured")
        
        # Use the SDK's simulate clearing method
        clearing = self.client.transactions.simulate_clearing(
            token=transaction_token,
            amount=amount_cents,
        )
        
        return {
            "debugging_request_id": getattr(clearing, "debugging_request_id", None),
            "status": "CLEARED"
        }

    def get_card(self, card_token: str) -> Dict[str, Any]:
        """
        Retrieve card details from Lithic.
        
        if not self.client:
            raise ValueError("Lithic API key not configured")
        
        Args:
            card_token: Lithic card token
            
        Returns:
            Dictionary with current card details
        """
        card = self.client.cards.retrieve(card_token)
        
        return {
            "token": getattr(card, "token", None),
            "last_four": getattr(card, "last_four", None),
            "exp_month": getattr(card, "exp_month", None),
            "exp_year": getattr(card, "exp_year", None),
            "state": getattr(card, "state", None),
            "type": getattr(card, "type", None),
            "memo": getattr(card, "memo", None),
        }


# Global service instance
lithic_service = LithicService()
