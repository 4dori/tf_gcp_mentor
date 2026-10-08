**Mentor Setup Guide**

Full Program Walkthrough & Prep

_Build and test the entire pipeline yourself before a mentee ever sees it_

# Contents

# What this guide is for

You're going to stand up a throwaway sandbox Google Cloud project and build the entire program in it — Terraform foundation, both ingestion lanes, orchestration, CI/CD, and the dashboard — before handing the code to a mentee, who applies the same runbook to their own subscription.

This is deliberately the same runbook a mentee will follow (Parts A through H below). That's the point: the only way to know the instructions are trustworthy is to have run them yourself, start to finish, recently.

Budget significantly more than the Terraform-only pass — a full first run including Cloud SQL setup, both lanes, and orchestration realistically takes the better part of a day, not an hour. Subsequent runs (after you've fixed whatever broke) go much faster.

# Prerequisites checklist

- A Google account you're comfortable using for a cloud sandbox — not your Anthropic/corporate one
- A payment method for account verification (see the free trial note below)
- Ability to install command-line tools on your machine
- A git hosting account to hand the module off from
- A full day, realistically, for the first end-to-end pass

# Part A — Foundation

## Step 1 — Create your sandbox project

1.  Go to console.cloud.google.com and sign in with the account you're dedicating to this.
2.  Create a new project — something like gcp-mentoring-sandbox-yourname. The project ID is globally unique and can't change later; the display name can.
3.  Link a billing account. If you don't have one yet, project setup walks you through creating one.

**ℹ On the free trial**

As of this writing, new Google Cloud customers get $300 in free credit valid for 90 days, which comfortably covers this kind of testing. Terms change, so confirm current details at cloud.google.com/free before relying on them.

**⚠ Before you continue**

• Use a personal, non-corporate email for this sandbox — same rule you'll give mentees.

• This is your own testing project, separate from any mentee's. Don't reuse it as a mentee's environment later.

## Step 2 — Install local tooling

\# macOS

brew install --cask google-cloud-sdk

brew tap hashicorp/tap && brew install hashicorp/tap/terraform

\# Linux

curl https://sdk.cloud.google.com | bash && exec -l $SHELL

\# Terraform: see developer.hashicorp.com/terraform/install for the apt/binary options

\# Windows

\# gcloud: cloud.google.com/sdk/docs/install | Terraform: choco install terraform

gcloud --version

terraform -version

git --version

## Step 3 — Authenticate

gcloud init

gcloud auth login

gcloud auth application-default login # separate credential store — Terraform reads this one

gcloud config set project YOUR_PROJECT_ID

gcloud config list

## Step 4 — Bootstrap: the state bucket

gcloud storage buckets create gs://YOUR_PROJECT_ID-tf-state --location=us-central1

gcloud storage buckets update gs://YOUR_PROJECT_ID-tf-state --versioning

**⚠ Bucket names are global**

• If that name is taken, bucket creation fails with a 409 — add a random suffix and retry.

## Step 5 — The Terraform foundation module

1.  Create the repo you'll hand to mentees and add versions.tf, variables.tf, apis.tf, service_accounts.tf, iam.tf, outputs.tf, terraform.tfvars.example, README.md.
2.  cp terraform.tfvars.example terraform.tfvars and fill in your sandbox project_id.
3.  Edit versions.tf's backend block to point at the state bucket from Step 4.

## Step 6 — init, plan, apply

terraform init

terraform plan

terraform apply

Expect roughly 10 resources on the first apply (7 APIs + 3 service accounts, before the IAM bindings that reference them).

## Common errors — foundation layer

| **Symptom / error** | **Likely cause** | **Fix** |
| --- | --- | --- |
| "Error 403: ...does not have permission to enable service" | Not Owner/Editor on the project, or billing not linked | Check your IAM role; confirm billing is linked |
| "Error 409: ...already exists" on the state bucket | Bucket names are global | Pick a more unique name |
| "Error 403" creating a service account right after apply starts | IAM API just enabled, hasn't propagated | Wait 1-2 min, re-run apply — it's safe to re-run |
| "Error acquiring the state lock" | A previous run didn't finish cleanly | Wait, then retry; use terraform force-unlock only if certain nothing else is running |

## Step 7 — Verify

gcloud iam service-accounts list --project=YOUR_PROJECT_ID

gcloud services list --enabled --project=YOUR_PROJECT_ID

# Architecture recap

_Figure 1 — the platform you're building across the parts below._

_Figure 2 — Lane A (Airbnb) and Lane B (AdventureWorks) share the same landing, transform, orchestration, and CI/CD pattern._

# Part B — Extend Terraform: storage, warehouse, secrets, budget

Add four new files to the same directory as your foundation module (versions.tf, service_accounts.tf, etc.) — Terraform picks up every .tf file in a directory as one configuration, so these join the same plan automatically.

## storage.tf

resource "google_storage_bucket" "landing" {

name = "${var.project_id}-landing"

location = var.region

uniform_bucket_level_access = true

force_destroy = true # convenience for a learning project; drop this for anything real

}

resource "google_storage_bucket" "deploy" {

name = "${var.project_id}-deploy"

location = var.region

uniform_bucket_level_access = true

force_destroy = true

}

resource "google_storage_bucket_iam_member" "dataproc_jobs_landing" {

bucket = google_storage_bucket.landing.name

role = "roles/storage.objectAdmin"

member = "serviceAccount:${google_service_account.dataproc_jobs.email}"

}

resource "google_storage_bucket_iam_member" "cloudbuild_deploy" {

bucket = google_storage_bucket.deploy.name

role = "roles/storage.objectAdmin"

member = "serviceAccount:${google_service_account.cloudbuild.email}"

}

This is the bucket-level IAM pattern flagged as a placeholder in the foundation module's iam.tf — you're now filling it in, because the buckets it references finally exist.

## bigquery.tf

resource "google_bigquery_dataset" "warehouse" {

dataset_id = "warehouse"

location = var.region

description = "Fact/dim tables for both the Airbnb and AdventureWorks lanes"

}

## secretmanager.tf

resource "google_secret_manager_secret" "cloud_sql_conn" {

secret_id = "cloud-sql-connection-string"

replication {

auto {}

}

}

resource "google_secret_manager_secret_iam_member" "dataproc_jobs_secret_access" {

secret_id = google_secret_manager_secret.cloud_sql_conn.id

role = "roles/secretmanager.secretAccessor"

member = "serviceAccount:${google_service_account.dataproc_jobs.email}"

}

**ℹ Terraform creates the secret container, not the value**

The connection string itself gets added afterward with a gcloud command (Part C), never written into a .tf file or committed to git — Terraform state and git history both persist longer than you want a live password to.

## budget.tf and its variables

variable "billing_account_id" {

type = string

}

variable "budget_amount_usd" {

type = number

default = 50

}

resource "google_billing_budget" "monthly" {

billing_account = var.billing_account_id

display_name = "mentoring-program-budget"

budget_filter {

projects = \["projects/${var.project_id}"\]

}

amount {

specified_amount {

currency_code = "USD"

units = tostring(var.budget_amount_usd)

}

}

threshold_rules { threshold_percent = 0.5 }

threshold_rules { threshold_percent = 0.9 }

threshold_rules { threshold_percent = 1.0 }

}

Add billing_account_id to your terraform.tfvars (the ID you saved earlier, formatted like XXXXXX-XXXXXX-XXXXXX). By default, budget alert emails go to anyone with a billing admin/user role on the account — for a solo project, that's you, automatically.

terraform plan

terraform apply

# Part C — Cloud SQL: the AdventureWorks source

## Create the instance

gcloud sql instances create adventureworks-db \\

\--database-version=POSTGRES_15 \\

\--tier=db-custom-2-8192 \\

\--region=us-central1 \\

\--availability-type=ZONAL \\

\--root-password=TEMPORARY_PASSWORD_CHANGE_ME

**⚠ On that root password**

• Treat it as temporary from the moment you type it — it's only there to bootstrap the instance.

• Typing a real password directly after --root-password puts it in your shell history. For anything beyond this throwaway sandbox, omit the flag and let gcloud prompt you instead.

gcloud sql databases create adventureworks --instance=adventureworks-db

## Load the AdventureWorks data

Cloud SQL doesn't provide an official Postgres port of AdventureWorks — it's a SQL Server sample database. Use a community-maintained conversion, which ships the CSVs and an install.sql. Verify the repo still works before relying on it — third-party repos go stale.

[lorint/AdventureWorks-for-Postgres on GitHub](https://github.com/lorint/AdventureWorks-for-Postgres)

Connect to your instance through the Cloud SQL Auth Proxy rather than exposing yourself to the public IP directly while you load data:

curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2/cloud-sql-proxy.linux.amd64

chmod +x cloud-sql-proxy

./cloud-sql-proxy YOUR_PROJECT_ID:us-central1:adventureworks-db &

\# in another terminal, following that repo's own install instructions:

psql "host=127.0.0.1 port=5432 dbname=adventureworks user=postgres" -f install.sql

## Create a least-privilege app user

The pipeline should never connect as the root/postgres user. Create a dedicated read-only account for it:

gcloud sql users create pipeline-reader --instance=adventureworks-db --password=ANOTHER_TEMPORARY_PASSWORD

\-- run these via psql, connected through the proxy:

GRANT CONNECT ON DATABASE adventureworks TO "pipeline-reader";

GRANT USAGE ON SCHEMA sales TO "pipeline-reader";

GRANT SELECT ON ALL TABLES IN SCHEMA sales TO "pipeline-reader";

## Store the connection string

printf 'postgresql://pipeline-reader:PASSWORD@&lt;PUBLIC_IP&gt;:5432/adventureworks' | \\

gcloud secrets versions add cloud-sql-connection-string --data-file=-

**⚠ A deliberate shortcut, flagged so you don't mistake it for a best practice**

• Dataproc Serverless batches don't have a fixed IP, so connecting to Cloud SQL's public IP from them means authorizing a wide network range (0.0.0.0/0) on the instance — acceptable only because this is a disposable learning project with a read-only app account and no sensitive data.

• The production-correct approach is a private IP Cloud SQL instance reachable only from a VPC that your Dataproc Serverless batches also run in. That's listed as an optional extension if you want the more rigorous version.

# Part D — Lane A: Airbnb ingestion

## Upload the CSVs

gcloud storage cp listings.csv calendar.csv reviews.csv gs://YOUR_PROJECT_ID-landing/raw/airbnb/

## Job 1 — csv_to_parquet.py

from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("airbnb-csv-to-parquet").getOrCreate()

RAW = "gs://YOUR_PROJECT_ID-landing/raw/airbnb/"

CURATED = "gs://YOUR_PROJECT_ID-landing/curated/airbnb/"

for name in \["listings", "calendar", "reviews"\]:

df = spark.read.option("header", True).option("multiLine", True).option("escape", '"').csv(RAW + name + ".csv")

assert df.columns, f"{name}.csv has no columns — check the upload before continuing"

df.write.mode("overwrite").parquet(CURATED + name)

spark.stop()

gcloud dataproc batches submit pyspark gs://YOUR_PROJECT_ID-deploy/jobs/airbnb/csv_to_parquet.py \\

\--project=YOUR_PROJECT_ID --region=us-central1 \\

\--batch=airbnb-csv-to-parquet \\

\--service-account=sa-dataproc-jobs@YOUR_PROJECT_ID.iam.gserviceaccount.com \\

\--deps-bucket=gs://YOUR_PROJECT_ID-deploy

gcloud dataproc batches describe airbnb-csv-to-parquet --region=us-central1

## Job 2 — transform_to_bq.py

from pyspark.sql import SparkSession, functions as F

spark = SparkSession.builder.appName("airbnb-transform").getOrCreate()

listings = spark.read.parquet("gs://YOUR_PROJECT_ID-landing/curated/airbnb/listings")

fact = (listings

.withColumn("price_usd", F.regexp_replace("price", "\[$,\]", "").cast("double"))

.filter(F.col("price_usd").isNotNull())

.select("id", "host_id", "neighbourhood_cleansed", "room_type", "price_usd",

"minimum_nights", "number_of_reviews", "review_scores_rating"))

\# data-quality checks — fail loudly before writing, rather than land a bad table

row_count = fact.count()

assert row_count > 0, "airbnb fact table would be empty — stopping before the BigQuery write"

null_ids = fact.filter(F.col("id").isNull()).count()

assert null_ids == 0, f"{null_ids} rows with a null id — stopping before the BigQuery write"

(fact.write.format("bigquery")

.option("table", "YOUR_PROJECT_ID.warehouse.airbnb_fact_listings")

.option("temporaryGcsBucket", "YOUR_PROJECT_ID-deploy")

.mode("overwrite")

.save())

spark.stop()

gcloud dataproc batches submit pyspark gs://YOUR_PROJECT_ID-deploy/jobs/airbnb/transform_to_bq.py \\

\--project=YOUR_PROJECT_ID --region=us-central1 \\

\--batch=airbnb-transform \\

\--service-account=sa-dataproc-jobs@YOUR_PROJECT_ID.iam.gserviceaccount.com \\

\--deps-bucket=gs://YOUR_PROJECT_ID-deploy

**ℹ BigQuery connector**

Dataproc Serverless includes a BigQuery connector. Do not add another connector with `spark.jars.packages`; a duplicate can cause Spark class-loading errors.

bq query --use_legacy_sql=false \\

'SELECT COUNT(\*) FROM \`YOUR_PROJECT_ID.warehouse.airbnb_fact_listings\`'

# Part E — Lane B: AdventureWorks ingestion

## Get the JDBC driver

curl -LO https://jdbc.postgresql.org/download/postgresql-42.7.3.jar

gcloud storage cp postgresql-42.7.3.jar gs://YOUR_PROJECT_ID-deploy/jars/

## Job 1 — extract_adventureworks.py

from pyspark.sql import SparkSession

from google.cloud import secretmanager

def get_secret(project_id, secret_id, version="latest"):

client = secretmanager.SecretManagerServiceClient()

name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"

return client.access_secret_version(name=name).payload.data.decode("utf-8")

PROJECT_ID = "YOUR_PROJECT_ID"

conn_string = get_secret(PROJECT_ID, "cloud-sql-connection-string")

\# parse host / user / password out of conn_string here — never hardcode any of them

spark = SparkSession.builder.appName("adventureworks-extract").getOrCreate()

jdbc_url = "jdbc:postgresql://&lt;HOST_FROM_SECRET&gt;:5432/adventureworks"

tables = \["sales.salesorderheader", "sales.salesorderdetail", "sales.product", "sales.customer"\]

for t in tables:

df = (spark.read.format("jdbc")

.option("url", jdbc_url)

.option("dbtable", t)

.option("user", "&lt;FROM_SECRET&gt;")

.option("password", "&lt;FROM_SECRET&gt;")

.option("driver", "org.postgresql.Driver")

.load())

df.write.mode("overwrite").parquet(

f"gs://YOUR_PROJECT_ID-landing/curated/adventureworks/{t.split('.')\[-1\]}")

spark.stop()

gcloud dataproc batches submit pyspark gs://YOUR_PROJECT_ID-deploy/jobs/adventureworks/extract_adventureworks.py \\

\--project=YOUR_PROJECT_ID --region=us-central1 \\

\--batch=adventureworks-extract \\

\--service-account=sa-dataproc-jobs@YOUR_PROJECT_ID.iam.gserviceaccount.com \\

\--deps-bucket=gs://YOUR_PROJECT_ID-deploy \\

\--jars=gs://YOUR_PROJECT_ID-deploy/jars/postgresql-42.7.3.jar

## Job 2 — transform to sales_fact / sales_dim

Same pattern as Lane A's transform job: read the parquet, build fact/dim tables (a detailed sales fact enriched by product/customer dimensions, plus an aggregate by day/month/product), run the same row-count and null checks, write to BigQuery in the same warehouse dataset.

# Part F — Orchestration: Cloud Workflows

A workflow definition submits each Dataproc Serverless batch in order. Skeleton shape:

main:

steps:

\- runAirbnbExtract:

call: googleapis.dataproc.v1.projects.locations.batches.create

args:

parent: projects/YOUR_PROJECT_ID/locations/us-central1

batchId: airbnb-csv-to-parquet-${string(sys.now())}

body:

pysparkBatch:

mainPythonFileUri: gs://YOUR_PROJECT_ID-deploy/jobs/airbnb/csv_to_parquet.py

result: airbnbExtractResult

\# ...repeat the pattern for the transform step, and for both AdventureWorks steps

**⚠ This is more fiddly than it looks — budget extra time**

• The batches.create connector call returns once a batch is submitted, not once it finishes. To make each step wait for the previous batch to actually complete before starting the next, you need a polling loop (call batches.get in a loop with a short sys.sleep between checks) — Google's Workflows connector documentation has the standard pattern for this.

• Get one lane working end-to-end manually first (as in Parts D and E) before wiring up Workflows — debugging orchestration on top of jobs you haven't verified independently is much harder than debugging either one alone.

gcloud workflows deploy airbnb-pipeline \\

\--source=pipeline.yaml --location=us-central1 \\

\--service-account=sa-workflows@YOUR_PROJECT_ID.iam.gserviceaccount.com

gcloud workflows run airbnb-pipeline --location=us-central1

gcloud workflows executions list airbnb-pipeline --location=us-central1

# Part G — CI/CD: Cloud Build

steps:

\- name: 'hashicorp/terraform:1.7'

args: \['init'\]

dir: 'terraform'

\- name: 'hashicorp/terraform:1.7'

args: \['apply', '-auto-approve'\]

dir: 'terraform'

\- name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'

entrypoint: 'sh'

args: \['-c', 'gcloud storage cp pyspark-jobs/airbnb/*.py gs://YOUR_PROJECT_ID-deploy/jobs/airbnb/; gcloud storage cp pyspark-jobs/adventureworks/*.py gs://YOUR_PROJECT_ID-deploy/jobs/adventureworks/'\]

\- name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'

entrypoint: 'gcloud'

args: \['storage', 'cp', 'workflows/pipeline.yaml', 'gs://YOUR_PROJECT_ID-deploy/workflows/'\]

\- name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'

entrypoint: 'gcloud'

args: \['workflows', 'deploy', 'airbnb-pipeline', '--source=workflows/pipeline.yaml', '--location=us-central1'\]

options:

logging: CLOUD_LOGGING_ONLY

**⚠ auto-approve means CI can change real infrastructure unattended**

• That's the point of CI/CD, but it also means a bad terraform apply -auto-approve merges straight into your project with nobody reviewing the plan output first. For anything beyond this program, split it into a plan-only trigger on pull requests and an apply trigger on merge to main, so a human reads the plan before it runs.

gcloud builds triggers create github \\

\--repo-name=YOUR_REPO --repo-owner=YOUR_GITHUB_USER \\

\--branch-pattern="^main$" --build-config=cloudbuild.yaml \\

\--service-account=projects/YOUR_PROJECT_ID/serviceAccounts/sa-cloudbuild@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Part H — Dashboard: Looker Studio

- Go to lookerstudio.google.com, create a new report, and connect the BigQuery connector to your warehouse dataset.
- Suggested visuals: a bar chart of average price by room_type (Airbnb), a line chart of sales by month (AdventureWorks), and a couple of scorecards for totals.
- Share the report link with your mentor once it's readable by someone who's never seen the data before.

# Troubleshooting: the rest of the pipeline

In addition to the foundation-layer errors covered earlier, these are the ones most worth knowing about ahead of time.

| **Symptom / error** | **Likely cause** | **Fix** |
| --- | --- | --- |
| Batch stays in PENDING for several minutes | Dataproc Serverless is provisioning compute for the first time in this project | Normal on a cold start — wait and re-check with gcloud dataproc batches describe; investigate quotas only if it's stuck past ~10 minutes |
| "ClassNotFoundException: org.postgresql.Driver" | The JDBC driver jar wasn't attached to the batch | Add --jars=gs://.../postgresql-42.7.3.jar to the submit command |
| Connection refused / timeout reaching Cloud SQL | The instance's authorized networks don't include wherever the batch is connecting from | Re-check the authorized networks on the Cloud SQL instance (see the flagged shortcut in Part C) |
| BigQuery write fails: temporaryGcsBucket not accessible | sa-dataproc-jobs lacks IAM access on that specific bucket | Confirm the google_storage_bucket_iam_member binding in storage.tf applied correctly |
| Workflow execution fails at the batches.create step | sa-workflows lacks dataproc.editor, or the YAML body is malformed | Check the service account's IAM roles first, then validate the YAML structure |
| Cloud Build trigger never fires on push | Trigger isn't connected to the right repo/branch, or the webhook wasn't installed | Re-check the trigger configuration in the console |
| terraform apply works locally but fails from Cloud Build | sa-cloudbuild is missing a role your personal account happens to have | Add the specific missing role explicitly — resist the urge to grant it Editor to make the error go away |
| BigQuery table exists but has 0 rows | A silent failure earlier in the chain — often a wrong GCS path | Check the batch's logs in Cloud Logging for the actual job, not just its final status |

# Optional extensions (once the core pipeline works)

- Stand up Cloud Composer and reimplement one lane's orchestration in Airflow, to compare it against Cloud Workflows directly.
- Provision and manage a Dataproc cluster on Compute Engine by hand, to see what Dataproc Serverless was abstracting away.
- Add Workload Identity Federation so Cloud Build never needs a long-lived service account key.
- Move Cloud SQL to a private IP inside a VPC, reachable from Dataproc Serverless via a subnet, instead of the public-IP shortcut used above.

# Tear down your sandbox test

terraform destroy

Also manually confirm the Cloud SQL instance is gone (Terraform doesn't manage it in this design — you created it directly with gcloud) — delete it explicitly if terraform destroy doesn't cover it:

gcloud sql instances delete adventureworks-db

If you won't reuse this sandbox project soon, consider deleting it entirely from the console to stop the clock on anything you might have missed.

# Package for handoff

- Push the Terraform module, PySpark job templates, workflow YAML, and cloudbuild.yaml to the repo mentees clone or fork from.
- Double-check terraform.tfvars (with your real project ID) was never committed — only terraform.tfvars.example should be in the repo.
- Double-check versions.tf's backend bucket still shows a generic placeholder, not your sandbox's actual bucket name.
- Confirm the AdventureWorks-for-Postgres source repo you're pointing mentees at still works — it's third-party and can go stale between rounds.
- Hand the mentee: the repo link, the Mentee Setup Guide, and the main program document.

# Ongoing maintenance

Re-run this entire guide against your sandbox whenever you change anything in the module or job templates, before handing an updated version to a new mentee. If you leave the sandbox sitting between rounds of testing, keep half an eye on its billing — Cloud SQL in particular bills continuously while it exists, unlike the serverless pieces.