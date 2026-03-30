#!/usr/bin/env python3
"""Simple test script to verify travel APIs are responding"""
import requests
import json

# API endpoints
VISA_API_URL = 'http://180.149.215.231:8088/travel_api/visa'
TICKET_API_URL = 'http://180.149.215.231:8088/travel_api/ticket'
HOTEL_API_URL = 'http://180.149.215.231:8088/travel_api/hotel'

def test_api(name, url, params=None):
    """Test an API endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing {name} API")
    print(f"URL: {url}")
    if params:
        print(f"Params: {params}")
    print(f"{'='*60}")

    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response Type: {type(data)}")
            print(f"Response Data:\n{json.dumps(data, indent=2)}")
            return True
        else:
            print(f"Error Response: {response.text}")
            return False
    except Exception as e:
        print(f"Exception: {str(e)}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("TRAVEL API TEST SUITE")
    print("="*60)

    # Test visa API
    visa_ok = test_api("Visa", VISA_API_URL)

    # Test flight API
    flight_ok = test_api("Flight/Ticket", TICKET_API_URL, {'destination': 'Dubai'})

    # Test hotel API
    hotel_ok = test_api("Hotel", HOTEL_API_URL, {'destination': 'Dubai'})

    print(f"\n{'='*60}")
    print("TEST RESULTS")
    print(f"{'='*60}")
    print(f"Visa API: {'✓ PASS' if visa_ok else '✗ FAIL'}")
    print(f"Flight API: {'✓ PASS' if flight_ok else '✗ FAIL'}")
    print(f"Hotel API: {'✓ PASS' if hotel_ok else '✗ FAIL'}")
    print(f"{'='*60}")
