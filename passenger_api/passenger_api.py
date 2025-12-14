#!/usr/bin/env python3
"""
Passenger Information API
Provides categorized, prioritized passenger information for watsonx agents
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os
import json
import logging

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL',
    "postgresql://neondb_owner:npg_EayzTwrm2B6S@ep-autumn-band-aebfrz67-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Table name
TABLE_NAME = "passengers"

def get_db_connection():
    """Create database connection"""
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def get_table_schema():
    """Get table schema for dynamic queries"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (TABLE_NAME,))
    schema = {row[0]: row[1] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return schema

# Load schema at startup
SCHEMA = get_table_schema()
logger.info(f"Loaded schema for {TABLE_NAME}: {list(SCHEMA.keys())}")

def categorize_passengers(passengers):
    """
    Categorize and prioritize passengers based on tier, special needs, age, etc.
    Returns structured JSON with priority ordering
    """
    categorized = {
        "total_count": len(passengers),
        "by_tier": {
            "Platinum": [],
            "Gold": [],
            "Silver": [],
            "None": []
        },
        "special_needs": [],
        "elderly": [],  # age >= 65
        "families": [],  # Groups with same PNR
        "wheelchair_required": [],
        "priority_order": []
    }

    pnr_groups = {}

    for passenger in passengers:
        # Extract data
        p_id = passenger.get('passenger_id')
        name = passenger.get('name')
        age = passenger.get('age')
        tier = passenger.get('loyalty_tier') or 'None'
        special_needs = passenger.get('special_needs', '[]')
        wheelchair = passenger.get('wheelchair_or_medical_time_required', False)
        pnr = passenger.get('pnr')

        # Parse special_needs JSON if it's a string
        if isinstance(special_needs, str):
            try:
                special_needs = json.loads(special_needs)
            except:
                special_needs = []

        # Categorize by tier
        if tier in categorized["by_tier"]:
            categorized["by_tier"][tier].append(passenger)
        else:
            categorized["by_tier"]["None"].append(passenger)

        # Special needs
        if special_needs and len(special_needs) > 0:
            categorized["special_needs"].append({
                **passenger,
                "needs_list": special_needs
            })

        # Elderly (65+)
        if age and age >= 65:
            categorized["elderly"].append(passenger)

        # Wheelchair
        if wheelchair:
            categorized["wheelchair_required"].append(passenger)

        # Group by PNR for family detection
        if pnr:
            if pnr not in pnr_groups:
                pnr_groups[pnr] = []
            pnr_groups[pnr].append(passenger)

    # Identify families (PNR with 2+ passengers)
    for pnr, group in pnr_groups.items():
        if len(group) >= 2:
            categorized["families"].append({
                "pnr": pnr,
                "passenger_count": len(group),
                "passengers": group
            })

    # Priority ordering (highest to lowest priority)
    # 1. Wheelchair/medical needs
    # 2. Platinum tier
    # 3. Elderly (65+)
    # 4. Gold tier
    # 5. Special needs
    # 6. Silver tier
    # 7. Others

    priority_buckets = [
        ("Wheelchair/Medical", categorized["wheelchair_required"]),
        ("Platinum Tier", categorized["by_tier"]["Platinum"]),
        ("Elderly (65+)", categorized["elderly"]),
        ("Gold Tier", categorized["by_tier"]["Gold"]),
        ("Special Needs", categorized["special_needs"]),
        ("Silver Tier", categorized["by_tier"]["Silver"]),
        ("Standard", categorized["by_tier"]["None"])
    ]

    for category_name, bucket in priority_buckets:
        for passenger in bucket:
            # Avoid duplicates in priority list
            p_id = passenger.get('passenger_id')
            if not any(p.get('passenger_id') == p_id for p in categorized["priority_order"]):
                categorized["priority_order"].append({
                    **passenger,
                    "priority_category": category_name
                })

    return categorized

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()

        return jsonify({
            "status": "healthy",
            "database": "connected",
            "total_passengers": count
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

@app.route('/passengers/flight/<flight_no>', methods=['GET'])
def get_passengers_by_flight(flight_no):
    """
    Get all passengers for a specific flight with categorization and priority ordering
    """
    logger.info(f"Getting passengers for flight: {flight_no}")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Query passengers for this flight
        query = f"SELECT * FROM {TABLE_NAME} WHERE UPPER(flight_no) = UPPER(%s) ORDER BY passenger_priority_score DESC"
        cur.execute(query, (flight_no,))

        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

        if not rows:
            cur.close()
            conn.close()
            return jsonify({
                "flight_no": flight_no,
                "message": "No passengers found for this flight",
                "passengers": [],
                "categorized": {
                    "total_count": 0,
                    "by_tier": {"Platinum": [], "Gold": [], "Silver": [], "None": []},
                    "special_needs": [],
                    "elderly": [],
                    "families": [],
                    "wheelchair_required": [],
                    "priority_order": []
                }
            })

        # Convert to list of dicts
        passengers = [dict(zip(columns, row)) for row in rows]

        # Categorize and prioritize
        categorized = categorize_passengers(passengers)

        cur.close()
        conn.close()

        return jsonify({
            "flight_no": flight_no,
            "passengers": passengers,
            "categorized": categorized
        })

    except Exception as e:
        logger.error(f"Error getting passengers for flight {flight_no}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/passengers/search', methods=['POST'])
def search_passengers():
    """
    Search passengers with filters
    Supports: flight_no, pnr, loyalty_tier, ticket_class, special_needs, email, phone
    """
    try:
        payload = request.get_json()
        logger.info(f"Passenger search request: {json.dumps(payload, indent=2)}")

        filters = []
        values = []

        # Extract known parameters
        flight_no = payload.get('flight_no')
        pnr = payload.get('pnr')
        loyalty_tier = payload.get('loyalty_tier')
        ticket_class = payload.get('ticket_class')
        email = payload.get('email')
        phone = payload.get('phone')
        wheelchair_required = payload.get('wheelchair_or_medical_time_required')
        min_age = payload.get('min_age')  # For elderly queries
        limit = payload.get('limit', 100)

        if flight_no:
            filters.append("UPPER(flight_no) = UPPER(%s)")
            values.append(flight_no)

        if pnr:
            filters.append("UPPER(pnr) = UPPER(%s)")
            values.append(pnr)

        if loyalty_tier:
            filters.append("UPPER(loyalty_tier) = UPPER(%s)")
            values.append(loyalty_tier)

        if ticket_class:
            filters.append("UPPER(ticket_class) = UPPER(%s)")
            values.append(ticket_class)

        if email:
            filters.append("LOWER(email) = LOWER(%s)")
            values.append(email)

        if phone:
            filters.append("phone = %s")
            values.append(phone)

        if wheelchair_required is not None:
            filters.append("wheelchair_or_medical_time_required = %s")
            values.append(wheelchair_required)

        if min_age:
            filters.append("age >= %s")
            values.append(int(min_age))

        # Build query
        query = f"SELECT * FROM {TABLE_NAME}"
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY passenger_priority_score DESC LIMIT %s"
        values.append(int(limit))

        logger.info(f"Executing query: {query}")
        logger.info(f"With values: {values}")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, values)

        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

        passengers = [dict(zip(columns, row)) for row in rows]

        # Categorize results
        categorized = categorize_passengers(passengers)

        cur.close()
        conn.close()

        return jsonify({
            "search_criteria": payload,
            "result_count": len(passengers),
            "passengers": passengers,
            "categorized": categorized
        })

    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/passengers/pnr/<pnr>', methods=['GET'])
def get_passengers_by_pnr(pnr):
    """
    Get all passengers with the same PNR (family/group booking)
    """
    logger.info(f"Getting passengers for PNR: {pnr}")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = f"SELECT * FROM {TABLE_NAME} WHERE UPPER(pnr) = UPPER(%s) ORDER BY passenger_priority_score DESC"
        cur.execute(query, (pnr,))

        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

        passengers = [dict(zip(columns, row)) for row in rows]

        cur.close()
        conn.close()

        return jsonify({
            "pnr": pnr,
            "passenger_count": len(passengers),
            "passengers": passengers,
            "is_group_booking": len(passengers) > 1
        })

    except Exception as e:
        logger.error(f"Error getting PNR {pnr}: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
