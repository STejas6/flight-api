#!/usr/bin/env python3
"""
Simple Flask REST API to connect watsonx Agent to Neon PostgreSQL database
This API provides endpoints for querying flight data
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for watsonx to access the API

# Neon database connection string
DATABASE_URL = "postgresql://neondb_owner:npg_EayzTwrm2B6S@ep-autumn-band-aebfrz67-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
TABLE_NAME = 'flights'
def get_db_connection():
    """Create a database connection"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

# -----------------------
# Schema Discovery
# -----------------------

def get_table_schema():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = %s
    """, (TABLE_NAME,))
    schema = {row[0]: row[1] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return schema


SCHEMA = get_table_schema()


# -----------------------
# Normalization Helpers
# -----------------------
def normalize_value(column, value):
    dtype = SCHEMA[column]

    if "character" in dtype or "text" in dtype:
        return value.upper()

    if "boolean" in dtype:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ["true", "yes", "1"]

    if "integer" in dtype:
        return int(value)

    if "numeric" in dtype or "double" in dtype:
        return float(value)

    return value


# -----------------------
# Query Builder
# -----------------------
def build_dynamic_query(payload):
    filters = []
    values = []

    limit = payload.pop("limit", None)

    # Special handling
    exclude_status = payload.pop("exclude_status", [])

    # Special handling for time-based queries
    departure_after = payload.pop("departure_after", None)
    departure_before = payload.pop("departure_before", None)
    arrival_after = payload.pop("arrival_after", None)
    arrival_before = payload.pop("arrival_before", None)

    for key, value in payload.items():
        if key not in SCHEMA:
            continue

        if value is None:
            continue

        normalized = normalize_value(key, value)

        # Special case: available_seats should use >= (minimum seats)
        if key == "available_seats":
            filters.append(f"{key} >= %s")
            values.append(normalized)
        elif isinstance(normalized, str):
            filters.append(f"{key} = %s")
            values.append(normalized)
        else:
            filters.append(f"{key} = %s")
            values.append(normalized)

    # Handle status exclusions
    for status in exclude_status:
        filters.append("status != %s")
        values.append(status.upper())

    # Handle time-based filtering
    if departure_after:
        filters.append("CAST(departure_time AS TIME) >= %s")
        values.append(departure_after)

    if departure_before:
        filters.append("CAST(departure_time AS TIME) <= %s")
        values.append(departure_before)

    if arrival_after:
        filters.append("CAST(arrival_time AS TIME) >= %s")
        values.append(arrival_after)

    if arrival_before:
        filters.append("CAST(arrival_time AS TIME) <= %s")
        values.append(arrival_before)

    sql = f"SELECT * FROM {TABLE_NAME}"

    if filters:
        sql += " WHERE " + " AND ".join(filters)

    sql += " ORDER BY departure_time"

    if limit:
        sql += " LIMIT %s"
        values.append(int(limit))

    return sql, values


@app.route('/', methods=['GET'])
def home():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "message": "Flight Data API is running",
        "endpoints": {
            "/search": "Search flights with natural language query",
            "/flight/<flight_no>": "Get specific flight details",
            "/health": "API health check"
        }
    })


@app.route("/flight/<flight_no>", methods=["GET"])
def get_flight(flight_no):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        f"SELECT * FROM {TABLE_NAME} WHERE flight_no = %s",
        (flight_no.upper(),)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"error": "Flight not found"}), 404

    return jsonify(row)


@app.route("/health", methods=["GET"])
def health():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()

    return jsonify({
        "status": "healthy",
        "database": "connected",
        "total_flights": count
    })

@app.route("/search", methods=["POST"])
def search_flights():
    # Enhanced logging and error handling
    print("=" * 80)
    print("INCOMING REQUEST TO /search")
    print(f"Content-Type: {request.content_type}")
    print(f"Headers: {dict(request.headers)}")

    # Try to get raw data for debugging
    try:
        raw_data = request.get_data(as_text=True)
        print(f"Raw request data: {raw_data}")
    except Exception as e:
        print(f"Could not read raw data: {e}")

    # Try to parse JSON with better error handling
    try:
        payload = request.get_json(force=True) or {}
        print(f"Parsed payload: {payload}")
    except Exception as e:
        print(f"ERROR parsing JSON: {e}")
        return jsonify({
            "error": "Invalid JSON in request body",
            "details": str(e),
            "content_type": request.content_type
        }), 400

    if not payload:
        print("ERROR: Empty payload")
        return jsonify({"error": "Request body is required"}), 400

    print("=" * 80)

    try:
        sql, values = build_dynamic_query(payload.copy())  # Use copy to preserve original
        print(f"Generated SQL: {sql}")
        print(f"SQL values: {values}")

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, values)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            return jsonify({
                "count": 0,
                "message": "No matching flights found",
                "search_results": []
            })

        results = []
        for r in rows:
            results.append({
                "title": f"{r['flight_no']} | {r['origin']} → {r['destination']}",
                "body": (
                    f"Flight {r['flight_no']} from {r['origin']} to {r['destination']}. "
                    f"Status: {r['status']}. "
                    f"Seats Available: {r['available_seats']}. "
                    f"Gate: {r['gate']}, Terminal: {r['terminal']}. "
                    f"Meal Service: {'Yes' if r['meal_service_available'] else 'No'}."
                ),
                **r
            })

        print(f"Returning {len(results)} results")
        return jsonify({
            "count": len(results),
            "search_results": results
        })

    except Exception as e:
        print(f"ERROR in search_flights: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# @app.route('/search', methods=['POST'])
# def search_flights():
#     """
#     Search flights based on natural language query or structured parameters
# 
#     Expected JSON body:
#     {
#         "query": "flights from DEL to BOM with available seats",
#         OR
#         "origin": "DEL",
#         "destination": "BOM",
#         "status": "ON_TIME",
#         "min_seats": 1
#     }
#     """
#     data = request.get_json()
# 
#     # Log the incoming request for debugging
#     print("="*80)
#     print("INCOMING REQUEST TO /search")
#     print(f"Request data: {data}")
#     print(f"Request headers: {dict(request.headers)}")
#     print("="*80)
# 
#     if not data:
#         print("ERROR: No data in request body")
#         return jsonify({"error": "No query provided"}), 400
# 
#     # watsonx sends extra fields (filter, metadata) - ignore them, just extract 'query'
#     if 'query' not in data and 'filter' in data:
#         # Some watsonx versions put the query in 'filter' instead
#         data['query'] = data.get('filter', '')
# 
#     if not data.get('query'):
#         print("ERROR: No 'query' field in request")
#         return jsonify({"error": "No query field provided", "received_data": data}), 400
# 
#     conn = get_db_connection()
#     if not conn:
#         return jsonify({"error": "Database connection failed"}), 500
# 
#     try:
#         cursor = conn.cursor(cursor_factory=RealDictCursor)
# 
#         # Build SQL query based on parameters
#         conditions = []
#         params = []
# 
#         # Check for structured parameters
#         if 'origin' in data and data['origin']:
#             conditions.append("origin = %s")
#             params.append(data['origin'].upper())
# 
#         if 'destination' in data and data['destination']:
#             conditions.append("destination = %s")
#             params.append(data['destination'].upper())
# 
#         if 'status' in data and data['status']:
#             conditions.append("status = %s")
#             params.append(data['status'].upper())
# 
#         if 'min_seats' in data and data['min_seats']:
#             conditions.append("available_seats >= %s")
#             params.append(int(data['min_seats']))
# 
#         if 'flight_no' in data and data['flight_no']:
#             conditions.append("flight_no = %s")
#             params.append(data['flight_no'].upper())
# 
#         # Parse natural language query if provided
#         result_limit = 50  # Default limit
# 
#         if 'query' in data and data['query']:
#             query_text = data['query']  # Keep original case
# 
#             # City name to airport code mapping (case-insensitive)
#             city_to_code = {
#                 'mumbai': 'BOM', 'delhi': 'DEL', 'bangalore': 'BLR', 'bengaluru': 'BLR',
#                 'chennai': 'MAA', 'kolkata': 'CCU', 'calcutta': 'CCU', 'hyderabad': 'HYD',
#                 'pune': 'PNQ', 'ahmedabad': 'AMD', 'kochi': 'COK', 'cochin': 'COK',
#                 'goa': 'GOI', 'jaipur': 'JAI', 'lucknow': 'LKO', 'chandigarh': 'IXC',
#                 'dubai': 'DXB', 'singapore': 'SIN', 'london': 'LHR', 'new york': 'JFK',
#                 'paris': 'CDG', 'bangkok': 'BKK', 'hong kong': 'HKG', 'tokyo': 'NRT'
#             }
# 
#             # Extract LIMIT from queries like "show 2 flights", "any 5 flights", "first 10 flights"
#             import re
#             limit_patterns = [
#                 r'(?:show|give|find|list)\s+(?:any\s+)?(\d+)\s+flights?',
#                 r'(?:first|top)\s+(\d+)\s+flights?',
#                 r'(\d+)\s+flights?',
#                 r'any\s+(\d+)'
#             ]
#             for pattern in limit_patterns:
#                 limit_match = re.search(pattern, query_text, re.IGNORECASE)
#                 if limit_match:
#                     result_limit = int(limit_match.group(1))
#                     break
# 
#             # Extract flight number (e.g., AI14110, 6E2345, ai14110, Ai14110) - case insensitive
#             flight_pattern = re.findall(r'\b([A-Za-z]{2}\d{3,5})\b', query_text, re.IGNORECASE)
#             if flight_pattern and 'flight_no' not in data:
#                 conditions.append("flight_no = %s")
#                 params.append(flight_pattern[0].upper())  # Always uppercase for DB
# 
#             # Replace city names with airport codes (case-insensitive)
#             query_processed = query_text
#             for city, code in city_to_code.items():
#                 query_processed = re.sub(r'\b' + city + r'\b', code, query_processed, flags=re.IGNORECASE)
# 
#             # Look for "origin as CODE" or "origin CODE" pattern (case-insensitive)
#             # Matches: "origin LHR", "origin as lhr", "ORIGIN IS Lhr", "origin del"
#             origin_as_pattern = re.search(r'origin\s+(?:(?:as|is|=)\s+)?([A-Za-z]{3})\b', query_processed, re.IGNORECASE)
#             if origin_as_pattern and 'origin' not in data:
#                 conditions.append("origin = %s")
#                 params.append(origin_as_pattern.group(1).upper())  # Always uppercase for DB
#                 print(f"DEBUG: Extracted origin from 'origin [as/is/=] CODE' pattern: {origin_as_pattern.group(1).upper()}")
# 
#             # Look for "destination as CODE" or "destination CODE" pattern (case-insensitive)
#             # Matches: "destination BOM", "DESTINATION AS bom", "Destination is Bom"
#             dest_as_pattern = re.search(r'destination\s+(?:(?:as|is|=)\s+)?([A-Za-z]{3})\b', query_processed, re.IGNORECASE)
#             if dest_as_pattern and 'destination' not in data:
#                 conditions.append("destination = %s")
#                 params.append(dest_as_pattern.group(1).upper())  # Always uppercase for DB
#                 print(f"DEBUG: Extracted destination from 'destination [as/is/=] CODE' pattern: {dest_as_pattern.group(1).upper()}")
# 
#             # IMPROVED Pattern matching - handles "flights from DEL to BOM" (case-insensitive)
#             # Pattern 1: "from ... CODE to CODE" (allows words between from and code)
#             route_pattern = re.search(r'from\s+(?:\w+\s+)*?([A-Za-z]{3})\s+to\s+([A-Za-z]{3})', query_processed, re.IGNORECASE)
#             if route_pattern and 'origin' not in data and 'destination' not in data:
#                 conditions.append("origin = %s")
#                 params.append(route_pattern.group(1).upper())  # Always uppercase for DB
#                 conditions.append("destination = %s")
#                 params.append(route_pattern.group(2).upper())  # Always uppercase for DB
#                 print(f"DEBUG: Extracted route from query: {route_pattern.group(1).upper()} to {route_pattern.group(2).upper()}")
#             else:
#                 # Pattern 2: "from ... CODE" separately (only if not already set by "origin as")
#                 if not origin_as_pattern and 'origin' not in data:
#                     from_pattern = re.search(r'from\s+(?:\w+\s+)*?([A-Za-z]{3})', query_processed, re.IGNORECASE)
#                     if from_pattern:
#                         conditions.append("origin = %s")
#                         params.append(from_pattern.group(1).upper())  # Always uppercase for DB
#                         print(f"DEBUG: Extracted origin: {from_pattern.group(1).upper()}")
# 
#                 # Pattern 3: "to CODE" separately (only if not already set by "destination as")
#                 if not dest_as_pattern and 'destination' not in data:
#                     to_pattern = re.search(r'to\s+([A-Za-z]{3})', query_processed, re.IGNORECASE)
#                     if to_pattern:
#                         conditions.append("destination = %s")
#                         params.append(to_pattern.group(1).upper())  # Always uppercase for DB
#                         print(f"DEBUG: Extracted destination: {to_pattern.group(1).upper()}")
# 
#             # Check for availability keywords (case-insensitive)
#             if re.search(r'\b(available|seats|availability|with seats|has seats)\b', query_text, re.IGNORECASE) and 'min_seats' not in data:
#                 conditions.append("available_seats > 0")
# 
#             # Check for status keywords with NEGATION support (case-insensitive)
#             if 'status' not in data:
#                 query_lower = query_text.lower()  # For easier pattern matching
# 
#                 # Check for NOT/NO negations
#                 is_negated_delayed = any(pattern in query_lower for pattern in [
#                     'not delayed', 'no delayed', 'not be delayed', 'which is not delayed',
#                     'that are not delayed', 'that is not delayed', 'without delay'
#                 ])
#                 is_negated_cancelled = any(pattern in query_lower for pattern in [
#                     'not cancelled', 'not canceled', 'no cancelled', 'no canceled',
#                     'not be cancelled', 'not be canceled'
#                 ])
# 
#                 # Handle multiple negations (BOTH not delayed AND not cancelled = ON_TIME only)
#                 if is_negated_delayed and is_negated_cancelled:
#                     # User wants flights that are NEITHER delayed NOR cancelled = ON_TIME only
#                     conditions.append("status = 'ON_TIME'")
#                     print("DEBUG: Detected NOT DELAYED AND NOT CANCELLED - showing only ON_TIME flights")
#                 # Handle single negations
#                 elif is_negated_delayed:
#                     # User wants flights that are NOT delayed (ON_TIME or CANCELLED)
#                     conditions.append("status != 'DELAYED'")
#                     print("DEBUG: Detected NOT DELAYED - excluding delayed flights")
#                 elif is_negated_cancelled:
#                     # User wants flights that are NOT cancelled (ON_TIME or DELAYED)
#                     conditions.append("status != 'CANCELLED'")
#                     print("DEBUG: Detected NOT CANCELLED - excluding cancelled flights")
#                 # Then check positive matches (only if no negation)
#                 elif 'delayed' in query_lower:
#                     conditions.append("status = 'DELAYED'")
#                     print("DEBUG: Detected DELAYED status")
#                 elif 'cancelled' in query_lower or 'canceled' in query_lower:
#                     conditions.append("status = 'CANCELLED'")
#                     print("DEBUG: Detected CANCELLED status")
#                 elif 'on time' in query_lower or 'on-time' in query_lower or 'ontime' in query_lower:
#                     conditions.append("status = 'ON_TIME'")
#                     print("DEBUG: Detected ON_TIME status")
# 
# 
#         # Allow limit override from request body
#         if 'limit' in data and data['limit']:
#             result_limit = int(data['limit'])
# 
#         # Build final SQL query
#         sql = "SELECT * FROM flights"
#         if conditions:
#             sql += " WHERE " + " AND ".join(conditions)
#         sql += f" ORDER BY departure_time LIMIT {result_limit};"
# 
#         cursor.execute(sql, params)
#         flights = cursor.fetchall()
#         cursor.close()
#         conn.close()
# 
#         # Convert to list of dicts and format for watsonx
#         results = []
#         for flight in flights:
#             flight_dict = dict(flight)
# 
#             # Convert datetime objects to strings
#             for key, value in flight_dict.items():
#                 if hasattr(value, 'isoformat'):
#                     flight_dict[key] = value.isoformat()
# 
#             # Format as document with 'body' field for watsonx
#             formatted_result = {
#                 "title": f"Flight {flight_dict.get('flight_no', 'N/A')} - {flight_dict.get('origin', '')} to {flight_dict.get('destination', '')}",
#                 "body": f"""Flight Number: {flight_dict.get('flight_no', 'N/A')}
# Route: {flight_dict.get('origin', 'N/A')} → {flight_dict.get('destination', 'N/A')}
# Departure: {flight_dict.get('departure_time', 'N/A')} from Terminal {flight_dict.get('terminal', 'N/A')}, Gate {flight_dict.get('gate', 'N/A')}
# Arrival: {flight_dict.get('arrival_time', 'N/A')}
# Duration: {flight_dict.get('flight_duration_minutes', 'N/A')} minutes
# Status: {flight_dict.get('status', 'N/A')}
# Aircraft: {flight_dict.get('aircraft_type', 'N/A')} (ID: {flight_dict.get('aircraft_id', 'N/A')})
# 
# Seat Availability:
# - Total available: {flight_dict.get('available_seats', 'N/A')} out of {flight_dict.get('capacity', 'N/A')} seats
# - Economy: {flight_dict.get('booking_class_availability_economy', 'N/A')} seats
# - Premium Economy: {flight_dict.get('booking_class_availability_premium', 'N/A')} seats
# - Business: {flight_dict.get('booking_class_availability_business', 'N/A')} seats
# 
# Additional Information:
# - Reliability Rating: {flight_dict.get('operational_reliability_rating', 'N/A')}
# - Codeshare: {flight_dict.get('is_codeshare', 'N/A')}
# - Meal Service: {flight_dict.get('meal_service_available', 'N/A')}
# - Min Connection Time: {flight_dict.get('min_connect_time_required', 'N/A')} minutes""",
#                 "metadata": flight_dict,  # Keep all raw data in metadata
#                 "flight_no": flight_dict.get('flight_no'),
#                 "origin": flight_dict.get('origin'),
#                 "destination": flight_dict.get('destination'),
#                 "status": flight_dict.get('status'),
#                 "available_seats": flight_dict.get('available_seats')
#             }
#             results.append(formatted_result)
# 
#         # Return in watsonx expected format
#         response_data = {
#             "count": len(results),
#             "search_results": results,
#             "query_parsed": {
#                 "conditions": conditions,
#                 "parameters": params
#             }
#         }
# 
#         print("="*80)
#         print("RETURNING RESPONSE")
#         print(f"Count: {len(results)}")
#         print(f"First result (if any): {results[0] if results else 'No results'}")
#         print("="*80)
# 
#         return jsonify(response_data)
# 
#     except Exception as e:
#         print(f"ERROR in search_flights: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500

@app.route('/routes', methods=['GET'])
def get_routes():
    """Get all unique routes"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT DISTINCT origin, destination, COUNT(*) as flight_count
            FROM flights
            GROUP BY origin, destination
            ORDER BY origin, destination;
        """)
        routes = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify({
            "count": len(routes),
            "routes": [dict(route) for route in routes]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("Flight Data API - Starting...")
    print("=" * 60)
    print("\nAPI Endpoints:")
    print("  GET  /              - API info")
    print("  GET  /health        - Health check")
    print("  GET  /flight/<no>   - Get specific flight")
    print("  POST /search        - Search flights")
    print("  GET  /routes        - Get all routes")
    print("\nStarting server on http://0.0.0.0:5000")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    app.run(host='0.0.0.0', port=5001, debug=True)
