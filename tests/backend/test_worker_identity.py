import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))
import unittest
from dataclasses import replace
from decimal import Decimal
from common.worker_identity import (
    ContractError, Failure, MAX_REVISION, revision, next_revision, worker_id,
    principal_from_verified_claims, principal_key, parse_worker, parse_link, parse_staff,
    assess_linkage, payload_digest,
)
from worker_identity_fixtures import fixture


class WorkerIdentityTests(unittest.TestCase):
    def test_consistent_owner_stays_policy_pending(self):
        p, w, l, s, *_ = fixture()
        self.assertEqual(assess_linkage(p, w, l, s), Failure.POLICY_PENDING)

    def test_no_role_receives_execution_grant(self):
        p, w, l, s, *_ = fixture()
        for role in ("owner", "admin", "staff", "client", "unknown"):
            self.assertEqual(assess_linkage(replace(p, role=role), w, l, s), Failure.POLICY_PENDING)

    def test_integral_db_numbers_are_explicitly_parsed(self):
        for value in (1, MAX_REVISION, Decimal("1.000")):
            self.assertIs(type(revision(value)), int)

    def test_invalid_revisions_fail_closed(self):
        for value in (True, False, 1.0, 1.5, "1", None, 0, -1, MAX_REVISION + 1,
                      Decimal("1.5"), Decimal("NaN"), Decimal("Infinity"), Decimal("sNaN")):
            with self.subTest(value=value), self.assertRaises(ContractError):
                revision(value)
        with self.assertRaises(ContractError):
            next_revision(MAX_REVISION)

    def test_email_or_guessed_id_is_not_canonical(self):
        for value in ("synthetic@example.invalid", "staff-a", "wrk_short", "wrk_" + "A" * 32, None):
            with self.assertRaises(ContractError):
                worker_id(value)

    def test_principal_binding_and_no_email_role_fallback(self):
        claims = {"iss": "https://issuer.example.invalid/pool-a", "sub": "subject-a",
                  "custom:company_id": "tenant_a", "cognito:groups": [], "email": "synthetic@example.invalid"}
        p = principal_from_verified_claims(claims, (claims["iss"],), "tenant_a")
        self.assertEqual(p.role, "unknown")
        for field, value in (("iss", "https://other.example.invalid"), ("sub", ""),
                             ("custom:company_id", "tenant_b"), ("cognito:groups", "owner")):
            with self.assertRaises(ContractError):
                principal_from_verified_claims(claims | {field: value}, (claims["iss"],), "tenant_a")

    def test_dual_role_does_not_downgrade_owner(self):
        issuer = "https://issuer.example.invalid/pool-a"
        p = principal_from_verified_claims({"iss": issuer, "sub": "subject-a", "custom:company_id": "tenant_a",
            "cognito:groups": ["staff", "owner"]}, (issuer,), "tenant_a")
        self.assertEqual(p.role, "owner")  # Proposed contract assumption, not runtime integration.

    def test_principal_key_binds_issuer_subject_and_tenant(self):
        p, *_ = fixture()
        for other in (replace(p, issuer="https://issuer.example.invalid/pool-b"),
                      replace(p, subject="subject-b"), replace(p, tenant="tenant_b")):
            self.assertNotEqual(principal_key(p), principal_key(other))

    def test_missing_and_unknown_record_fields(self):
        p, w, l, s, *_ = fixture()
        for bad in (w | {"unexpected": True}, {k:v for k,v in w.items() if k != "version"}, w | {"contract_version": 2}):
            with self.assertRaises(ContractError):
                parse_worker(bad, p.tenant)
        with self.assertRaises(ContractError):
            parse_link(l | {"contract_version": 2}, p)

    def test_wrong_tenant_on_each_record(self):
        p, w, l, s, *_ = fixture()
        for index in range(3):
            records = [w, l, s]
            records[index] = records[index] | {"company_id": "tenant_b"}
            self.assertEqual(assess_linkage(p, *records), Failure.WRONG_TENANT)

    def test_reciprocal_and_subject_mismatch(self):
        p, w, l, s, *_ = fixture()
        self.assertEqual(assess_linkage(p, w, l | {"staff_id": "staff-b"}, s), Failure.MISMATCH)
        self.assertEqual(assess_linkage(p, w, l, s | {"cognito_sub": "subject-b"}), Failure.MISMATCH)

    def test_revoked_and_inactive_records(self):
        p, w, l, s, *_ = fixture()
        for index, field in ((0, "is_active"), (0, "is_assignable"), (1, "is_active"), (2, "is_active"), (2, "is_assignable")):
            records = [w, l, s]
            records[index] = records[index] | {field: False}
            self.assertEqual(assess_linkage(p, *records), Failure.INACTIVE)
        self.assertEqual(assess_linkage(p, w, None, s), Failure.UNLINKED)

    def test_truthy_flags_do_not_qualify(self):
        p, w, l, s, *_ = fixture()
        self.assertEqual(assess_linkage(p, w | {"is_active": "true"}, l, s), Failure.MALFORMED)

    def test_staff_legacy_display_fields_are_not_proof(self):
        p, w, l, s, *_ = fixture()
        self.assertEqual(parse_staff(s | {"email": "synthetic@example.invalid", "display_name": "Synthetic"}, p.tenant), s)
        with self.assertRaises(ContractError):
            parse_staff(s | {"cognito_sub": "unlinked"}, p.tenant)

    def test_digest_is_derived_from_exact_bytes(self):
        self.assertNotEqual(payload_digest(b"notes-a"), payload_digest(b"notes-b"))
        with self.assertRaises(ContractError):
            payload_digest("notes")

    def test_errors_do_not_echo_private_record_data(self):
        with self.assertRaises(ContractError) as error:
            worker_id("synthetic@example.invalid")
        self.assertEqual(str(error.exception), "MALFORMED_RECORD")

    def test_malformed_principal_has_explicit_failure(self):
        p, w, l, s, *_ = fixture()
        for bad in (None, {}, replace(p, issuer="http://issuer.example.invalid"), replace(p, subject="")):
            self.assertEqual(assess_linkage(bad, w, l, s), Failure.MALFORMED)

    def test_malformed_record_containers_have_explicit_failure(self):
        p, w, l, s, *_ = fixture()
        for bad in (None, [], "record", True):
            self.assertEqual(assess_linkage(p, bad, l, s), Failure.MALFORMED)
