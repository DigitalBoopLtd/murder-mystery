#!/bin/bash

# Setup script for Murder Mystery Game

echo "🔍 Setting up Murder Mystery Game..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python found: $(python3 --version)"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found."
    if [ -f "env.example" ]; then
        echo "📄 Creating .env from env.example..."
        cp env.example .env
        echo "📝 A new .env file has been created from env.example."
        echo "   Open it and add your API keys (at least OPENAI_API_KEY)."
    else
        echo "⚠️  env.example not found either."
        echo "   Please create a .env file with at least:"
        echo "   OPENAI_API_KEY=your_openai_api_key_here"
    fi
else
    echo "✅ .env file found"
fi

echo ""
echo "✨ Setup complete!"
echo ""
echo "To run the application:"
echo "  1. Activate the virtual environment: source venv/bin/activate"
echo "  2. Make sure your .env file has at least OPENAI_API_KEY set"
echo "     (optionally ELEVENLABS_API_KEY and HF_TOKEN for voice and images)"
echo "  3. Run: python app.py"
echo ""







