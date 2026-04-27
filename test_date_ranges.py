#!/usr/bin/env python3
"""
Simple test script to verify the /date_ranges endpoint works correctly.
"""
import requests
import json
from datetime import datetime

def test_date_ranges_endpoint():
    """Test the new /date_ranges endpoint"""
    try:
        # Assuming the Flask app runs on localhost:5001
        url = "http://localhost:5001/wandikweza/date_ranges"
        
        print(f"Testing endpoint: {url}")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Endpoint responded successfully!")
            print("\nDate ranges:")
            print(json.dumps(data, indent=2))
            
            # Validate response structure
            expected_tables = [
                'patient_age_categories',
                'patient_gender_counts', 
                'patient_location_counts',
                'patient_refund_count',
                'patient_stay_times'
            ]
            
            for table in expected_tables:
                if table in data:
                    table_data = data[table]
                    print(f"\n✅ {table}: {table_data['start_date']} to {table_data['end_date']}")
                else:
                    print(f"\n❌ Missing table: {table}")
                    
        else:
            print(f"❌ Endpoint failed with status {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Flask app. Make sure it's running on localhost:5001")
    except Exception as e:
        print(f"❌ Error testing endpoint: {str(e)}")

if __name__ == "__main__":
    test_date_ranges_endpoint()