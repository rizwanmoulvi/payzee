#!/usr/bin/env python3
"""
Quick test script for the payzee Backend API.
Run this after starting the server with: uvicorn src.main:app --reload
"""
import requests
import json
import sys

API_BASE = "http://localhost:8000"
API_KEY = "test-api-key-change-in-production"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def test_health():
    """Test the health endpoint."""
    print("🔍 Testing health endpoint...")
    response = requests.get(f"{API_BASE}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_create_card():
    """Test creating a virtual card (will fail without Lithic API key)."""
    print("🔍 Testing card creation endpoint...")
    payload = {
        "stellar_transaction_id": "test-tx-12345",
        "amount_cents": 10000,
        "merchant_name": "Test Merchant"
    }
    
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/cards/create",
            headers=headers,
            json=payload
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    print()

def test_list_cards():
    """Test listing all cards."""
    print("🔍 Testing list cards endpoint...")
    response = requests.get(f"{API_BASE}/api/v1/cards", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

if __name__ == "__main__":
    print("=" * 60)
    print("payzee Backend API Tests")
    print("=" * 60)
    print()
    
    try:
        test_health()
        test_list_cards()
        
        print("⚠️  Note: Card creation will fail without a valid Lithic API key.")
        print("   Add your Lithic sandbox API key to .env to test card creation.")
        print()
        test_create_card()
        
        print("=" * 60)
        print("✅ All basic tests completed!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to server.")
        print("   Make sure the server is running: uvicorn src.main:app --reload")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
