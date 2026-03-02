# StockForge Backend Deployment Guide - Render

This guide will help you deploy the StockForge backend to Render.

## Prerequisites

1. **GitHub Account**: Your code is already pushed to https://github.com/VinayWeb-create/StockForge
2. **Render Account**: Sign up at https://render.com (free tier available)
3. **MongoDB**: Use MongoDB Atlas (https://www.mongodb.com/cloud/atlas) - free tier available
4. **Redis**: Use Redis Cloud (https://redis.com/cloud) or Upstash Redis (https://upstash.com) - free tier available

## Step-by-Step Deployment

### 1. Set Up External Services

#### MongoDB Atlas Setup
- Go to https://www.mongodb.com/cloud/atlas
- Create a free cluster
- Create a database user with credentials
- Get your connection string (MONGO_URI)
- Whitelist Render's IP (or use "0.0.0.0/0" for development)

#### Redis Cloud Setup
- Go to https://redis.com/cloud or https://upstash.com
- Create a free Redis instance
- Get your Redis URL (REDIS_URL)

### 2. Prepare Environment Variables

You'll need these environment variables on Render:

```
SECRET_KEY=your-secret-key-here
FLASK_ENV=production
FLASK_DEBUG=false
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?appName=YourApp
MONGO_DB_NAME=stockforge
JWT_SECRET_KEY=your-jwt-secret-key
REDIS_URL=redis://default:password@host:port/0
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### 3. Deploy to Render

#### Option A: Using render.yaml (Recommended)

1. Go to https://dashboard.render.com
2. Click **New +** → **Web Service**
3. Connect your GitHub repository (VinayWeb-create/StockForge)
4. Select the repository
5. If using `render.yaml`:
   - Render will automatically detect it
   - Configure environment variables in the dashboard
6. Click **Create Web Service**

#### Option B: Manual Setup

1. Go to https://dashboard.render.com
2. Click **New +** → **Web Service**
3. Connect your GitHub repository
4. Fill in the following:
   - **Name**: `stockforge-api` (or your preferred name)
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `cd backend && gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT app:app`
5. Set **Environment Variables**:
   - Add all variables from Section 2 above
6. Click **Create Web Service**

### 4. Configure Environment Variables

In Render Dashboard:
1. Go to your service → **Environment**
2. Add each variable:
   - `SECRET_KEY`: Generate a strong random string
   - `FLASK_ENV`: `production`
   - `FLASK_DEBUG`: `false`
   - `MONGO_URI`: Your MongoDB connection string
   - `MONGO_DB_NAME`: `stockforge`
   - `JWT_SECRET_KEY`: Your JWT secret key
   - `REDIS_URL`: Your Redis URL
   - `ALLOWED_ORIGINS`: Your frontend URL

### 5. Deploy

1. Push any changes to GitHub on the `main` branch
2. Render will automatically redeploy
3. Check the **Logs** tab to monitor deployment

### 6. Test Your Deployment

Once deployed, test the API:

```bash
# Health check
curl https://your-app-name.onrender.com/health

# Expected response:
# {"status":"ok","timestamp":"2024-03-02T..."}
```

## Monitoring & Troubleshooting

### Check Logs
- Go to **Logs** tab in Render Dashboard to see real-time logs

### Common Issues

**Error: Module not found**
- Make sure `requirements.txt` is in the root directory
- Check that all imports in backend modules are correct

**MongoDB Connection Failed**
- Verify MONGO_URI is correct
- Check IP whitelist in MongoDB Atlas (should include Render's IPs)
- Ensure user credentials are correct

**Redis Connection Failed**
- Redis is optional for basic features
- The app falls back to in-memory storage if Redis is unavailable
- For caching to work, ensure REDIS_URL is correct

**Port Issues**
- Render assigns a PORT environment variable
- Start command uses `$PORT` - this is correct

### View Logs
```
In Render Dashboard → Your Service → Logs
```

## Performance Considerations

- **Starter Plan**: Limited resources, suitable for low-traffic development
- **Standard Plan**: Better for production uses
- **Scaling**: Consider upgrading plan if experiencing high traffic

## Next Steps

1. **Frontend Deployment**: Deploy frontend separately to Render Static Site, GitHub Pages, or Vercel
2. **Custom Domain**: Add a custom domain in Render → Settings
3. **SSL/TLS**: Automatically provided by Render

## Useful Links

- Render Docs: https://render.com/docs
- Flask Docs: https://flask.palletsprojects.com/
- MongoDB Atlas: https://www.mongodb.com/cloud/atlas
- Redis Cloud: https://redis.com/cloud

## Support

If you encounter issues:
1. Check Render logs for error messages
2. Verify all environment variables are set correctly
3. Test locally with `python backend/app.py`
4. Check MongoDB and Redis connectivity
