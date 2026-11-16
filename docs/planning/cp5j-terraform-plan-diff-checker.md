# CP-5J — Offline Terraform Nested Plan Diff Checker

**Status:** Source implementation, offline and synthetic-tested only. Draft PR only, not merged.
**Checkpoint:** B6-B2 CP-5J. Base `main` `469e0e67622f1b71f079a5092a875b963a4b8cd5`.
**Gates unchanged:** `W1_PRODUCTION_RELEASE_AUTHORIZED=NO`, `W3C2_UNTARGETED_APPLY_ACTIVATES_W1=YES`.

This tool authorizes nothing. A PASS is a technical policy match only. It grants no release, deployment, plan or apply authority. Credential authority and rotation approval are separate owner controls.

---

## 1. Purpose

The CP-5 targeted plan for `aws_lambda_function.cancellation`, `.review` and `.admin` was first classified `PLAN_COMPLETED_UNEXPECTED_DIFF`, because the earlier ad-hoc checker treated nested `after_unknown` objects (`environment`, `architectures`, `ephemeral_storage`, `logging_config`, `tracing_config`) as if each were `true`. Separately, follow-up review (`UNEXPECTED_CONFIG_CHANGE_CONFIRMED`) found a real nested change that a flat checker cannot isolate: admin's `environment[0].variables.STRIPE_SECRET_KEY`.

CP-5J replaces that ad-hoc check with a deterministic, reusable checker that:

- finds every configured attribute change in `resource_changes`, recursively through objects and arrays;
- resolves `after_unknown` down to its `true` leaves;
- fails closed on anything outside an explicit, reviewed allowlist;
- never emits attribute values.

The old saved plan `cp5.tfplan` stays **NEVER APPLY**. This checker was never run against it, nor against any other real plan.

## 2. Files

| File | Role |
|---|---|
| `scripts/cp5/nested_diff.py` | Comparison engine. Value-blind recursive diff, marker validation, sensitivity lookup. |
| `scripts/cp5/plan_diff_checker.py` | Policy and reporting. Plan structure validation, policies, classification, sanitized report. |
| `tests/cp5/test_plan_diff_checker.py` | Synthetic `unittest` suite (standard library only). |
| `docs/planning/cp5j-terraform-plan-diff-checker.md` | This document. |

No Terraform, infrastructure, backend, web, mobile, CI workflow or existing script file is modified.

## 3. Input contract

- The input is an **already materialized**, in-memory Python object equal to Terraform's JSON plan representation (`resource_changes`, `output_changes`, and optionally `errored`, `complete` and `deferred_changes`).
- The checker never opens, discovers, scans or fetches files. It has no default plan path and no command-line entry point.
- The checker never reads the plan's `variables`, `planned_values`, `prior_state` or `configuration` sections. Terraform variable values live in `variables` and are never touched.
- Only plain JSON types are accepted: `dict` with `str` keys, `list`, `str`, `int`, `float`, `bool` and `None`. Subclasses of these types are rejected too, so their `__eq__` and `__repr__` are never invoked.
- Every `resource_changes[*].change` must carry `actions`, `before`, `after`, `after_unknown`, `before_sensitive` and `after_sensitive`.

## 4. Pure-function API

```python
import plan_diff_checker as pdc          # with scripts/cp5 on sys.path

result = pdc.check_plan(plan_obj)        # strict default policy
result = pdc.check_plan(plan_obj, pdc.strict_code_only_policy())
result.classification                    # one of the seven codes below
result.passed                            # True only for PASS_EXACT_ALLOWED_DIFF
result.to_dict()                         # sanitized, JSON-serializable summary
pdc.render_report(result)                # sanitized text report

rotation = pdc.stripe_test_key_rotation_policy(rotation_separately_authorized=True)
result = pdc.check_plan(plan_obj, rotation)
```

- `check_plan` never raises for bad plan input. Every error maps to a FAIL classification with a fixed reason code. An unexpected internal exception becomes `FAIL_MALFORMED_PLAN` / `internal_error`, and the exception text is discarded.
- The input object is never mutated.
- The engine (`nested_diff.diff_values`) returns only two sets of paths: `changed` and `unknown`.

### Classifications

| Code | Meaning |
|---|---|
| `PASS_EXACT_ALLOWED_DIFF` | Every change and unknown matches the selected policy exactly. |
| `FAIL_UNEXPECTED_RESOURCE` | A resource outside the policy changes; a data-source read is pending; or `deferred_changes` is non-empty. |
| `FAIL_UNEXPECTED_ACTION` | An expected resource has an action other than `["update"]`: create, delete, replacement, no-op, `replace_paths`, a move (`previous_address`) or an import. |
| `FAIL_UNEXPECTED_ATTRIBUTE` | A configured attribute changes that the policy does not allow. |
| `FAIL_UNEXPECTED_UNKNOWN` | An attribute becomes unknown that the policy does not allow. |
| `FAIL_MALFORMED_PLAN` | Structural uncertainty, for example missing fields, wrong types, duplicate addresses, contradictory unknown markers, excessive depth, `errored: true` or `complete: false`. Checking stops at the first such problem. |
| `FAIL_POLICY_MISMATCH` | The policy's conditions are not met: hash mismatch, required change absent, expected resource absent, rotation constraint failed, unexpected output change, or an invalid policy object. |

When several findings exist, the headline uses this fixed precedence: MALFORMED, then UNEXPECTED_RESOURCE, UNEXPECTED_ACTION, UNEXPECTED_ATTRIBUTE, UNEXPECTED_UNKNOWN, POLICY_MISMATCH. All findings are listed in a deterministic order.

## 5. Recursive comparison semantics

- **Objects:** the union of keys from `before`, `after` and `after_unknown` is visited in sorted order.
- **Arrays:** compared positionally, index by index, up to the longest of the three. Arrays are never sorted, because no schema evidence for order-insensitivity is used. Additions, removals, reordering and length changes therefore all surface as `path[i]` changes. Terraform nested blocks keep their index identity, for example `environment[0].variables`.
- **Missing versus null:** an absent key is distinct from `null`. `null` to absent is a change.
- **Scalars:** compared with strict type equality. `30`, `30.0`, `true` and `"30"` are all different.
- **Mixed kinds** (scalar against container, object against array, null against empty) count as a change at that path.
- **Depth:** nesting deeper than 64 levels is `FAIL_MALFORMED_PLAN` (`depth_exceeded`).

## 6. `after_unknown` handling

- Boolean `true` at a path means the whole value at that path is unknown. That path is reported as an **unknown** leaf and is not compared.
- A nested object or array in `after_unknown` is **not** unknown. The checker recurses into it, and only its `true` leaves are reported. This is the exact defect that misclassified CP-5.
- `false` or an absent entry means the value is known.
- A `true` marker next to a concrete non-null `after` value is contradictory, so it is malformed (`unknown_with_known_value`). A nested marker containing `true` whose shape does not match `after` is also malformed (`unknown_shape_mismatch`).
- A `true` marker for a key absent from `before` and `after` is reported as unknown. Terraform omits unknown values from `after`.
- Unknown leaves are never automatically allowed. Each one must appear in the policy's `allowed_unknown` set; otherwise the result is `FAIL_UNEXPECTED_UNKNOWN`.

## 7. Sensitive-path handling

- Values are compared only inside the engine. No value, fingerprint or hash of a value is retained, returned, logged or put in an exception. `MalformedInput` carries only a fixed reason code. Value-bearing internal fields are excluded from `repr`.
- A path is reported `sensitive: true` when any of these hold:
  - `before_sensitive` or `after_sensitive` marks the path, any ancestor of it, or any descendant of it;
  - the marker's shape does not fit the path (treated as sensitive, conservatively);
  - the path is under `environment`;
  - a segment name matches `SECRET`, `TOKEN`, `PASSWORD`, `PASSWD`, `CREDENTIAL`, `PRIVATE`, `API_KEY` or `APIKEY`, or ends in `_KEY`.
- Rendered paths redact keys that are not simple identifiers, and keys that contain credential-shaped text. Distinctive forms (`sk_test_`/`sk_live_` and the `rk_`/`pk_` equivalents, `whsec_`, `AKIA`, `ASIA`, `github_pat_`, `xoxb-` and similar) match anywhere in a key. Short prefixes (`sk_`, `rk_`, `pk_`, `ghp_`-style, `eyJ`) match at the start or after a non-alphanumeric character, so ordinary names such as `task_role` stay readable. Redacted keys appear as `<redacted-key>`.
- **Resource addresses** are untrusted plan data. The original address is used internally only, for exact policy matching and duplicate detection, and is never copied into a public result object (including internal `repr`). Public results carry `sanitize_address(address)`:
  - the three canonical release addresses are always readable;
  - any other address is readable only if it is a plain, unquoted Terraform address (optional `module.<name>[<int>]` prefixes, optional `data.`, `<type>.<name>`, optional integer index), is at most 256 characters, and contains no credential-shaped text;
  - everything else, including **any quoted (string) index key**, renders as `<redacted-resource-address>`. No hash or fingerprint of the original is produced.
- **Policy labels** are caller-supplied. They render only if they match `^[a-z0-9][a-z0-9-]{0,63}$` with no credential-shaped text; otherwise they appear as `<redacted-policy-name>`. Addresses taken from policy rules go through the same address sanitizer.
- **Output boundary audit.** Every public field and where it comes from:

  | Field | Source | Treatment |
  |---|---|---|
  | `classification`, `reason`, `kind`, `verdict`, `notice` | Fixed internal values | Emitted as-is |
  | `counts`, `sensitive`, `expected`, `passed` | Computed integers and booleans | Emitted as-is |
  | `actions` | Plan data | Validated against a fixed action set; anything else is malformed |
  | resource `address` | Plan data, or policy rules | `sanitize_address` |
  | attribute `path` | Plan keys plus integer indexes | `format_path` key redaction |
  | output finding address | Plan output names | `output.` + key redaction |
  | `policy` | Caller policy object | `sanitize_policy_name` |
  | resource `type` | Plan data | Never emitted |

- A report contains only: classification, sanitized policy name, action counts, sanitized resource addresses, sanitized paths, kind (`configured` or `unknown`), the sensitive flag, the verdict, fixed reason codes and the authority notice.

## 8. Strict default policy (`strict-code-only-3-lambda`)

The default when no policy is given.

- **Resources:** exactly `aws_lambda_function.cancellation`, `aws_lambda_function.review` and `aws_lambda_function.admin`, each of type `aws_lambda_function`, each with actions exactly `["update"]`. That is 0 add, 3 change, 0 destroy, with no replacements.
- **Other resources:** any other managed resource with a non-`no-op` action fails, as does any data-source read. `no-op` entries elsewhere are accepted only if their `before` and `after` are identical.
- **Outputs:** any `output_changes` entry other than `["no-op"]` fails.
- **Required configured change:** `source_code_hash` must change, and its new value must equal exactly `861IQwFAXAIGW507wbNOgse3MCI12CIDbcsau8Ol5jc=`. The report shows only allowed or rejected, never the value.
- **Allowed computed unknown:** `last_modified` only. It is permitted, not required.
- **Everything else must stay unchanged and known.** That includes `environment[0].variables`, `role`, `handler`, `function_name`, `runtime`, `timeout`, `memory_size`, `layers`, `tags`, `vpc_config`, `tracing_config`, `logging_config`, `architectures` and `ephemeral_storage`.
- Terraform's own 0/3/0 summary is never trusted. Counts are recomputed, and attribute rules apply regardless of the counts.

## 9. Optional Stripe test-key rotation policy (`stripe-test-key-rotation-3-lambda`)

- **Never the default.** It is available only through `stripe_test_key_rotation_policy(rotation_separately_authorized=True)`. The argument is keyword-only and must be the literal `True`; `1`, `"true"` or any other truthy value raises `ValueError`.
- **Plan content cannot select it.** The plan is never read for policy selection. A test injects policy-like keys at the plan, variable and resource level, and the result stays on the strict policy.
- **What it allows:** the strict policy, plus exactly one additional configured path, `aws_lambda_function.admin` `environment[0].variables.STRIPE_SECRET_KEY`.
- **Conditions on that change** (checked internally; only a boolean result is kept):
  - the key exists before and after, as a non-empty string;
  - the new value starts with a Stripe test-mode prefix (`sk_test_` or `rk_test_`) and contains no `_live_`.
- **What it rejects:**
  - the same key on cancellation or review;
  - any other environment variable, including `STRIPE_WEBHOOK_SECRET`, `STRIPE_ENV` and `STRIPE_ENVIRONMENT`;
  - any `stripe_webhook` Lambda update;
  - an unknown `STRIPE_SECRET_KEY`;
  - additional Lambdas;
  - a hash mismatch.
- **If the key does not change,** the rotation profile still passes, with the same result as the strict policy.
- **Scope of the check:** it verifies the change path and test mode only. It never validates a credential, calls Stripe, stores a new credential or embeds any key value.

## 10. Test matrix

All fixtures are synthetic and built in code. Credential-shaped sentinels are assembled from fragments at runtime; none is a literal credential-shaped token. No fixture comes from any real plan, state, tfvars file, AWS account or Stripe account.

| ID | Case | Expected | Test(s) |
|---|---|---|---|
| A | Exact 0/3/0 code-only | PASS | `test_A_exact_030_code_only_pass` |
| B | Candidate hash mismatch | FAIL_POLICY_MISMATCH | `test_B_candidate_hash_mismatch_fails`, `test_hash_*` |
| C | Additional Lambda | FAIL_UNEXPECTED_RESOURCE | `test_C_additional_lambda_fails` |
| D | `job` Lambda update | FAIL_UNEXPECTED_RESOURCE | `test_D_job_lambda_fails` |
| E | `intake` Lambda update | FAIL_UNEXPECTED_RESOURCE | `test_E_intake_lambda_fails` |
| F | IAM update | FAIL_UNEXPECTED_RESOURCE | `test_F_iam_update_fails` |
| G | API Gateway update | FAIL_UNEXPECTED_RESOURCE | `test_G_api_gateway_update_fails` |
| H | Create action | FAIL_UNEXPECTED_ACTION / RESOURCE | `test_H_create_action_fails` |
| I | Delete action | FAIL_UNEXPECTED_ACTION / RESOURCE | `test_I_delete_action_fails` |
| J | Replacement (both orders) | FAIL_UNEXPECTED_ACTION | `test_J_replacement_fails`, `test_replace_paths_fail` |
| K | Admin Stripe key under default policy | FAIL_UNEXPECTED_ATTRIBUTE | `test_K_admin_stripe_key_change_default_policy_fails` |
| L | Admin Stripe key under explicit rotation policy | PASS | `test_L_admin_stripe_key_change_rotation_policy_passes` |
| M | Webhook secret difference (admin env and `stripe_webhook` resource) | FAIL | `test_M_webhook_secret_difference_fails` |
| N | Other admin env var | FAIL_UNEXPECTED_ATTRIBUTE | `test_N_other_admin_env_var_fails` |
| O | Cancellation env var | FAIL_UNEXPECTED_ATTRIBUTE | `test_O_cancellation_env_var_fails` |
| P | Review env var | FAIL_UNEXPECTED_ATTRIBUTE | `test_P_review_env_var_fails` |
| Q | Nested block and scalar config changes (13 variants, both policies) | FAIL_UNEXPECTED_ATTRIBUTE | `test_Q_nested_block_changes_fail` |
| R | Nested unknown leaf | FAIL_UNEXPECTED_UNKNOWN | `test_R_*` |
| S | Expected `last_modified` unknown | PASS | `test_S_*` |
| T | Unexpected computed unknown | FAIL_UNEXPECTED_UNKNOWN | `test_T_unexpected_computed_unknown_fails` |
| U | Array element addition | FAIL_UNEXPECTED_ATTRIBUTE | `test_U_array_element_addition_fails` |
| V | Array element removal | FAIL_UNEXPECTED_ATTRIBUTE | `test_V_array_element_removal_fails` |
| W | Array reordering | FAIL_UNEXPECTED_ATTRIBUTE | `test_W_array_reordering_fails` |
| X | Missing attribute | FAIL_UNEXPECTED_ATTRIBUTE | `test_X_missing_attribute_fails` |
| Y | Null versus missing | FAIL_UNEXPECTED_ATTRIBUTE | `test_Y_null_versus_missing_fails` |
| Z | Malformed plans (25 variants) | FAIL_MALFORMED_PLAN | `test_Z_malformed_plans` |
| AA | Missing `resource_changes` | FAIL_MALFORMED_PLAN | `test_AA_missing_resource_changes` |
| AB | Duplicate addresses | FAIL_MALFORMED_PLAN | `test_AB_duplicate_addresses` |
| AC | Unexpected output change | FAIL_POLICY_MISMATCH | `test_AC_unexpected_output_change_fails` |
| AD | Pending data-source read | FAIL_UNEXPECTED_RESOURCE | `test_AD_pending_data_source_read_fails` |
| AE | Sensitive marker propagation | PASS, flags correct | `test_AE_*`, `test_terraform_marker_alone_marks_sensitive` |
| AF | No secrets emitted on failure | no sentinel in output | `test_AF_*` |
| AG | No secrets emitted on success | no sentinel in output | `test_AG_no_secrets_on_success` |
| AH | No raw JSON printed | stdout/stderr empty; no braces in text report | `test_AH_no_raw_json_printed` |
| AI | No unexpected exception `repr` | FAIL_MALFORMED_PLAN, no sentinel | `test_AI_*` |
| AJ | Deterministic ordering | identical output under key/entry reordering, repeated | `test_AJ_deterministic_ordering`, `test_render_is_stable` |
| AK | Unknown versus configured distinction | kinds correct | `test_AK_unknown_vs_configured_distinction` |
| AL | Mixed nested dicts, arrays and nulls | exact leaf paths | `test_AL_mixed_nested_dicts_arrays_nulls`, engine tests |
| AM | No Stripe integration | AST and source audit | `test_AM_no_stripe_integration_or_paths` |
| AN | Plan content cannot activate rotation | strict stays selected | `test_AN_plan_content_cannot_activate_rotation`, `test_rotation_requires_explicit_true` |
| AO | No network, subprocess, file or environment access in the core | AST allowlist plus runtime tripwires | `test_AO_*` |
| SA-A–D | Unsafe resource addresses: synthetic test key, webhook secret or token in quoted indexes, names or nested module segments | `<redacted-resource-address>`, still FAIL_UNEXPECTED_RESOURCE | `TestAddressSanitization.test_ABCD_*` |
| SA-E | Safe and canonical addresses stay readable | readable | `test_E_safe_addresses_remain_readable` |
| SA-F | Unexpected-resource classification unchanged after redaction | FAIL_UNEXPECTED_RESOURCE | `test_F_*` |
| SA-G | Duplicate detection uses original addresses | distinct originals allowed; identical originals malformed | `test_G_*` |
| SA-H–K | Redaction in `to_dict()`, `render_report()`, report and finding objects, `repr`/`str`, internal entry `repr`, malformed path | no sentinel anywhere | `test_HIJ_*`, `test_K_*` |
| SA-L | Deterministic output with several redacted addresses | identical across orderings | `test_L_*` |
| SA-N/O | Strict policy and explicit-only rotation policy unchanged | unchanged | `test_N_*`, `test_O_*` |
| SA-P | No false PASS introduced by redaction | FAIL | `test_P_*` |
| SA-labels | Caller policy labels and policy-rule addresses sanitized | redacted placeholders | `test_policy_label_sanitized`, `test_policy_rule_address_sanitized_when_absent` |
| SA-keys | Credential-shaped text embedded mid-key redacted; ordinary names readable | as stated | `test_key_redaction_matches_embedded_but_not_ordinary_names` |

Every check-path test also asserts that:

- the checker writes nothing to stdout or stderr;
- no synthetic sentinel appears in the text report, `to_dict()` JSON, `repr` or `str`;
- no raw plan fragment (`"before"`, `"after"`, `"variables":`, `"resource_changes"`, fixture values) appears in the output.

**Local results (Windows, Python 3.13.3, `-I -B`, standard library only):**

- 107 tests, OK, on three consecutive runs (93 original plus 14 address and label sanitization regressions added in the CP-5J security correction).
- Mutation check: 31 of 31 targeted mutants killed. The mutants included:
  - reintroducing the CP-5 nested-unknown bug;
  - bypassing the attribute and unknown allowlists;
  - disabling the hash match, the live-mode check, the explicit opt-in, the action check, duplicate detection, the output check, the noop-diff check, the errored-plan check, the sensitivity marker, the environment override and the key redaction;
  - bypassing the address sanitizer, allowing quoted indexes, removing the credential search or the length cap, emitting raw addresses on each of the three report paths, emitting unsanitized policy labels, anchoring the credential pattern to the prefix only, and dropping the deterministic report sort.
- Sources were restored byte-exact after each mutation run, and the suite passed again.

```text
python -I -B -m unittest discover -s tests/cp5 -t tests/cp5 -v
```

The repository CI `backend` job runs `pytest tests/backend` only, so it does **not** execute this suite. The CP-5J tests must be run explicitly.

## 11. Security restrictions

- Imports are limited to `__future__`, `dataclasses`, `typing`, `re` and the sibling engine, and this is enforced by an AST test.
- No `open`, `print`, `eval`, `exec`, `__import__`, `getattr`, environment access, subprocess, socket or URL access appears in either module.
- No CLI, `__main__` or `argv` handling.
- A runtime test patches file, environment, subprocess, socket and URL entry points to raise, and `check_plan` still completes normally.
- No secrets, credentials, real plan JSON or live environment data appear in source, tests or this document.

## 12. Example synthetic input (abridged)

Placeholders only. This is not real data.

```json
{
  "format_version": "1.2",
  "resource_changes": [
    {
      "address": "aws_lambda_function.admin",
      "mode": "managed",
      "type": "aws_lambda_function",
      "name": "admin",
      "change": {
        "actions": ["update"],
        "before": {"source_code_hash": "<SYNTHETIC_OLD_HASH>", "last_modified": "<SYNTHETIC_TIME>",
                   "environment": [{"variables": {"STRIPE_SECRET_KEY": "<SYNTHETIC_OLD_TEST_KEY>"}}]},
        "after":  {"source_code_hash": "861IQwFAXAIGW507wbNOgse3MCI12CIDbcsau8Ol5jc=",
                   "environment": [{"variables": {"STRIPE_SECRET_KEY": "<SYNTHETIC_NEW_TEST_KEY>"}}]},
        "after_unknown": {"last_modified": true, "environment": [{"variables": {}}]},
        "before_sensitive": {"environment": [{"variables": {"STRIPE_SECRET_KEY": true}}]},
        "after_sensitive":  {"environment": [{"variables": {"STRIPE_SECRET_KEY": true}}]}
      }
    }
  ],
  "output_changes": {}
}
```

## 13. Example sanitized output

This output was generated from the synthetic suite fixtures, with admin's `STRIPE_SECRET_KEY` changed, under the strict policy:

```text
CP-5J plan diff check
classification: FAIL_UNEXPECTED_ATTRIBUTE
policy: strict-code-only-3-lambda
counts: add=0, change=3, destroy=0, replace=0, read=0
resource: aws_lambda_function.admin actions=update expected=true
  configured environment[0].variables.STRIPE_SECRET_KEY sensitive=true verdict=rejected
  configured source_code_hash sensitive=false verdict=allowed
  unknown last_modified sensitive=false verdict=allowed
resource: aws_lambda_function.cancellation actions=update expected=true
  configured source_code_hash sensitive=false verdict=allowed
  unknown last_modified sensitive=false verdict=allowed
resource: aws_lambda_function.review actions=update expected=true
  configured source_code_hash sensitive=false verdict=allowed
  unknown last_modified sensitive=false verdict=allowed
finding: FAIL_UNEXPECTED_ATTRIBUTE reason=configured_change_not_allowed address=aws_lambda_function.admin path=environment[0].variables.STRIPE_SECRET_KEY
notice: PASS is a technical policy match only; it grants no release, deployment, plan or apply authority. Credential authority and rotation approval are separate controls.
```

## 14. Known limitations

1. **Synthetic validation only.** The checker has never processed a real Terraform plan. Real-plan shape compatibility is still unverified, including whether Terraform 1.14.8 with AWS provider 5.100.0 emits additional `after_unknown` leaves for a code-only Lambda update. Any such leaf will fail closed (`FAIL_UNEXPECTED_UNKNOWN`), and widening the allowlist would require a new reviewed policy entry.
2. **Plan materialization is out of scope.** Producing plan JSON from a saved plan needs Terraform with working-directory and provider access, and the JSON contains sensitive values in clear text. That step is a separately authorized, owner-gated operation, and its output must be treated as secret material.
3. **Positional arrays.** Order-insensitive set-typed attributes would report a reorder as a change. That is a conservative false FAIL, never a false PASS.
4. **Strict numeric typing.** `30` and `30.0` differ. Also a conservative false FAIL at worst.
5. **Contradictory unknown markers** (`true` alongside a concrete value) are rejected as malformed rather than interpreted.
6. **`resource_drift` is not evaluated.** It describes refresh-detected drift, not planned actions. Planned actions in `resource_changes` are always evaluated.
7. **Restricted test keys** (`rk_test_`) are accepted by the rotation profile alongside `sk_test_`. Which key type to deploy is an owner decision.
8. **Output-change failures** are classified `FAIL_POLICY_MISMATCH`, because outputs are not resources.
9. **Import path:** `scripts/cp5` must be on `sys.path`. No package `__init__` was added, to keep the change scope minimal.
10. **Address redaction is conservative.** Every non-canonical address with a quoted index (for example `for_each` keys) renders as `<redacted-resource-address>`, and several such resources become indistinguishable in a report. Reviewers then need the plan's own resource list, under the separately gated real-plan procedure, to identify them. Redaction never changes a verdict.
11. **Credential-shape detection is pattern-based.** A credential with no recognizable shape inside an otherwise plain, unquoted address segment would still render. Quoted indexes, the usual place for arbitrary strings in an address, are always redacted.

## 15. Deployment authorization boundary

- This change is source and tests only. Merging it (separately authorized) would change `main`, not production.
- No Terraform command, AWS call, Stripe operation, credential access, real plan read or deployment was performed in CP-5J.
- A PASS from this checker never substitutes for owner review of the plan, for the separate approval of the exact saved-plan identity before any apply, or for the separate credential-rotation authorization.

## 16. Future real-plan inspection gate

Running the checker on a real plan is a **separate, explicitly authorized checkpoint**, and it requires at minimum:

1. Owner approval naming the exact saved-plan file and its SHA-256. The old `cp5.tfplan` remains NEVER APPLY and is not a candidate.
2. Approval of the materialization step: who runs it, where, and how the clear-text JSON is protected and destroyed. Plan JSON contains secret values.
3. An explicit policy choice. Strict is the default. The rotation profile is used only after the separate Stripe test-key rotation authorization, and only with `rotation_separately_authorized=True` passed by the caller.
4. Retention of the sanitized report only, never the plan JSON.
5. A FAIL means stop and report. A PASS still requires owner review and a separate apply approval of the exact reviewed plan identity, within any Stripe overlap window.
