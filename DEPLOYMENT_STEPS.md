# Flight Data API - Deployment Guide

This folder contains all files needed to deploy the Flight Data REST API to Render.com for permanent access.

## What's Included

- `app.py` - Main Flask application with all API endpoints
- `requirements.txt` - Python package dependencies
- `Procfile` - Deployment configuration for Render
- `DEPLOYMENT_STEPS.md` - This file with detailed deployment instructions

## Prerequisites

1. GitHub account (free)
2. Render account (free) - https://render.com
3. Your Neon database is already set up with flight data loaded

---

# DEPLOYMENT STEPS TO RENDER.COM

## Step 1: Create a GitHub Repository

### Option A: Using GitHub Web Interface

1. Go to https://github.com and sign in
2. Click the "+" icon (top right) → "New repository"
3. Repository settings:
   - **Name**: `flight-api`
   - **Description**: `REST API for flight data queries`
   - **Visibility**: Public (or Private - both work)
   - **Initialize**: Leave unchecked (we'll push existing code)
4. Click "Create repository"

### Option B: Using Command Line

```bash
# Navigate to the render folder
cd "/Users/tejas.s02/Downloads/Watsonx_AgenticAI/New Generated Data/FreshData/render"

# Initialize git repository
git init

# Add all files
git add .

# Commit files
git commit -m "Initial commit: Flight Data API"

# Add GitHub remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/flight-api.git

# Push to GitHub
git branch -M main
git push -u origin main
```

**If you get authentication errors**, use a Personal Access Token:
- Go to GitHub → Settings → Developer Settings → Personal Access Tokens
- Generate new token with "repo" scope
- Use the token as your password when pushing

---

## Step 2: Deploy to Render

1. **Sign Up/Login to Render**
   - Go to https://render.com
   - Click "Get Started" or "Sign In"
   - Use GitHub to sign in (easiest)

2. **Create New Web Service**
   - Click "New +" button (top right)
   - Select "Web Service"

3. **Connect GitHub Repository**
   - Render will ask permission to access your GitHub repos
   - Click "Configure account" → Allow access
   - Find and select your `flight-api` repository
   - Click "Connect"

4. **Configure the Web Service**

   Fill in these settings:

   **Basic Settings:**
   - **Name**: `flight-data-api` (or any name you prefer)
   - **Region**: Choose closest to you (e.g., Oregon, Ohio)
   - **Branch**: `main`
   - **Root Directory**: Leave blank (or `.` if it asks)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

   **Instance Type:**
   - Select **"Free"** (free tier is sufficient)

   **Environment Variables:**
   Click "Advanced" → "Add Environment Variable":
   - **Key**: `DATABASE_URL`
   - **Value**: `postgresql://neondb_owner:npg_EayzTwrm2B6S@ep-autumn-band-aebfrz67-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require`

   (This is your Neon connection string)

5. **Deploy**
   - Click "Create Web Service"
   - Render will start building and deploying (takes 2-5 minutes)
   - Watch the logs in the dashboard

6. **Get Your API URL**
   - Once deployed, you'll see: ✓ "Live" with a green indicator
   - Copy your API URL from the top (looks like: `https://flight-data-api.onrender.com`)

---

## Step 3: Test Your Deployed API

Open a terminal and test:

```bash
# Replace YOUR_RENDER_URL with your actual Render URL
RENDER_URL="https://flight-data-api.onrender.com"

# Test 1: Health check
curl $RENDER_URL/health

# Test 2: Get specific flight
curl $RENDER_URL/flight/AI14110

# Test 3: Search flights from DEL to BOM
curl -X POST $RENDER_URL/search \
  -H "Content-Type: application/json" \
  -d '{"origin": "DEL", "destination": "BOM", "min_seats": 1}'

# Test 4: Natural language search
curl -X POST $RENDER_URL/search \
  -H "Content-Type: application/json" \
  -d '{"query": "flights from DEL to BOM with available seats"}'
```

If all tests return JSON responses, your API is working!

---

## Step 4: Connect to watsonx Agent Builder

Now use your Render URL in watsonx:

1. Go to watsonx Agent Builder
2. Navigate to **Knowledge Sources** → **Custom Service**
3. Configure:
   - **Name**: `Flight Database API`
   - **URL**: `https://YOUR_RENDER_URL.onrender.com` (your Render URL)
   - **Authentication**: None (for now)

See `WATSONX_CONFIGURATION.md` for detailed watsonx setup instructions.

---

## Troubleshooting

### Deployment Failed
- Check Render logs for errors
- Verify `requirements.txt` lists all dependencies
- Ensure `Procfile` contains: `web: gunicorn app:app`

### API Returns 500 Error
- Check Render logs: Click "Logs" tab in Render dashboard
- Verify DATABASE_URL environment variable is set correctly
- Test Neon connection from Render logs

### API is Slow to Respond (First Request)
- **This is normal!** Free tier Render services "spin down" after 15 minutes of inactivity
- First request after idle takes ~30 seconds to wake up
- Subsequent requests are fast
- **Solution for production**: Upgrade to paid tier ($7/month) for always-on service

### Can't Push to GitHub
- Generate Personal Access Token on GitHub
- Use token instead of password when pushing

---

## Updating the API

When you make changes to `app.py`:

```bash
cd "/Users/tejas.s02/Downloads/Watsonx_AgenticAI/New Generated Data/FreshData/render"

git add .
git commit -m "Update API endpoints"
git push origin main
```

Render will automatically detect the push and redeploy (takes 2-3 minutes).

---

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information and available endpoints |
| `/health` | GET | Health check (returns database status) |
| `/flight/<flight_no>` | GET | Get specific flight by flight number |
| `/search` | POST | Search flights (natural language or structured) |
| `/routes` | GET | Get all available routes |

---

## Free Tier Limits (Render)

- **750 hours/month** of runtime (sufficient for 24/7 operation)
- **Auto sleep after 15 min** of inactivity (first request slow)
- **Unlimited requests** while awake
- **500MB RAM** (plenty for this API)

**To upgrade to always-on**: $7/month removes auto-sleep

---

## Security Considerations (For Production)

1. **Add API Key Authentication**
   - Modify `app.py` to require API key in headers
   - Set API key as environment variable in Render

2. **Rate Limiting**
   - Add Flask-Limiter to prevent abuse
   - Example: 100 requests per minute per IP

3. **HTTPS Only**
   - Render provides HTTPS by default ✓

4. **Database Credentials**
   - Already using environment variables ✓
   - Never commit DATABASE_URL to git

---

## Support

If you encounter issues:
1. Check Render logs (most informative)
2. Test API locally first: `python3 app.py`
3. Verify Neon database is accessible
4. Check GitHub repository has all files

---

## Cost Summary

- **Neon Database**: FREE (up to 3GB)
- **Render Hosting**: FREE (with auto-sleep)
- **GitHub Repository**: FREE
- **Total**: $0/month for testing and development

For production with always-on API: $7/month
