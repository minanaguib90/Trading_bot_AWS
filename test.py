import requests
import json
import time

def test_webhook():
    base_url = "http://localhost:5000"
    
    # Test accounts endpoint
    print("\nTesting /accounts endpoint:")
    try:
        response = requests.get(f"{base_url}/accounts")
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")
    
    # Test webhook
    print("\nTesting webhook:")
    webhook_data = {
        "symbol": "BTCUSDT",
        "side": "buy",
        "tpOrderType": "limit",
        "slOrderType": "market"
    }
    
    try:
        response = requests.post(f"{base_url}/webhook", json=webhook_data)
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")
    
    # Wait for orders to be processed
    time.sleep(5)
    
    # Test account1 status
    print("\nTesting account1 status:")
    try:
        response = requests.get(f"{base_url}/account/account1/status")
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_webhook()
