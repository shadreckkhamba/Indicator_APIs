#!/bin/bash
# Simple curl test for the new /date_ranges endpoint

echo "Testing /date_ranges endpoint..."
curl -X GET "http://localhost:5001/wandikweza/date_ranges" \
     -H "Content-Type: application/json" \
     -w "\nStatus: %{http_code}\n" \
     | python3 -m json.tool

echo -e "\n\nTo test manually, run:"
echo "python3 run.py"
echo "Then in another terminal:"
echo "curl http://localhost:5001/wandikweza/date_ranges | python3 -m json.tool"