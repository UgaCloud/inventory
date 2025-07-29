#!/bin/zsh
# This cron script runs the Django management command to generate daily cash summaries at 23:59 every day.

# Set the path to your project directory
cd /Users/abdulhakiim/Me/UGACloud/Projects/inventory

# Activate your virtual environment if needed
# source /path/to/venv/bin/activate

# Run the management command
/opt/homebrew/bin/python3 manage.py daily_cash_summary
