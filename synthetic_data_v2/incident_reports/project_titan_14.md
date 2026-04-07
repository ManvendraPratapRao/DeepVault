**Incident Report: Project Titan Failure**
======================================

**Issue Description**
-------------------

On March 23, 2024, Project Titan experienced a critical failure due to a cascading effect of Redis cache expiration and Kubernetes pod restarts, resulting in a 30-minute outage of our Qdrant-based search service. The incident was triggered by an unexpected increase in Qdrant query rates, which led to Redis cache overloading and subsequent pod restarts.

**Timeline**
------------

* **08:45 UTC**: Qdrant query rates spike to 5x normal levels, causing Redis cache to become overloaded.
* **09:00 UTC**: Kubernetes pods responsible for Qdrant begin to restart due to Redis cache expiration.
* **09:10 UTC**: Search service becomes unavailable, affecting 75% of users.
* **09:20 UTC**: Aman (Staff Backend Engineer) and David (ML Engineer) are alerted and begin investigation.
* **09:30 UTC**: Aman identifies the root cause as Redis cache expiration and Kubernetes pod restarts.
* **09:45 UTC**: David confirms the issue and assists Aman in implementing a temporary fix.
* **10:00 UTC**: Search service becomes available again, but with reduced performance.
* **10:15 UTC**: Aman and David implement a permanent fix and conduct thorough testing.
* **11:00 UTC**: Search service is fully restored to normal performance.

**Root Cause Analysis**
----------------------

The root cause of the failure was a combination of factors:

1.  **Unforeseen Increase in Qdrant Query Rates**: An unexpected surge in Qdrant query rates led to Redis cache overloading.
2.  **Insufficient Redis Cache Configuration**: Redis cache expiration was set too low, causing cache expiration and subsequent pod restarts.
3.  **Inadequate Kubernetes Pod Restart Handling**: Kubernetes pods were not properly configured to handle restarts, leading to service unavailability.

**Fix Applied**
--------------

To prevent similar failures in the future, the following fixes were applied:

1.  **Increased Redis Cache Configuration**: Redis cache expiration was increased to reduce cache expiration and subsequent pod restarts.
2.  **Improved Kubernetes Pod Restart Handling**: Kubernetes pods were modified to handle restarts more effectively, reducing service unavailability.
3.  **Qdrant Query Rate Limiting**: Qdrant query rate limiting was implemented to prevent unexpected surges in query rates.

**Lessons Learned**
------------------

1.  **Monitor Redis Cache Performance**: Regular monitoring of Redis cache performance is crucial to prevent cache overloading and subsequent pod restarts.
2.  **Improve Kubernetes Pod Restart Handling**: Kubernetes pods should be configured to handle restarts more effectively to reduce service unavailability.
3.  **Implement Qdrant Query Rate Limiting**: Qdrant query rate limiting should be implemented to prevent unexpected surges in query rates.

**Connection to Project Nexus**
--------------------------------

This incident was inspired by a similar issue previously worked on by Mia (Staff SRE/DevOps) as part of Project Nexus. Mia's experience and expertise were invaluable in reviewing this incident and providing guidance on the necessary fixes.

**Action Items**
----------------

1.  **Review and Update Documentation**: Review and update documentation to reflect the fixes applied and lessons learned.
2.  **Conduct Regular Monitoring**: Conduct regular monitoring of Redis cache performance and Kubernetes pod restarts to prevent similar failures.
3.  **Implement Qdrant Query Rate Limiting**: Implement Qdrant query rate limiting to prevent unexpected surges in query rates.