**Project Nexus Deployment Runbook**
=====================================

**Author:** David (ML Engineer)
**Date:** 2024-06-09
**Version:** 1.0

**CROSS-REFERENCING (CRITICAL):** This deployment runbook was inspired by Project Sentinel, specifically the work on Kubernetes cluster federation. Mia (Staff SRE/DevOps) previously worked on a related issue, reviewed this document, and provided valuable feedback.

**Pre-requisites:**
-----------------

*   Project Nexus codebase is updated to the latest commit on the production branch.
*   The development and staging environments have been updated to ensure compatibility with the production code.
*   The necessary AWS resources (EC2 instances, RDS database, S3 buckets) have been created and configured.
*   The Kubernetes cluster (with the necessary namespaces, deployments, and services) has been set up and validated.
*   The production namespace has been isolated from the development and staging namespaces.

**Step-by-Step Instructions:**
-----------------------------

### Step 1: Prepare the Environment

*   Log in to the production Kubernetes cluster using `kubectx` or `kubectl`.
*   Verify that the necessary namespaces (e.g., `nexus-prod`) are available and healthy.
*   Check the current deployment configuration using `kubectl get deployments -n nexus-prod`.

### Step 2: Build the Docker Image

*   Run `docker build -t nexus-prod-image .` to build the Docker image for the production environment.
*   Verify that the image has been created successfully using `docker images`.

### Step 3: Push the Image to ECR

*   Tag the image with the latest version using `docker tag nexus-prod-image:latest <account_id>.dkr.ecr.<region>.amazonaws.com/nexus-prod-image:latest`.
*   Push the image to ECR using `docker push <account_id>.dkr.ecr.<region>.amazonaws.com/nexus-prod-image:latest`.

### Step 4: Update the Deployment

*   Create a new Kubernetes deployment configuration file (`nexus-prod-deployment.yaml`) with the latest image version.
*   Apply the new deployment configuration using `kubectl apply -f nexus-prod-deployment.yaml -n nexus-prod`.
*   Verify that the deployment has been updated successfully using `kubectl get deployments -n nexus-prod`.

### Step 5: Validate the Deployment

*   Run a series of integration tests to ensure that the deployment is working as expected.
*   Use `kubectl get pods -n nexus-prod` to verify that the pods are running and healthy.
*   Use `kubectl logs nexus-prod-pod -n nexus-prod` to verify that the application logs are healthy.

**Troubleshooting Common Errors:**
------------------------------------

*   **Deployment failed: "image not found"**
    +   Verify that the image has been pushed to ECR correctly.
    +   Check that the image version matches the one specified in the deployment configuration.
*   **Deployment failed: "connection refused"**
    +   Verify that the necessary AWS resources (EC2 instances, RDS database, S3 buckets) are available and healthy.
    +   Check that the Kubernetes services are configured correctly.
*   **Deployment failed: "timeout"**
    +   Verify that the Kubernetes cluster has enough resources to handle the deployment.
    +   Check that the deployment configuration is correct and not causing any bottlenecks.

**Rollback Procedures:**
-------------------------

*   If the deployment fails, roll back to the previous deployment version using `kubectl rolling-update nexus-prod-deployment -n nexus-prod`.
*   If the deployment is successful but exhibits unexpected behavior, roll back to the previous deployment version using `kubectl rolling-update nexus-prod-deployment -n nexus-prod`.

**Post-Deployment Tasks:**
---------------------------

*   Verify that the deployment has been done correctly by checking the application logs and metrics.
*   Update the documentation to reflect the new deployment version.
*   Schedule a review of the deployment runbook to identify areas for improvement.