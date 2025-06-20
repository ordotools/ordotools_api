#!/bin/bash

echo "🚀 Starting OrdoTools API on Render..."

# Run cache warmup
echo "📚 Running cache warmup..."
python3 warmup_cache.py

# Check if warmup was successful (optional)
if [ $? -eq 0 ]; then
    echo "✅ Cache warmup completed successfully"
else
    echo "⚠️ Cache warmup had issues, but continuing..."
fi

# Start the FastAPI server
echo "🌐 Starting FastAPI server..."
python3 -m uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
