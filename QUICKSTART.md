# 🚀 Quick Start Guide

## Prerequisites Check

```bash
# Check if you have the required tools
python3 --version  # Should be 3.9+
node --version     # Should be 18+
npm --version
```

---

## Development Setup (5 minutes)

### Step 1: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your Supabase credentials
# Get them from: https://app.supabase.com/project/_/settings/api
nano .env  # or use your preferred editor
```

**Required variables:**
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...
```

### Step 2: Run Setup

```bash
# Install all dependencies (backend + frontend)
./scripts/dev/setup.sh
```

This will:
- ✅ Check required tools
- ✅ Create Python virtual environment
- ✅ Install Python dependencies
- ✅ Install Node.js dependencies
- ✅ Validate environment configuration

### Step 3: Start the Application

```bash
# Start backend and frontend
./scripts/dev/up.sh
```

The application will:
- 🔧 Start backend on http://localhost:8001
- 🌐 Start frontend on http://localhost:3000
- 📝 Create log files in `logs/`
- 🎯 Auto-open browser

**Wait for:**
```
✅ Backend ready at http://localhost:8001
✅ Frontend ready at http://localhost:3000
```

### Step 4: Validate Everything Works

```bash
# In a new terminal, run health checks
./scripts/dev/doctor.sh
```

You should see all green ✅ checks.

### Step 5: Access the Application

Open your browser to:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8001/api/health

Use "Login with IA" for instant demo access!

---

## Daily Development Workflow

```bash
# Start working
./scripts/dev/up.sh

# Check if everything is healthy
./scripts/dev/doctor.sh

# Do your development work...

# Stop when done (or press CTRL+C)
./scripts/dev/down.sh
```

---

## Common Tasks

### Start Only Backend

```bash
./scripts/dev/up.sh --backend-only
```

### Start Only Frontend

```bash
./scripts/dev/up.sh --frontend-only
```

### Check Logs

```bash
# Follow backend logs
tail -f logs/backend-*.log

# Follow frontend logs
tail -f logs/frontend-*.log

# Follow both
tail -f logs/*.log
```

### Restart After Code Changes

```bash
# Stop
./scripts/dev/down.sh

# Start again
./scripts/dev/up.sh
```

### Clean Restart

```bash
# Stop everything
./scripts/dev/down.sh

# Free ports manually (if needed)
lsof -ti:8001 | xargs kill -9  # Backend
lsof -ti:3000 | xargs kill -9  # Frontend

# Start fresh
./scripts/dev/up.sh
```

---

## Production Deployment

### Step 1: Create Production Environment

```bash
# Copy template
cp .env.example .env.production

# Edit with production values
nano .env.production
```

**Generate strong secrets:**
```bash
openssl rand -hex 32  # For SECRET_KEY
openssl rand -hex 32  # For JWT_SECRET
```

### Step 2: Build

```bash
./scripts/prod/build.sh
```

Output: `alca-financas-YYYYMMDD-HHMMSS.tar.gz`

### Step 3: Deploy and Run

```bash
# Test locally first
./scripts/prod/run.sh

# Or deploy to server
scp alca-financas-*.tar.gz user@server:/path/
ssh user@server 'cd /path && tar -xzf alca-financas-*.tar.gz'
ssh user@server 'cd /path && ./scripts/prod/run.sh'
```

### Step 4: Migrations (if needed)

```bash
./scripts/prod/migrate.sh
```

---

## Troubleshooting

### "Port already in use"

```bash
./scripts/dev/down.sh
```

Or manually:
```bash
lsof -ti:8001 | xargs kill -9
lsof -ti:3000 | xargs kill -9
```

### "Backend not responding"

```bash
# Check logs
tail -50 logs/backend-*.log

# Check Supabase connection
curl -H "apikey: YOUR_ANON_KEY" \
     https://your-project.supabase.co/rest/v1/
```

### "Frontend can't reach backend"

```bash
# Check backend is running
curl http://localhost:8001/api/health

# Check frontend .env
cat frontend/.env

# Should show: VITE_API_URL=http://localhost:8001
```

### CORS Errors

Add to `.env`:
```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000
```

Restart backend.

### Dependencies Out of Date

```bash
./scripts/dev/setup.sh
```

---

## Docker Alternative

### Development with Docker

```bash
# Start everything
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Production with Docker

```bash
# Build first
./scripts/prod/build.sh

# Then use production compose
docker-compose -f docker-compose.prod.yml up -d
```

---

## Getting Help

### Documentation

- **Environment Setup**: `docs/ENVIRONMENTS.md`
- **Database Migrations**: `scripts/db/README.md`
- **Implementation Details**: `IMPLEMENTATION_SUMMARY.md`
- **Main README**: `README.md`

### Commands

```bash
# Validate environment
./scripts/dev/doctor.sh

# Check script help
./scripts/dev/up.sh --help  # (some scripts have --help)
```

### Health Check URLs

- Backend: http://localhost:8001/api/health
- Frontend: http://localhost:3000

---

## Checklist for First Run

- [ ] Clone repository
- [ ] Copy `.env.example` to `.env`
- [ ] Get Supabase credentials
- [ ] Edit `.env` with real credentials
- [ ] Run `./scripts/dev/setup.sh`
- [ ] Run `./scripts/dev/up.sh`
- [ ] Run `./scripts/dev/doctor.sh` (should be all ✅)
- [ ] Open http://localhost:3000
- [ ] Try "Login with IA"
- [ ] Explore the dashboard

---

## Success Indicators

You know it's working when:

1. ✅ `./scripts/dev/doctor.sh` shows all green
2. ✅ Backend responds: `curl http://localhost:8001/api/health`
3. ✅ Frontend loads: http://localhost:3000
4. ✅ Login works (demo or real credentials)
5. ✅ Dashboard displays data

---

## Next Steps

Once everything is running:

1. **Explore the app**: Try all features
2. **Read the docs**: Check `docs/ENVIRONMENTS.md`
3. **Make changes**: Edit code and see live reload
4. **Run tests**: `cd frontend && npm test`
5. **Prepare for prod**: Follow production deployment section

---

**Need Help?**
- Check `IMPLEMENTATION_SUMMARY.md` for full details
- Review `docs/ENVIRONMENTS.md` for configuration
- See `README.md` for project overview

**Happy coding! 🚀**
