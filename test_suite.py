import unittest
import requests

# URL of your local server
BASE_URL = "http://127.0.0.1:5001"

class TestSecureSentinel(unittest.TestCase):

    def test_1_monitor_is_public(self):
        """Test 1: The Dashboard should be viewable by anyone (No Password)"""
        print("\n🧪 TEST 1: Checking Dashboard Access...")
        try:
            response = requests.get(f"{BASE_URL}/api/monitor")
            # We expect 200 OK
            self.assertEqual(response.status_code, 200)
            print("   ✅ PASS: Dashboard is accessible.")
        except Exception as e:
            self.fail(f"   ❌ FAIL: Server not reachable. Is it running? Error: {e}")

    def test_2_telemetry_blocks_unauthorized(self):
        """Test 2: Sending data WITHOUT a key should be BLOCKED"""
        print("🧪 TEST 2: Attempting Unauthorized Data Injection...")
        fake_data = {"temperature": 99, "gas": 9999, "motion": 1}
        
        # Try to POST without headers
        response = requests.post(f"{BASE_URL}/api/telemetry", json=fake_data)
        
        # We expect 403 Forbidden
        if response.status_code == 403:
            print("   ✅ PASS: Security System blocked the attack (403 Forbidden).")
        else:
            print(f"   ❌ FAIL: Server accepted bad data! Status Code: {response.status_code}")
            self.fail("Security breach detected.")

    def test_3_telemetry_accepts_valid_key(self):
        """Test 3: Sending data WITH the correct key should work"""
        print("🧪 TEST 3: Sending Authorized Data...")
        
        # This must match the key in server.py
        headers = {"X-API-Key": "Sentinel-X99-Secure-Token"}
        valid_data = {"temperature": 24.5, "gas": 200, "motion": 0}
        
        response = requests.post(f"{BASE_URL}/api/telemetry", json=valid_data, headers=headers)
        
        # We expect 200 OK
        if response.status_code == 200:
            print("   ✅ PASS: Authorized data accepted.")
        else:
            print(f"   ❌ FAIL: Valid key rejected. Status Code: {response.status_code}")
            self.fail("Valid key did not work.")

if __name__ == '__main__':
    # This runs the tests
    unittest.main(verbosity=0)