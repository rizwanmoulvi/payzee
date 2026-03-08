"""Application configuration using Pydantic Settings."""
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Security
    api_key: str = "changeme"

    # Lithic Configuration
    lithic_api_key: str = ""
    lithic_environment: Literal["sandbox", "production"] = "sandbox"
    lithic_webhook_secret: str = ""  # For webhook signature verification

    # Stellar Configuration
    stellar_network: Literal["testnet", "public"] = "testnet"
    stellar_rpc_url: str = "https://soroban-testnet.stellar.org:443"  # Soroban RPC endpoint
    stellar_platform_secret: str = ""  # Platform's secret key for sending refunds

    # Soroban Contract (Phase 2)
    stellar_escrow_contract: str = "CDSWWCK54G7N5U5DBYBBP3S4FFPGFOCJXDDOJLQ4HNSDPL2NC67CWQZ3"  # Escrow contract ID
    stellar_usdc_token: str = "CBIELTK6YBZJU5UP2WWQEUCYKLPU6AUNZ2BQ4WWFEIE3USCIHMXQDAMA"  # USDC token contract ID

    # Database
    database_url: str = "sqlite:///./stellar_pay.db"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
settings = Settings()
