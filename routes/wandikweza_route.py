from flask import Blueprint, request, jsonify
import gzip
import io
import math
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
from models.patient_age_category_model import PatientAgeCategory
from models.patient_gender_count_model import PatientGenderCount
from models.patient_location_count_model import PatientLocationCount
from models.patient_refund_count_model import PatientRefundCount

DAYS_TO_FETCH = 7
RECENT_RECORDS_COUNT = 10
STAY_DISTRIBUTION_MAX_HOURS = 10.0
STAY_DISTRIBUTION_BUCKET_MINUTES = 1


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
            date_str = record.push_time.date().strftime("%Y-%m-%d")
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
            if record.difference_hours is None or record.push_time is None:
                continue
            try:
                hours = float(record.difference_hours)
            except (TypeError, ValueError):
                continue
            if hours < 0 or hours >= STAY_DISTRIBUTION_MAX_HOURS:
                continue

            date_key = record.push_time.date().strftime("%Y-%m-%d")
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
    shortest and longest stay in decimal hours.

    Supports:
    - period=day|week|month (defaults to day)
    - date=YYYY-MM-DD for a single-day snapshot
    - start_date=YYYY-MM-DD and end_date=YYYY-MM-DD for an inclusive range
    """
    try:
        period = (request.args.get('period') or 'day').lower()
        date_str = request.args.get('date')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        now = datetime.now()
        start = None
        end_exclusive = None

        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({
                    'error': 'Invalid date format. Use YYYY-MM-DD for date.'
                }), 400
            start = datetime.combine(target_date, datetime.min.time())
            end_exclusive = start + timedelta(days=1)
        elif start_date_str or end_date_str:
            if not start_date_str or not end_date_str:
                return jsonify({
                    'error': 'Both start_date and end_date are required when filtering by range.'
                }), 400
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({
                    'error': 'Invalid date format. Use YYYY-MM-DD for start_date and end_date.'
                }), 400
            if end_date < start_date:
                return jsonify({
                    'error': 'end_date must be greater than or equal to start_date.'
                }), 400
            start = datetime.combine(start_date, datetime.min.time())
            end_exclusive = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
        elif period == 'day':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_exclusive = start + timedelta(days=1)
        elif period == 'week':
            start = (now - timedelta(days=now.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_exclusive = start + timedelta(days=7)
        elif period == 'month':
            start = (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
            if now.month == 12:
                end_exclusive = datetime(now.year + 1, 1, 1)
            else:
                end_exclusive = datetime(now.year, now.month + 1, 1)
        else:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_exclusive = start + timedelta(days=1)

        query = db.session.query(PatientStayTime).filter(PatientStayTime.push_time >= start)
        if end_exclusive is not None:
            query = query.filter(PatientStayTime.push_time < end_exclusive)

        records = query.all()

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

        filter_desc = date_str or (f"{start_date_str}..{end_date_str}" if start_date_str or end_date_str else period)
        logger.info(f"/stay_times_distribution: filter={filter_desc} entries={len(entries)} shortest={response['shortest_stay']} longest={response['longest_stay']}")
        return jsonify(response), 200

    except Exception as e:
        logger.exception("Error in /stay_times_distribution")
        return jsonify({"error": str(e)}), 500


@wandikweza_bp.route('/stay_times_trend', methods=['GET'])
def stay_times_trend():
    """
    Returns daily aggregated stay time trend data.
    Optional query params:
    - start_date=YYYY-MM-DD
    - end_date=YYYY-MM-DD
    If omitted, defaults to the last 7 days.
    Each entry contains: day (YYYY-MM-DD), avg_stay_hours, total_patients
    """
    try:
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")

        if start_date_str or end_date_str:
            if not start_date_str or not end_date_str:
                return jsonify({
                    "error": "Both start_date and end_date are required when filtering by week."
                }), 400
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                return jsonify({
                    "error": "Invalid date format. Use YYYY-MM-DD for start_date and end_date."
                }), 400

            if end_date < start_date:
                return jsonify({
                    "error": "end_date must be greater than or equal to start_date."
                }), 400

            start_dt = datetime.combine(start_date, datetime.min.time())
            end_exclusive = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
        else:
            now = datetime.now()
            start_dt = now - timedelta(days=7)
            end_exclusive = now

        records = (
            db.session.query(PatientStayTime)
            .filter(PatientStayTime.push_time >= start_dt)
            .filter(PatientStayTime.push_time < end_exclusive)
            .all()
        )

        # Group by date
        daily_data = {}
        for r in records:
            if r.push_time is None or r.difference_hours is None:
                continue

            try:
                if isinstance(r.push_time, datetime):
                    day_value = r.push_time.date()
                else:
                    day_value = datetime.fromisoformat(str(r.push_time)).date()
                date_str = day_value.strftime("%Y-%m-%d")
            except Exception:
                # Skip malformed timestamps instead of failing the entire request
                continue

            if date_str not in daily_data:
                daily_data[date_str] = {'hours': [], 'count': 0}

            try:
                hours = float(r.difference_hours)
                if not math.isfinite(hours):
                    continue
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
        logger.info(
            f"/stay_times_trend: returned {len(entries)} days of data "
            f"for range {start_dt.isoformat()} to {end_exclusive.isoformat()} (exclusive end)"
        )
        return jsonify(response), 200

    except Exception as e:
        logger.exception("Error in /stay_times_trend")
        return jsonify({"error": str(e)}), 500


@wandikweza_bp.route('/patient_records', methods=['GET'])
def get_patient_records():
    """
    Returns individual patient records with patient_id, arrival_time, and departure_time.
    Optional query params:
    - period: 'day' | 'week' | 'month' | 'all' (defaults to 'month')
    - limit: max number of records to return (defaults to 100)
    - offset: pagination offset (defaults to 0)
    """
    try:
        period = (request.args.get('period') or 'month').lower()
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))

        now = datetime.now()
        
        # Build query based on period
        query = db.session.query(PatientStayTime)
        
        if period == 'day':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(PatientStayTime.push_time >= start)
        elif period == 'week':
            start = now - timedelta(days=7)
            query = query.filter(PatientStayTime.push_time >= start)
        elif period == 'month':
            start = now - timedelta(days=30)
            query = query.filter(PatientStayTime.push_time >= start)
        elif period == 'all':
            # No date filter for 'all'
            pass
        else:
            # Default to month if invalid period
            start = now - timedelta(days=30)
            query = query.filter(PatientStayTime.push_time >= start)

        # Order by arrival time (most recent first)
        query = query.order_by(PatientStayTime.arrival_time.desc())

        total_count = query.count()
        records = query.limit(limit).offset(offset).all()

        patients = []
        for r in records:
            patients.append({
                "patient_id": r.patient_id,
                "arrival_time": r.arrival_time.isoformat() if r.arrival_time else None,
                "departure_time": r.departure_time.isoformat() if r.departure_time else None
            })

        response = {
            "patients": patients,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "period": period
        }

        logger.info(f"/patient_records: period={period} returned {len(patients)} records (total={total_count})")
        return jsonify(response), 200

    except Exception as e:
        logger.exception("Error in /patient_records")
        return jsonify({"error": str(e)}), 500


@wandikweza_bp.route('/date_ranges', methods=['GET'])
def get_date_ranges():
    """
    Returns dynamic date ranges for each table based on actual data.
    For each table, returns the first day of the month to the last day data was created.
    
    Response format:
    {
        "patient_age_categories": {
            "start_date": "2026-04-01",
            "end_date": "2026-04-08",
            "table_name": "patient_age_categories",
            "date_field": "time_stamp"
        },
        ...
    }
    """
    try:
        ranges = {}
        
        # Define table configurations with their models and date fields
        table_configs = [
            {
                'key': 'patient_age_categories',
                'model': PatientAgeCategory,
                'date_field': 'time_stamp',
                'table_name': 'patient_age_categories'
            },
            {
                'key': 'patient_gender_counts', 
                'model': PatientGenderCount,
                'date_field': 'time_stamp',
                'table_name': 'patient_gender_counts'
            },
            {
                'key': 'patient_location_counts',
                'model': PatientLocationCount, 
                'date_field': 'time_stamp',
                'table_name': 'patient_location_counts'
            },
            {
                'key': 'patient_refund_count',
                'model': PatientRefundCount,
                'date_field': 'refund_timestamp', 
                'table_name': 'patient_refund_count'
            },
            {
                'key': 'patient_stay_times',
                'model': PatientStayTime,
                'date_field': 'push_time',
                'table_name': 'patient_stay_times'
            }
        ]
        
        for config in table_configs:
            try:
                model = config['model']
                date_field = getattr(model, config['date_field'])
                
                # Get the latest date from the table
                latest_record = db.session.query(func.max(date_field)).scalar()
                
                if latest_record:
                    # Convert to date if it's a datetime
                    if hasattr(latest_record, 'date'):
                        end_date = latest_record.date()
                    else:
                        end_date = latest_record
                    
                    # Start date is first day of the month
                    start_date = end_date.replace(day=1)
                    
                    ranges[config['key']] = {
                        'start_date': start_date.strftime('%Y-%m-%d'),
                        'end_date': end_date.strftime('%Y-%m-%d'),
                        'table_name': config['table_name'],
                        'date_field': config['date_field']
                    }
                else:
                    # No data in table
                    ranges[config['key']] = {
                        'start_date': None,
                        'end_date': None,
                        'table_name': config['table_name'],
                        'date_field': config['date_field']
                    }
                    
            except Exception as e:
                logger.warning(f"Error getting date range for {config['key']}: {str(e)}")
                ranges[config['key']] = {
                    'start_date': None,
                    'end_date': None,
                    'table_name': config['table_name'],
                    'date_field': config['date_field'],
                    'error': str(e)
                }
        
        logger.info(f"/date_ranges: returned ranges for {len(ranges)} tables")
        return jsonify(ranges), 200
        
    except Exception as e:
        logger.exception("Error in /date_ranges")
        return jsonify({"error": str(e)}), 500
