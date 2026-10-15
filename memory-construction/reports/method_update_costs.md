# METHOD01–02 development updates

Primary metric: total LLM input + output tokens. Independent clones with equal legal exact-request/vector caches. Only rows with a matched construction signature are valid method comparisons. The earlier expanded20 diagnostic had no saved full requests, zero exact hits and is excluded from benefit claims. The first r1 web timing overlaps snapshot preparation and is not paired latency evidence.

| Run | Policy | LLM in/out | Calls | Emb vectors/tokens | Publish s | Edited/re-extracted | Event checks | Note check |
|---|---|---:|---:|---:|---:|---:|---:|---|
| r1-web-1ad1af4b-state4 | b3 | 8012/697 | 2 | 7/8058 | 76.42 | 0/4 | 0/2 | None |
| r1-web-1ad1af4b-state4 | delta | 5042/542 | 2 | 5/7818 | 80.87 | 0/2 | 1/2 | None |
| r1-web-1ad1af4b-state4 | ours | 3926/354 | 1 | 5/7807 | 39.53 | 0/2 | 1/2 | None |
| v10-enterprise-0ab99e0c-count-replacement | delta_retract | 11962/358 | 3 | 3/4502 | 26.06 | 1/1 | 2/2 | None |
| v10-web-1ad1af4b-title-replacement | delta_retract | 1355/87 | 2 | 5/7796 | 8.98 | 2/0 | 0/2 | None |
| v11-enterprise-0ab99e0c-count-replacement | delta_guarded | 1083/162 | 1 | 3/4424 | 12.85 | 2/0 | 2/2 | None |
| v11-enterprise-0ab99e0c-state_revision-state5 | delta_guarded | 0/0 | 0 | 2/261 | 0.65 | 2/0 | 2/2 | None |
| v11-enterprise-0ab99e0c-workflow_revision-state6 | delta_guarded | 0/0 | 0 | 3/578 | 0.77 | 2/0 | 2/2 | True |
| v11-enterprise-49f98e9e-state_revision-state4 | delta_guarded | 0/0 | 0 | 2/234 | 0.60 | 2/0 | 2/2 | None |
| v11-enterprise-49f98e9e-workflow_revision-state5 | delta_guarded | 0/0 | 0 | 3/437 | 0.68 | 2/0 | 2/2 | True |
| v11-new-enterprise-49f98e9e-sort-replacement | b3 | 13268/306 | 1 | 3/4313 | 14.70 | 0/2 | 1/2 | None |
| v11-new-enterprise-49f98e9e-sort-replacement | delta_guarded | 10057/188 | 2 | 3/4351 | 9.84 | 1/1 | 2/2 | None |
| v11-new-web-2e8f6477-reply-replacement | b3 | 28830/716 | 2 | 5/4676 | 31.25 | 0/4 | 1/2 | None |
| v11-new-web-2e8f6477-reply-replacement | delta_guarded | 1634/209 | 2 | 3/4433 | 7.59 | 2/0 | 2/2 | None |
| v11-r1-enterprise-0ab99e0c-count-replacement | b3 | 14431/335 | 1 | 3/4341 | 19.96 | 0/2 | 0/2 | None |
| v11-r1-enterprise-0ab99e0c-count-replacement | delta_guarded | 1083/162 | 1 | 3/4424 | 8.49 | 2/0 | 2/2 | None |
| v11-r1-web-1ad1af4b-title-replacement | b3 | 7986/678 | 2 | 7/7999 | 27.72 | 0/4 | 1/2 | None |
| v11-r1-web-1ad1af4b-title-replacement | delta_guarded | 1633/341 | 2 | 5/7766 | 14.76 | 2/0 | 2/2 | None |
| v11-r2-enterprise-0ab99e0c-count-replacement | b3 | 14431/320 | 1 | 3/4326 | 15.65 | 0/2 | 0/2 | None |
| v11-r2-enterprise-0ab99e0c-count-replacement | delta_guarded | 1083/55 | 1 | 3/4424 | 3.56 | 2/0 | 2/2 | None |
| v11-r2-enterprise-0ab99e0c-count-replacement | ours | 14431/264 | 1 | 3/4271 | 13.47 | 0/2 | 0/2 | None |
| v11-r2-web-1ad1af4b-title-replacement | b3 | 7986/801 | 2 | 7/8122 | 26.81 | 0/4 | 1/2 | None |
| v11-r2-web-1ad1af4b-title-replacement | delta_guarded | 1633/357 | 2 | 5/7782 | 13.32 | 2/0 | 1/2 | None |
| v11-r2-web-1ad1af4b-title-replacement | ours | 3913/322 | 1 | 5/7736 | 12.38 | 0/2 | 0/2 | None |
| v11-r3-enterprise-0ab99e0c-count-replacement | b3 | 14431/380 | 1 | 3/4387 | 17.37 | 0/2 | 1/2 | None |
| v11-r3-enterprise-0ab99e0c-count-replacement | delta_guarded | 1083/162 | 1 | 3/4424 | 6.32 | 2/0 | 2/2 | None |
| v11-r3-web-1ad1af4b-title-replacement | b3 | 7986/760 | 2 | 7/8082 | 25.84 | 0/4 | 1/2 | None |
| v11-r3-web-1ad1af4b-title-replacement | delta_guarded | 1633/251 | 2 | 5/7774 | 9.70 | 2/0 | 2/2 | None |
| v11-web-1ad1af4b-state_revision-state4 | delta_guarded | 0/0 | 0 | 5/7834 | 2.44 | 2/0 | 2/2 | None |
| v11-web-1ad1af4b-title-replacement | delta_guarded | 1633/165 | 2 | 5/7770 | 11.89 | 2/0 | 2/2 | None |
| v11-web-1ad1af4b-workflow_revision-state3 | delta_guarded | 0/0 | 0 | 3/451 | 0.54 | 2/0 | 2/2 | True |
| v11-web-2e8f6477-state_revision-state3 | delta_guarded | 0/0 | 0 | 3/4488 | 1.48 | 2/0 | 2/2 | None |
| v11-web-2e8f6477-workflow_revision-state4 | delta_guarded | 0/0 | 0 | 3/559 | 0.58 | 2/0 | 2/2 | True |
| v2-enterprise-0ab99e0c-state5 | b3 | 14409/386 | 1 | 2/297 | 31.42 | 0/2 | 0/2 | None |
| v2-enterprise-0ab99e0c-state5 | delta | 1583/464 | 1 | 2/255 | 30.00 | 2/0 | 2/2 | None |
| v2-enterprise-0ab99e0c-state5 | ours | 14409/290 | 1 | 2/201 | 21.01 | 0/2 | 0/2 | None |
| v2-web-1ad1af4b-state4 | b3 | 8012/801 | 2 | 7/8162 | 54.20 | 0/4 | 0/2 | None |
| v2-web-1ad1af4b-state4 | delta | 1297/391 | 1 | 5/7736 | 18.26 | 2/0 | 2/2 | None |
| v2-web-1ad1af4b-state4 | ours | 3926/353 | 1 | 5/7806 | 17.71 | 0/2 | 1/2 | None |
| v3-web-1ad1af4b-state4 | delta | 5250/441 | 2 | 5/7807 | 31.00 | 0/3 | 0/2 | None |
| v4-enterprise-0ab99e0c-state_revision-state5 | delta | 1647/93 | 1 | 2/259 | 7.21 | 2/0 | 2/2 | None |
| v4-enterprise-0ab99e0c-workflow_revision-state6 | b3 | 31159/1349 | 3 | 6/1123 | 50.80 | 0/4 | 0/2 | False |
| v4-enterprise-0ab99e0c-workflow_revision-state6 | delta | 19147/1018 | 3 | 4/783 | 61.78 | 0/2 | 0/2 | False |
| v4-enterprise-0ab99e0c-workflow_revision-state6 | ours | 17240/954 | 2 | 4/774 | 33.14 | 0/2 | 0/2 | False |
| v4-web-1ad1af4b-state4 | delta | 1361/89 | 1 | 5/7828 | 9.01 | 2/0 | 2/2 | None |
| v4-web-1ad1af4b-workflow_revision-state3 | b3 | 5278/676 | 2 | 4/503 | 34.70 | 0/2 | 0/2 | True |
| v4-web-1ad1af4b-workflow_revision-state3 | delta | 6749/772 | 3 | 4/495 | 50.34 | 0/2 | 0/2 | False |
| v4-web-1ad1af4b-workflow_revision-state3 | ours | 5278/758 | 2 | 4/576 | 32.58 | 0/2 | 1/2 | True |
| v5-enterprise-0ab99e0c-state_revision-state5 | b3 | 14409/429 | 1 | 2/340 | 20.56 | 0/2 | 0/2 | None |
| v5-enterprise-0ab99e0c-state_revision-state5 | delta_notes | 1554/32 | 1 | 2/261 | 2.52 | 2/0 | 2/2 | None |
| v5-enterprise-0ab99e0c-state_revision-state5 | ours | 14409/383 | 1 | 2/294 | 17.22 | 0/2 | 0/2 | None |
| v5-enterprise-0ab99e0c-workflow_revision-state6 | b3 | 31159/1487 | 3 | 6/1238 | 68.21 | 0/4 | 0/2 | False |
| v5-enterprise-0ab99e0c-workflow_revision-state6 | delta_notes | 1815/41 | 1 | 3/578 | 3.35 | 2/0 | 2/2 | True |
| v5-enterprise-0ab99e0c-workflow_revision-state6 | ours | 17240/921 | 2 | 4/766 | 44.31 | 0/2 | 0/2 | False |
| v5-enterprise-49f98e9e-state_revision-state4 | b3 | 26306/536 | 2 | 4/358 | 39.05 | 0/4 | 0/2 | None |
| v5-enterprise-49f98e9e-state_revision-state4 | delta_notes | 1381/32 | 1 | 2/234 | 3.39 | 2/0 | 2/2 | None |
| v5-enterprise-49f98e9e-state_revision-state4 | ours | 13407/325 | 1 | 2/236 | 22.28 | 0/2 | 0/2 | None |
| v5-enterprise-49f98e9e-workflow_revision-state5 | b3 | 15839/726 | 2 | 4/543 | 42.96 | 0/2 | 0/2 | False |
| v5-enterprise-49f98e9e-workflow_revision-state5 | delta_notes | 1357/36 | 1 | 3/437 | 4.53 | 2/0 | 2/2 | True |
| v5-enterprise-49f98e9e-workflow_revision-state5 | ours | 15839/724 | 2 | 4/581 | 43.94 | 0/2 | 0/2 | False |
| v5-web-1ad1af4b-state_revision-state4 | b3 | 8012/716 | 2 | 7/8077 | 25.55 | 0/4 | 1/2 | None |
| v5-web-1ad1af4b-state_revision-state4 | delta_notes | 1268/32 | 1 | 5/7834 | 3.76 | 2/0 | 2/2 | None |
| v5-web-1ad1af4b-state_revision-state4 | ours | 3926/357 | 1 | 5/7809 | 13.42 | 0/2 | 0/2 | None |
| v5-web-1ad1af4b-workflow3 | delta | 2821/366 | 2 | 4/512 | 35.09 | 2/0 | 2/2 | True |
| v5-web-1ad1af4b-workflow3 | delta_notes | 1379/36 | 1 | 3/451 | 2.10 | 2/0 | 2/2 | True |
| v5-web-1ad1af4b-workflow_revision-state3 | b3 | 5278/853 | 2 | 4/653 | 29.31 | 0/2 | 0/2 | True |
| v5-web-1ad1af4b-workflow_revision-state3 | delta_notes | 1379/36 | 1 | 3/451 | 2.03 | 2/0 | 2/2 | True |
| v5-web-1ad1af4b-workflow_revision-state3 | ours | 5278/687 | 2 | 4/513 | 21.56 | 0/2 | 0/2 | False |
| v5-web-2e8f6477-state_revision-state3 | b3 | 9980/492 | 1 | 3/4498 | 24.07 | 0/2 | 0/2 | None |
| v5-web-2e8f6477-state_revision-state3 | delta_notes | 11346/470 | 2 | 3/4445 | 34.21 | 0/2 | 0/2 | None |
| v5-web-2e8f6477-state_revision-state3 | ours | 9980/473 | 1 | 3/4480 | 33.99 | 0/2 | 0/2 | None |
| v5-web-2e8f6477-workflow_revision-state4 | b3 | 26383/1135 | 3 | 6/898 | 75.72 | 0/4 | 0/2 | False |
| v5-web-2e8f6477-workflow_revision-state4 | delta_notes | 1662/36 | 1 | 3/559 | 4.26 | 2/0 | 2/2 | True |
| v5-web-2e8f6477-workflow_revision-state4 | ours | 17071/818 | 2 | 4/675 | 51.93 | 0/2 | 0/2 | False |
| v6-enterprise-0ab99e0c-workflow_revision-source-append | source_append | 0/0 | 0 | 3/578 | 0.79 | 2/0 | 2/2 | True |
| v6-web-1ad1af4b-state_revision-source-append | source_append | 0/0 | 0 | 5/7834 | 2.46 | 2/0 | 2/2 | None |
| v6-web-2e8f6477-state3 | delta_notes | 1360/19 | 1 | 3/4488 | 3.59 | 2/0 | 2/2 | None |
| v6a-enterprise-0ab99e0c-count-replacement | b3 | 14431/430 | 1 | 3/4437 | 18.84 | 0/2 | 1/2 | None |
| v6a-enterprise-0ab99e0c-count-replacement | delta_notes | 17144/550 | 2 | 3/4383 | 22.45 | 0/2 | 0/2 | None |
| v6a-web-1ad1af4b-title-replacement | b3 | 7986/713 | 2 | 7/8038 | 24.69 | 0/4 | 2/2 | None |
| v6a-web-1ad1af4b-title-replacement | delta_notes | 5410/545 | 2 | 5/7787 | 18.93 | 0/2 | 0/2 | None |
| v7-enterprise-0ab99e0c-count-replacement | b3 | 14431/296 | 1 | 3/4303 | 14.87 | 0/2 | 0/2 | None |
| v7-enterprise-0ab99e0c-count-replacement | delta_notes | 3692/316 | 2 | 1/4096 | 11.14 | 2/0 | 0/2 | None |
| v7-web-1ad1af4b-title-replacement | b3 | 7986/717 | 2 | 7/8039 | 24.30 | 0/4 | 0/2 | None |
| v7-web-1ad1af4b-title-replacement | delta_notes | 2115/368 | 2 | 5/7793 | 12.94 | 2/0 | 2/2 | None |
| v8-enterprise-0ab99e0c-count-replacement | delta_notes | 2180/324 | 2 | 3/4331 | 11.53 | 2/0 | 2/2 | None |
| v8-web-1ad1af4b-title-replacement | delta_notes | 1633/263 | 2 | 5/7770 | 10.08 | 2/0 | 2/2 | None |
| v9-enterprise-0ab99e0c-count-replacement | delta_retract | 2058/232 | 2 | 3/4424 | 12.09 | 2/0 | 2/2 | None | INVALID IMPLEMENTATION
| v9-web-1ad1af4b-title-replacement | delta_retract | 1511/164 | 2 | 5/7769 | 12.08 | 2/0 | 2/2 | None | INVALID IMPLEMENTATION

Generated-memory checks exclude raw states and copied thought metadata. Lexical pass is a necessary check, not semantic quality certification. Semantic review and fixed Reader regression remain separate constraints. V5 cases are additive controlled annotations; later literal_revision cases are controlled replacements, not observed real-world updates or continuous-growth claims. No method is frozen.
