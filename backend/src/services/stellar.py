"""Stellar network service for USDC refund transactions."""
import logging
from decimal import Decimal
from typing import Optional

from stellar_sdk import (
    Asset,
    Keypair,
    Network,
    Server,
    TransactionBuilder,
)
from stellar_sdk.exceptions import (
    BadRequestError,
    BadResponseError,
    NotFoundError,
)

from ..config import settings

logger = logging.getLogger(__name__)


class StellarService:
    """
    Service for interacting with Stellar network.
    
    Handles USDC refund transactions back to user wallets.
    """

    # Circle USDC on Stellar Mainnet
    USDC_ISSUER = "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN"
    USDC_ASSET_CODE = "USDC"
    
    # For testnet (development)
    TESTNET_USDC_ISSUER = "GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5"

    def __init__(
        self,
        network: str = "testnet",
        platform_secret: Optional[str] = None,
    ) -> None:
        """
        Initialize Stellar service.
        
        Args:
            network: 'testnet' or 'public' (mainnet)
            platform_secret: Platform's Stellar secret key for signing transactions
        """
        self.network = network
        self.platform_secret = platform_secret or settings.stellar_platform_secret
        
        # Set up Stellar Server (Horizon)
        if network == "public":
            self.server = Server("https://horizon.stellar.org")
            self.network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE
            self.usdc_issuer = self.USDC_ISSUER
        else:
            self.server = Server("https://horizon-testnet.stellar.org")
            self.network_passphrase = Network.TESTNET_NETWORK_PASSPHRASE
            self.usdc_issuer = self.TESTNET_USDC_ISSUER
        
        # Load platform keypair
        if self.platform_secret:
            try:
                self.platform_keypair = Keypair.from_secret(self.platform_secret)
                logger.info(f"Stellar service initialized with platform address: {self.platform_keypair.public_key}")
            except Exception as e:
                logger.error(f"Failed to load platform keypair: {e}")
                self.platform_keypair = None
        else:
            logger.warning("Platform secret key not configured - refunds will not work")
            self.platform_keypair = None

    def send_usdc_refund(
        self,
        destination_address: str,
        amount_cents: int,
        memo: Optional[str] = None,
    ) -> dict:
        """
        Send USDC refund to user's Stellar wallet.
        
        Args:
            destination_address: User's Stellar public key (G...)
            amount_cents: Amount in cents to refund (e.g., 250 = $2.50)
            memo: Optional memo for the transaction
            
        Returns:
            dict with transaction details:
            {
                "success": True,
                "tx_hash": "abc123...",
                "amount_usdc": "2.50",
                "destination": "GABC..."
            }
            
        Raises:
            ValueError: If platform keypair not configured
            BadRequestError: If transaction is malformed
            NotFoundError: If destination account doesn't exist
        """
        if not self.platform_keypair:
            raise ValueError("Platform secret key not configured")
        
        # Convert cents to USDC amount
        # Example: 250 cents = $2.50 USDC
        amount_usdc = Decimal(amount_cents) / Decimal(100)
        amount_str = str(amount_usdc)
        
        logger.info(f"Sending {amount_str} USDC refund to {destination_address}")
        
        try:
            # Load platform account
            platform_account = self.server.load_account(
                self.platform_keypair.public_key
            )
            
            # Create USDC asset
            usdc = Asset(self.USDC_ASSET_CODE, self.usdc_issuer)
            
            # Build transaction
            transaction_builder = TransactionBuilder(
                source_account=platform_account,
                network_passphrase=self.network_passphrase,
                base_fee=100,  # 0.00001 XLM
            )
            
            # Add payment operation
            transaction_builder.append_payment_op(
                destination=destination_address,
                asset=usdc,
                amount=amount_str,
            )
            
            # Add memo if provided
            if memo:
                transaction_builder.add_text_memo(memo[:28])  # Max 28 chars
            
            # Set timeout and build
            transaction = transaction_builder.set_timeout(30).build()
            
            # Sign transaction
            transaction.sign(self.platform_keypair)
            
            # Submit to network
            response = self.server.submit_transaction(transaction)
            
            logger.info(f"Refund successful: {response['hash']}")
            
            return {
                "success": True,
                "tx_hash": response["hash"],
                "amount_usdc": amount_str,
                "destination": destination_address,
                "ledger": response.get("ledger"),
            }
            
        except NotFoundError as e:
            logger.error(f"Destination account not found: {destination_address}")
            raise ValueError(f"Destination account does not exist: {destination_address}")
            
        except BadRequestError as e:
            logger.error(f"Bad request error: {e}")
            raise ValueError(f"Transaction failed: {str(e)}")
            
        except BadResponseError as e:
            logger.error(f"Stellar network error: {e}")
            raise RuntimeError(f"Stellar network error: {str(e)}")
            
        except Exception as e:
            logger.error(f"Unexpected error sending refund: {e}")
            raise RuntimeError(f"Failed to send refund: {str(e)}")

    def validate_address(self, address: str) -> bool:
        """
        Validate a Stellar address format.
        
        Args:
            address: Stellar public key to validate
            
        Returns:
            True if valid format, False otherwise
        """
        try:
            # Check if it's a valid Stellar public key
            Keypair.from_public_key(address)
            return True
        except Exception:
            return False

    def check_account_exists(self, address: str) -> bool:
        """
        Check if a Stellar account exists on the network.
        
        Args:
            address: Stellar public key
            
        Returns:
            True if account exists, False otherwise
        """
        try:
            self.server.load_account(address)
            return True
        except NotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking account: {e}")
            return False


# Global instance
stellar_service = StellarService()
