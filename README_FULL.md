# Drive & Notion Folder Automation (Refactor Example)

This repository contains a **refactored version of a project originally designed and implemented by me**, which is currently running in production within a real company environment.

For **privacy and confidentiality reasons**, the original production codebase cannot be shared publicly.  
This repository provides a **functionally equivalent refactor**, preserving the overall architecture, patterns, and technical decisions, while removing or abstracting any company-specific, sensitive, or identifying information.

The purpose of this refactor is to **demonstrate the technical approach, design decisions, and integration patterns** used in the original system—without exposing private business logic, credentials, or data.

⚠️ **Important note**  
This code is intended as a **technical reference and portfolio example**. It does not contain credentials, secrets, or confidential information.

---

## 🧩 What does this service do?

- Queries a **Notion database**
- Detects clients pending processing
- Automatically creates a **folder structure in Google Drive**
- Moves and renames documents from a template folder
- Marks the client as processed in Notion
- Stores an **execution log in Google Cloud Storage**
- Exposes an **HTTP endpoint (Flask)** for remote execution (e.g. Cloud Run)

---

## 📁 Project structure

```text
.
├── main.py            # Main application (Flask + business logic)
├── gcs_helpers.py     # Google Cloud Storage helpers
├── requirements.txt   # Python dependencies
├── Dockerfile         # Docker image definition
├── .dockerignore      # Docker build exclusions
├── .gitignore         # Git exclusions
```

---

## 🔐 Secret management

This project **does NOT include secrets in the codebase**.

All sensitive configuration is loaded from **Google Secret Manager**, using:

- Application Default Credentials (ADC)
- An environment variable pointing to the secret resource

The secret is expected to contain a JSON payload with at least:

- A Google Drive service account
- A Notion API token
- Google Drive folder IDs
- A Notion database ID

---

## 🌍 Environment variables

### Required

```bash
GCP_SECRET_NAME=<secret-resource-name>
```

Example:

```
projects/123456/secrets/my-secret/versions/latest
```

---

## ▶️ Run locally

**Requirements:**
- Python 3.10+
- Google Cloud SDK (`gcloud`)
- Application Default Credentials enabled

```bash
gcloud auth application-default login
pip install -r requirements.txt
export GCP_SECRET_NAME="projects/.../secrets/.../versions/latest"
python main.py
```

---

## 🐳 Run with Docker

```bash
docker build -t drive-notion-automation .
docker run -p 8080:8080 \
  -e GCP_SECRET_NAME="projects/.../secrets/.../versions/latest" \
  drive-notion-automation
```

---

## ☁️ Recommended deployment

This service is designed to run on:

- Google Cloud Run
- Google Compute Engine
- Any environment with Application Default Credentials enabled

---

## 🧪 DRY RUN mode

To test the full workflow without modifying Google Drive or Notion:

```bash
export DRY_RUN=1
```

All operations will be simulated and only logs will be written.

---

## 📌 Disclaimer

This repository is a **refactored technical example** created for demonstration and portfolio purposes.  
It does not expose real production data, credentials, or confidential company information.

---

## 📄 License

Free to use for educational and reference purposes.
