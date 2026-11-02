# RunBook Backend — Pre-Implementation Questions

> Fill in your answers below each question.  
> Once answered, share this file back and we will implement end-to-end.

---

## Section 1 — Django App Structure

**Q1. Should the RunBook backend be a brand-new Django app (`runbooks/`) inside `Codly_Backend/`, or should it extend the existing `ai_ops/` app?**

Recommendation: New app keeps it clean and separate from customer-facing ai_ops.

*Your answer:*  
```
[Answer here]
```

---

**Q2. The existing `ai_ops/` app already has `AIWorkflow`, `WorkflowTrigger`, `WorkflowRun` models that are used for the customer-facing AI Ops feature. Should the RunBook models be completely separate, or should RunBook reuse / extend those models?**

Recommendation: Keep separate — RunBooks are admin-managed, AI Ops is customer-managed. Different permissions, different execution patterns.

*Your answer:*  
```
[Answer here]
```

---

## Section 2 — EC2 Post-Deploy RunBook — Step Details

**Q3. For the Compliance Scan step — which compliance standard should the EC2 Post-Deploy RunBook scan by default: CIS Level 1, CIS Level 2, or SOC2? Should the admin be able to configure this per-step when creating the RunBook?**

*Your answer:*  
```
[Answer here]
```

---

**Q4. For the OS Patching step — should it apply ALL patches (full system update) or only security patches? And after patching, if a reboot is required, should it auto-reboot the instance or pause and ask the admin?**

*Your answer:*  
```
[Answer here]
```

---

**Q5. For the OS Hardening step — the existing `chatbot/os_hardening/agents.py` uses a very different pattern (LangGraph stateful graph with direct `ChatOpenAI` calls, which violates backend instructions). Should we:**

   - **(a)** Wrap the existing hardening agent as-is for now (fastest path, but technical debt)  
   - **(b)** Rewrite OS Hardening to use `MaskedReactAgentBuilder` / SwarmAgents like OS Management (correct pattern, more work)  

*Your answer:*  
```
[Answer here]
```

---

**Q6. For the Human Checkpoint step — who will approve/reject the checkpoint?**

   - **(a)** Any admin user in the Admin Portal  
   - **(b)** Only the admin who created the RunBook  
   - **(c)** A specific admin role (e.g., "Operator" and above)  

*Your answer:*  
```
[Answer here]
```

---

**Q7. For the "Install Agents" step — which monitoring/SIEM agents should be installed by default in the EC2 Post-Deploy RunBook? Check all that apply:**

   - [ ] CloudWatch agent  
   - [ ] Datadog agent  
   - [ ] Splunk Universal Forwarder  
   - [ ] Elastic/Filebeat  
   - [ ] CrowdStrike Falcon  
   - [ ] Other: `_______________`

*Your answer (check boxes above or list here):*  
```
[Answer here]
```

---

**Q8. For the "Create Ticket" step — which ITSM should it create tickets in by default for the EC2 Post-Deploy RunBook?**

   - **(a)** Freshservice  
   - **(b)** Jira  
   - **(c)** Zendesk  
   - **(d)** ManageEngine  
   - **(e)** Whichever is configured for that customer (dynamic lookup)  

*Your answer:*  
```
[Answer here]
```

---

## Section 3 — Triggering

**Q9. For the CloudTrail `RunInstances` trigger — do you already have AWS EventBridge set up to forward CloudTrail events to an HTTP endpoint? Or do we need to design that setup as part of this feature?**

*Your answer:*  
```
[Answer here]
```

---

**Q10. The CloudTrail webhook will be an unauthenticated HTTP endpoint (no cookie). We plan to use HMAC-SHA256 signature verification (similar to GitHub webhooks). Is that acceptable, or do you prefer a different security mechanism (e.g., IP allowlist, API key header)?**

*Your answer:*  
```
[Answer here]
```

---

**Q11. For Phase 1, which trigger types do you want to support first? (We can add others later)**

   - [ ] Manual (admin clicks "Run Now" in the portal) — *always included*  
   - [ ] CloudTrail event (e.g., RunInstances)  
   - [ ] Scheduled (cron, e.g., nightly)  
   - [ ] Ticket-based (e.g., new P1 in Freshservice)  

*Your answer:*  
```
[Answer here]
```

---

## Section 4 — Real-Time Streaming

**Q12. For real-time run progress in the Admin Portal, should we use WebSockets (like the existing `ai_ops/consumers.py` pattern) or HTTP polling (simpler but less real-time)?**

Recommendation: WebSocket — consistent with the existing pattern and gives live step-by-step updates.

*Your answer:*  
```
[Answer here]
```

---

## Section 5 — Multi-Tenancy & Permissions

**Q13. When an admin creates a RunBook, is it scoped to a specific customer + account, or can it be a template that can be applied to multiple customers?**

   - **(a)** Always scoped to one customer + one account  
   - **(b)** Scoped to a customer but can run against any of their accounts (selected at run time)  
   - **(c)** Global template — admin picks customer + account when triggering a run  

*Your answer:*  
```
[Answer here]
```

---

**Q14. Should a customer's own portal users (non-admin) ever be able to see RunBook runs or results, or is this strictly an admin-only feature?**

*Your answer:*  
```
[Answer here]
```

---

## Section 6 — Context Passing Between Steps

**Q15. When the RunBook is triggered by a CloudTrail event, the trigger payload contains `{instance_id, region, account_id}`. Each subsequent step (patching, hardening, etc.) needs to know which instance to operate on. Should this context be:**

   - **(a)** Automatically passed to every step (the executor injects `instance_id` + `region` automatically)  
   - **(b)** Explicitly mapped per step in the RunBook config (admin configures where each step gets its input from)  

Recommendation: (a) for the EC2 use case — automatic context passing is simpler and correct.

*Your answer:*  
```
[Answer here]
```

---

**Q16. Should a step be able to use the OUTPUT of a previous step as its input? For example, Step 1 (Compliance Scan) returns `{violations_count: 3}` and Step 2 should only run if `violations_count > 0`. Do we need this conditional logic in Phase 1?**

*Your answer:*  
```
[Answer here]
```

---

## Section 7 — API & Frontend Wiring

**Q17. The admin portal frontend (`codly-admin-portal`) currently uses sample/static data for RunBooks. Once the backend is ready, should we also update the frontend to call the real APIs as part of this implementation, or will that be a separate step?**

*Your answer:*  
```
[Answer here]
```

---

**Q18. Are there any existing API routes in `Codly_Backend` that the RunBook APIs should be mounted under? For example:**

   - **(a)** `/admin-api/runbooks/` (recommended — consistent with other admin endpoints)  
   - **(b)** `/api/runbooks/`  
   - **(c)** Something else  

*Your answer:*  
```
[Answer here]
```

---

## Section 8 — Execution & Error Handling

**Q19. If a step fails (e.g., SSH connection refused during OS patching), what should happen by default?**

   - **(a)** Stop the entire RunBook run, mark as failed  
   - **(b)** Pause and send a human checkpoint asking admin what to do  
   - **(c)** Skip the failed step and continue to the next one  
   - **(d)** Configurable per step (different steps have different `on_failure` policy)  

*Your answer:*  
```
[Answer here]
```

---

**Q20. Should there be a maximum timeout for a full RunBook run? If a step hangs (e.g., waiting for SSH), should the run auto-fail after a certain time?**

*Your answer:*  
```
[Answer here]
```

---

## Section 9 — Notifications

**Q21. When a RunBook run completes (or fails), should an automatic notification be sent? If yes, where?**

   - [ ] Slack (which channel?)  
   - [ ] Email (to whom — admin who triggered it? RunBook creator? Both?)  
   - [ ] ITSM ticket update  
   - [ ] In-portal notification only (no external)  

*Your answer:*  
```
[Answer here]
```

---

## Section 10 — One Clarifying Question

**Q22. Just to confirm scope — for this implementation we are building ONLY the EC2 Post-Deploy RunBook use case end-to-end (backend + wiring to admin portal). We are NOT building a general-purpose drag-and-drop RunBook canvas builder yet. The canvas is already built in the frontend as a static UI. Correct?**

   - **(a)** Yes — implement EC2 Post-Deploy RunBook backend only, wire it to the existing static canvas  
   - **(b)** No — I want the RunBook CRUD APIs too so admins can create/edit RunBooks from the canvas  

*Your answer:*  
```
[Answer here]
```

---

*Once you fill these in, I will read this file and implement everything end-to-end.*
