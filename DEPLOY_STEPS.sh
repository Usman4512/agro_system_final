# =====================================================================
#  AGRO SYSTEM — Complete Google Cloud Run Deployment Guide
#  Follow steps 1 to 5 in order. Takes about 20-30 minutes total.
# =====================================================================


# ─────────────────────────────────────────────
# BEFORE YOU START — Install Google Cloud CLI
# ─────────────────────────────────────────────
# 1. Go to: https://cloud.google.com/sdk/docs/install
# 2. Download and install for Windows
# 3. Open Command Prompt and run: gcloud init
# 4. Login with your Google account when browser opens


# ─────────────────────────────────────────────
# STEP 1 — Create your Google Cloud Project
# ─────────────────────────────────────────────

gcloud auth login
gcloud projects create agro-system-app --name="Agro System"
gcloud config set project agro-system-app

# Enable required services
gcloud services enable run.googleapis.com
gcloud services enable sql-component.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable artifactregistry.googleapis.com


# ─────────────────────────────────────────────
# STEP 2 — Create MySQL Database (Cloud SQL)
# Takes 5-10 minutes to create
# ─────────────────────────────────────────────

gcloud sql instances create agro-db \
  --database-version=MYSQL_8_0 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --root-password=YourRootPassword123

gcloud sql databases create agrosystem --instance=agro-db

gcloud sql users create agro_user \
  --instance=agro-db \
  --password=YourUserPassword456

# Save this connection name — you need it in Step 3:
gcloud sql instances describe agro-db --format="value(connectionName)"
# Example output: agro-system-app:us-central1:agro-db


# ─────────────────────────────────────────────
# STEP 3 — Deploy to Cloud Run
# Run this from inside the agro_deploy folder
# REPLACE all values in CAPITAL LETTERS
# ─────────────────────────────────────────────

cd C:\path\to\agro_deploy

gcloud run deploy agro-system \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --add-cloudsql-instances agro-system-app:us-central1:agro-db \
  --set-env-vars SECRET_KEY="agro4512meri" \
  --set-env-vars MYSQL_HOST="/cloudsql/agro-system-app:us-central1:agro-db" \
  --set-env-vars MYSQL_USER="root" \
  --set-env-vars MYSQL_PASSWORD="Usman$5000" \
  --set-env-vars MYSQL_DB="agrosystem" \
  --set-env-vars MYSQL_PORT="3306" \
  --set-env-vars MAIL_USERNAME="mu4512222@gmail.com" \
  --set-env-vars MAIL_PASSWORD="keed pnby jutn qgno" \
  --set-env-vars MAIL_DEFAULT_SENDER="Agro System <mu4512222@gmail.com>" \
  --set-env-vars ADMIN_EMAIL="mu4512222@gmail.com" \
  --set-env-vars JAZZCASH_NUMBER="03214512624" \
  --set-env-vars EASYPAISA_NUMBER="03131631965" \
  --set-env-vars OWNER_NAME="M Usman Manzoor"

# After deploy you get a live URL like:
# https://agro-system-xxxxxxxx-uc.a.run.app


# ─────────────────────────────────────────────
# STEP 4 — Open your live app
# ─────────────────────────────────────────────

gcloud run services describe agro-system \
  --region us-central1 \
  --format="value(status.url)"

# Default admin login:
#   URL:      https://your-app-url/auth/login
#   Username: admin
#   Password: admin123
#
# IMPORTANT: Change this password immediately after first login!


# ─────────────────────────────────────────────
# STEP 5 — How to receive payments from farmers
# ─────────────────────────────────────────────
#
# 1. Farmer visits your app and registers (30 day free trial)
# 2. After trial expires — farmer sees subscription page
# 3. Farmer sends Rs.500/1500/3000 to your JazzCash number
# 4. Farmer enters transaction ID in the app
# 5. YOU login as admin → go to /payment/admin/requests
# 6. YOU click Approve → farmer account activates instantly
# 7. Money is already in your JazzCash wallet!
#
# Payment requests link (after login as admin):
# https://your-app-url/payment/admin/requests


# ─────────────────────────────────────────────
# GMAIL APP PASSWORD (for email features)
# ─────────────────────────────────────────────
# 1. Go to myaccount.google.com
# 2. Security → 2-Step Verification → Enable
# 3. Security → App Passwords
# 4. Select: Mail → Other → type "Agro System"
# 5. Copy the 16-character password
# 6. Use it as MAIL_PASSWORD above


# ─────────────────────────────────────────────
# USEFUL COMMANDS
# ─────────────────────────────────────────────

# See live logs (for debugging)
gcloud run services logs read agro-system --region us-central1

# Update a single environment variable
gcloud run services update agro-system \
  --region us-central1 \
  --set-env-vars JAZZCASH_NUMBER="03001234567"

# Redeploy after any code changes
gcloud run deploy agro-system --source . --region us-central1

# Stop the app (to avoid charges)
gcloud run services delete agro-system --region us-central1


# ─────────────────────────────────────────────
# MONTHLY COSTS
# ─────────────────────────────────────────────
# Cloud Run:  FREE (2 million requests free/month)
# Cloud SQL:  ~Rs.2,000/month (db-f1-micro)
# Total:      ~Rs.2,000/month running cost
#
# If you have 10 paying farmers at Rs.500 = Rs.5,000 income
# Minus Rs.2,000 hosting = Rs.3,000 pure profit
