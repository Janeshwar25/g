#!/bin/bash

# Quick Start Script for Forge AI Enterprise LLM Gateway Upgrade
# Usage: bash quick_start.sh

set -e

echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                                                                            ║"
echo "║        FORGE AI - ENTERPRISE LLM GATEWAY QUICK START                      ║"
echo "║                                                                            ║"
echo "║        Upgrading from Groq API → Company LLM Gateway (OAuth2)             ║"
echo "║                                                                            ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "${BLUE}[1/6] Checking Python version...${NC}"
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3.11 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✓ Python $PYTHON_VERSION found"

# Check if credentials.env exists
echo ""
echo "${BLUE}[2/6] Checking configuration...${NC}"
if [ ! -f "credentials.env" ]; then
    echo "⚠ credentials.env not found"
    echo "Creating credentials.env from env.template..."
    cp env.template credentials.env
    echo "✓ Created credentials.env"
    echo ""
    echo "${YELLOW}⚠️  NEXT STEP:${NC}"
    echo "Edit credentials.env and add your LLM_GATEWAY_* variables:"
    echo "  - LLM_GATEWAY_CLIENT_ID"
    echo "  - LLM_GATEWAY_CLIENT_SECRET"
    echo "  - LLM_GATEWAY_PROJECT_ID"
    echo "  - LLM_GATEWAY_TOKEN_URL"
    echo "  - LLM_GATEWAY_BASE_URL"
    echo ""
    echo "Get these from your IT/DevOps team."
    exit 1
else
    echo "✓ credentials.env found"
fi

# Check if requirements.txt exists
echo ""
echo "${BLUE}[3/6] Checking dependencies...${NC}"
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found"
    exit 1
fi

# Install/update dependencies
echo "Installing dependencies..."
pip3 install -q -r requirements.txt
echo "✓ Dependencies installed"

# Run verification
echo ""
echo "${BLUE}[4/6] Running automated verification...${NC}"
if [ -f "verify_deployment.py" ]; then
    echo "Running 41 deployment checks..."
    python3 verify_deployment.py 2>&1 | tail -20
else
    echo "⚠ verify_deployment.py not found"
fi

# Show documentation
echo ""
echo "${BLUE}[5/6] Documentation files...${NC}"
echo ""
echo "📚 Start with these documents (in order):"
echo ""
echo "  1. COMPLETION_SUMMARY.md       (10 min)  - Overview & checklist"
echo "  2. QUICK_REFERENCE.md          (5 min)   - Quick facts"
echo "  3. ENTERPRISE_LLM_README.md    (20 min)  - Setup guide"
echo "  4. ENTERPRISE_LLM_EXAMPLES.py  (10 min)  - Run code examples"
echo ""
echo "Advanced:"
echo "  - ENTERPRISE_LLM_INTEGRATION.md - Technical deep dive"
echo "  - MIGRATION_GROQ_TO_ENTERPRISE.md - Deployment guide"
echo "  - SECURITY_CHECKLIST.md         - Security review"
echo ""

# Show next steps
echo ""
echo "${BLUE}[6/6] Next steps...${NC}"
echo ""
echo "${GREEN}✓ Quick start complete!${NC}"
echo ""
echo "📋 Your action items:"
echo ""
echo "  1. Edit credentials.env with LLM_GATEWAY_* variables"
echo "  2. Read: COMPLETION_SUMMARY.md"
echo "  3. Run: python3 verify_deployment.py"
echo "  4. Run: python3 ENTERPRISE_LLM_EXAMPLES.py"
echo "  5. Read: ENTERPRISE_LLM_README.md"
echo ""
echo "🚀 When ready to run:"
echo ""
echo "  Terminal 1: python3 app/app.py"
echo "  Terminal 2: streamlit run app/app.py"
echo ""
echo "📞 Need help?"
echo ""
echo "  - Check ENTERPRISE_LLM_README.md § Troubleshooting"
echo "  - Review ENTERPRISE_LLM_EXAMPLES.py for code samples"
echo "  - Run: python3 verify_deployment.py"
echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo ""
