# GCP Mentoring Program — Data Platform

A GCP data platform template with two ingestion lanes feeding one BigQuery warehouse, orchestrated by Cloud Workflows and deployed via Cloud Build CI/CD.

**Terraform manages:** APIs, service accounts and IAM, GCS buckets, BigQuery dataset, Secret Manager container, Cloud SQL instance and database, plus the static egress IP, Cloud Router, and Cloud NAT used by Dataproc to reach Cloud SQL.
**Manual steps:** database passwords, the Secret Manager connection-string value, and AdventureWorks data import.

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

Expected: about 30 resources, including enabled APIs, service accounts and IAM, storage buckets, BigQuery dataset, Secret Manager, Cloud SQL, and Dataproc network egress resources. Terraform also reserves a static NAT IP and allows only that `/32` through Cloud SQL's public-IP authorized networks.

---

## Part B — Upload JDBC driver

```bash
# Download postgresql-42.7.3.jar from https://jdbc.postgresql.org/download/
gcloud storage cp postgresql-42.7.3.jar gs://${PROJECT_ID}-deploy/jars/
```

---

## Part C — Cloud SQL and AdventureWorks data

Terraform creates the PostgreSQL instance, `adventureworks` database, static
egress IP, Cloud Router, and Cloud NAT. The existing default subnet is reused;
Dataproc Serverless jobs that connect to Cloud SQL must select that subnet.

For an existing sandbox created before Cloud SQL was managed by Terraform,
import the instance and database once before applying the updated configuration:

```bash
cd terraform
terraform import google_sql_database_instance.adventureworks \
  projects/${PROJECT_ID}/instances/adventureworks-db
terraform import google_sql_database.adventureworks \
  projects/${PROJECT_ID}/instances/adventureworks-db/databases/adventureworks
terraform apply
cd ..
```

Terraform outputs the Cloud SQL authorized egress address and Dataproc subnet:

```bash
terraform -chdir=terraform output dataproc_nat_ip
terraform -chdir=terraform output dataproc_subnet
```

Terraform enables Cloud SQL deletion protection. The instance and database
have `prevent_destroy`; remove those protections deliberately before teardown.
Cloud NAT has ongoing hourly and per-GiB charges, so destroy this sandbox's
resources when the mentoring project is finished.

Create or set an administrator password and create the pipeline user. Keep both
passwords out of source control:

```bash
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
GRANT USAGE ON SCHEMA production TO "pipeline-reader";
GRANT SELECT ON ALL TABLES IN SCHEMA production TO "pipeline-reader";
ALTER DEFAULT PRIVILEGES IN SCHEMA sales
  GRANT SELECT ON TABLES TO "pipeline-reader";
ALTER DEFAULT PRIVILEGES IN SCHEMA production
  GRANT SELECT ON TABLES TO "pipeline-reader";
SQL
```

### Store the pipeline connection string

Terraform creates the Secret Manager container but not its value. Add a version
after loading the database. In PowerShell, use the Cloud SQL public IP as the
connection host; the NAT IP is the client egress address, not the database host.
Use a temporary file:

```powershell
$PROJECT_ID = (gcloud config get-value project).Trim()
$sqlHost = gcloud sql instances describe adventureworks-db --project=$PROJECT_ID --format='value(ipAddresses[0].ipAddress)'
"host=$sqlHost;user=pipeline-reader;password=PIPELINE_PASSWORD;dbname=adventureworks" |
  Set-Content -NoNewline connection.txt

gcloud secrets versions add cloud-sql-connection-string `
  --project=$PROJECT_ID `
  --data-file=connection.txt

Remove-Item connection.txt
```

Do not commit `connection.txt` or replace the placeholders in this README with
real credentials.

> **Network note:** Cloud NAT gives Dataproc a static public egress IP, which Terraform adds to Cloud SQL as a `/32` authorized network. The AdventureWorks extract batch must use `--subnet=default` to use this NAT path. No VPN or broad `0.0.0.0/0` rule is required.

> **Schema note:** The extractor expects `sales.salesorderheader`,
> `sales.salesorderdetail`, `sales.customer`, `production.product`, and
> `production.productsubcategory`. Verify those tables exist after `install.sql`
> completes. The `pipeline-reader` account needs `SELECT` privileges in both
> `sales` and `production` schemas.

> **Teardown note:** Terraform manages the Cloud SQL instance/database and
> protects them from deletion. To tear down the sandbox, deliberately remove
> `prevent_destroy` in `terraform/cloud_sql.tf` and disable Cloud SQL deletion
> protection before running `terraform destroy`.

---

## Part D — Lane A: Airbnb flat files

```bash
# Upload the source CSVs and stage the two PySpark jobs
gcloud storage cp listings.csv calendar.csv reviews.csv \
  gs://${PROJECT_ID}-landing/raw/airbnb/
gcloud storage cp pyspark-jobs/airbnb/csv_to_parquet.py \
  pyspark-jobs/airbnb/transform_to_bq.py \
  gs://${PROJECT_ID}-deploy/jobs/airbnb/

# Extract all three CSVs to Parquet. Wait for this batch to succeed before
# submitting the transform batch.
gcloud dataproc batches submit pyspark gs://${PROJECT_ID}-deploy/jobs/airbnb/csv_to_parquet.py \
  --region=us-central1 \
  --service-account=sa-dataproc-jobs@${PROJECT_ID}.iam.gserviceaccount.com \
  --deps-bucket=gs://${PROJECT_ID}-deploy \
  -- --project=${PROJECT_ID}

gcloud dataproc batches submit pyspark gs://${PROJECT_ID}-deploy/jobs/airbnb/transform_to_bq.py \
  --region=us-central1 \
  --service-account=sa-dataproc-jobs@${PROJECT_ID}.iam.gserviceaccount.com \
  --deps-bucket=gs://${PROJECT_ID}-deploy \
  -- --project=${PROJECT_ID}
```

> **Dataproc note:** Dataproc Serverless includes a BigQuery connector. Do not
> add another connector with `spark.jars.packages`; loading a second copy can
> cause Spark class-loading errors. The transform writes `listings.csv` data to
> `${PROJECT_ID}.warehouse.airbnb_fact_listings`.

---

## Part E — Lane B: AdventureWorks (relational)

```bash
# Stage the Lane B jobs. The JDBC jar was uploaded in Part B.
gcloud storage cp pyspark-jobs/adventureworks/extract_adventureworks.py \
  pyspark-jobs/adventureworks/transform_adventureworks.py \
  gs://${PROJECT_ID}-deploy/jobs/adventureworks/

# Use the NAT-enabled subnet so this batch reaches Cloud SQL from its
# Terraform-allowlisted static egress IP. Wait for extraction to succeed.
gcloud dataproc batches submit pyspark gs://${PROJECT_ID}-deploy/jobs/adventureworks/extract_adventureworks.py \
  --region=us-central1 \
  --service-account=sa-dataproc-jobs@${PROJECT_ID}.iam.gserviceaccount.com \
  --deps-bucket=gs://${PROJECT_ID}-deploy \
  --jars=gs://${PROJECT_ID}-deploy/jars/postgresql-42.7.3.jar \
  --subnet=default \
  -- --project=${PROJECT_ID}

gcloud dataproc batches submit pyspark gs://${PROJECT_ID}-deploy/jobs/adventureworks/transform_adventureworks.py \
  --region=us-central1 \
  --service-account=sa-dataproc-jobs@${PROJECT_ID}.iam.gserviceaccount.com \
  --deps-bucket=gs://${PROJECT_ID}-deploy \
  -- --project=${PROJECT_ID}
```

> **Dataproc note:** Dataproc Serverless includes a BigQuery connector. Do not
> add another connector with `spark.jars.packages`; a duplicate can cause Spark
> class-loading errors. The extractor reads products from `production`, while
> orders and customers come from `sales`.

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
