# Date Ranges API Endpoint

## Overview
The `/wandikweza/date_ranges` endpoint provides dynamic date ranges for each table in the billing indicators database. This is designed to support Superset date range badges by providing the actual data availability ranges for each chart.

## Endpoint Details
- **URL**: `/wandikweza/date_ranges`
- **Method**: `GET`
- **Content-Type**: `application/json`

## Response Format
The endpoint returns a JSON object with date ranges for each table:

```json
{
  "patient_age_categories": {
    "start_date": "2026-04-01",
    "end_date": "2026-04-08", 
    "table_name": "patient_age_categories",
    "date_field": "time_stamp"
  },
  "patient_gender_counts": {
    "start_date": "2026-04-01",
    "end_date": "2026-04-08",
    "table_name": "patient_gender_counts", 
    "date_field": "time_stamp"
  },
  "patient_location_counts": {
    "start_date": "2026-04-01",
    "end_date": "2026-04-08",
    "table_name": "patient_location_counts",
    "date_field": "time_stamp"
  },
  "patient_refund_count": {
    "start_date": "2026-04-01", 
    "end_date": "2026-04-07",
    "table_name": "patient_refund_count",
    "date_field": "refund_timestamp"
  },
  "patient_stay_times": {
    "start_date": "2026-04-01",
    "end_date": "2026-04-08",
    "table_name": "patient_stay_times",
    "date_field": "push_time"
  }
}
```

## Date Range Logic
For each table:
- **Start Date**: First day of the month containing the latest data
- **End Date**: The actual last date when data was created/updated
- **Format**: YYYY-MM-DD

## Table Mappings
| Table Key | Database Table | Date Field |
|-----------|----------------|------------|
| `patient_age_categories` | `patient_age_categories` | `time_stamp` |
| `patient_gender_counts` | `patient_gender_counts` | `time_stamp` |
| `patient_location_counts` | `patient_location_counts` | `time_stamp` |
| `patient_refund_count` | `patient_refund_count` | `refund_timestamp` |
| `patient_stay_times` | `patient_stay_times` | `push_time` |

## Error Handling
- If a table has no data, `start_date` and `end_date` will be `null`
- If there's an error accessing a specific table, an `error` field will be included
- The endpoint will still return data for other tables even if one fails

## Usage Examples

### cURL
```bash
curl -X GET "http://localhost:5001/wandikweza/date_ranges" \
     -H "Content-Type: application/json"
```

### Python
```python
import requests

response = requests.get("http://localhost:5001/wandikweza/date_ranges")
date_ranges = response.json()

# Get refund data range
refund_range = date_ranges["patient_refund_count"]
print(f"Refund data: {refund_range['start_date']} to {refund_range['end_date']}")
```

### JavaScript/Fetch
```javascript
fetch('/wandikweza/date_ranges')
  .then(response => response.json())
  .then(data => {
    console.log('Date ranges:', data);
    // Use for Superset date range badges
  });
```

## Integration with Superset
This endpoint is designed to work with Superset date range badges:

1. Call this endpoint to get current data ranges
2. Use the `start_date` and `end_date` for each chart's date range badge
3. Display as "Data available: April 1, 2026 - April 8, 2026"

## Testing
Run the test script to verify the endpoint:
```bash
python3 test_date_ranges.py
```

Or use the curl test:
```bash
./test_curl.sh
```