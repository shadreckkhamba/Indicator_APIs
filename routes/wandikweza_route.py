from flask import Blueprint, request, jsonify
import gzip
import io
from services.patient_categories_service import save_patient_data_upsert
from models.last_update_status_model import LastUpdateStatus
from extensions.extensions import db
from pytz import timezone, utc
import json
from extensions.extensions import db, logger
from sqlalchemy import text
from sqlalchemy import text, func
from flask import jsonify
from datetime import datetime, timedelta
from models.patient_stay_time_model import PatientStayTime

DAYS_TO_FETCH = 7
RECENT_RECORDS_COUNT = 10
STAY_DISTRIBUTION_MAX_HOURS = 10.0
STAY_DISTRIBUTION_BUCKET_MINUTES = 10


wandikweza_bp = Blueprint('wandikweza', __name__)
LOCAL_TZ = timezone('Africa/Blantyre')

from datetime import datetime, time

def parse_time_safe(value: str) -> time | None:
    """Parse HH:MM:SS string into Python time object."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M:%S").time()
    except Exception as e:
        logger.warning(f"Failed to parse time '{value}': {e}")
        return None


def parse_datetime_safe(value: str) -> datetime | None:
    """Parse full ISO datetime string into Python datetime object."""
    if not value:
        return None
    try:
        # Parse ISO 8601 string
        dt = datetime.fromisoformat(value)
        # Convert to local timezone if it has tzinfo
        if dt.tzinfo:
            dt = dt.astimezone(LOCAL_TZ)
        else:
            dt = LOCAL_TZ.localize(dt)
        return dt
    except Exception as e:
        logger.warning(f"Failed to parse datetime '{value}': {e}")
        return None

@wandikweza_bp.route('/save_patient_data', methods=['POST'])
@wandikweza_bp.route('/save_patient_data/', methods=['POST'])
def save_patient_category_data_route():
    """
    Route: Receives JSON (supports gzip), passes to service, returns response.
    """
    try:
        if request.headers.get('Content-Encoding') == 'gzip':
            compressed_data = request.get_data()
            with gzip.GzipFile(fileobj=io.BytesIO(compressed_data)) as f:
                data = f.read()
            data = json.loads(data)
        else:
            data = request.get_json()
    except Exception as e:
        return jsonify({"error": f"Failed to parse JSON payload: {str(e)}"}), 400

    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    result = save_patient_data_upsert(data)

    if "error" in result:
        return jsonify(result), 500

    return jsonify(result), 200


@wandikweza_bp.route('/last_update_status', methods=['GET'])
def get_last_update_status():
    """
    Route: Returns the last updated timestamp, converted to Malawi local time.
    """
    last = db.session.query(LastUpdateStatus).order_by(LastUpdateStatus.last_updated.desc()).first()
    if not last or not last.last_updated:
        return jsonify({"last_updated": None}), 200

    last_updated_utc = last.last_updated
    if last_updated_utc.tzinfo is None:
        last_updated_utc = last_updated_utc.replace(tzinfo=utc)

    last_updated_local = last_updated_utc.astimezone(LOCAL_TZ)

    return jsonify({"last_updated": last_updated_local.isoformat()}), 200

from models.patient_stay_time_model import PatientStayTime


from flask import jsonify
from sqlalchemy import text
from datetime import datetime, timedelta
from extensions.extensions import db, logger
from models.patient_stay_time_model import PatientStayTime

@wandikweza_bp.route('/daily_average_stay', methods=['GET'])
def get_daily_average_stay():
    """
    Returns daily average stay times calculated dynamically from raw data.
    No longer stores calculated values in DB - calculates everything on-demand.
    """
    try:
        today_dt = datetime.now()
        start_of_week = today_dt - timedelta(days=today_dt.weekday())  # Monday

        # Get all records and calculate in Python to avoid SQLAlchemy issues
        all_records = db.session.query(PatientStayTime).all()
        
        if not all_records:
            return jsonify({
                "today": {
                    "date": today_dt.strftime("%Y-%m-%d"),
                    "avg_stay_hours": 0.0,
                    "recent_avg": 0.0,
                    "percent_change": 0.0,
                    "patient_count": 0
                },
                "trend": [],
                "stay_distribution": {}
            }), 200

        # Group records by date and sort by departure time
        daily_data = {}
        for record in all_records:
            date_str = record.arrival_time.date().strftime("%Y-%m-%d")
            if date_str not in daily_data:
                daily_data[date_str] = []
            daily_data[date_str].append({
                'hours': float(record.difference_hours),
                'departure_time': record.departure_time
            })

        # Sort records within each day by departure time
        for date_str in daily_data:
            daily_data[date_str].sort(key=lambda x: x['departure_time'])

        # Calculate daily averages and running averages
        daily_averages = {}
        for date_str, records in daily_data.items():
            hours_list = [r['hours'] for r in records]
            daily_averages[date_str] = {
                'avg_hours': sum(hours_list) / len(hours_list),
                'count': len(hours_list),
                'records': records
            }

        # Use actual today's date
        today_str = today_dt.strftime("%Y-%m-%d")
        sorted_dates = sorted(daily_averages.keys(), reverse=True)
        
        if not sorted_dates:
            return jsonify({
                "today": {
                    "date": today_str,
                    "avg_stay_hours": 0.0,
                    "recent_avg": 0.0,
                    "percent_change": 0.0,
                    "patient_count": 0
                },
                "trend": [],
                "stay_distribution": {}
            }), 200

        # Check if today has data, otherwise use 0
        if today_str in daily_averages:
            today_records = daily_averages[today_str]['records']
            today_avg = daily_averages[today_str]['avg_hours']
            today_count = daily_averages[today_str]['count']
        else:
            today_records = []
            today_avg = 0.0
            today_count = 0

        # recent_avg is the average of today's records excluding the most recent one
        recent_avg = 0.0
        if len(today_records) > 1:
            recent_hours = [r['hours'] for r in today_records[:-1]]
            if recent_hours:
                recent_avg = sum(recent_hours) / len(recent_hours)

        # Calculate percent change
        percent_change = 0.0
        if recent_avg > 0:
            percent_change = ((today_avg - recent_avg) / recent_avg) * 100
        elif recent_avg == 0 and today_avg > 0:
            # Coming from 0 to positive value - show as 100% increase
            percent_change = 100.0
        elif recent_avg == 0 and today_avg == 0:
            # Both are 0 - no change
            percent_change = 0.0

        # Build weekly trend
        trend = []
        for i in range((today_dt - start_of_week).days + 1):
            day_dt = start_of_week + timedelta(days=i)
            day_str = day_dt.strftime("%Y-%m-%d")
            
            if day_str in daily_averages:
                avg_hours = round(daily_averages[day_str]['avg_hours'], 2)
            else:
                avg_hours = 0.0

            # Percent change vs most recent day
            day_percent_change = 0.0
            if today_avg > 0:
                day_percent_change = round(((avg_hours - today_avg) / today_avg) * 100, 2)
            elif avg_hours == 0:
                day_percent_change = 0.0
            else:
                day_percent_change = -100.0

            trend.append({
                "day": day_str,
                "avg_hours": avg_hours,
                "percent_change_vs_today": day_percent_change
            })

        # Build stay distribution buckets (10-minute buckets up to 10 hours)
        bucket_size_hours = STAY_DISTRIBUTION_BUCKET_MINUTES / 60.0
        bucket_count = int(STAY_DISTRIBUTION_MAX_HOURS / bucket_size_hours)
        bucket_counts = [0] * bucket_count

        for record in all_records:
            if record.difference_hours is None:
                continue
            try:
                hours = float(record.difference_hours)
            except (TypeError, ValueError):
                continue
            if hours < 0 or hours >= STAY_DISTRIBUTION_MAX_HOURS:
                continue
            bucket_index = int(hours / bucket_size_hours)
            if 0 <= bucket_index < bucket_count:
                bucket_counts[bucket_index] += 1

        # Build stay distribution per day
        stay_distribution = {}
        for record in all_records:
            if record.difference_hours is None or record.arrival_time is None:
                continue
            try:
                hours = float(record.difference_hours)
            except (TypeError, ValueError):
                continue
            if hours < 0 or hours >= STAY_DISTRIBUTION_MAX_HOURS:
                continue

            date_key = record.arrival_time.date().strftime("%Y-%m-%d")
            if date_key not in stay_distribution:
                stay_distribution[date_key] = [0] * bucket_count

            bucket_index = int(hours / bucket_size_hours)
            if 0 <= bucket_index < bucket_count:
                stay_distribution[date_key][bucket_index] += 1

        for date_key, counts in stay_distribution.items():
            stay_distribution[date_key] = [
                {"hours": round(i * bucket_size_hours, 2), "count": counts[i]}
                for i in range(bucket_count)
            ]

        response = {
            "today": {
                "date": today_str,
                "avg_stay_hours": round(today_avg, 2),
                "recent_avg": round(recent_avg, 2),
                "percent_change": round(percent_change, 2),
                "patient_count": today_count
            },
            "trend": trend,
            "stay_distribution": stay_distribution
        }

        logger.info(f"Daily average calculated: today={today_str} avg={today_avg:.2f}h ({today_count} patients), previous={recent_avg:.2f}h, change={percent_change:.2f}%")
        return jsonify(response), 200

    except Exception as e:
        logger.exception("Error in /daily_average_stay")
        return jsonify({"error": str(e)}), 500


@wandikweza_bp.route('/stay_times_distribution', methods=['GET'])
def stay_times_distribution():
    """
    Returns a list of stay time entries formatted as HH:MM:SS plus
    shortest and longest stay in decimal hours. Supports `period` query
    param: 'day' | 'week' | 'month' (defaults to 'day').
    """
    try:
        period = (request.args.get('period') or 'day').lower()
        now = datetime.now()

        if period == 'day':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            start = now - timedelta(days=7)
        elif period == 'month':
            start = now - timedelta(days=30)
        else:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        records = (
            db.session.query(PatientStayTime)
            .filter(PatientStayTime.arrival_time >= start)
            .all()
        )

        entries = []
        shortest = None
        longest = None

        for r in records:
            hours = None
            if r.difference_hours is not None:
                try:
                    hours = float(r.difference_hours)
                except Exception:
                    hours = None

            if hours is None:
                continue

            # Convert decimal hours -> HH:MM:SS
            h = int(hours)
            m = int((hours - h) * 60)
            s = int(round((((hours - h) * 60) - m) * 60))
            # Normalize rounding overflow
            if s >= 60:
                s -= 60
                m += 1
            if m >= 60:
                m -= 60
                h += 1

            diff_str = f"{h:02d}:{m:02d}:{s:02d}"
            entries.append({"difference": diff_str})

            if shortest is None or hours < shortest:
                shortest = hours
            if longest is None or hours > longest:
                longest = hours

        response = {
            "entries": entries,
            "shortest_stay": round(shortest, 2) if shortest is not None else None,
            "longest_stay": round(longest, 2) if longest is not None else None,
        }

        logger.info(f"/stay_times_distribution: period={period} entries={len(entries)} shortest={response['shortest_stay']} longest={response['longest_stay']}")
        return jsonify(response), 200

    except Exception as e:
        logger.exception("Error in /stay_times_distribution")
        return jsonify({"error": str(e)}), 500


@wandikweza_bp.route('/stay_times_trend', methods=['GET'])
def stay_times_trend():
    """
    Returns daily aggregated stay time trend data for the past 7 days.
    Each entry contains: day (YYYY-MM-DD), avg_stay_hours, total_patients
    """
    try:
        now = datetime.now()
        start = now - timedelta(days=7)

        records = (
            db.session.query(PatientStayTime)
            .filter(PatientStayTime.arrival_time >= start)
            .all()
        )

        # Group by date
        daily_data = {}
        for r in records:
            if r.arrival_time is None or r.difference_hours is None:
                continue

            date_str = r.arrival_time.date().strftime("%Y-%m-%d")
            if date_str not in daily_data:
                daily_data[date_str] = {'hours': [], 'count': 0}

            try:
                hours = float(r.difference_hours)
                daily_data[date_str]['hours'].append(hours)
                daily_data[date_str]['count'] += 1
            except (TypeError, ValueError):
                continue

        # Calculate daily averages
        entries = []
        for date_str in sorted(daily_data.keys()):
            data = daily_data[date_str]
            if data['hours']:
                avg_hours = sum(data['hours']) / len(data['hours'])
                entries.append({
                    "day": date_str,
                    "avg_stay_hours": round(avg_hours, 2),
                    "total_patients": data['count']
                })

        response = {"entries": entries}
        logger.info(f"/stay_times_trend: returned {len(entries)} days of data")
        return jsonify(response), 200

    except Exception as e:
        logger.exception("Error in /stay_times_trend")
        return jsonify({"error": str(e)}), 500
