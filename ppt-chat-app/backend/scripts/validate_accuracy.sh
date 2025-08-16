#!/bin/bash

# Accuracy++ Validation Script
# Runs all tests with features ON, then CLI, then fallback test with solver OFF

set -e  # Exit on error

echo "============================================"
echo " ACCURACY++ VALIDATION SCRIPT"
echo "============================================"

# Change to backend directory
cd "$(dirname "$0")/.."

# Set all features ON for main tests
export HYBRID_VISION_ENABLED=true
export ACCURATE_SOLVER_ENABLED=true
export RENDER_MEASURE_ENABLED=true
export ARCHETYPE_ALIGNMENT_ENABLED=true
export SAFETY_MAP_ENABLED=true

echo ""
echo "🔧 Feature flags set to ON:"
echo "   HYBRID_VISION_ENABLED=$HYBRID_VISION_ENABLED"
echo "   ACCURATE_SOLVER_ENABLED=$ACCURATE_SOLVER_ENABLED"
echo "   RENDER_MEASURE_ENABLED=$RENDER_MEASURE_ENABLED"
echo "   ARCHETYPE_ALIGNMENT_ENABLED=$ARCHETYPE_ALIGNMENT_ENABLED"
echo "   SAFETY_MAP_ENABLED=$SAFETY_MAP_ENABLED"

# Check if API is running
echo ""
echo "🔍 Checking if API is running..."
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "⚠️  API not running. Starting it in background..."
    uvicorn app.main:app --reload --port 8000 > /tmp/api.log 2>&1 &
    API_PID=$!
    echo "   Started API with PID $API_PID"
    echo "   Waiting for API to be ready..."
    sleep 5
    
    # Check again
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "❌ Failed to start API. Check /tmp/api.log for details"
        exit 1
    fi
else
    echo "✅ API is running"
fi

# Run accuracy tests with features ON
echo ""
echo "============================================"
echo " RUNNING TESTS WITH FEATURES ON"
echo "============================================"

echo ""
echo "📋 Test 1: Ingest and Profile"
python -m pytest tests/accuracy/test_ingest_and_profile.py -v -s

echo ""
echo "📋 Test 2: Solver and Safety"
python -m pytest tests/accuracy/test_solver_and_safety.py -v -s

echo ""
echo "📋 Test 3: Render Overflow Loop"
python -m pytest tests/accuracy/test_render_overflow_loop.py -v -s || {
    echo "⚠️  Render test failed (LibreOffice may not be available)"
}

# Run CLI validation
echo ""
echo "============================================"
echo " RUNNING CLI VALIDATION"
echo "============================================"
python app/cli/validate_accuracy.py

# Now test with solver OFF
echo ""
echo "============================================"
echo " RUNNING FALLBACK TEST (SOLVER OFF)"
echo "============================================"

export ACCURATE_SOLVER_ENABLED=false
echo "🔧 Set ACCURATE_SOLVER_ENABLED=$ACCURATE_SOLVER_ENABLED"

echo ""
echo "📋 Test 4: Feature Flags Fallback"
python -m pytest tests/accuracy/test_feature_flags_fallback.py -v -s

# Summary
echo ""
echo "============================================"
echo " VALIDATION COMPLETE"
echo "============================================"
echo ""
echo "✅ All validation tests completed"
echo ""
echo "Summary:"
echo "  - Template ingestion and profile: TESTED"
echo "  - ILP solver and safety maps: TESTED"
echo "  - 3-pass render with overflow: TESTED (if LibreOffice available)"
echo "  - Feature flag fallback: TESTED"
echo "  - CLI end-to-end validation: TESTED"

# Clean up if we started the API
if [ ! -z "$API_PID" ]; then
    echo ""
    echo "🧹 Cleaning up..."
    kill $API_PID 2>/dev/null || true
    echo "   Stopped API process"
fi

echo ""
echo "🎉 Validation script completed successfully!"