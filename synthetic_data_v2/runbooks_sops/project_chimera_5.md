**Project Chimera Deployment Runbook**
=====================================

**Project Details**
---------------------

* Project Lead: Priya (Data Scientist)
* Product Designer: Marcus
* Date: 2023-09-25
* Length Profile: Comprehensive and exhaustive
* CROSS-REFERENCING: Inspired by Project Sentinel. Elena (Product Manager) was consulted on related issues.

**Pre-requisites**
-------------------

### 1. Environment Setup

* Ensure all team members have access to the development, testing, and production environments.
* Verify that each environment has the required resources (CPU, RAM, storage) to run the application.
* Set up the necessary network configurations and security groups to isolate the environments.

### 2. Application Build

* Ensure the project is built using the latest version of the build tool (Maven 3.8.1).
* Verify that the build process is successful and the artifact is deployed to the artifact repository (Artifactory).

### 3. Database Setup

* Ensure the database schema is created and the necessary tables are populated with sample data.
* Verify that the database credentials are correct and the connection string is properly configured.

### 4. Configuration Files

* Ensure that all configuration files (application.properties, database.properties, etc.) are correctly formatted and contain the necessary values.
* Verify that the configuration files are properly loaded and used by the application.

### 5. Testing

* Ensure that all unit tests and integration tests are passing.
* Verify that the application is properly configured to run in the development, testing, and production environments.

**Step-by-Step Instructions**
-----------------------------

### 1. Deployment Preparation

* Log in to the development environment using SSH.
* Run the following command to update the package manager: `sudo apt update && sudo apt upgrade -y`
* Run the following command to install the necessary dependencies: `sudo apt install -y openjdk-11-jdk`

### 2. Build and Deploy the Application

* Run the following command to build the application: `mvn clean package`
* Run the following command to deploy the application to the development environment: `docker-compose up -d`

### 3. Verify Deployment

* Run the following command to verify that the application is running: `docker ps`
* Run the following command to verify that the application is accessible: `curl http://localhost:8080`

### 4. Test the Application

* Run the following command to execute the unit tests: `mvn test`
* Run the following command to execute the integration tests: `mvn integration-test`

### 5. Promote to Testing Environment

* Run the following command to deploy the application to the testing environment: `docker-compose -f docker-compose-testing.yml up -d`
* Verify that the application is running and accessible in the testing environment.

### 6. Test and Validate

* Run the following command to execute the unit tests and integration tests in the testing environment: `mvn test` and `mvn integration-test`
* Verify that the application is working as expected in the testing environment.

### 7. Promote to Production Environment

* Run the following command to deploy the application to the production environment: `docker-compose -f docker-compose-production.yml up -d`
* Verify that the application is running and accessible in the production environment.

**Troubleshooting**
-------------------

### 1. Application Not Running

* Check the logs for errors: `docker logs <container_name>`
* Verify that the application is properly configured: `docker-compose config`

### 2. Database Connection Issues

* Verify that the database credentials are correct: `docker-compose exec db psql -U <username>`
* Verify that the connection string is properly configured: `docker-compose exec app cat application.properties`

### 3. Configuration File Issues

* Verify that the configuration files are correctly formatted: `docker-compose exec app cat application.properties`
* Verify that the configuration files are properly loaded and used by the application: `docker-compose exec app java -jar <jar_name>`

### 4. Testing Issues

* Verify that the unit tests and integration tests are passing: `mvn test` and `mvn integration-test`
* Verify that the application is properly configured to run in the development, testing, and production environments: `docker-compose config`

**Rollback Procedures**
----------------------

### 1. Rollback to Previous Version

* Run the following command to rollback to the previous version: `git checkout <previous_commit>`

### 2. Rollback to Previous Deployment

* Run the following command to rollback to the previous deployment: `docker-compose down` and `docker-compose up -d <previous_container>`

### 3. Manual Rollback

* Manually restore the previous version of the application from the backup: `docker-compose exec db pg_restore <backup_file>`

**Change Log**
--------------

* 2023-09-25: Initial version of the deployment runbook.
* 2023-09-26: Updated the troubleshooting section to include additional steps.
* 2023-09-27: Updated the rollback procedures to include manual rollback.

**Acknowledgments**
-----------------

This deployment runbook was inspired by Project Sentinel and reviewed by Elena (Product Manager) for related issues.