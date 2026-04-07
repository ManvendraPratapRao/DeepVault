Project Aurora Deployment Runbook
=====================================

### Pre-requisites

* Project Aurora is built and packaged in a containerized environment using Docker
* Kubernetes cluster is up-to-date and configured with necessary permissions
* Priya (Data Scientist) has reviewed and validated data processing pipeline

### Step-by-Step Instructions

1. **Update Kubernetes deployment**: Run the following command to update the deployment with the latest image
   ```bash
kubectl set image deployment/aurora-deployment aurora=<image-name>:<new-version>
```
2. **Verify deployment**: Check the status of the deployment and its pods
   ```bash
kubectl get deployments -n <namespace> && kubectl get pods -n <namespace>
```
3. **Monitor for errors**: Use `kubectl logs` to monitor for any errors or exceptions
   ```bash
kubectl logs -f <pod-name> -n <namespace>
```
4. **Verify data processing pipeline**: Use ` Priya's (Data Scientist) pipeline validation script` to ensure data is being processed correctly

### Troubleshooting common errors

* **Deployment not updating**: Check if the image is properly updated and if the deployment is correctly configured
* **Pods not coming up**: Check for any errors in the pod logs and verify if the necessary dependencies are installed
* **Data processing pipeline errors**: Consult Priya (Data Scientist) for help with pipeline configuration and validation

### Rollback procedures

* **Rollback to previous version**: Run the following command to rollback to the previous version of the image
   ```
kubectl set image deployment/aurora-deployment aurora=<image-name>:<previous-version>