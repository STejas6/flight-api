# Quick Reference - watsonx Custom Service Configuration

## IMMEDIATE COPY-PASTE VALUES FOR WATSONX

### 1. Custom Service URL
**After deploying to Render:**
```
https://YOUR-APP-NAME.onrender.com
```

**For ngrok testing (temporary):**
```
https://YOUR-NGROK-ID.ngrok-free.app
```

---

### 2. Authentication Type
```
None
```

---

### 3. Default Filter
```json
{
  "min_seats": 1
}
```

---

### 4. Metadata
```json
{
  "description": "Flight schedule database with 5000 flights containing real-time status, availability, and routing information",
  "data_type": "structured",
  "source": "PostgreSQL database via REST API",
  "update_frequency": "real-time",
  "fields": ["flight_no", "origin", "destination", "departure_time", "arrival_time", "status", "available_seats", "aircraft_type"],
  "search_endpoint": "/search",
  "retrieval_method": "POST"
}
```

---

### 5. Knowledge Base Description (for Agent Behavior)

**Short Version (if character limit):**
```
FLIGHT DATABASE ACCESS:
You have access to 5,000 flights via REST API.

CRITICAL RULES:
1. ALWAYS include flight_no in responses (mandatory identifier)
2. For availability: use available_seats > 0
3. Status values: ON_TIME, DELAYED, CANCELLED (exact match only)
4. Airport codes: BOM (Mumbai), DEL (Delhi), BLR (Bangalore), MAA (Chennai), etc.

QUERY METHODS:
- Natural language: {"query": "flights from DEL to BOM with seats"}
- Structured: {"origin": "DEL", "destination": "BOM", "min_seats": 1}
- Specific flight: GET /flight/AI14110

RESPONSE FORMAT:
Flight [flight_no]: [origin] → [destination]
Departure: [time] | Arrival: [time] | Status: [status] | Seats: [available]
```

**Full Version:**
See `WATSONX_CONFIGURATION.md` file - copy the entire "KNOWLEDGE BASE DESCRIPTION" section.

---

## QUICK START STEPS

### Option 1: Using ngrok (Immediate Testing - 5 minutes)

1. **Install ngrok:**
   ```bash
   brew install ngrok
   ```

2. **Start your Flask API:**
   ```bash
   cd "/Users/tejas.s02/Downloads/Watsonx_AgenticAI/New Generated Data/FreshData"
   python3 flight_api.py
   ```

3. **Start ngrok (new terminal):**
   ```bash
   ngrok http 5001
   ```

4. **Copy the ngrok URL** (e.g., `https://abc123.ngrok-free.app`)

5. **Configure watsonx:**
   - Knowledge Source → Custom Service
   - URL: Your ngrok URL
   - Authentication: None
   - Default Filter: `{"min_seats": 1}`
   - Paste Knowledge Base Description

6. **Test in watsonx:**
   - "flight details of AI14110"
   - "flights from DEL to BOM with available seats"

---

### Option 2: Deploy to Render (Permanent - 15 minutes)

1. **Push code to GitHub:**
   ```bash
   cd "/Users/tejas.s02/Downloads/Watsonx_AgenticAI/New Generated Data/FreshData/render"
   git init
   git add .
   git commit -m "Flight API"
   git remote add origin https://github.com/YOUR_USERNAME/flight-api.git
   git push -u origin main
   ```

2. **Deploy on Render:**
   - Go to https://render.com
   - New → Web Service
   - Connect GitHub repo
   - Name: flight-data-api
   - Environment: Python 3
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app`
   - Add env var: `DATABASE_URL` = [your Neon connection string]
   - Deploy (takes 3-5 minutes)

3. **Copy Render URL** (e.g., `https://flight-data-api.onrender.com`)

4. **Configure watsonx** (same as Option 1, but use Render URL)

---

## TEST QUERIES FOR WATSONX

After configuration, test with these:

1. ✅ "flight details of AI14110"
2. ✅ "flights from DEL to BOM with available seats"
3. ✅ "show me all delayed flights"
4. ✅ "which flights go from Mumbai to Bangalore"
5. ✅ "is flight AI14110 on time"
6. ✅ "list flights with more than 50 seats available"

---

## TROUBLESHOOTING CHECKLIST

- [ ] API URL is correct and accessible
- [ ] API returns JSON when you curl `/health`
- [ ] Default Filter is valid JSON
- [ ] Metadata is valid JSON
- [ ] Knowledge Base Description is pasted completely
- [ ] Agent behavior includes query interpretation rules
- [ ] Test queries return results in watsonx chat

---

## API ENDPOINTS SUMMARY

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Check if API and DB are working |
| `/flight/<flight_no>` | GET | Get specific flight details |
| `/search` | POST | Search flights (main endpoint) |
| `/routes` | GET | List all available routes |

---

## IMPORTANT NOTES

⚠️ **ngrok free tier**: URL changes each time you restart ngrok
✅ **Render free tier**: Permanent URL, but sleeps after 15 min inactivity
💰 **Cost**: Everything is FREE for testing (Neon + Render + ngrok)

🔒 **Security**: No authentication configured (fine for testing, add API key for production)

⏱️ **Performance**: First request after idle may take 30 seconds (Render waking up)

---

## FILE LOCATIONS

All deployment files are in:
```
/Users/tejas.s02/Downloads/Watsonx_AgenticAI/New Generated Data/FreshData/render/
```

Files:
- `app.py` - Flask API application
- `requirements.txt` - Python dependencies
- `Procfile` - Render deployment config
- `DEPLOYMENT_STEPS.md` - Detailed deployment guide
- `WATSONX_CONFIGURATION.md` - Complete watsonx setup (THIS FILE)
- `QUICK_REFERENCE.md` - Quick copy-paste values

---

## NEXT STEPS AFTER SETUP

1. Test all queries in watsonx
2. Monitor API usage in Render/ngrok dashboard
3. Add more test flights to Neon database if needed
4. Implement API key authentication for production
5. Consider upgrading Render to paid tier ($7/mo) for always-on API

---

End of Quick Reference
