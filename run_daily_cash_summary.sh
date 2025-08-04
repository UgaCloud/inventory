#!/bin/zsh
# This cron script runs the Django management command to generate daily cash summaries at 23:59 every day.

# Set the path to the project directory
cd /Users/abdulhakiim/Me/UGACloud/Projects/inventory

# Activate the virtual environment if needed
source ../venv/bin/activate

# Run the management command
/opt/homebrew/bin/python3 manage.py generate_daily_cash_summaries
