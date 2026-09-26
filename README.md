# GCP Mentoring Program — Data Platform

A GCP data platform template with two ingestion lanes feeding one BigQuery warehouse, orchestrated by Cloud Workflows and deployed via Cloud Build CI/CD.

**Terraform manages:** service accounts, IAM, GCS buckets, BigQuery dataset, Secret Manager container, billing budget.  
**Not Terraform:** Cloud SQL (created manually via `gcloud`).

---

## Architecture

```
Airbnb CSVs ──► GCS landing ──► Dataproc (csv_to_parquet) ──► GCS curated ──► Dataproc (transform_to_bq) ──►┐
                                                                                                              ├──► BigQuery warehouse ──► Looker Studio
Cloud SQL ───► Dataproc (extract_adventureworks) ──► GCS curated ──► Dataproc (transform_adventureworks) ──►┘

Cloud Workflows sequences all 4 batches with polling loops.
Cloud Build runs terraform apply + copies artifacts on every push.
```

---

## Prerequisites

| Tool | Version |
|------|---------|
| Terraform | ≥ 1.5 |
| gcloud CLI | latest |
| Python | 3.10+ (local dev only) |

---

## Part A — Bootstrap (one-time, run as project owner)

### 1. Create the Terraform state bucket

```bash
export PROJECT_ID=your-gcp-project-id
gcloud storage buckets create gs://${PROJECT_ID}-tf-state \
  --location=us-central1
gcloud storage buckets update gs://${PROJECT_ID}-tf-state \
  --versioning
```

### 2. Configure variables

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# Edit terraform.tfvars and fill in your real values
```

> **Never commit `terraform.tfvars`** — it is in `.gitignore`.

### 3. Update the backend bucket placeholder

Edit `terraform/versions.tf` and replace `YOUR_PROJECT_ID-tf-state` with your real bucket name.

### 4. Run Terraform

```bash
cd terraform
terraform init
terraform apply
```

Expected: ~20 resources (9 APIs, 3 service accounts, 2 buckets, 4 bucket IAM bindings, 1 BQ dataset, 1 secret, 1 secret IAM binding, 1 budget).

---

## Part B — Upload JDBC driver

```bash
# Download postgresql-42.7.3.jar from https://jdbc.postgresql.org/download/
gcloud storage cp postgresql-42.7.3.jar gs://${PROJECT_ID}-deploy/jars/
```

---

## Part C — Create Cloud SQL (manual, NOT Terraform)

```bash
gcloud sql instances create adventureworks-db \
  --database-version=POSTGRES_15 \
  --tier=db-custom-2-8192 \
  --region=us-central1 \
  --availability-type=zonal

gcloud sql databases create adventureworks --instance=adventureworks-db

# Set an admin password for the one-time import.
gcloud sql users set-password postgres \
  --instance=adventureworks-db \
  --password=CHOOSE_A_STRONG_ADMIN_PASSWORD

# Create the pipeline user. Use a strong password and keep it out of git.
gcloud sql users create pipeline-reader \
  --instance=adventureworks-db \
  --password=CHOOSE_A_STRONG_PASSWORD
```

### Load AdventureWorks data

The upstream project is a set of CSV files plus `install.sql`, not a single
PostgreSQL dump. Run the import from Cloud Shell or another machine with
`psql`, Ruby, and the Cloud SQL Auth Proxy installed.

```bash
git clone https://github.com/lorint/AdventureWorks-for-Postgres.git
cd AdventureWorks-for-Postgres

# Download AdventureWorks-oltp-install-script.zip from:
# https://github.com/Microsoft/sql-server-samples/releases/download/adventureworks/
# Extract its CSV files into this directory, then run:
ruby update_csvs.rb
```

Start the proxy in a second terminal:

```bash
gcloud components install cloud-sql-proxy
cloud-sql-proxy \
  ${PROJECT_ID}:us-central1:adventureworks-db \
  --port=5432
```

Import using the `postgres` administrator, not `pipeline-reader`:

```bash
PGPASSWORD='POSTGRES_PASSWORD' psql \
  -h 127.0.0.1 -p 5432 -U postgres -d adventureworks -f install.sql
```

Grant the pipeline user read access after the import:

```bash
PGPASSWORD='POSTGRES_PASSWORD' psql \
  -h 127.0.0.1 -p 5432 -U postgres -d adventureworks <<'SQL'
GRANT USAGE ON SCHEMA sales TO "pipeline-reader";
GRANT SELECT ON ALL TABLES IN SCHEMA sales TO "pipeline-reader";
ALTER DEFAULT PRIVILEGES IN SCHEMA sales
  GRANT SELECT ON TABLES TO "pipeline-reader";
SQL
```

### Store the pipeline connection string

The Terraform resource creates only the Secret Manager container. Add its first
version after the database is loaded. In PowerShell, use a temporary file:

```powershell
'host=HOST_IP;user=pipeline-reader;password=PIPELINE_PASSWORD;dbname=adventureworks' |
  Set-Content -NoNewline connection.txt

gcloud secrets versions add cloud-sql-connection-string `
  --project=$env:PROJECT_ID `
  --data-file=connection.txt

Remove-Item connection.txt
```

Do not commit `connection.txt` or replace the placeholders in this README with
real credentials.

> **Security note:** The Cloud SQL Auth Proxy is used for the local import, but the Dataproc extractor connects directly to the host in Secret Manager. If using a public IP, configure a restricted authorized network path for Dataproc; never use `0.0.0.0/0` outside a disposable sandbox. For production, prefer private IP and VPC connectivity.

> **Schema note:** The extractor expects `sales.salesorderheader`,
> `sales.salesorderdetail`, `sales.product`, and `sales.customer`. Verify those
> tables exist after `install.sql` completes. The `pipeline-reader` account must
> have `SELECT` privileges on them.

> **Teardown note:** `terraform destroy` does NOT delete the Cloud SQL instance. Run `gcloud sql instances delete adventureworks-db` separately.

---

## Part D — Lane A: Airbnb flat files

```bash
# Upload source files
gcloud storage cp listings.csv calendar.csv reviews.csv \
  gs://${PROJECT_ID}-landing/raw/airbnb/

# Run Lane A (or let Cloud Workflows do it)
gcloud dataproc batches submit pyspark gs://${PROJECT_ID}-deploy/jobs/csv_to_parquet.py \
  --region=us-central1 \
  --service-account=sa-dataproc-jobs@${PROJECT_ID}.iam.gserviceaccount.com \
  --deps-bucket=gs://${PROJECT_ID}-deploy \
  -- --project=${PROJECT_ID}

gcloud dataproc batches submit pyspark gs://${PROJECT_ID}-deploy/jobs/transform_to_bq.py \
  --region=us-central1 \
  --service-account=sa-dataproc-jobs@${PROJECT_ID}.iam.gserviceaccount.com \
  --deps-bucket=gs://${PROJECT_ID}-deploy \
  --properties spark.jars.packages=com.google.cloud.spark:spark-bigquery-with-dependencies_2.12:0.36.1 \
  -- --project=${PROJECT_ID}
```

---

## Part E — Lane B: AdventureWorks (relational)

```bash
gcloud dataproc batches submit pyspark gs://${PROJECT_ID}-deploy/jobs/extract_adventureworks.py \
  --region=us-central1 \
  --service-account=sa-dataproc-jobs@${PROJECT_ID}.iam.gserviceaccount.com \
  --deps-bucket=gs://${PROJECT_ID}-deploy \
  --jars=gs://${PROJECT_ID}-deploy/jars/postgresql-42.7.3.jar \
  -- --project=${PROJECT_ID}

gcloud dataproc batches submit pyspark gs://${PROJECT_ID}-deploy/jobs/transform_adventureworks.py \
  --region=us-central1 \
  --service-account=sa-dataproc-jobs@${PROJECT_ID}.iam.gserviceaccount.com \
  --deps-bucket=gs://${PROJECT_ID}-deploy \
  --properties spark.jars.packages=com.google.cloud.spark:spark-bigquery-with-dependencies_2.12:0.36.1 \
  -- --project=${PROJECT_ID}
```

---

## Part F — Deploy and run the full pipeline via Cloud Workflows

```bash
# Deploy workflow
gcloud workflows deploy mentoring-pipeline \
  --source=workflows/pipeline.yaml \
  --service-account=sa-workflows@${PROJECT_ID}.iam.gserviceaccount.com \
  --location=us-central1

# Trigger a run
gcloud workflows run mentoring-pipeline \
  --data="{\"project_id\":\"${PROJECT_ID}\",\"region\":\"us-central1\"}" \
  --location=us-central1
```

---

## CI/CD with Cloud Build

On every push, Cloud Build will:
1. `terraform apply` (idempotent)
2. Copy PySpark scripts to `gs://$PROJECT-deploy/jobs/`
3. Copy `pipeline.yaml` to `gs://$PROJECT-deploy/workflows/`
4. Deploy/update the Cloud Workflow

Set the following substitution variables on the Cloud Build trigger:
- `_BILLING_ACCOUNT_ID` — your billing account
- `_REGION` — default `us-central1`
- `_BUDGET_USD` — default `50`

---

## BigQuery tables (written by PySpark, not Terraform)

| Table | Lane | Description |
|-------|------|-------------|
| `warehouse.airbnb_fact_listings` | A | Cleaned Airbnb listings fact table |
| `warehouse.sales_fact` | B | Detailed AdventureWorks sales enriched by product/customer |
| `warehouse.sales_dim` | B | Aggregate by day, month, product |

---

## .gitignore

```
terraform/terraform.tfvars
*.tfstate
*.tfstate.*
.terraform/
__pycache__/
*.pyc
```
