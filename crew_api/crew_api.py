#!/usr/bin/env python3
"""
Crew Management API
Provides crew and crew assignment information for watsonx agents
Handles crew availability, assignments, and disruption management
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os
import logging
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

def get_db_connection():
    """Create database connection"""
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def dict_from_row(cursor, row):
    """Convert database row to dictionary"""
    if not row:
        return None
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))

def dicts_from_rows(cursor, rows):
    """Convert database rows to list of dictionaries"""
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in rows]

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM crew")
        crew_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM crew_assignments")
        assignment_count = cur.fetchone()[0]
        cur.close()
        conn.close()

        return jsonify({
            "status": "healthy",
            "database": "connected",
            "total_crew": crew_count,
            "total_assignments": assignment_count
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

@app.route('/crew/search', methods=['POST'])
def search_crew():
    """
    Search crew members with filters
    Supports: role, certifications, base_airport, current_location, current_status,
              max_duty_hours, available_after, available_before, limit
    """
    try:
        payload = request.get_json()
        logger.info(f"Crew search request: {payload}")

        filters = []
        values = []

        # Extract parameters
        role = payload.get('role')
        certifications = payload.get('certifications')  # Aircraft type
        base_airport = payload.get('base_airport')
        current_location = payload.get('current_location')
        current_status = payload.get('current_status')
        max_duty_hours = payload.get('max_duty_hours')  # Filter crew under this limit
        available_after = payload.get('available_after')  # ISO timestamp
        available_before = payload.get('available_before')  # ISO timestamp
        limit = payload.get('limit', 50)

        if role:
            filters.append("UPPER(role) = UPPER(%s)")
            values.append(role)

        if certifications:
            # Check if crew has this certification (aircraft type)
            filters.append("UPPER(certifications) LIKE UPPER(%s)")
            values.append(f"%{certifications}%")

        if base_airport:
            filters.append("UPPER(base_airport) = UPPER(%s)")
            values.append(base_airport)

        if current_location:
            filters.append("UPPER(current_location) = UPPER(%s)")
            values.append(current_location)

        if current_status:
            filters.append("UPPER(current_status) = UPPER(%s)")
            values.append(current_status)

        if max_duty_hours is not None:
            # Find crew with duty hours LESS than this value
            filters.append("duty_hours_last_7d < %s")
            values.append(float(max_duty_hours))

        if available_after:
            # Find crew available AFTER this time (next_legal_availability <= time)
            filters.append("next_legal_availability <= %s")
            values.append(available_after)

        if available_before:
            # Find crew available BEFORE this time
            filters.append("next_legal_availability >= %s")
            values.append(available_before)

        # Build query
        query = "SELECT * FROM crew"
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY next_legal_availability, duty_hours_last_7d LIMIT %s"
        values.append(int(limit))

        logger.info(f"Executing query: {query}")
        logger.info(f"With values: {values}")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, values)

        rows = cur.fetchall()
        crew_list = dicts_from_rows(cur, rows)

        cur.close()
        conn.close()

        # Categorize results
        categorized = categorize_crew(crew_list)

        return jsonify({
            "search_criteria": payload,
            "count": len(crew_list),
            "crew": crew_list,
            "categorized": categorized
        })

    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/crew/<crew_id>', methods=['GET'])
def get_crew_details(crew_id):
    """
    Get specific crew member details including all their assignments
    """
    logger.info(f"Getting details for crew: {crew_id}")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get crew details
        cur.execute("SELECT * FROM crew WHERE UPPER(crew_id) = UPPER(%s)", (crew_id,))
        crew_row = cur.fetchone()

        if not crew_row:
            cur.close()
            conn.close()
            return jsonify({"error": f"Crew member {crew_id} not found"}), 404

        crew = dict_from_row(cur, crew_row)

        # Get all assignments for this crew member
        cur.execute("""
            SELECT * FROM crew_assignments
            WHERE UPPER(crew_id) = UPPER(%s)
            ORDER BY flight_date DESC
        """, (crew_id,))

        assignment_rows = cur.fetchall()
        assignments = dicts_from_rows(cur, assignment_rows)

        cur.close()
        conn.close()

        return jsonify({
            "crew": crew,
            "assignments": assignments,
            "assignment_count": len(assignments)
        })

    except Exception as e:
        logger.error(f"Error getting crew {crew_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/crew/flight/<flight_no>', methods=['GET'])
def get_crew_by_flight(flight_no):
    """
    Get all crew members assigned to a specific flight with flight details
    """
    logger.info(f"Getting crew for flight: {flight_no}")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # First, get flight details
        cur.execute("""
            SELECT
                flight_no,
                aircraft_type,
                origin,
                destination,
                departure_time,
                arrival_time,
                status
            FROM flights
            WHERE UPPER(flight_no) = UPPER(%s)
            LIMIT 1
        """, (flight_no,))

        flight_row = cur.fetchone()
        flight_details = dict_from_row(cur, flight_row) if flight_row else None

        # Get crew assignments for this flight with crew details
        cur.execute("""
            SELECT
                ca.assignment_id,
                ca.crew_id,
                ca.flight_no,
                ca.role AS assignment_role,
                ca.flight_date,
                ca.origin,
                ca.destination,
                ca.status AS assignment_status,
                c.name,
                c.role AS crew_role,
                c.certifications,
                c.base_airport,
                c.current_location,
                c.current_status,
                c.duty_hours_last_7d,
                c.max_duty_limit_hours,
                c.next_legal_availability
            FROM crew_assignments ca
            JOIN crew c ON ca.crew_id = c.crew_id
            WHERE UPPER(ca.flight_no) = UPPER(%s)
            ORDER BY ca.role, c.name
        """, (flight_no,))

        rows = cur.fetchall()
        crew_assignments = dicts_from_rows(cur, rows)

        cur.close()
        conn.close()

        if not crew_assignments:
            return jsonify({
                "flight_no": flight_no,
                "flight_details": flight_details,
                "message": "No crew assigned to this flight",
                "crew": [],
                "count": 0
            })

        # Check certification match if flight details available
        certification_status = []
        if flight_details and flight_details.get('aircraft_type'):
            required_cert = flight_details['aircraft_type']
            for crew in crew_assignments:
                crew_certs = crew.get('certifications', '').upper()
                has_cert = required_cert.upper() in crew_certs
                certification_status.append({
                    "crew_id": crew.get('crew_id'),
                    "name": crew.get('name'),
                    "role": crew.get('assignment_role'),
                    "has_required_certification": has_cert,
                    "required": required_cert,
                    "has": crew.get('certifications')
                })

        # Categorize by role
        by_role = {
            "Pilot": [],
            "Co-Pilot": [],
            "Cabin Crew": []
        }

        for crew in crew_assignments:
            role = crew.get('assignment_role', crew.get('crew_role', 'Unknown'))
            if role in by_role:
                by_role[role].append(crew)

        return jsonify({
            "flight_no": flight_no,
            "flight_details": flight_details,
            "crew": crew_assignments,
            "count": len(crew_assignments),
            "by_role": by_role,
            "certification_status": certification_status
        })

    except Exception as e:
        logger.error(f"Error getting crew for flight {flight_no}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/assignments/search', methods=['POST'])
def search_assignments():
    """
    Search crew assignments
    Supports: crew_id, flight_no, role, status, flight_date_after, flight_date_before,
              origin, destination, limit
    """
    try:
        payload = request.get_json()
        logger.info(f"Assignment search request: {payload}")

        filters = []
        values = []

        crew_id = payload.get('crew_id')
        flight_no = payload.get('flight_no')
        role = payload.get('role')
        status = payload.get('status')
        flight_date_after = payload.get('flight_date_after')
        flight_date_before = payload.get('flight_date_before')
        origin = payload.get('origin')
        destination = payload.get('destination')
        limit = payload.get('limit', 100)

        if crew_id:
            filters.append("UPPER(crew_id) = UPPER(%s)")
            values.append(crew_id)

        if flight_no:
            filters.append("UPPER(flight_no) = UPPER(%s)")
            values.append(flight_no)

        if role:
            filters.append("UPPER(role) = UPPER(%s)")
            values.append(role)

        if status:
            filters.append("UPPER(status) = UPPER(%s)")
            values.append(status)

        if flight_date_after:
            filters.append("flight_date >= %s")
            values.append(flight_date_after)

        if flight_date_before:
            filters.append("flight_date <= %s")
            values.append(flight_date_before)

        if origin:
            filters.append("UPPER(origin) = UPPER(%s)")
            values.append(origin)

        if destination:
            filters.append("UPPER(destination) = UPPER(%s)")
            values.append(destination)

        query = "SELECT * FROM crew_assignments"
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY flight_date DESC LIMIT %s"
        values.append(int(limit))

        logger.info(f"Executing query: {query}")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, values)

        rows = cur.fetchall()
        assignments = dicts_from_rows(cur, rows)

        cur.close()
        conn.close()

        return jsonify({
            "search_criteria": payload,
            "count": len(assignments),
            "assignments": assignments
        })

    except Exception as e:
        logger.error(f"Assignment search error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/crew/available', methods=['POST'])
def find_available_crew():
    """
    Find available crew for disruption management
    Specialized endpoint that combines multiple filters for replacement crew
    Supports: certifications_required, location, role, available_after, max_duty_hours
    """
    try:
        payload = request.get_json()
        logger.info(f"Available crew search: {payload}")

        filters = []
        values = []

        certifications_required = payload.get('certifications_required')  # Aircraft type
        location = payload.get('location')  # Airport code
        role = payload.get('role')  # Pilot, Co-Pilot, Cabin Crew
        available_after = payload.get('available_after')  # ISO timestamp
        max_duty_hours = payload.get('max_duty_hours', 50)  # Default to 50 hours
        limit = payload.get('limit', 20)

        # Must be in AVAILABLE, STANDBY_AIRPORT, or STANDBY_HOME status
        filters.append("current_status IN ('AVAILABLE', 'STANDBY_AIRPORT', 'STANDBY_HOME')")

        if certifications_required:
            filters.append("UPPER(certifications) LIKE UPPER(%s)")
            values.append(f"%{certifications_required}%")

        if location:
            # Match either base_airport or current_location
            filters.append("(UPPER(base_airport) = UPPER(%s) OR UPPER(current_location) = UPPER(%s))")
            values.append(location)
            values.append(location)

        if role:
            filters.append("UPPER(role) = UPPER(%s)")
            values.append(role)

        if available_after:
            filters.append("next_legal_availability <= %s")
            values.append(available_after)

        # Duty hours constraint
        filters.append("duty_hours_last_7d < %s")
        values.append(float(max_duty_hours))

        query = "SELECT * FROM crew WHERE " + " AND ".join(filters)
        query += " ORDER BY next_legal_availability, duty_hours_last_7d LIMIT %s"
        values.append(int(limit))

        logger.info(f"Executing query: {query}")
        logger.info(f"With values: {values}")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, values)

        rows = cur.fetchall()
        available_crew = dicts_from_rows(cur, rows)

        cur.close()
        conn.close()

        # Categorize by availability status
        categorized = {
            "immediate": [],  # AVAILABLE or next_legal_availability is past
            "standby_airport": [],  # At airport on standby
            "standby_home": [],  # At home on standby
            "soon": []  # Available within next few hours
        }

        now = datetime.utcnow()
        for crew in available_crew:
            status = crew.get('current_status', '')
            next_avail = crew.get('next_legal_availability')

            if isinstance(next_avail, str):
                next_avail = datetime.fromisoformat(next_avail.replace('Z', '+00:00'))

            if status == 'AVAILABLE' or (next_avail and next_avail <= now):
                categorized['immediate'].append(crew)
            elif status == 'STANDBY_AIRPORT':
                categorized['standby_airport'].append(crew)
            elif status == 'STANDBY_HOME':
                categorized['standby_home'].append(crew)
            else:
                categorized['soon'].append(crew)

        return jsonify({
            "search_criteria": payload,
            "count": len(available_crew),
            "available_crew": available_crew,
            "categorized": categorized
        })

    except Exception as e:
        logger.error(f"Available crew search error: {str(e)}")
        return jsonify({"error": str(e)}), 500

def categorize_crew(crew_list):
    """Categorize crew members for easier analysis"""
    categorized = {
        "by_role": {
            "Pilot": [],
            "Co-Pilot": [],
            "Cabin Crew": []
        },
        "by_status": {
            "AVAILABLE": [],
            "STANDBY_AIRPORT": [],
            "STANDBY_HOME": [],
            "RESTING": [],
            "UNAVAILABLE": []
        },
        "low_duty_hours": [],  # Under 30 hours
        "high_duty_hours": [],  # Over 45 hours
        "available_now": []  # Available immediately
    }

    now = datetime.utcnow()

    for crew in crew_list:
        role = crew.get('role', 'Unknown')
        status = crew.get('current_status', 'UNAVAILABLE')
        duty_hours = crew.get('duty_hours_last_7d', 0)
        next_avail = crew.get('next_legal_availability')

        # By role
        if role in categorized['by_role']:
            categorized['by_role'][role].append(crew)

        # By status
        if status in categorized['by_status']:
            categorized['by_status'][status].append(crew)

        # Duty hours
        if duty_hours < 30:
            categorized['low_duty_hours'].append(crew)
        elif duty_hours > 45:
            categorized['high_duty_hours'].append(crew)

        # Available now
        if isinstance(next_avail, str):
            try:
                next_avail = datetime.fromisoformat(next_avail.replace('Z', '+00:00'))
            except:
                next_avail = None

        if next_avail and next_avail <= now:
            categorized['available_now'].append(crew)

    return categorized

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=True)
