# GCP Deployment Reference (temporary — for this live demo cluster)

- **Project ID:** active-cove-504716-f7
- **Cluster name:** llm-router-demo
- **Zone:** us-east1-b
- **Node pool:** 2x e2-small (resized up from 1 — single node had insufficient
  capacity to schedule both the router and mongo pods)
- **Artifact Registry image:** us-east1-docker.pkg.dev/active-cove-504716-f7/llm-router-repo/router:latest
- **Public IP (router Service, LoadBalancer):** 34.73.192.177
- **Budget alert:** "NO Spending" — triggers at $0.50 / $0.90 / $1.00

## Cleanup command (run this once screenshots/testing are done)

```bash
gcloud container clusters delete llm-router-demo --zone=us-east1-b --quiet
```

This deletes the cluster and its nodes — stops any further billing against
the free trial credit. The Artifact Registry image and the GCP project
itself can stay (no ongoing cost for either at rest).
