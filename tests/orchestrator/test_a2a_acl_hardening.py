"""G1.6-C2: offline hardening of the approval-boundary guard.

Covers token privileges, alternate-data-stream / path-form attacks, trusted
volume binding, the executing identity (no mock can be ENFORCED), volume-root
DELETE semantics, and approval-file identity pinning against TOCTOU.

All cases use MOCKED descriptors/handles unless marked ``*_native_*`` (those run
only on the matching OS, are READ-ONLY, and never log on as another account).
Windows-native results are reported separately from Linux CI.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import os
from pathlib import Path

import pytest

from scripts.orchestrator import acl_guard as g
from scripts.orchestrator import cli, errors
from scripts.orchestrator.acl_guard import (
    Ace,
    AclUnreadable,
    ApprovedFileSnapshot,
    BoundaryPolicy,
    FileIdentity,
    Identity,
    MockedDescriptorApprovalGuard,
    NodeSecurity,
    PosixNode,
    Privilege,
    ProductionApprovalGuard,
    VolumeBinding,
    VolumeInfo,
)
from scripts.orchestrator.manifest import load_manifest

from tests.orchestrator import a2a_support as s
from tests.orchestrator import test_a2a_acl_guard as base

A = base.AGENT
OWNER = base.OWNER
MAN, APPR, AGENT_ROOT, ROOT = base.MAN, base.APPR, base.AGENT_ROOT, base.ROOT


def ident(**kw) -> Identity:
    return base.agent_identity(**kw)


def backend(**kw):
    return base.FakeBackend(**kw)


def check(be=None, **kw):
    return base.check(be, **kw)


def priv(name, enabled=True, removed=False):
    return Privilege(name, enabled=enabled, removed=removed)


# --- 1. dangerous token privileges ----------------------------------------------


@pytest.mark.parametrize("name", sorted(g.DANGEROUS_PRIVILEGES))
@pytest.mark.parametrize("enabled", [True, False])
def test_every_dangerous_privilege_is_fatal_whether_enabled_or_disabled(name, enabled):
    who = ident(privileges=base.BENIGN + (priv(name, enabled),))
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(backend(identity=who))
    # the dangerous-set branch (not merely the "unexpected privilege" backstop) must fire
    assert f"token holds {name} (" in e.value.detail and "unexpected" not in e.value.detail
    assert ("enabled" in e.value.detail) if enabled else ("can be enabled" in e.value.detail)


@pytest.mark.parametrize("name", ["SeBackupPrivilege", "SeRestorePrivilege", "SeTakeOwnershipPrivilege"])
def test_the_dacl_bypass_privileges_are_named_in_the_dangerous_set(name):
    assert name in g.DANGEROUS_PRIVILEGES


def test_a_removed_privilege_is_ignored():
    who = ident(privileges=base.BENIGN + (priv("SeBackupPrivilege", enabled=False, removed=True),))
    assert check(backend(identity=who))[0].enforced


def test_an_unexpected_but_not_listed_privilege_is_fatal():
    who = ident(privileges=base.BENIGN + (priv("SeCreatePagefilePrivilege"),))
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(backend(identity=who))
    assert "unexpected privilege" in e.value.detail


def test_unreadable_privileges_are_unverifiable_never_inferred_from_groups():
    # A perfect, non-admin group set must not make an unread privilege list "safe".
    who = ident(privileges=None)
    assert who.group_sids and g.SID_ADMINISTRATORS not in who.all_ids
    with pytest.raises(errors.ApprovalBoundaryUnverifiable) as e:
        check(backend(identity=who))
    assert "privileges" in e.value.detail


def test_an_unnamed_privilege_is_unverifiable():
    who = ident(privileges=base.BENIGN + (priv("LUID:0:99"),))
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        check(backend(identity=who))


def test_an_empty_privilege_list_is_valid_and_accepted():
    assert check(backend(identity=ident(privileges=())))[0].enforced


@pytest.mark.parametrize("rid,exc", [(0x3000, errors.ApprovalBoundaryViolation), (0x4000, errors.ApprovalBoundaryViolation), (None, errors.ApprovalBoundaryUnverifiable)])
def test_high_or_unreadable_integrity_is_not_accepted(rid, exc):
    with pytest.raises(exc):
        check(backend(identity=ident(integrity_rid=rid)))


def test_low_and_medium_integrity_are_accepted():
    for rid in (0x1000, 0x2000):
        assert check(backend(identity=ident(integrity_rid=rid)))[0].enforced


def test_policy_can_never_allow_list_a_dangerous_privilege():
    with pytest.raises(ValueError):
        BoundaryPolicy(privilege_allowlist=frozenset({"SeBackupPrivilege"}))


def test_a_policy_allow_list_extension_for_a_harmless_privilege_works():
    pol = dataclasses.replace(base.POLICY, privilege_allowlist=g.BENIGN_PRIVILEGES | {"SeCreateGlobalPrivilege"})
    who = ident(privileges=base.BENIGN + (priv("SeCreateGlobalPrivilege"),))
    assert g.verify_boundary(backend(identity=who), pol, MAN, APPR).enforced


# --- 2. alternate data streams and path normalization -----------------------------


@pytest.mark.parametrize(
    "bad",
    [
        MAN + ":evil",
        MAN + "::$DATA",
        MAN + ":stream:$DATA",
        "C:\\petcare-agent\\approvals:hidden\\a2a.json",
        MAN + ".",
        MAN + " ",
        "C:\\petcare-agent\\approvals\\a2a.json...",
        "C:\\petcare-agent\\..\\petcare-agent\\approvals\\a2a.json",
        "C:\\petcare-agent\\.\\approvals\\a2a.json",
        "C:petcare-agent\\approvals\\a2a.json",
        "C:\\PETCAR~1\\approvals\\a2a.json",
        "C:\\petcare-agent\\approvals\\CON",
        "C:\\petcare-agent\\approvals\\nul.json",
        "C:\\petcare-agent\\approvals\\COM1",
        "C:\\petcare-agent\\approvals\\a?.json",
        "C:\\petcare-agent\\approvals\\*.json",
        "C:\\petcare-agent\\approvals\\a<b>.json",
        "\\\\?\\C:\\petcare-agent\\approvals\\a2a.json",
        "\\\\.\\C:\\petcare-agent\\approvals\\a2a.json",
        "\\\\?\\UNC\\server\\share\\a.json",
        "C:\\petcare-agent\\approvals\\a2a.json\x00.txt",
        "C:\\petcare-agent\\approvals\\a\x01.json",
        "",
    ],
)
def test_unsafe_or_ambiguous_manifest_path_forms_are_rejected(bad):
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(manifest=bad)
    assert "path rejected" in e.value.detail


@pytest.mark.parametrize("bad_dir", ["C:\\petcare-agent:approvals", "C:\\petcare-agent\\approvals::$INDEX_ALLOCATION", "C:\\petcare-agent\\approvals."])
def test_unsafe_approvals_dir_forms_are_rejected(bad_dir):
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(manifest=None, approvals=bad_dir)
    assert "path rejected" in e.value.detail


def test_legitimate_drive_letter_syntax_and_forward_slashes_are_preserved():
    assert g.canonical_windows_path("C:\\") == "C:\\"
    assert g.canonical_windows_path("p:\\approvals\\a.json") == "P:\\approvals\\a.json"
    assert g.canonical_windows_path("C:/petcare-agent//approvals/a2a.json") == MAN
    report, _ = check(manifest="c:/petcare-agent/approvals/a2a.json")
    assert report.enforced and report.nodes_checked == 4


@pytest.mark.parametrize("bad", ["relative/a.json", "/srv/owner/../etc/passwd", "/srv/./owner", "/srv/owner\x00", ""])
def test_posix_path_forms_are_rejected(bad):
    with pytest.raises(g.PathRejected):
        g.canonical_posix_path(bad)


def test_posix_guard_rejects_a_dot_segment_path():
    with pytest.raises(errors.ApprovalBoundaryViolation):
        base.pcheck_args(base.FakePosix(), "/srv/owner/approvals/../approvals/a.json", base.PAPPR)


# --- 3. trusted volume binding -------------------------------------------------------


def vol(**kw) -> VolumeInfo:
    return dataclasses.replace(base.GOOD_VOLUME, **kw)


def test_the_trusted_volume_is_bound_by_guid_and_reported_short():
    report, _ = check()
    assert report.volume == "cc594c83"


@pytest.mark.parametrize(
    "change,needle",
    [
        ({"dos_target": "\\??\\C:\\attacker-folder"}, "substituted"),
        ({"dos_target": "\\Device\\LanmanRedirector\\server\\share"}, "substituted"),
        ({"dos_target": ""}, "substituted"),
        ({"mount_root": "C:\\petcare-agent\\"}, "mount-point"),
        ({"mount_root": "D:\\"}, "mount-point"),
        ({"drive_type": 4}, "fixed local"),
        ({"drive_type": 2}, "fixed local"),
        ({"volume_guid": "\\\\?\\Volume{00000000-0000-0000-0000-000000000000}\\"}, "not a trusted volume"),
        ({"filesystem": "ReFS"}, "filesystem"),
        ({"label": "PetCareAgentX"}, "label"),
        ({"serial": 1}, "serial"),
        ({"bus_type": 11}, "file-backed virtual"),
        ({"bus_type": 17}, "file-backed virtual"),
    ],
)
def test_a_substituted_redirected_or_untrusted_volume_is_refused(change, needle):
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(backend(volume=vol(**change)))
    assert needle in e.value.detail


def test_a_matching_label_alone_never_establishes_trust():
    # Same label/serial/fs/bus but a different volume GUID: refused.
    other = vol(volume_guid="\\\\?\\Volume{11111111-2222-3333-4444-555555555555}\\")
    assert other.label == "PetCareAgent" and other.serial == 0xABCD1234
    with pytest.raises(errors.ApprovalBoundaryViolation):
        check(backend(volume=other))


def test_guid_comparison_ignores_case_only():
    assert check(backend(volume=vol(volume_guid=base.VOL_GUID.upper().replace("\\\\?\\VOLUME", "\\\\?\\Volume"))))[0].enforced


def test_unreadable_or_untyped_volume_identity_is_unverifiable():
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        check(backend(volume=AclUnreadable("denied")))
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        check(backend(volume="P:"))  # type: ignore[arg-type]

    class NoVolume(base.FakeBackend):
        volume_info = None  # type: ignore[assignment]

    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        check(NoVolume())


def test_unreadable_bus_type_is_unverifiable_only_when_the_binding_requires_it():
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        check(backend(volume=vol(bus_type=None)))
    relaxed = dataclasses.replace(
        base.POLICY, trusted_volumes=(VolumeBinding(base.VOL_GUID, label="PetCareAgent", require_file_backed_virtual=False),)
    )
    assert g.verify_boundary(backend(volume=vol(bus_type=None)), relaxed, MAN, APPR).enforced


@pytest.mark.parametrize(
    "policy",
    [
        dataclasses.replace(base.POLICY, trusted_volumes=()),
        dataclasses.replace(base.POLICY, expected_agent_sid=None),
        dataclasses.replace(base.POLICY, trusted_owner_sids=frozenset()),
    ],
)
def test_unset_trust_configuration_is_unverifiable(policy):
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        g.verify_boundary(backend(), policy, MAN, APPR)


def test_volume_binding_rejects_malformed_values():
    for bad in ("", "P:", "\\\\?\\Volume{nope}\\", "\\\\?\\Volume{cc594c83-54d8-4340-9d57-05ed19f20112}"):
        with pytest.raises(ValueError):
            VolumeBinding(bad)
    with pytest.raises(ValueError):
        VolumeBinding(base.VOL_GUID, serial=-1)


# --- 4. the actual executing identity ----------------------------------------------------


def test_the_owner_token_is_refused_even_with_a_perfect_looking_descriptor_set():
    owner_tok = Identity(OWNER, frozenset({base.EVERYONE, base.USERS, base.AUTH_USERS}), frozenset({base.ADMINS}),
                         privileges=base.BENIGN, integrity_rid=0x2000)
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(backend(identity=owner_tok))
    assert "not the expected agent" in e.value.detail and "not distinct" in e.value.detail


def test_any_token_other_than_the_expected_agent_is_refused():
    stranger = ident(user_sid="S-1-5-21-111-222-333-7777")
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(backend(identity=stranger))
    assert "not the expected agent" in e.value.detail


def test_posix_executing_uid_must_equal_the_expected_agent_uid():
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        base.pcheck(base.FakePosix(euid=1234))
    assert "not the expected agent" in e.value.detail


def test_production_guard_accepts_no_injected_backend_or_identity():
    params = list(inspect.signature(ProductionApprovalGuard.__init__).parameters)
    assert params == ["self", "policy"]
    with pytest.raises(TypeError):
        ProductionApprovalGuard(base.POLICY, base.FakeBackend())  # type: ignore[call-arg]
    assert "backend" not in inspect.getsource(ProductionApprovalGuard.__init__)


def test_mocked_descriptor_guard_is_offline_only_and_never_enforced():
    guard = MockedDescriptorApprovalGuard(base.POLICY, backend())
    report = guard.verify(MAN, APPR)
    assert guard.offline_only is True and report.enforced is False and report.mode == "OFFLINE_MOCKED_DESCRIPTORS"
    assert check()[0].enforced is True  # the pure evaluator still labels enforced when asked
    assert g.verify_boundary(backend(), base.POLICY, MAN, APPR, enforced=False).enforced is False


def test_mocked_descriptor_guard_is_refused_with_non_fixture_adapters(config, write_manifest):
    manifest = base.load(config, write_manifest)

    class NotAFixture:
        calls = 0

        def get_pull_request(self, *a, **k):
            NotAFixture.calls += 1
            raise AssertionError("must not be reached")

    runner, transport = s.make_runner(config, manifest, approval_guard=MockedDescriptorApprovalGuard(base.POLICY, backend()))
    runner.observer = NotAFixture()
    with pytest.raises(errors.ApprovalBoundaryViolation):
        runner.run(s.make_request())
    assert NotAFixture.calls == 0 and transport.calls == 0


class DuckEnforced:
    """Claims ENFORCED without being the built-in production guard."""

    mode = "ENFORCED"
    offline_only = False
    calls = 0

    def verify(self, manifest_path, approvals_dir):
        DuckEnforced.calls += 1
        return g.BoundaryReport("ENFORCED", "nt", True, 4, "duck")

    def read_approved(self, manifest_path, approvals_dir):
        return None


def test_a_duck_typed_enforced_guard_cannot_attest_the_boundary(config, write_manifest):
    manifest = base.load(config, write_manifest)
    obs = base.CountingObserver(s.FIX)
    runner, transport = base.build_runner(config, manifest, DuckEnforced(), obs)
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        runner.run(s.make_request())
    assert "built-in production" in e.value.detail
    assert DuckEnforced.calls == 0 and obs.calls == 0 and transport.calls == 0 and not runner.store.exists()


def test_a_subclass_of_the_production_guard_is_also_refused(config, write_manifest):
    class Sub(ProductionApprovalGuard):
        pass

    manifest = base.load(config, write_manifest)
    obs = base.CountingObserver(s.FIX)
    runner, transport = base.build_runner(config, manifest, Sub(base.POLICY), obs)
    with pytest.raises(errors.ApprovalBoundaryViolation):
        runner.run(s.make_request())
    assert obs.calls == 0 and transport.calls == 0


def test_the_production_guard_requires_a_pinned_snapshot_before_any_external_call(config, write_manifest):
    manifest = base.load(config, write_manifest)
    obs = base.CountingObserver(s.FIX)
    runner, transport = base.build_runner(config, manifest, ProductionApprovalGuard(base.POLICY), obs)
    with pytest.raises(errors.ApprovalBoundaryUnverifiable) as e:
        runner.run(s.make_request())
    assert "pinned snapshot" in e.value.detail
    assert obs.calls == 0 and transport.calls == 0 and not runner.store.exists()


# --- 5. volume-root DELETE semantics -----------------------------------------------------------


def root_with(*aces):
    nodes = base.good_nodes()
    nodes[ROOT] = NodeSecurity(ROOT, base.TRUSTED_INSTALLER, (Ace(base.SYSTEM, base.FULL), Ace(base.ADMINS, base.FULL)) + aces, is_dir=True)
    return nodes


def test_delete_alone_on_the_volume_root_is_inert_and_accepted():
    # Authenticated Users Modify on a default volume root includes DELETE but not DELETE_CHILD.
    for ace in (Ace(base.USERS, g.DELETE), Ace(base.AUTH_USERS, base.MODIFY)):
        assert check(backend(nodes=root_with(ace)))[0].enforced


@pytest.mark.parametrize("right", [g.FILE_DELETE_CHILD, g.WRITE_DAC, g.WRITE_OWNER, g.GENERIC_ALL])
def test_the_other_dangerous_rights_stay_fatal_on_the_volume_root(right):
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(backend(nodes=root_with(Ace(base.USERS, g.DELETE | right))))
    assert ROOT in e.value.detail


def test_delete_with_delete_child_on_the_root_is_still_fatal():
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(backend(nodes=root_with(Ace(base.USERS, g.DELETE | g.FILE_DELETE_CHILD))))
    assert "DELETE_CHILD" in e.value.detail


def test_delete_stays_fatal_on_a_non_root_ancestor():
    nodes = base.replace(base.good_nodes(), AGENT_ROOT, aces=base.owner_aces(inherited=False) + (Ace(base.USERS, g.DELETE),))
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(backend(nodes=nodes))
    assert "DELETE" in e.value.detail


def test_delete_stays_fatal_when_the_root_is_itself_the_approvals_target():
    nodes = {ROOT: NodeSecurity(ROOT, OWNER, (Ace(base.SYSTEM, base.FULL), Ace(OWNER, base.FULL), Ace(base.USERS, g.DELETE)), is_dir=True)}
    with pytest.raises(errors.ApprovalBoundaryViolation):
        check(backend(nodes=nodes), manifest=None, approvals=ROOT)


def test_the_root_exception_does_not_hide_a_non_delete_write_right_on_a_target():
    nodes = base.replace(base.good_nodes(), APPR, aces=base.owner_aces() + (Ace(base.USERS, g.DELETE),))
    with pytest.raises(errors.ApprovalBoundaryViolation):
        check(backend(nodes=nodes))


# --- 6. file identity pinning and TOCTOU -----------------------------------------------------------

CONTENT = json.dumps({"hello": "approval"}).encode()


class FakePinned:
    def __init__(self, content=CONTENT, *, path=MAN, nlinks=1, reparse=False, final_path=None, node=None):
        self.content = content
        self.path = path
        self.identity = FileIdentity(7, 4242, len(content), 111, nlinks)
        self.identity_now = self.identity
        self.final_path = final_path or path
        self.is_reparse = reparse
        self._node = node
        self.path_ok = True
        self.closed = False
        self.on_read = None
        self.reads = 0

    def node(self):
        return self._node if self._node is not None else base.good_nodes()[MAN]

    def read_all(self, max_bytes):
        self.reads += 1
        if self.on_read:
            self.on_read(self)
        if len(self.content) > max_bytes:
            raise AclUnreadable("approval file is larger than the allowed maximum")
        return self.content

    def current_identity(self):
        return self.identity_now

    def path_matches(self):
        return self.path_ok

    def close(self):
        self.closed = True


class PinBackend(base.FakeBackend):
    def __init__(self, pinned=None, open_error=None, **kw):
        super().__init__(**kw)
        self.pinned = pinned if pinned is not None else FakePinned()
        self.open_error = open_error
        self.opened = []

    def open_pinned(self, path):
        self.opened.append(path)
        if self.open_error:
            raise self.open_error
        return self.pinned


def read(be, **kw):
    return g.read_pinned_approval(be, base.POLICY, kw.pop("manifest", MAN), kw.pop("approvals", APPR), enforced=kw.pop("enforced", False))


def test_pinned_read_returns_the_bytes_hash_and_identity_and_pins_the_handle():
    be = PinBackend()
    snap = read(be)
    assert snap.content == CONTENT and snap.sha256 == hashlib.sha256(CONTENT).hexdigest()
    assert snap.identity == be.pinned.identity and snap.report.pinned is True
    assert be.opened == [MAN] and not be.pinned.closed
    snap.revalidate()
    snap.close()
    snap.close()  # idempotent
    assert be.pinned.closed and snap.closed
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        snap.revalidate()


def test_snapshot_context_manager_closes_the_handle():
    be = PinBackend()
    with read(be) as snap:
        assert not snap.closed
    assert be.pinned.closed


@pytest.mark.parametrize(
    "pinned,needle",
    [
        (FakePinned(nlinks=2), "hard links"),
        (FakePinned(reparse=True), "reparse"),
        (FakePinned(final_path="C:\\attacker\\a2a.json"), "different path"),
        (FakePinned(final_path="D:\\petcare-agent\\approvals\\a2a.json"), "different path"),
    ],
)
def test_a_hardlinked_reparse_or_redirected_open_is_refused_and_closed(pinned, needle):
    be = PinBackend(pinned=pinned)
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        read(be)
    assert needle in e.value.detail and pinned.closed


def test_the_descriptor_of_the_open_handle_is_evaluated_not_just_the_path():
    # The path-based read looked fine, but the handle's own descriptor is agent-writable / agent-owned.
    for bad_node in (
        NodeSecurity(MAN, OWNER, base.owner_aces(agent_mask=base.MODIFY)),
        NodeSecurity(MAN, A, base.owner_aces()),
        NodeSecurity(MAN, OWNER, base.owner_aces(), is_reparse=True),
    ):
        pinned = FakePinned(node=bad_node)
        with pytest.raises(errors.ApprovalBoundaryViolation):
            read(PinBackend(pinned=pinned))
        assert pinned.closed


def test_an_unreadable_handle_descriptor_is_unverifiable():
    pinned = FakePinned(node=NodeSecurity(MAN, OWNER, (), dacl_present=False))
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        read(PinBackend(pinned=pinned))
    assert pinned.closed


def test_replacement_or_modification_during_the_read_is_detected():
    def swap_identity(p):
        p.identity_now = FileIdentity(7, 9999, p.identity.size, p.identity.mtime_ns, 1)  # different file index

    pinned = FakePinned()
    pinned.on_read = swap_identity
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        read(PinBackend(pinned=pinned))
    assert "while it was being read" in e.value.detail and pinned.closed

    def touch(p):
        p.identity_now = dataclasses.replace(p.identity, mtime_ns=p.identity.mtime_ns + 1)

    pinned = FakePinned()
    pinned.on_read = touch
    with pytest.raises(errors.ApprovalBoundaryViolation):
        read(PinBackend(pinned=pinned))


def test_a_path_that_stops_naming_the_opened_file_is_detected():
    pinned = FakePinned()
    pinned.on_read = lambda p: setattr(p, "path_ok", False)
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        read(PinBackend(pinned=pinned))
    assert "no longer names" in e.value.detail and pinned.closed


def test_an_acl_change_on_the_chain_between_check_and_read_is_detected():
    be = PinBackend()

    def widen(p):
        be.nodes[APPR.lower()] = NodeSecurity(APPR, OWNER, base.owner_aces(agent_mask=base.MODIFY), is_dir=True)

    be.pinned.on_read = widen
    with pytest.raises(errors.ApprovalBoundaryViolation):
        read(be)
    assert be.pinned.closed


def test_a_chain_that_changes_shape_between_checks_is_detected():
    be = PinBackend()
    calls = {"n": 0}
    original = be.read_node

    def flaky(path):
        calls["n"] += 1
        if calls["n"] > 4 and path == ROOT:  # second pass loses the root node
            raise AclUnreadable("vanished")
        return original(path)

    be.read_node = flaky
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        read(be)
    assert be.pinned.closed


def test_oversize_unopenable_and_unpinnable_files_fail_closed():
    big = FakePinned(content=b"x" * (g.MAX_APPROVAL_BYTES + 1))
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        read(PinBackend(pinned=big))
    assert big.closed
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        read(PinBackend(open_error=AclUnreadable("sharing violation")))

    class NoPin(base.FakeBackend):
        pass

    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        read(NoPin())


def test_a_bad_chain_means_the_file_is_never_opened():
    nodes = base.replace(base.good_nodes(), APPR, aces=base.owner_aces(agent_mask=base.MODIFY))
    be = PinBackend(nodes=nodes)
    with pytest.raises(errors.ApprovalBoundaryViolation):
        read(be)
    assert be.opened == []


def test_an_alternate_stream_path_is_never_opened():
    be = PinBackend()
    with pytest.raises(errors.ApprovalBoundaryViolation):
        read(be, manifest=MAN + ":evil")
    assert be.opened == []


def test_revalidate_detects_later_replacement_modification_and_path_drift():
    be = PinBackend()
    snap = read(be)
    be.pinned.path_ok = False
    with pytest.raises(errors.ApprovalBoundaryViolation):
        snap.revalidate()
    be.pinned.path_ok = True
    be.pinned.identity_now = dataclasses.replace(be.pinned.identity, size=999)
    with pytest.raises(errors.ApprovalBoundaryViolation):
        snap.revalidate()
    be.pinned.identity_now = be.pinned.identity
    be.pinned.content = b'{"hello": "EVIL"}'  # same length would pass identity; the hash must still catch it
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        snap.revalidate()
    assert "content changed" in e.value.detail
    snap.close()


def test_mocked_guard_reads_a_pinned_snapshot_and_offline_guards_return_none():
    snap = MockedDescriptorApprovalGuard(base.POLICY, PinBackend()).read_approved(MAN, APPR)
    assert snap is not None and snap.content == CONTENT and snap.report.enforced is False
    snap.close()
    assert MockedDescriptorApprovalGuard(base.POLICY, backend()).read_approved(MAN, APPR) is None
    assert g.OfflineFixtureApprovalGuard().read_approved(MAN, APPR) is None


def test_posix_pinned_read_evaluates_the_open_fd_not_the_path():
    class PosixPinBackend(base.FakePosix):
        def __init__(self, pinned):
            super().__init__()
            self.pinned = pinned

        def open_pinned(self, path):
            return self.pinned

    class PosixPinned(FakePinned):
        def node(self):
            return self._node or PosixNode(base.PMAN, 0, 0o100644)

    good = PosixPinned(path=base.PMAN)
    snap = g.read_pinned_approval(PosixPinBackend(good), base.PPOL, base.PMAN, base.PAPPR, enforced=False)
    assert snap.content == CONTENT
    snap.close()
    bad = PosixPinned(path=base.PMAN, node=PosixNode(base.PMAN, 0, 0o100666))
    with pytest.raises(errors.ApprovalBoundaryViolation):
        g.read_pinned_approval(PosixPinBackend(bad), base.PPOL, base.PMAN, base.PAPPR, enforced=False)
    assert bad.closed


# --- manifest loading from pinned bytes -----------------------------------------------------------


def test_manifest_is_parsed_from_the_pinned_bytes_and_the_path_is_not_reread(config, write_manifest):
    path = write_manifest(**s.pr_overrides())
    on_disk = path.read_bytes()
    from_path = load_manifest(path, config)
    assert from_path.source_sha256 is None
    from_bytes = load_manifest(path, config, content=on_disk)
    assert from_bytes.fingerprint() == from_path.fingerprint()
    assert from_bytes.source_sha256 == hashlib.sha256(on_disk).hexdigest()
    # Swap the file on disk after the snapshot: the loader must keep using the pinned bytes.
    path.write_text(json.dumps({"evil": True}), encoding="utf-8")
    still = load_manifest(path, config, content=on_disk)
    assert still.fingerprint() == from_path.fingerprint() and still.scope_id == from_path.scope_id


def test_invalid_pinned_bytes_are_an_invalid_manifest_not_a_crash(config, write_manifest):
    path = write_manifest(**s.pr_overrides())
    for bad in (b"\xff\xfe\x00", b"not json", b"[]"):
        with pytest.raises(errors.ApprovalInvalid):
            load_manifest(path, config, content=bad)


def test_pinned_bytes_do_not_bypass_the_location_trust_checks(config, write_manifest, runtime_dir):
    inside_runtime = write_manifest(directory=runtime_dir)
    with pytest.raises(errors.ApprovalUntrustedSource):
        load_manifest(inside_runtime, config, content=inside_runtime.read_bytes())


def _snapshot(sha, pinned=None):
    pinned = pinned or FakePinned()
    return ApprovedFileSnapshot(
        path=MAN, content=CONTENT, sha256=sha, identity=pinned.identity, pinned=pinned,
        report=g.BoundaryReport("ENFORCED", "nt", True, 4, "t", "v", True),
    )


def test_the_runner_rejects_a_manifest_that_is_not_the_pinned_snapshot(config, write_manifest):
    manifest = base.load(config, write_manifest)  # loaded from the path: no source_sha256
    snap = _snapshot(hashlib.sha256(CONTENT).hexdigest())
    obs = base.CountingObserver(s.FIX)
    runner, transport = base.build_runner(config, manifest, ProductionApprovalGuard(base.POLICY), obs)
    runner.approved_snapshot = snap
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        runner.run(s.make_request())
    assert "not the pinned approval file" in e.value.detail
    assert obs.calls == 0 and transport.calls == 0

    pinned_manifest = load_manifest(Path(manifest.source_path), config, content=Path(manifest.source_path).read_bytes())
    mismatched = _snapshot("0" * 64)
    runner2, transport2 = base.build_runner(config, pinned_manifest, ProductionApprovalGuard(base.POLICY), base.CountingObserver(s.FIX))
    runner2.approved_snapshot = mismatched
    with pytest.raises(errors.ApprovalBoundaryViolation):
        runner2.run(s.make_request())
    assert transport2.calls == 0


def test_the_runner_revalidates_the_pinned_snapshot_before_any_external_call(config, write_manifest):
    path = write_manifest(**s.pr_overrides())
    data = path.read_bytes()
    manifest = load_manifest(path, config, content=data)
    pinned = FakePinned(content=data)
    snap = _snapshot(hashlib.sha256(data).hexdigest(), pinned)
    pinned.content = b"tampered"  # the pinned file no longer matches what was verified
    obs = base.CountingObserver(s.FIX)
    runner, transport = base.build_runner(config, manifest, ProductionApprovalGuard(base.POLICY), obs)
    runner.approved_snapshot = snap
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        runner.run(s.make_request())
    assert "content changed" in e.value.detail
    assert obs.calls == 0 and transport.calls == 0 and not runner.store.exists()


# --- CLI ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra",
    [
        ("--trusted-owner-sid", OWNER, "--trusted-volume-guid", "not-a-guid"),
        ("--trusted-owner-sid", OWNER, "--trusted-volume-guid", base.VOL_GUID, "--trusted-volume-serial", "zz"),
        ("--trusted-owner-sid", OWNER, "--expected-agent-sid", "alice"),
    ],
)
def test_cli_rejects_malformed_volume_or_agent_identity_flags(write_manifest, runtime_dir, approvals_dir, capsys, extra):
    path = write_manifest(**s.pr_overrides())
    assert cli.main(base._cli(runtime_dir, approvals_dir, path, *extra)) == 2
    assert "APPROVAL_BOUNDARY_UNVERIFIABLE" in capsys.readouterr().err


def test_cli_enforced_without_agent_and_volume_binding_is_unverifiable(write_manifest, runtime_dir, approvals_dir, capsys):
    path = write_manifest(**s.pr_overrides())
    flag = ("--trusted-owner-sid", OWNER) if os.name == "nt" else ("--trusted-owner-uid", "0")
    assert cli.main(base._cli(runtime_dir, approvals_dir, path, *flag)) == 2
    assert "APPROVAL_BOUNDARY_UNVERIFIABLE" in capsys.readouterr().err
    assert not (runtime_dir / "a2a_checkpoint.json").exists()


def test_cli_offline_fixture_path_still_works_with_the_pinned_loader_disabled(write_manifest, runtime_dir, approvals_dir, capsys):
    path = write_manifest(**s.pr_overrides())
    assert cli.main(base._cli(runtime_dir, approvals_dir, path, "--offline-fixtures")) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["approval_boundary"]["mode"] == "OFFLINE_FIXTURE_UNENFORCED" and out["approval_boundary"]["pinned"] is False


# --- POSIX-native (real fds; runs on Linux CI) -----------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="POSIX-native check")
def test_posix_native_pinned_open_reads_pins_and_detects_replacement(tmp_path):
    be = g.PosixSecurityBackend()
    f = tmp_path / "a.json"
    f.write_bytes(b'{"a":1}')
    pin = be.open_pinned(str(f))
    try:
        assert pin.read_all(100) == b'{"a":1}'
        assert pin.identity.nlinks == 1 and pin.is_reparse is False and pin.final_path.endswith("a.json")
        assert pin.path_matches() and pin.current_identity() == pin.identity
        os.replace(str(f), str(tmp_path / "moved.json"))
        (tmp_path / "a.json").write_bytes(b'{"evil":1}')
        assert pin.path_matches() is False  # the path now names a different inode
        assert pin.read_all(100) == b'{"a":1}'  # but the pinned bytes are still the verified ones
    finally:
        pin.close()


@pytest.mark.skipif(os.name == "nt", reason="POSIX-native check")
def test_posix_native_open_refuses_symlinks_directories_and_oversize(tmp_path):
    be = g.PosixSecurityBackend()
    real = tmp_path / "real.json"
    real.write_text("{}")
    (tmp_path / "link.json").symlink_to(real)
    with pytest.raises(AclUnreadable):
        be.open_pinned(str(tmp_path / "link.json"))
    with pytest.raises(AclUnreadable):
        be.open_pinned(str(tmp_path))
    big = tmp_path / "big.json"
    big.write_bytes(b"x" * 200)
    pin = be.open_pinned(str(big))
    try:
        with pytest.raises(AclUnreadable):
            pin.read_all(100)
    finally:
        pin.close()


@pytest.mark.skipif(os.name == "nt", reason="POSIX-native check")
def test_posix_native_hardlink_and_modification_are_visible_in_identity(tmp_path):
    be = g.PosixSecurityBackend()
    f = tmp_path / "a.json"
    f.write_bytes(b"{}")
    pin = be.open_pinned(str(f))
    try:
        os.link(str(f), str(tmp_path / "second.json"))
        assert pin.current_identity().nlinks == 2 and pin.current_identity() != pin.identity
    finally:
        pin.close()


@pytest.mark.skipif(os.name == "nt", reason="POSIX-native check")
def test_posix_native_pinned_read_through_the_guard_refuses_a_same_identity_tmp_tree(tmp_path):
    d = tmp_path / "approvals"
    d.mkdir()
    f = d / "a.json"
    f.write_text("{}")
    guard = ProductionApprovalGuard(BoundaryPolicy(trusted_owner_uids=frozenset({0}), expected_agent_uid=os.geteuid()))
    with pytest.raises(errors.ApprovalBoundaryViolation):
        guard.read_approved(f, d)


# --- Windows-native (real ctypes backend; READ-ONLY; temp files only) --------------------------------


def _win():
    from scripts.orchestrator.acl_windows import WindowsSecurityBackend

    return WindowsSecurityBackend()


@pytest.mark.skipif(os.name != "nt", reason="Windows-native check")
def test_windows_native_token_privileges_and_integrity_are_read_and_named():
    who = _win().current_identity()
    assert who.privileges is not None and who.integrity_rid is not None
    assert all(p.name.startswith("Se") and p.name.endswith("Privilege") for p in who.privileges), who.privileges
    assert who.integrity_rid in (0x1000, 0x2000, 0x3000, 0x4000)
    assert any(p.name == "SeChangeNotifyPrivilege" for p in who.privileges)  # in every token


@pytest.mark.skipif(os.name != "nt", reason="Windows-native check")
def test_windows_native_volume_info_describes_the_real_volume(tmp_path):
    info = _win().volume_info(str(tmp_path))
    assert info.mount_root.upper() == (str(tmp_path)[:3]).upper()
    assert g._GUID_PATH_RE.match(info.volume_guid) and g._DEVICE_RE.match(info.dos_target)
    assert info.drive_type == 3 and info.filesystem and isinstance(info.serial, int)


@pytest.mark.skipif(os.name != "nt", reason="Windows-native check")
def test_windows_native_pinned_open_denies_writers_renamers_and_deleters(tmp_path):
    be = _win()
    f = tmp_path / "a.json"
    f.write_bytes(b'{"a":1}')
    pin = be.open_pinned(str(f))
    try:
        assert pin.read_all(100) == b'{"a":1}'
        assert pin.identity.nlinks == 1 and not pin.is_reparse and pin.path_matches()
        assert os.path.normcase(pin.final_path) == os.path.normcase(str(f))
        node = pin.node()
        assert node.owner and node.dacl_present and node.aces
        with pytest.raises(PermissionError):
            f.write_bytes(b"evil")
        with pytest.raises(PermissionError):
            os.rename(str(f), str(f) + ".moved")
        with pytest.raises(PermissionError):
            os.remove(str(f))
        assert pin.read_all(100) == b'{"a":1}' and pin.current_identity() == pin.identity
    finally:
        pin.close()
    f.write_bytes(b"after")  # released once closed


@pytest.mark.skipif(os.name != "nt", reason="Windows-native check")
def test_windows_native_open_through_a_junction_reports_a_different_final_path(tmp_path):
    import _winapi

    be = _win()
    target = tmp_path / "target"
    target.mkdir()
    (target / "a.json").write_text("{}")
    link = tmp_path / "junction"
    _winapi.CreateJunction(str(target), str(link))
    requested = str(link / "a.json")
    pin = be.open_pinned(requested)
    try:
        assert os.path.normcase(pin.final_path) != os.path.normcase(requested)
        assert os.path.normcase(pin.final_path) == os.path.normcase(str(target / "a.json"))
    finally:
        pin.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows-native check")
def test_windows_native_alternate_stream_and_odd_paths_are_refused_before_any_open(tmp_path):
    be = _win()
    me = be.current_identity().user_sid
    d = tmp_path / "approvals"
    d.mkdir()
    f = d / "a.json"
    f.write_text("{}")
    guard = ProductionApprovalGuard(BoundaryPolicy(
        trusted_owner_sids=frozenset({me}), expected_agent_sid=me,
        trusted_volumes=(VolumeBinding(be.volume_info(str(d)).volume_guid, require_file_backed_virtual=False),),
    ))
    for bad in (str(f) + ":evil", str(f) + "::$DATA", str(f) + ".", str(d) + "\\..\\approvals\\a.json"):
        with pytest.raises(errors.ApprovalBoundaryViolation) as e:
            guard.read_approved(bad, d)
        assert "path rejected" in e.value.detail


@pytest.mark.skipif(os.name != "nt", reason="Windows-native check")
def test_windows_native_production_guard_refuses_the_owner_process_token(tmp_path):
    """The running (owner) token is not an agent: even a perfectly named policy is refused."""

    be = _win()
    me = be.current_identity().user_sid
    d = tmp_path / "approvals"
    d.mkdir()
    f = d / "a.json"
    f.write_text("{}")
    other = "S-1-5-21-1-2-3-4242"
    guard = ProductionApprovalGuard(BoundaryPolicy(
        trusted_owner_sids=frozenset({g.SID_SYSTEM}), expected_agent_sid=other,
        trusted_volumes=(VolumeBinding(be.volume_info(str(d)).volume_guid, require_file_backed_virtual=False),),
    ))
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        guard.verify(f, d)
    assert "not the expected agent" in e.value.detail
    assert me != other
