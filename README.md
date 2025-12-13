# Flight Data API - Render Deployment Package

This folder contains everything needed to deploy a production-ready REST API that connects your Neon PostgreSQL database to watsonx Agent Builder.

## 📁 Files Included

| File | Purpose |
|------|---------|
| `app.py` | Main Flask REST API application |
| `requirements.txt` | Python package dependencies |
| `Procfile` | Render deployment configuration |
| `DEPLOYMENT_STEPS.md` | Complete step-by-step deployment guide for Render.com |
| `WATSONX_CONFIGURATION.md` | Detailed watsonx Agent Builder configuration |
| `QUICK_REFERENCE.md` | Quick copy-paste values for immediate setup |
| `README.md` | This file - overview and getting started |

## 🚀 Quick Start

### Option 1: Test Locally with ngrok (5 minutes)

```bash
# Install dependencies
pip3 install flask flask-cors psycopg2-binary

# Start the API
cd "/Users/tejas.s02/Downloads/Watsonx_AgenticAI/New Generated Data/FreshData/render"
python3 app.py

# In another terminal, expose to internet
brew install ngrok
ngrok http 5001
```

Use the ngrok URL in watsonx Custom Service configuration.

### Option 2: Deploy to Render (Permanent, 15 minutes)

See `DEPLOYMENT_STEPS.md` for complete instructions.

Quick summary:
1. Push this folder to GitHub
2. Connect GitHub repo to Render.com
3. Deploy as Web Service
4. Use Render URL in watsonx

## 📚 Documentation Guide

### For Deployment:
→ Read `DEPLOYMENT_STEPS.md` first

### For watsonx Configuration:
→ Read `WATSONX_CONFIGURATION.md` for complete setup

### For Quick Copy-Paste:
→ Use `QUICK_REFERENCE.md` for immediate values

## 🔧 Configuration Required

### In Render (Environment Variables):
```
DATABASE_URL=postgresql://neondb_owner:npg_EayzTwrm2B6S@ep-autumn-band-aebfrz67-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require
```

### In watsonx (Custom Service):
- **URL**: Your Render or ngrok URL
- **Authentication**: None (for testing)
- **Default Filter**: `{"min_seats": 1}`
- **Metadata**: See `QUICK_REFERENCE.md`
- **Description**: See `WATSONX_CONFIGURATION.md`

## 🧪 API Endpoints

Once deployed, your API provides:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information |
| `/health` | GET | Health check (verify DB connection) |
| `/flight/<flight_no>` | GET | Get specific flight by number |
| `/search` | POST | Search flights (main endpoint) |
| `/routes` | GET | List all available routes |

## 📋 Testing the API

### Test 1: Health Check
```bash
curl https://YOUR-API-URL.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "total_flights": 5000
}
```

### Test 2: Specific Flight
```bash
curl https://YOUR-API-URL.com/flight/AI14110
```

### Test 3: Search Flights
```bash
curl -X POST https://YOUR-API-URL.com/search \
  -H "Content-Type: application/json" \
  -d '{"origin": "DEL", "destination": "BOM", "min_seats": 1}'
```

### Test 4: Natural Language Search
```bash
curl -X POST https://YOUR-API-URL.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "flights from DEL to BOM with available seats"}'
```

## ✅ watsonx Test Queries

After connecting to watsonx, test with these queries:

1. "flight details of AI14110"
2. "flights from DEL to BOM with available seats"
3. "show me all delayed flights"
4. "which flights go from Mumbai to Bangalore"
5. "is flight AI14110 on time"

## 💡 Important Notes

### Free Tier Limitations:
- **Render**: Sleeps after 15 min inactivity (first request slow)
- **Neon**: 3GB storage limit (sufficient for 5K flights)
- **ngrok**: URL changes on restart (not permanent)

### For Production:
- Add API key authentication (see `WATSONX_CONFIGURATION.md` security section)
- Upgrade Render to paid tier ($7/mo) for always-on
- Implement rate limiting
- Add monitoring and logging

## 🔒 Security

**Current configuration**: No authentication (fine for testing)

**For production**, implement:
1. API key authentication
2. Rate limiting
3. Input validation
4. CORS restrictions

See security section in `WATSONX_CONFIGURATION.md`.

## 🐛 Troubleshooting

**Problem**: API returns 500 error
→ Check Render logs for database connection issues

**Problem**: Slow first request
→ Expected behavior (free tier wakes up from sleep)

**Problem**: "No flights found" for valid queries
→ Verify Neon database still has data (check with `/health`)

**Problem**: watsonx can't connect
→ Test API URL directly in browser or curl
→ Verify URL is publicly accessible (not localhost)

## 📞 Support & Resources

- **Render Documentation**: https://render.com/docs
- **Flask Documentation**: https://flask.palletsprojects.com/
- **Neon Documentation**: https://neon.tech/docs
- **watsonx Agent Builder**: https://www.ibm.com/docs/en/watsonx

## 📈 Next Steps

1. ✅ Deploy API (Option 1 or 2)
2. ✅ Test all endpoints
3. ✅ Configure watsonx Custom Service
4. ✅ Test queries in watsonx
5. 🔄 Monitor usage and performance
6. 🔒 Add authentication for production
7. 📊 Add analytics/logging if needed

## 🎯 Project Structure

```
render/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── Procfile                    # Render deployment config
├── DEPLOYMENT_STEPS.md         # Full deployment guide
├── WATSONX_CONFIGURATION.md    # Complete watsonx setup
├── QUICK_REFERENCE.md          # Quick copy-paste values
└── README.md                   # This file
```

## 🔗 Connection Flow

```
User Query
    ↓
watsonx Agent Builder
    ↓
Custom Service (REST API)
    ↓
Flask API (app.py)
    ↓
Neon PostgreSQL Database
    ↓
5,000 Flight Records
```

## ✨ Features

- ✅ Natural language query parsing
- ✅ Structured parameter queries
- ✅ Real-time database access
- ✅ CORS enabled for web access
- ✅ JSON responses
- ✅ Error handling
- ✅ Health monitoring
- ✅ Production-ready (with security additions)

---

**Need Help?** Refer to the detailed guides in this folder:
- Deployment issues → `DEPLOYMENT_STEPS.md`
- watsonx setup → `WATSONX_CONFIGURATION.md`
- Quick values → `QUICK_REFERENCE.md`

Good luck with your deployment! 🚀
