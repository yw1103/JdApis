---
name: jd-shopping-assistant
description: "Use the jd-apis MCP to turn a user's JD shopping request into a controlled workflow: verify login, capture a cart baseline, search and filter products against explicit requirements, inspect reviews, score seller evidence, confirm the finalist, perform supported merchant-message and cart actions, and return an auditable report. Use for JD product research, comparison, shortlisting, or assisted cart addition. Do not use for checkout, ordering, or payment."
---

# JD Shopping Assistant

Use the `jd-apis` MCP as the source of truth. Keep a compact working record throughout the run so every recommendation and action can be traced to tool output.

## Operating Rules

- Treat each MCP result as JSON even when the transport returns it as a string. Check `ok`, status fields, and error fields before using payload data.
- Never claim that a message was sent or an item was added unless the corresponding mutation tool returned success.
- Do not place orders, submit checkout, select payment, or pay.
- Before any merchant message or cart mutation, show the exact SKU, quantity, selected specification, price snapshot, seller, known caveats, and exact message text. Obtain the user's explicit confirmation for that action packet.
- Keep phone numbers, verification codes, cookies, auth paths, and account identifiers out of reports. Ask only for login input required by the selected login flow.
- Distinguish `confirmed`, `conflicting`, and `not found in available data`. Missing evidence is not a match and is not proof of a mismatch.
- Use a measured request rate. Do not repeatedly retry errors. For broad 403, 605, or throttling failures, call `jd_diagnose` once and report the result.

## Capability Preflight

The current MCP provides login, search, product detail, comments, cart count, and read-only chat tools. Before promising the final actions, inspect the available tools.

The complete workflow needs these mutation capabilities:

- A merchant text tool equivalent to `jd_chat_send_text(vender_id, sku, text)`.
- A cart mutation tool equivalent to `jd_cart_add(sku, quantity)`.

At the time this skill was created, neither mutation tool existed in this repository's MCP server. If either is unavailable, complete all supported research, prepare the exact pending action, mark that action `blocked_by_missing_tool`, and name the missing capability in the final report. Do not substitute a shell script, browser, private API guess, or a success claim.

## Workflow

### 1. Establish a Valid Session

1. Call `jd_check_session`.
2. If the session is alive, continue without logging in again.
3. If it is not alive, prefer QR login:
   - Call `jd_login_qr_start` and display the returned QR image to the user.
   - After the user scans and confirms in the JD app, call `jd_login_qr_wait` with a reasonable timeout.
   - If the response is `qr_refreshed`, display the new QR and wait again.
4. Use SMS login only when the user asks for it or cannot use QR. Never echo the mobile number or codes into the report.
5. Call `jd_check_session` again. Stop if it is still invalid.

### 2. Build the Purchase Brief

Translate the user's request into this internal structure:

```text
category:
use_case:
quantity:
budget_min:
budget_max:
must_have:
preferred:
excluded:
delivery_or_region:
assumptions:
search_keywords:
```

Classify objective requirements such as size, model, capacity, compatibility, material, quantity, stock, and price ceiling as `must_have` when the user makes them mandatory. Keep subjective preferences such as appearance or brand preference under `preferred` unless the user clearly makes them mandatory.

Generate one to three concise search phrases. Put the product category and the most discriminating attributes in the phrase; use product detail for the rest. If the category is ambiguous or two hard requirements conflict, ask one concise clarification before searching.

### 3. Capture the Cart Baseline

Call `jd_cart_num` once before product research. Store both the raw response and the normalized count as `cart_count_before`. If the count cannot be parsed, preserve the raw response and mark the baseline unavailable.

### 4. Search and Verify

1. Call `jd_search` for the primary phrase on page 1.
2. Search page 2 or an alternate phrase only when page 1 has too few plausible candidates or insufficient variety. Use at most three phrases and two pages per phrase in one run unless the user asks for a broader search.
3. Deduplicate results by SKU.
4. Use title, price, seller, good-rate, and review count to select at most 12 plausible SKUs for `jd_product_detail`; do not treat title text as final proof of a specification.
5. Compare the detail response against every `must_have` field. Record evidence for each field.
6. Place candidates into exactly one group:
   - `exact_match`: every hard requirement is confirmed.
   - `near_match`: at least one hard requirement conflicts.
   - `needs_verification`: no conflict is visible, but at least one hard requirement is absent from the available data.
7. Do not rank a near match or unverified candidate as an exact match.

If fewer than three exact matches remain, pause before review analysis. Show the exact matches, the closest rejected or unverified candidates, and the requirement causing each exclusion. Explain whether the likely cause is an over-specific query, a possibly incorrect parameter, missing detail data, or genuinely scarce inventory. Ask the user whether the brief is correct or which requirement may be relaxed. Continue only after the user answers.

### 5. Read Reviews

For the strongest three exact matches, call `jd_product_comments` with `count=10` and inspect five to ten usable reviews per candidate.

- Summarize recurring positive themes and recurring negative themes separately.
- Include concrete fit signals tied to the purchase brief, such as compatibility, durability, sizing, authenticity, packaging, delivery, or after-sales experience.
- Give more weight to repeated specific observations than to vague praise or isolated complaints.
- If the returned sample contains no negative review, say so. Do not relabel neutral text as negative or imply that negative reviews were fetched separately.
- Do not infer seller misconduct, counterfeit goods, or fake reviews without direct evidence.

### 6. Score Seller Evidence

Hard-requirement fit is a gate and is not part of the seller score. Score only exact matches.

Use a 100-point seller evidence score:

| Component | Points | Evidence |
| --- | ---: | --- |
| Store reputation | 25 | Search/detail good-rate and store signals |
| Product review quality | 30 | Positive themes, negative severity, consistency |
| Fulfillment and service signals | 20 | Delivery, packaging, support, returns, after-sales comments |
| Store identity and listing quality | 15 | Seller identity, official/self-operated signals when explicitly present, specification clarity |
| Evidence strength | 10 | Review volume, usable sample size, field coverage |

For each component, cite the observed evidence in a short note. When a component lacks data, mark it unavailable and normalize the score across available components. Always publish evidence coverage as `high`, `medium`, or `low`; a high normalized score with low coverage must not outrank a well-supported candidate automatically.

Rank finalists using seller score, evidence coverage, severity of negative themes, price fit, and preferred requirements. Keep the reasoning visible rather than relying on the numeric score alone.

### 7. Prepare and Confirm the Final Action

For the leading candidate, call `jd_chat_info` with its seller ID and SKU to verify the available merchant identity and chat context. This call initializes or reads context; it does not prove that a message was sent.

Then prepare a confirmation packet containing:

```text
product_name:
sku:
selected_specification:
quantity:
price_snapshot:
seller:
hard_requirements_verified:
remaining_caveats:
merchant_message:
expected_cart_action:
```

Write the merchant message as a concise checklist. Include only requirements relevant to this SKU and ask for explicit confirmation where appropriate. Do not include private user data.

Show the packet to the user and ask for one explicit confirmation covering the exact message and cart action. A general request to research products does not authorize these external mutations.

After confirmation:

1. If a merchant-send tool exists, send exactly the approved text and record its returned status. If it does not exist, mark the send blocked and do not imply contact occurred.
2. If a cart-add tool exists, add the approved SKU and quantity. If it does not exist, mark the add blocked.
3. After a successful cart-add response, call `jd_cart_num` again and store `cart_count_after` plus the observed delta. State that cart count semantics may represent lines or units unless the API response proves which one.

If a merchant response is necessary to establish a hard requirement, do not add the item until the response confirms it. Read chat history only when it can identify that response reliably.

## Final Report

Return a report in the user's language with these sections:

1. `Outcome`: completed, awaiting user clarification, awaiting confirmation, or blocked by capability/error.
2. `Purchase brief`: hard requirements, preferences, exclusions, assumptions, and search phrases.
3. `Search coverage`: queries, pages, candidate count, exact-match count, and evidence limits.
4. `Shortlist`: SKU, product, seller, price snapshot, requirement status, review findings, seller score, and evidence coverage.
5. `Rejected or unverified`: the closest alternatives and the exact reason each was excluded.
6. `Finalist`: why it ranked first, important negative signals, and remaining caveats.
7. `Merchant contact`: approved message text and the actual send result.
8. `Cart audit`: count before, requested mutation, actual mutation result, count after, and observed delta.
9. `Next action`: the single concrete action still required, if any.

Use `not available` for unknown values. Never fill report fields with invented data. Include direct JD product URLs when the search result provides them.
