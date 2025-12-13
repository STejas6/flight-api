# Passenger Information API - Deployment Guide

## Overview
This API provides categorized passenger information for watsonx Orchestrate agents managing flight disruptions.

## Files Created
- `passenger_api.py` - Main Flask API
- `passenger_api_openapi.json` - OpenAPI specification for watsonx Tools
- `PASSENGER_AGENT_BEHAVIOR.txt` - Agent behavior instructions for watsonx
- `requirements.txt` - Python dependencies
- `runtime.txt` - Python version (3.11.9)
- `Procfile` - Render deployment configuration

---

## DEPLOYMENT OPTIONS

### Option 1: New GitHub Repo (Cleaner, Recommended for Simplicity)
### Option 2: Same Repo as Flight API (Efficient, Single Repo Management)

We'll use **Option 2** - same repo, separate Render service.

---

## STEP-BY-STEP DEPLOYMENT TO RENDER

### STEP 1: Push to GitHub

If you haven't already, initialize git in the parent directory:

```bash
cd "/Users/tejas.s02/Downloads/Watsonx_AgenticAI/New Generated Data/FreshData"
git init
git add .
git commit -m "Add passenger API"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

**OR** if you already have the flight API in GitHub, just add and push:

```bash
cd "/Users/tejas.s02/Downloads/Watsonx_AgenticAI/New Generated Data/FreshData"
git add "Python and Insert scripts/Passenger watsonx/"
git commit -m "Add passenger information API"
git push
```

### STEP 2: Create New Web Service in Render

1. Go to https://dashboard.render.com/
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository (if not already connected)
4. Click **"Configure account"** and authorize Render to access your repo

### STEP 3: Configure Passenger API Service

**Basic Settings:**
- **Name:** `passenger-api` (or your choice)
- **Region:** Same as flight API (for consistent latency)
- **Branch:** `main`
- **Root Directory:** `Python and Insert scripts/Passenger watsonx`
  - ⚠️ **IMPORTANT:** This tells Render to use this subdirectory as the app root
- **Runtime:** `Python 3`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn passenger_api:app`
  - (This overrides Procfile if specified, but Procfile is already correct)

**Environment Variables:**
Click **"Advanced"** → **"Add Environment Variable"**

Add this variable:
- **Key:** `DATABASE_URL`
- **Value:** `<YOUR_NEON_DATABASE_URL>`
  - ⚠️ Use the SAME database URL as your flight API
  - It connects to the same database but queries the `passengers` table

**Instance Type:**
- Select **"Free"** (same as flight API)

### STEP 4: Deploy

1. Click **"Create Web Service"**
2. Wait for deployment (2-3 minutes)
3. Watch the build logs:
   - Should show: `Installing Python version 3.11.9...`
   - Should show: `Installing dependencies...`
   - Should show: `Starting gunicorn...`
4. When complete, you'll see: **"Live ✓"** with a green indicator

### STEP 5: Get Your API URL

Your passenger API will be deployed at:
```
https://passenger-api-XXXX.onrender.com
```

Copy this URL - you'll need it for watsonx configuration.

### STEP 6: Test the API

**Test 1: Health Check**
```bash
curl https://passenger-api-XXXX.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "total_passengers": 10000
}
```

**Test 2: Get Passengers for a Flight**
```bash
curl https://passenger-api-XXXX.onrender.com/passengers/flight/AI6117
```

Should return passengers with categorization.

**Test 3: Search with Filters**
```bash
curl -X POST https://passenger-api-XXXX.onrender.com/passengers/search \
  -H "Content-Type: application/json" \
  -d '{"flight_no": "AI6117", "min_age": 65}'
```

Should return elderly passengers on flight AI6117.

---

## STEP 7: Configure watsonx Orchestrate

### 7a. Update OpenAPI Specification

Before uploading to watsonx, update the server URL in `passenger_api_openapi.json`:

```json
"servers": [
  {
    "url": "https://passenger-api-XXXX.onrender.com",
    "description": "Passenger API Production Server"
  }
]
```

Replace `XXXX` with your actual Render subdomain.

### 7b. Create New Agent in watsonx Orchestrate

1. Go to watsonx Orchestrate
2. Create a new agent (separate from flight agent)
3. **Name:** "Passenger Information Assistant"
4. **Description:** "Manages passenger information during flight disruptions"

### 7c. Add Tools Integration

1. In the agent configuration, go to **"Tools"**
2. Click **"Add Tool"** → **"OpenAPI Specification"**
3. Upload `passenger_api_openapi.json` (with updated URL)
4. watsonx will detect 4 operations:
   - `getPassengersByFlight`
   - `searchPassengers`
   - `getPassengersByPnr`
   - `healthCheck`

### 7d. Add Behavior Instructions

1. Go to **"Instructions"** or **"Behavior"** section
2. Copy the entire contents of `PASSENGER_AGENT_BEHAVIOR.txt`
3. Paste into the agent's instruction field
4. Save the agent

---

## ARCHITECTURE SUMMARY

You now have **TWO separate agents** with **TWO separate APIs**:

### Agent 1: Flight Information
- **API:** `https://flight-api-e9zf.onrender.com`
- **Purpose:** Search flights, check status, find available seats
- **Database Table:** `flights`

### Agent 2: Passenger Information
- **API:** `https://passenger-api-XXXX.onrender.com`
- **Purpose:** Manage passengers during disruptions, categorize by priority
- **Database Table:** `passengers`

**Both APIs:**
- Connect to the SAME Neon PostgreSQL database
- Use the SAME DATABASE_URL environment variable
- Query different tables
- Deployed as separate Render services
- Live in the same GitHub repo (different subdirectories)

---

## GITHUB REPOSITORY STRUCTURE

```
Watsonx_AgenticAI/
└── New Generated Data/
    └── FreshData/
        ├── render_deployment/          # Flight API
        │   ├── app.py
        │   ├── requirements.txt
        │   ├── runtime.txt
        │   └── Procfile
        │
        └── Python and Insert scripts/
            ├── Passenger watsonx/      # Passenger API (NEW)
            │   ├── passenger_api.py
            │   ├── passenger_api_openapi.json
            │   ├── PASSENGER_AGENT_BEHAVIOR.txt
            │   ├── requirements.txt
            │   ├── runtime.txt
            │   └── Procfile
            │
            ├── 01_create_passengers_table.sql
            ├── 02_insert_passengers_part01.sql
            ├── ... (other SQL files)
            └── generate_passengers_inserts.py
```

---

## TESTING SCENARIOS

After deployment, test these queries in watsonx:

1. **"Which passengers are affected by flight AI6117 being cancelled?"**
   - Should use `getPassengersByFlight`
   - Should return categorized list with priority order

2. **"Show me elderly passengers on flight AI6117"**
   - Should use `searchPassengers` with `min_age: 65`
   - Should return elderly passengers only

3. **"Who needs wheelchair assistance?"**
   - Should use `searchPassengers` with `wheelchair_or_medical_time_required: true`
   - Should return wheelchair passengers

4. **"Are there any families on this flight?"**
   - Should use `getPassengersByFlight`
   - Should return `categorized.families` array

---

## TROUBLESHOOTING

**Issue:** Build fails with Python 3.13 error
- **Solution:** runtime.txt should have `python-3.11.9`
- Set Python version in Render dashboard to 3.11.9

**Issue:** Database connection fails
- **Solution:** Check DATABASE_URL environment variable in Render
- Ensure it's the same URL from Neon (starts with `postgresql://`)

**Issue:** 404 errors on API calls
- **Solution:** Check Root Directory is set to `Python and Insert scripts/Passenger watsonx`
- Verify Start Command is `gunicorn passenger_api:app`

**Issue:** No passengers returned
- **Solution:** Make sure you ran all 5 SQL INSERT files in Neon
- Verify: `SELECT COUNT(*) FROM passengers;` should return 10000

---

## COST SUMMARY

**Render Free Tier:**
- Flight API: Free (already deployed)
- Passenger API: Free (new service)
- **Total:** $0/month for both APIs

**Neon Free Tier:**
- Single database with 2 tables (flights + passengers)
- **Total:** $0/month

Both APIs stay within free tier limits.

---

## NEXT STEPS AFTER DEPLOYMENT

1. Run the 5 passenger SQL files in Neon (if not done already)
2. Push passenger API code to GitHub
3. Deploy to Render following steps above
4. Test API endpoints with curl
5. Update OpenAPI JSON with production URL
6. Configure watsonx agent with Tools + Behavior
7. Test queries in watsonx

---

## NEED A NEW REPO?

**Answer: NO** - you can use the same GitHub repo with this structure:

```
your-repo/
├── flight_api/           # Flight API folder
│   └── app.py
└── passenger_api/        # Passenger API folder
    └── passenger_api.py
```

In Render, you create TWO separate web services pointing to:
- Service 1: Root Directory = `flight_api/` (or your current path)
- Service 2: Root Directory = `passenger_api/` (or your current path)

This is the recommended approach - single repo, multiple services.
