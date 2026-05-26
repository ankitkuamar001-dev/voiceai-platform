#!/bin/bash
# ============================================================
# VoiceAI — Initial Setup Script
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🚀 VoiceAI — Setting up development environment..."
echo "=================================================="

# ── Step 1: Check prerequisites ──
echo ""
echo "📋 Checking prerequisites..."

command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required. Install from https://docker.com"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ Node.js is required. Install from https://nodejs.org"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3.12+ is required."; exit 1; }

echo "  ✅ Docker: $(docker --version | head -1)"
echo "  ✅ Node.js: $(node --version)"
echo "  ✅ Python: $(python3 --version)"

# ── Step 2: Set up environment ──
echo ""
echo "🔧 Setting up environment..."

if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "  ✅ Created .env from .env.example"
    echo "  ⚠️  Please edit .env and add your API keys!"
else
    echo "  ✅ .env already exists"
fi

# ── Step 3: Start infrastructure ──
echo ""
echo "🐳 Starting infrastructure (PostgreSQL + Redis)..."

cd "$PROJECT_DIR"
docker compose up -d postgres redis
echo "  ⏳ Waiting for services to be healthy..."
sleep 5

# Wait for PostgreSQL
for i in {1..30}; do
    if docker compose exec -T postgres pg_isready -U voiceai >/dev/null 2>&1; then
        echo "  ✅ PostgreSQL is ready"
        break
    fi
    sleep 1
done

# Wait for Redis
for i in {1..30}; do
    if docker compose exec -T redis redis-cli -a changeme_redis_password ping >/dev/null 2>&1; then
        echo "  ✅ Redis is ready"
        break
    fi
    sleep 1
done

# ── Step 4: Install frontend dependencies ──
echo ""
echo "📦 Installing frontend dependencies..."

if [ -d "$PROJECT_DIR/frontend/dashboard" ] && [ -f "$PROJECT_DIR/frontend/dashboard/package.json" ]; then
    cd "$PROJECT_DIR/frontend/dashboard"
    npm install --silent
    echo "  ✅ Frontend dependencies installed"
else
    echo "  ⚠️  Frontend not yet initialized"
fi

# ── Step 5: Summary ──
echo ""
echo "=================================================="
echo "✅ VoiceAI development environment is ready!"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your API keys"
echo "  2. Start all services:  make up"
echo "  3. Open dashboard:      http://localhost:3000"
echo "  4. API Gateway:         http://localhost:8080"
echo ""
echo "Quick commands:"
echo "  make up        — Start all services"
echo "  make down      — Stop all services"
echo "  make logs      — View logs"
echo "  make fe-dev    — Start frontend dev server"
echo "  make ingest-kb — Ingest knowledge base docs"
echo "=================================================="
