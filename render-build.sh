#!/usr/bin/env bash
# Render build script for installing system dependencies
# This script runs during deployment on Render.com

set -o errexit  # Exit on error

echo "🔧 Installing system dependencies..."

# Install font utilities and Fira Code font
apt-get update
apt-get install -y fontconfig fonts-firacode

# Verify font installation
echo "📦 Installed fonts:"
fc-list | grep -i "fira" || echo "⚠️ Fira Code font may not be properly installed"

# Rebuild matplotlib font cache
echo "🔄 Rebuilding matplotlib font cache..."
python -c "import matplotlib.font_manager; matplotlib.font_manager._rebuild()"

echo "✅ Build script completed successfully"
