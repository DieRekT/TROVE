#!/bin/bash
# Setup script for Archive Detective backend
set -e

echo "🔧 Setting up Archive Detective backend..."

# Check Python version
python3 --version || { echo "ERROR: Python 3 not found"; exit 1; }

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Create .env from .env.example if .env doesn't exist
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "📝 Creating .env from .env.example..."
        cp .env.example .env
        echo "⚠️  Please edit .env and set your TROVE_API_KEY"
    else
        echo "⚠️  .env.example not found, creating basic .env..."
        cat > .env << 'EOF'
TROVE_API_KEY=your_trove_api_key_here
TROVEING_DB=troveing.sqlite
EOF
        echo "⚠️  Please edit .env and set your TROVE_API_KEY"
    fi
else
    echo "✅ .env already exists"
fi

# Initialize database (will be created on first run)
echo "💾 Database will be initialized on first run"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env and set TROVE_API_KEY"
echo "  2. Run: ./run.sh"
echo ""

