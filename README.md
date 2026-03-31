# 🔒 Network Security — Phishing URL Detection

An end-to-end machine learning pipeline that ingests phishing-URL network data from MongoDB, trains a classifier, tracks experiments with MLflow, serves predictions via a FastAPI REST API and a Streamlit dashboard, and ships the whole stack to AWS (ECR + ECS) through a GitHub Actions CI/CD pipeline.

---

## 📑 Table of Contents

- [Overview](#overview)
- [Project Architecture](#project-architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Pipeline Stages](#pipeline-stages)
- [Model Training & Experiment Tracking](#model-training--experiment-tracking)
- [API Endpoints](#api-endpoints)
- [Streamlit Dashboard](#streamlit-dashboard)
- [Outputs](#outputs)
- [Setup & Installation](#setup--installation)
- [Environment Variables](#environment-variables)
- [Docker](#docker)
- [CI/CD — GitHub Actions](#cicd--github-actions)
- [AWS Deployment](#aws-deployment)

---

## Overview

This project solves the binary classification problem of detecting phishing URLs. Given a set of URL-level and page-level features (30 features in total), the model predicts whether a URL is **phishing (1)** or **legitimate (0)**.

The solution follows a modular, production-grade ML pipeline pattern:

```
MongoDB  →  Data Ingestion  →  Data Validation  →  Data Transformation
         →  Model Training  →  FastAPI / Streamlit  →  AWS S3 / ECR / ECS
```

---

## Project Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────────────┐
│  MongoDB    │────▶│              Training Pipeline                    │
│  (raw data) │     │  Ingestion → Validation → Transformation → Train  │
└─────────────┘     └───────────────────────┬──────────────────────────┘
                                            │ artifacts + model
                                ┌───────────▼───────────┐
                                │   final_model/         │
                                │   ├── model.pkl        │
                                │   └── preprocessor.pkl │
                                └───────────┬───────────┘
                           ┌────────────────┼─────────────────┐
                           ▼                ▼                  ▼
                     FastAPI REST     Streamlit UI        AWS S3 Sync
                     (app.py)        (streamlit_app.py)  (Artifacts +
                     /train          Predictions +        final_model)
                     /predict        Visualisations
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Data storage | Local CSV file (`Network_Data/phisingData.csv`) |
| ML framework | scikit-learn (KNNImputer, GridSearchCV, Random Forest, GBM, AdaBoost, Decision Tree, Logistic Regression) |
| Experiment tracking | MLflow + DagsHub |
| API | FastAPI + Uvicorn |
| UI | Streamlit + Plotly |
| Data drift | scipy (KS-test) |
| Cloud storage | AWS S3 |
| Containerisation | Docker |
| CI/CD | GitHub Actions |
| Deployment | AWS ECR + ECS (self-hosted runner) |
| Certificate pinning | certifi |

---

## Project Structure

```
NetworkSecurity/
├── app.py                          # FastAPI application
├── main.py                         # Manual pipeline runner
├── push_data.py                    # Upload CSV to MongoDB
├── streamlit_app.py                # Streamlit dashboard
├── Dockerfile
├── requirements.txt
├── setup.py
├── data_schema/
│   └── schema.yaml                 # 31-column schema + column types
├── Network_Data/
│   └── phisingData.csv             # Raw dataset
├── networksecurity/
│   ├── components/                 # Pipeline stage implementations
│   │   ├── data_ingestion.py
│   │   ├── data_validation.py
│   │   ├── data_transformation.py
│   │   └── model_trainer.py
│   ├── pipeline/
│   │   └── training_pipeline.py    # Orchestrates all stages
│   ├── entity/
│   │   ├── config_entity.py        # Dataclasses for stage configs
│   │   └── artifact_entity.py      # Dataclasses for stage outputs
│   ├── constant/
│   │   └── training_pipeline/      # All project-wide constants
│   ├── utils/
│   │   ├── main_utils/utils.py     # YAML / numpy / pickle helpers + evaluate_models
│   │   └── ml_utils/
│   │       ├── metric/             # Classification metric artifact
│   │       └── model/estimator.py  # NetworkModel wrapper (preprocessor + model)
│   ├── exception/exception.py
│   ├── logging/logger.py
│   └── cloud/s3_syncer.py
├── mlruns/                         # MLflow experiment runs
├── final_model/                    # Saved preprocessor + best model
├── Artifacts/                      # Timestamped pipeline artifacts
├── prediction_output/output.csv    # Latest batch predictions
└── .github/workflows/main.yml      # CI/CD workflow
```

---

## Pipeline Stages

### 1 · Data Ingestion
- Reads the raw dataset directly from **`Network_Data/phisingData.csv`** on disk — no database connection required.
- Replaces `"na"` strings with `NaN`.
- Saves the raw dataset to `Artifacts/<timestamp>/data_ingestion/feature_store/phisingData.csv`.
- Splits 80/20 into train/test and saves to `Artifacts/<timestamp>/data_ingestion/ingested/`.
- **Output artifact:** `DataIngestionArtifact(trained_file_path, test_file_path)`

### 2 · Data Validation
- Validates that the number of columns in train and test sets matches the **31 columns** defined in `data_schema/schema.yaml`.
- Runs a **Kolmogorov–Smirnov drift test** (threshold `p < 0.05`) on every feature column between train and test sets.
- Writes a `drift_report.yaml` listing the p-value and drift status for each column.
- Saves validated CSV files to `Artifacts/<timestamp>/data_validation/validated/`.
- **Output artifact:** `DataValidationArtifact(validation_status, valid_train_file_path, valid_test_file_path, drift_report_file_path)`

### 3 · Data Transformation
- Drops the target column `Result` from features.
- Replaces `-1` labels with `0` so the target is strictly binary (`0` = legitimate, `1` = phishing).
- Fits a **KNNImputer** (`n_neighbors=3`, `weights="uniform"`) on the training set and transforms both splits.
- Saves the resulting numpy arrays (`.npy`) and the fitted preprocessor (`.pkl`) under `Artifacts/<timestamp>/data_transformation/`.
- Also saves `final_model/preprocessor.pkl` for serving.
- **Output artifact:** `DataTransformationArtifact(transformed_object_file_path, transformed_train_file_path, transformed_test_file_path)`

### 4 · Model Training
- Runs **GridSearchCV (cv=3)** across five classifiers:

  | Model | Hyperparameters searched |
  |---|---|
  | Random Forest | `n_estimators` ∈ {8, 16, 32, 128, 256} |
  | Decision Tree | `criterion` ∈ {gini, entropy, log_loss} |
  | Gradient Boosting | `learning_rate`, `subsample`, `n_estimators` |
  | Logistic Regression | default |
  | AdaBoost | `learning_rate`, `n_estimators` |

- Selects the model with the **highest F1 score** on the test set.
- Wraps the best model + preprocessor into a `NetworkModel` object.
- Saves `final_model/model.pkl` (best estimator) and `final_model/preprocessor.pkl`.
- Logs **F1, Precision, Recall** for both train and test splits to **MLflow**.
- **Output artifact:** `ModelTrainerArtifact(trained_model_file_path, train_metric_artifact, test_metric_artifact)`

### 5 · Cloud Sync (S3)
- After training, `Artifacts/` → `s3://netwwoorksecurity/artifact/<timestamp>/`
- `final_model/` → `s3://netwwoorksecurity/final_model/<timestamp>/`

---

## Model Training & Experiment Tracking

MLflow runs are stored in `mlruns/` and can also be tracked on **DagsHub**.

Metrics logged per run:

| Metric | Description |
|---|---|
| `f1_score` | F1 score on the test set |
| `precision` | Precision score on the test set |
| `recall_score` | Recall score on the test set |

To view the MLflow UI locally:

```bash
mlflow ui
```

Then open `http://127.0.0.1:5000`.

---

## API Endpoints

Start the server:

```bash
python app.py
# or
uvicorn app:app --host localhost --port 8000 --reload
```

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Redirects to `/docs` (Swagger UI) |
| `GET` | `/train` | Triggers the full training pipeline |
| `POST` | `/predict` | Accepts a CSV file upload and returns an HTML table of predictions |

### `/predict` — example with curl

```bash
curl -X POST "http://localhost:8000/predict" \
     -F "file=@valid_data/test.csv" \
     --output predictions.html
```

The response renders via `templates/table.html` — a Bootstrap-styled HTML table with an extra `predicted_column` appended.  
Results are also saved to `prediction_output/output.csv`.

---

## Streamlit Dashboard

```bash
streamlit run streamlit_app.py
```

Pages:

| Page | Description |
|---|---|
| **Home** | Project overview and usage instructions |
| **Make Predictions** | Upload a CSV → instant predictions + pie chart of threat distribution + downloadable results CSV |
| **Train Model** | Trigger a full pipeline run from the UI |
| **About** | Tech stack and contact info |

---

## Outputs

After a successful pipeline run the following files are produced:

```
Artifacts/
└── <MM_DD_YYYY_HH_MM_SS>/
    ├── data_ingestion/
    │   ├── feature_store/phisingData.csv       # Raw data pulled from MongoDB
    │   └── ingested/
    │       ├── train.csv                        # 80% training split
    │       └── test.csv                         # 20% test split
    ├── data_validation/
    │   ├── validated/
    │   │   ├── train.csv                        # Validated training data
    │   │   └── test.csv                         # Validated test data
    │   └── drift_report/
    │       └── report.yaml                      # Per-column KS-test p-value + drift flag
    ├── data_transformation/
    │   ├── transformed/
    │   │   ├── train.npy                        # KNN-imputed training array
    │   │   └── test.npy                         # KNN-imputed test array
    │   └── transformed_object/
    │       └── preprocessing.pkl               # Fitted KNNImputer pipeline
    └── model_trainer/
        └── trained_model/
            └── model.pkl                        # NetworkModel(preprocessor + best estimator)

final_model/
├── model.pkl                                   # Best estimator (for serving)
└── preprocessor.pkl                            # Fitted KNNImputer (for serving)

prediction_output/
└── output.csv                                  # Latest predictions with appended column

logs/
└── <MM_DD_YYYY_HH_MM_SS>.log                  # Timestamped application log

mlruns/
└── 0/
    └── <run_id>/
        ├── metrics/                             # f1_score, precision, recall_score
        └── tags/                               # Run metadata
```

---

## Setup & Installation

### Prerequisites

- Python 3.10+
- AWS credentials (for S3 sync and deployment)

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/NetworkSecurity.git
cd NetworkSecurity

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
# or install as a package
pip install -e .

# 4. Create a .env file (see Environment Variables section)

# 5. Run the training pipeline
python main.py

# 7. Start the API server
python app.py

# 8. (Optional) Start the Streamlit dashboard
streamlit run streamlit_app.py
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
AWS_REGION=<your-region>
```

> No database credentials needed — data is read directly from `Network_Data/phisingData.csv`.

---

## Docker

```bash
# Build
docker build -t networksecurity:latest .

# Run
docker run -d -p 8080:8080 \
  -e AWS_ACCESS_KEY_ID=<key> \
  -e AWS_SECRET_ACCESS_KEY=<secret> \
  -e AWS_REGION=<region> \
  networksecurity:latest
```

---

## CI/CD — GitHub Actions

The workflow at `.github/workflows/main.yml` has three jobs that run on every push to `main`:

| Job | Trigger | Steps |
|---|---|---|
| **Continuous Integration** | push to `main` | Lint + unit test placeholders |
| **Continuous Delivery** | after CI passes | Configure AWS credentials → login to ECR → `docker build` + `docker push` |
| **Continuous Deployment** | after CD passes | Pull latest image from ECR → `docker run` on self-hosted runner → `docker system prune` |

### Required GitHub Secrets

| Secret | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | AWS IAM access key |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key |
| `AWS_REGION` | e.g. `us-east-1` |
| `ECR_REPOSITORY_NAME` | ECR repository name |
| `AWS_ECR_LOGIN_URI` | ECR registry URI (e.g. `<account>.dkr.ecr.<region>.amazonaws.com`) |

---

## AWS Deployment

1. **ECR** — Docker image is built and pushed automatically by the CD job.
2. **ECS / Self-hosted runner** — The deployment job pulls the latest image and runs the container on port `8080`.
3. **S3** — Pipeline artifacts and final models are synced to `s3://netwwoorksecurity/` after each training run.

---

*Author: Shrey Golekar · shreygolekar@gmail.com*
