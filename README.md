# Drive & Notion Folder Automation

Automation service that provisions Google Drive folder structures for Notion records and manages document templates.

This repository contains a **refactored and anonymized version** of a production system currently used in a real company environment.  
The original implementation cannot be published due to confidentiality constraints.

## What it does

- Queries a Notion database for pending clients
- Creates structured folder hierarchies in Google Drive
- Copies and renames documents from templates
- Updates Notion records once processing is complete
- Writes execution logs to Google Cloud Storage
- Exposes an HTTP endpoint for automated execution

## Key technical points

- Integration between Notion API and Google Drive API
- Secrets managed via Google Secret Manager
- Stateless execution with persistent logs
- Dockerized service designed for Cloud Run
- DRY_RUN mode for non-destructive testing

## Disclaimer

This repository is a **technical reference and portfolio example**.  
All sensitive information, credentials, and company-specific logic have been removed or abstracted.
