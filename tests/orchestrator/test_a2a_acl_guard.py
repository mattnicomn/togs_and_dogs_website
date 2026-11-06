"""G1.6-B: offline Windows-ACL (and POSIX) approval-boundary enforcement.

Cases 1-9 use MOCKED security descriptors, so they run identically on Linux CI
and Windows. Tests that touch the real OS are marked and reported separately:
  * ``test_windows_native_*``  -- run only on Windows (real ctypes backend);
  * ``test_posix_native_*``    -- run only on POSIX.
No ACL, owner, account or password is ever changed by any test here.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

from scripts.orchestrator import acl_guard as g
from scripts.orchestrator import cli, errors
import dataclasses

from scripts.orchestrator.acl_guard import (
    Ace,
    AclUnreadable,
    BoundaryPolicy,
    Identity,
    MockedDescriptorApprovalGuard,
    NodeSecurity,
    OfflineFixtureApprovalGuard,
    PosixNode,
    Privilege,
    ProductionApprovalGuard,
    VolumeBinding,
    VolumeInfo,
)
from scripts.orchestrator.adapters.github_observer import FixtureGitHubObserver
from scripts.orchestrator.adapters.openai_evidence_reviewer import OpenAIEvidenceReviewer, ReviewerConfig
from scripts.orchestrator.evidence_review import EvidenceReviewRunner
from scripts.orchestrator.manifest import load_manifest

from tests.orchestrator import a2a_support as s

PKG = Path(__file__).resolve().parents[2] / "scripts" / "orchestrator"

OWNER = "S-1-5-21-111-222-333-1001"
AGENT = "S-1-5-21-111-222-333-1008"
EVERYONE, USERS, AUTH_USERS = "S-1-1-0", "S-1-5-32-545", "S-1-5-11"
SYSTEM, ADMINS, TRUSTED_INSTALLER = g.SID_SYSTEM, g.SID_ADMINISTRATORS, g.SID_TRUSTED_INSTALLER

RX = 0x1200A9  # audited agent read & execute
MODIFY = 0x1301BF  # audited agent Modify
FULL = 0x1F01FF

ROOT = "C:\\"
AGENT_ROOT = "C:\\petcare-agent"
APPR = "C:\\petcare-agent\\approvals"
MAN = "C:\\petcare-agent\\approvals\\a2a.json"


BENIGN = tuple(Privilege(n, enabled=(n == "SeChangeNotifyPrivilege")) for n in sorted(g.BENIGN_PRIVILEGES))
VOL_GUID = "\\\\?\\Volume{cc594c83-54d8-4340-9d57-05ed19f20112}\\"
GOOD_VOLUME = VolumeInfo(
    mount_root="C:\\", dos_target="\\Device\\HarddiskVolume11", volume_guid=VOL_GUID, drive_type=3,
    filesystem="NTFS", label="PetCareAgent", serial=0xABCD1234, bus_type=g.BUS_FILE_BACKED_VIRTUAL,
    vendor="Msft", product="Virtual Disk",
)


def agent_identity(**kw) -> Identity:
    base = dict(
        user_sid=AGENT,
        group_sids=frozenset({EVERYONE, USERS, AUTH_USERS, "S-1-5-4", "S-1-2-1"}),
        deny_only_group_sids=frozenset(),
        privileges=BENIGN,
        integrity_rid=0x2000,
    )
    base.update(kw)
    return Identity(**base)


class FakeBackend:
    platform = "nt"

    def __init__(self, identity=None, nodes=None, unreadable=(), volume=None):
        self.volume = volume if volume is not None else GOOD_VOLUME
        self.identity = identity if identity is not None else agent_identity()
        # Windows paths are case-insensitive: look nodes up by lower-cased path.
        self.nodes = {k.lower(): v for k, v in (nodes if nodes is not None else good_nodes()).items()}
        self.unreadable = {p.lower() for p in unreadable}
        self.reads: list[str] = []

    def current_identity(self):
        if isinstance(self.identity, Exception):
            raise self.identity
        return self.identity

    def volume_info(self, path):
        if isinstance(self.volume, Exception):
            raise self.volume
        return self.volume

    def read_node(self, path):
        self.reads.append(path)
        key = path.lower()
        if key in self.unreadable or key not in self.nodes:
            raise AclUnreadable("mock: access denied")
        return self.nodes[key]


def owner_aces(agent_mask=RX, inherited=True):
    return (
        Ace(SYSTEM, FULL, inherited=inherited),
        Ace(ADMINS, FULL, inherited=inherited),
        Ace(OWNER, FULL, inherited=inherited),
        Ace(AGENT, agent_mask, inherited=inherited),
    )


def good_nodes():
    return {
        ROOT: NodeSecurity(ROOT, TRUSTED_INSTALLER, (
            Ace(SYSTEM, FULL), Ace(ADMINS, FULL), Ace(USERS, RX), Ace(AUTH_USERS, RX),
        ), is_dir=True),
        AGENT_ROOT: NodeSecurity(AGENT_ROOT, OWNER, owner_aces(inherited=False), is_dir=True),
        APPR: NodeSecurity(APPR, OWNER, owner_aces(), is_dir=True),
        MAN: NodeSecurity(MAN, OWNER, owner_aces()),
    }


POLICY = BoundaryPolicy(
    trusted_owner_sids=frozenset({OWNER}),
    expected_agent_sid=AGENT,
    trusted_volumes=(VolumeBinding(VOL_GUID, label="PetCareAgent", serial=0xABCD1234),),
)


def check(backend=None, manifest=MAN, approvals=APPR):
    backend = backend or FakeBackend()
    return g.verify_boundary(backend, POLICY, manifest, approvals), backend


def replace(nodes, path, **changes):
    n = dict(nodes)
    old = n[path]
    n[path] = NodeSecurity(**{**old.__dict__, **changes})
    return n


# --- 8: the correct, protected layout is accepted ----------------------------


def test_correct_protected_layout_is_accepted():
    report, backend = check()
    assert report.enforced and report.mode == "ENFORCED" and report.platform == "nt"
    assert report.nodes_checked == 4 and report.agent.endswith("-1008")
    assert backend.reads == [MAN, APPR, AGENT_ROOT, ROOT]


def test_audited_host_values_match_the_modelled_masks():
    assert RX & g.DANGEROUS_TARGET == 0
    assert MODIFY & g.DANGEROUS_TARGET != 0  # Modify must be flagged on the approvals dir
    assert RX & g.DANGEROUS_ANCESTOR == 0


# --- 1: agent-writeable approvals rejected -----------------------------------


@pytest.mark.parametrize("path", [APPR, MAN, AGENT_ROOT])
def test_agent_modify_on_the_chain_is_rejected(path):
    nodes = replace(good_nodes(), path, aces=owner_aces(agent_mask=MODIFY))
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(FakeBackend(nodes=nodes))
    assert path in e.value.detail


@pytest.mark.parametrize("right", [g.FILE_WRITE_DATA, g.FILE_APPEND_DATA, g.FILE_DELETE_CHILD, g.DELETE, g.GENERIC_WRITE, g.GENERIC_ALL, g.FILE_WRITE_ATTRIBUTES, g.FILE_WRITE_EA])
def test_each_single_dangerous_right_on_approvals_is_rejected(right):
    nodes = replace(good_nodes(), APPR, aces=owner_aces(agent_mask=RX | right))
    with pytest.raises(errors.ApprovalBoundaryViolation):
        check(FakeBackend(nodes=nodes))


# --- 2: agent-owned approvals rejected even with an RX-only DACL -------------


@pytest.mark.parametrize("path", [APPR, MAN, AGENT_ROOT])
def test_agent_owned_node_is_rejected_even_with_rx_only_dacl(path):
    nodes = replace(good_nodes(), path, owner=AGENT, aces=(Ace(OWNER, FULL), Ace(AGENT, RX)))
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(FakeBackend(nodes=nodes))
    assert "owned by the agent" in e.value.detail


def test_owner_that_is_an_agent_group_is_rejected():
    nodes = replace(good_nodes(), APPR, owner=USERS)
    with pytest.raises(errors.ApprovalBoundaryViolation):
        check(FakeBackend(nodes=nodes))


def test_untrusted_third_party_owner_is_rejected():
    nodes = replace(good_nodes(), APPR, owner="S-1-5-21-9-9-9-5000")
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(FakeBackend(nodes=nodes))
    assert "not a trusted owner" in e.value.detail


# --- 3: WRITE_DAC / WRITE_OWNER rejected ---------------------------------------


@pytest.mark.parametrize("right", [g.WRITE_DAC, g.WRITE_OWNER])
@pytest.mark.parametrize("path", [APPR, MAN, AGENT_ROOT, ROOT])
def test_agent_write_dac_or_write_owner_is_rejected_anywhere_on_the_chain(path, right):
    nodes = good_nodes()
    nodes[path] = NodeSecurity(**{**nodes[path].__dict__, "aces": nodes[path].aces + (Ace(AGENT, right),)})
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(FakeBackend(nodes=nodes))
    assert ("WRITE_DAC" if right == g.WRITE_DAC else "WRITE_OWNER") in e.value.detail


# --- 4: broad group / inherited write rejected --------------------------------


@pytest.mark.parametrize("group", [USERS, AUTH_USERS, EVERYONE, "S-1-5-4"])
def test_broad_group_write_even_when_inherited_is_rejected(group):
    nodes = replace(good_nodes(), APPR, aces=owner_aces() + (Ace(group, MODIFY, inherited=True),))
    with pytest.raises(errors.ApprovalBoundaryViolation):
        check(FakeBackend(nodes=nodes))


def test_users_fullcontrol_on_the_drive_root_is_rejected_as_ancestor_replacement():
    """The audited host's C:\\ grants BUILTIN\\Users FullControl (this folder).
    DELETE_CHILD there lets the agent rename/replace C:\\petcare-agent."""

    nodes = good_nodes()
    nodes[ROOT] = NodeSecurity(ROOT, TRUSTED_INSTALLER, (Ace(SYSTEM, FULL), Ace(ADMINS, FULL), Ace(USERS, FULL)), is_dir=True)
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(FakeBackend(nodes=nodes))
    assert "DELETE_CHILD" in e.value.detail and ROOT in e.value.detail


def test_modify_on_a_non_root_ancestor_is_rejected_because_modify_includes_delete():
    nodes = replace(good_nodes(), AGENT_ROOT, aces=owner_aces(agent_mask=MODIFY, inherited=False))
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(FakeBackend(nodes=nodes))
    assert "DELETE" in e.value.detail


def test_inherit_only_aces_do_not_apply_to_the_node_itself():
    nodes = replace(
        good_nodes(), AGENT_ROOT,
        aces=owner_aces(inherited=False) + (Ace(USERS, FULL, inherit_only=True),),
    )
    report, _ = check(FakeBackend(nodes=nodes))
    assert report.enforced


def test_a_deny_ace_is_never_relied_on_to_cancel_a_grant():
    nodes = replace(
        good_nodes(), APPR,
        aces=owner_aces(agent_mask=MODIFY) + (Ace(AGENT, g.FILE_WRITE_DATA, allow=False),),
    )
    with pytest.raises(errors.ApprovalBoundaryViolation):
        check(FakeBackend(nodes=nodes))


def test_a_deny_ace_alone_grants_nothing():
    nodes = replace(good_nodes(), APPR, aces=owner_aces() + (Ace(AGENT, FULL, allow=False),))
    report, _ = check(FakeBackend(nodes=nodes))
    assert report.enforced


def test_rights_held_only_by_an_unrelated_principal_are_fine():
    nodes = replace(good_nodes(), APPR, aces=owner_aces() + (Ace("S-1-5-21-9-9-9-7777", FULL),))
    report, _ = check(FakeBackend(nodes=nodes))
    assert report.enforced


# --- 5: reparse / junction escape rejected -------------------------------------


@pytest.mark.parametrize("path", [MAN, APPR, AGENT_ROOT, ROOT])
def test_reparse_point_anywhere_on_the_chain_is_rejected(path):
    nodes = replace(good_nodes(), path, is_reparse=True)
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(FakeBackend(nodes=nodes))
    assert "reparse" in e.value.detail


@pytest.mark.parametrize(
    "manifest,approvals",
    [
        ("D:\\elsewhere\\a2a.json", APPR),
        (APPR, APPR),
        ("C:\\petcare-agent\\approvals-evil\\a2a.json", APPR),
        ("\\\\server\\share\\approvals\\a.json", "\\\\server\\share\\approvals"),
        ("relative\\a.json", "relative"),
        ("\\\\?\\C:\\petcare-agent\\approvals\\a.json", APPR),
    ],
)
def test_paths_outside_or_non_local_are_rejected(manifest, approvals):
    with pytest.raises(errors.ApprovalBoundaryViolation):
        check(manifest=manifest, approvals=approvals)


def test_path_comparison_is_case_insensitive_on_windows():
    report, _ = check(manifest="c:\\PETCARE-AGENT\\Approvals\\a2a.json", approvals="C:\\petcare-agent\\approvals")
    assert report.enforced and report.nodes_checked == 4


def test_a_nested_manifest_checks_every_directory_down_from_the_approvals_dir():
    deep_dir = APPR + "\\2026"
    deep_man = deep_dir + "\\a.json"
    nodes = good_nodes()
    nodes[deep_dir] = NodeSecurity(deep_dir, OWNER, owner_aces(), is_dir=True)
    nodes[deep_man] = NodeSecurity(deep_man, OWNER, owner_aces())
    report, _ = check(FakeBackend(nodes=nodes), manifest=deep_man)
    assert report.nodes_checked == 5
    nodes[deep_dir] = NodeSecurity(deep_dir, OWNER, owner_aces(agent_mask=MODIFY), is_dir=True)
    with pytest.raises(errors.ApprovalBoundaryViolation):
        check(FakeBackend(nodes=nodes), manifest=deep_man)


# --- 6: unverifiable ACL rejected ----------------------------------------------


@pytest.mark.parametrize("path", [MAN, APPR, AGENT_ROOT, ROOT])
def test_unreadable_descriptor_is_unverifiable(path):
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        check(FakeBackend(unreadable={path}))


def test_missing_node_is_unverifiable():
    nodes = good_nodes()
    del nodes[AGENT_ROOT]
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        check(FakeBackend(nodes=nodes))


def test_null_dacl_is_unverifiable():
    nodes = replace(good_nodes(), APPR, dacl_present=False, aces=())
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        check(FakeBackend(nodes=nodes))


def test_unknown_owner_is_unverifiable():
    nodes = replace(good_nodes(), APPR, owner=None)
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        check(FakeBackend(nodes=nodes))


def test_unreadable_identity_is_unverifiable():
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        check(FakeBackend(identity=AclUnreadable("token")))


def test_no_trusted_owner_configured_is_unverifiable():
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        g.verify_boundary(FakeBackend(), BoundaryPolicy(), MAN, APPR)


def test_unsupported_platform_is_unverifiable():
    class Odd(FakeBackend):
        platform = "plan9"

    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        check(Odd())


def test_violation_outranks_unverifiable_and_both_are_untrusted_source_stops():
    nodes = replace(good_nodes(), APPR, aces=owner_aces(agent_mask=MODIFY))
    with pytest.raises(errors.ApprovalBoundaryViolation):
        check(FakeBackend(nodes=nodes, unreadable={ROOT}))
    assert issubclass(errors.ApprovalBoundaryViolation, errors.ApprovalUntrustedSource)
    assert issubclass(errors.ApprovalBoundaryUnverifiable, errors.ApprovalUntrustedSource)
    assert errors.ApprovalBoundaryViolation.reason_code == "APPROVAL_BOUNDARY_VIOLATION"
    assert errors.ApprovalBoundaryUnverifiable.reason_code == "APPROVAL_BOUNDARY_UNVERIFIABLE"


# --- 7: same identity rejected ---------------------------------------------------


def test_agent_is_the_owner_is_rejected():
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(FakeBackend(identity=agent_identity(user_sid=OWNER)))
    assert "not distinct" in e.value.detail


def test_agent_member_of_a_trusted_owner_group_is_rejected():
    pol = dataclasses.replace(POLICY, trusted_owner_sids=frozenset({"S-1-5-21-111-222-333-2000"}))
    ident = agent_identity(group_sids=agent_identity().group_sids | {"S-1-5-21-111-222-333-2000"})
    with pytest.raises(errors.ApprovalBoundaryViolation):
        g.verify_boundary(FakeBackend(identity=ident), pol, MAN, APPR)


@pytest.mark.parametrize("field,sid", [("group_sids", ADMINS), ("deny_only_group_sids", ADMINS), ("group_sids", SYSTEM)])
def test_administrator_or_system_capable_agent_is_rejected_even_when_deny_only(field, sid):
    ident = agent_identity(**{field: getattr(agent_identity(), field) | {sid}})
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(FakeBackend(identity=ident))
    assert "administrator" in e.value.detail


def test_the_audited_same_identity_hard_stop_scenario_is_rejected():
    """G1.6: orchestrator running as the Administrators-member owner account."""

    ident = Identity(OWNER, frozenset({EVERYONE, USERS, AUTH_USERS}), frozenset({ADMINS}), privileges=BENIGN, integrity_rid=0x2000)
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(FakeBackend(identity=ident))
    assert "not distinct" in e.value.detail and "administrator" in e.value.detail


def test_sids_in_messages_are_shortened():
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        check(FakeBackend(identity=agent_identity(user_sid=OWNER)))
    nodes = replace(good_nodes(), APPR, owner=AGENT)
    with pytest.raises(errors.ApprovalBoundaryViolation) as e2:
        check(FakeBackend(nodes=nodes))
    assert "111-222-333" not in e2.value.detail and "S-1-5-21-...-1008" in e2.value.detail
    assert g.short_sid("S-1-5-21-111-222-333-1008") == "S-1-5-21-...-1008"
    assert g.short_sid("S-1-5-18") == "S-1-5-18" and g.short_sid(None) == "<none>"


def test_policy_rejects_malformed_sids_and_uids():
    for bad in ("", "alice", "S-1-", "S-2-5-18", "S-1-5-18; drop"):
        with pytest.raises(ValueError):
            BoundaryPolicy(trusted_owner_sids=frozenset({bad}))
    with pytest.raises(ValueError):
        BoundaryPolicy(trusted_owner_uids=frozenset({-1}))


# --- POSIX model (mocked) ---------------------------------------------------------


class FakePosix:
    platform = "posix"

    def __init__(self, euid=1000, nodes=None):
        self.euid = euid
        self.nodes = nodes if nodes is not None else posix_good()

    def current_identity(self):
        return self.euid

    def read_node(self, path):
        if path not in self.nodes:
            raise AclUnreadable("missing")
        return self.nodes[path]


def posix_good():
    return {
        "/srv/owner/approvals/a.json": PosixNode("/srv/owner/approvals/a.json", 0, 0o100644),
        "/srv/owner/approvals": PosixNode("/srv/owner/approvals", 0, 0o40755, is_dir=True),
        "/srv/owner": PosixNode("/srv/owner", 0, 0o40755, is_dir=True),
        "/srv": PosixNode("/srv", 0, 0o40755, is_dir=True),
        "/": PosixNode("/", 0, 0o40755, is_dir=True),
    }


PPOL = BoundaryPolicy(trusted_owner_uids=frozenset({0}), expected_agent_uid=1000)
PMAN, PAPPR = "/srv/owner/approvals/a.json", "/srv/owner/approvals"


def pcheck(backend, policy=PPOL):
    return g.verify_boundary(backend, policy, PMAN, PAPPR)


def pcheck_args(backend, manifest, approvals, policy=PPOL):
    return g.verify_boundary(backend, policy, manifest, approvals)


def pmut(nodes, path, **kw):
    n = dict(nodes)
    n[path] = PosixNode(**{**n[path].__dict__, **kw})
    return n


def test_posix_correct_layout_accepted():
    assert pcheck(FakePosix()).enforced


@pytest.mark.parametrize("mode", [0o100666, 0o100664, 0o100602])
def test_posix_writable_manifest_rejected(mode):
    with pytest.raises(errors.ApprovalBoundaryViolation):
        pcheck(FakePosix(nodes=pmut(posix_good(), PMAN, mode=mode)))


def test_posix_agent_owned_approvals_rejected():
    with pytest.raises(errors.ApprovalBoundaryViolation):
        pcheck(FakePosix(nodes=pmut(posix_good(), PAPPR, uid=1000)))


def test_posix_symlink_rejected():
    with pytest.raises(errors.ApprovalBoundaryViolation):
        pcheck(FakePosix(nodes=pmut(posix_good(), "/srv/owner", is_symlink=True)))


def test_posix_group_writable_ancestor_rejected_unless_sticky():
    with pytest.raises(errors.ApprovalBoundaryViolation):
        pcheck(FakePosix(nodes=pmut(posix_good(), "/srv", mode=0o40777)))
    assert pcheck(FakePosix(nodes=pmut(posix_good(), "/srv", mode=0o41777))).enforced


def test_posix_root_agent_and_same_identity_rejected():
    with pytest.raises(errors.ApprovalBoundaryViolation):
        pcheck(FakePosix(euid=0))
    with pytest.raises(errors.ApprovalBoundaryViolation):
        pcheck(FakePosix(euid=1000), dataclasses.replace(PPOL, trusted_owner_uids=frozenset({0, 1000})))


def test_posix_untrusted_ancestor_owner_and_unreadable_and_no_trusted_uid():
    with pytest.raises(errors.ApprovalBoundaryViolation):
        pcheck(FakePosix(nodes=pmut(posix_good(), "/srv", uid=4242)))
    nodes = posix_good()
    del nodes["/srv"]
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        pcheck(FakePosix(nodes=nodes))
    with pytest.raises(errors.ApprovalBoundaryUnverifiable):
        pcheck(FakePosix(), BoundaryPolicy())


@pytest.mark.skipif(os.name == "nt", reason="POSIX-native check")
def test_posix_native_same_identity_is_refused(tmp_path):
    """Real stat on a tmp dir: the test process owns it, so it is not protected."""

    d = tmp_path / "approvals"
    d.mkdir()
    f = d / "a.json"
    f.write_text("{}")
    guard = ProductionApprovalGuard(BoundaryPolicy(trusted_owner_uids=frozenset({0}), expected_agent_uid=os.geteuid()))
    with pytest.raises(errors.ApprovalBoundaryViolation):
        guard.verify(f, d)


@pytest.mark.skipif(os.name == "nt", reason="POSIX-native check")
def test_posix_native_symlinked_manifest_is_refused(tmp_path):
    real = tmp_path / "real.json"
    real.write_text("{}")
    d = tmp_path / "approvals"
    d.mkdir()
    (d / "a.json").symlink_to(real)
    guard = ProductionApprovalGuard(BoundaryPolicy(trusted_owner_uids=frozenset({0}), expected_agent_uid=os.geteuid()))
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        guard.verify(d / "a.json", d)
    assert "symlink" in e.value.detail


# --- Windows-native (real ctypes backend; READ-ONLY) -----------------------------


@pytest.mark.skipif(os.name != "nt", reason="Windows-native check")
def test_windows_native_backend_reads_a_real_descriptor_and_identity(tmp_path):
    from scripts.orchestrator.acl_windows import WindowsSecurityBackend

    be = WindowsSecurityBackend()
    ident = be.current_identity()
    assert ident.user_sid.startswith("S-1-5-") and ident.group_sids
    node = be.read_node(str(tmp_path))
    assert node.is_dir and not node.is_reparse and node.dacl_present and node.owner
    assert node.aces and all(a.sid.startswith("S-1-") for a in node.aces)
    # Everyone group is in every token.
    assert "S-1-1-0" in ident.group_sids


@pytest.mark.skipif(os.name != "nt", reason="Windows-native check")
def test_windows_native_same_identity_tmp_tree_is_refused(tmp_path):
    from scripts.orchestrator.acl_windows import WindowsSecurityBackend

    d = tmp_path / "approvals"
    d.mkdir()
    f = d / "a.json"
    f.write_text("{}")
    be = WindowsSecurityBackend()
    me = be.current_identity().user_sid
    info = be.volume_info(str(d))
    binding = VolumeBinding(info.volume_guid, require_file_backed_virtual=False)
    guard = ProductionApprovalGuard(
        BoundaryPolicy(trusted_owner_sids=frozenset({me}), expected_agent_sid=me, trusted_volumes=(binding,))
    )
    with pytest.raises(errors.ApprovalBoundaryViolation) as e:
        guard.verify(f, d)
    assert "not distinct" in e.value.detail


@pytest.mark.skipif(os.name != "nt", reason="Windows-native check")
def test_windows_native_unreadable_path_is_unverifiable(tmp_path):
    from scripts.orchestrator.acl_windows import WindowsSecurityBackend

    with pytest.raises(AclUnreadable):
        WindowsSecurityBackend().read_node(str(tmp_path / "does-not-exist"))


@pytest.mark.skipif(os.name != "nt", reason="Windows-native check")
def test_windows_native_junction_is_flagged_as_reparse(tmp_path):
    import _winapi

    from scripts.orchestrator.acl_windows import WindowsSecurityBackend

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "junction"
    _winapi.CreateJunction(str(target), str(link))
    assert WindowsSecurityBackend().read_node(str(link)).is_reparse


# --- guard wiring: nothing external happens before the boundary is proven ------


class CountingObserver(FixtureGitHubObserver):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.calls = 0

    def get_pull_request(self, *a, **kw):
        self.calls += 1
        return super().get_pull_request(*a, **kw)


class SpyGuard:
    """Offline-only spy: records when the boundary check ran."""

    mode = "OFFLINE_MOCKED_DESCRIPTORS"
    offline_only = True

    def __init__(self, observer=None, fail=None):
        self.observer, self.fail, self.verified = observer, fail, 0
        self.calls_at_verify = None

    def verify(self, manifest_path, approvals_dir):
        self.verified += 1
        self.calls_at_verify = self.observer.calls if self.observer else None
        if self.fail:
            raise self.fail
        return g.BoundaryReport("OFFLINE_MOCKED_DESCRIPTORS", "nt", False, 4, "spy")

    def read_approved(self, manifest_path, approvals_dir):
        return None


def build_runner(config, manifest, guard, observer=None, transport=None):
    runner, t = s.make_runner(config, manifest, transport=transport, approval_guard=guard)
    if observer is not None:
        runner.observer = observer
    return runner, t


def load(config, write_manifest):
    return load_manifest(write_manifest(**s.pr_overrides()), config)


def test_boundary_is_proven_before_any_observer_or_provider_call(config, write_manifest):
    manifest = load(config, write_manifest)
    obs = CountingObserver(s.FIX)
    guard = SpyGuard(obs)
    runner, transport = build_runner(config, manifest, guard, obs)
    with pytest.raises(errors.MilestoneOwnerStop):
        runner.run(s.make_request())
    assert guard.verified == 1 and guard.calls_at_verify == 0
    assert obs.calls > 0 and transport.calls == 1
    assert runner.boundary_report.mode == "OFFLINE_MOCKED_DESCRIPTORS"
    assert runner.summary()["approval_boundary"]["enforced"] is False


@pytest.mark.parametrize("exc", [errors.ApprovalBoundaryViolation("x"), errors.ApprovalBoundaryUnverifiable("x")])
def test_failed_boundary_means_no_external_operation_and_no_run_state(config, write_manifest, exc):
    manifest = load(config, write_manifest)
    obs = CountingObserver(s.FIX)
    runner, transport = build_runner(config, manifest, SpyGuard(obs, fail=exc), obs)
    with pytest.raises(type(exc)):
        runner.run(s.make_request())
    assert obs.calls == 0 and transport.calls == 0
    assert not runner.store.exists() and not (config.runtime_dir / "a2a.lock").exists()
    assert not (config.runtime_dir / "a2a_state.json").exists()
    assert "approval_boundary_refused" in config.log_path.read_text(encoding="utf-8")


def mock_chain_runner(config, write_manifest, backend):
    """A runner whose manifest/approvals paths sit on the MOCKED C:\\ chain."""

    import dataclasses

    manifest = dataclasses.replace(load(config, write_manifest), source_path=Path(MAN))
    cfg = dataclasses.replace(config, approvals_dir=Path(APPR))
    obs = CountingObserver(s.FIX)
    guard = MockedDescriptorApprovalGuard(POLICY, backend)
    runner, transport = build_runner(cfg, manifest, guard, obs)
    return runner, transport, obs


def test_runner_with_a_failing_real_guard_and_mock_descriptors_does_no_external_operation(config, write_manifest):
    nodes = replace(good_nodes(), APPR, aces=owner_aces(agent_mask=MODIFY))
    runner, transport, obs = mock_chain_runner(config, write_manifest, FakeBackend(nodes=nodes))
    with pytest.raises(errors.ApprovalBoundaryViolation):
        runner.run(s.make_request())
    assert obs.calls == 0 and transport.calls == 0 and not runner.store.exists()


def test_runner_with_the_mocked_guard_and_a_protected_mock_chain_proceeds_to_the_owner_gate(config, write_manifest):
    runner, transport, obs = mock_chain_runner(config, write_manifest, FakeBackend())
    with pytest.raises(errors.MilestoneOwnerStop):
        runner.run(s.make_request())
    assert obs.calls > 0 and transport.calls == 1
    # Mocked descriptors are never reported as an enforced boundary.
    assert runner.summary()["approval_boundary"]["enforced"] is False
    assert runner.summary()["approval_boundary"]["mode"] == "OFFLINE_MOCKED_DESCRIPTORS"


def test_runner_with_the_real_guard_stops_on_the_audited_host_root_acl(config, write_manifest):
    nodes = good_nodes()
    nodes[ROOT] = NodeSecurity(ROOT, TRUSTED_INSTALLER, (Ace(SYSTEM, FULL), Ace(ADMINS, FULL), Ace(USERS, FULL), Ace(AUTH_USERS, MODIFY)), is_dir=True)
    runner, transport, obs = mock_chain_runner(config, write_manifest, FakeBackend(nodes=nodes))
    with pytest.raises(errors.ApprovalBoundaryViolation):
        runner.run(s.make_request())
    assert obs.calls == 0 and transport.calls == 0


def test_runner_requires_an_approval_guard_keyword(config, write_manifest):
    manifest = load(config, write_manifest)
    reviewer = OpenAIEvidenceReviewer(s.DeterministicMockTransport(), s.default_reviewer_config())
    with pytest.raises(TypeError):
        EvidenceReviewRunner(  # type: ignore[call-arg]
            config=config, manifest=manifest, observer=FixtureGitHubObserver(s.FIX),
            reviewer=reviewer, baseline_ids=s.baseline_ids(),
        )
    for bad in (None, object(), "ENFORCED"):
        with pytest.raises(TypeError):
            EvidenceReviewRunner(
                config=config, manifest=manifest, observer=FixtureGitHubObserver(s.FIX),
                reviewer=reviewer, baseline_ids=s.baseline_ids(), approval_guard=bad,  # type: ignore[arg-type]
            )


def test_offline_fixture_guard_is_unenforced_and_reported_as_such(config, write_manifest):
    manifest = load(config, write_manifest)
    runner, _ = s.make_runner(config, manifest)
    with pytest.raises(errors.MilestoneOwnerStop):
        runner.run(s.make_request())
    summary = runner.summary()
    assert summary["approval_boundary"] == {
        "mode": "OFFLINE_FIXTURE_UNENFORCED", "platform": "n/a", "enforced": False,
        "nodes_checked": 0, "agent": "n/a", "volume": "", "pinned": False,
    }
    assert OfflineFixtureApprovalGuard.offline_only is True


def test_offline_fixture_guard_is_refused_with_a_non_fixture_observer(config, write_manifest):
    manifest = load(config, write_manifest)

    class NotAFixture:
        calls = 0

        def get_pull_request(self, *a, **k):
            NotAFixture.calls += 1
            raise AssertionError("must not be reached")

    runner, transport = s.make_runner(config, manifest)
    runner.observer = NotAFixture()
    with pytest.raises(errors.ApprovalBoundaryViolation):
        runner.run(s.make_request())
    assert NotAFixture.calls == 0 and transport.calls == 0 and not runner.store.exists()


def test_offline_fixture_guard_is_refused_with_a_non_mock_transport(config, write_manifest):
    manifest = load(config, write_manifest)

    class LiveLooking:
        calls = 0

        def send(self, request, *, timeout_s):
            LiveLooking.calls += 1
            raise AssertionError("must not be reached")

    live = LiveLooking()
    runner, _ = s.make_runner(config, manifest, transport=live)
    assert runner.reviewer.is_offline_mock is False
    with pytest.raises(errors.ApprovalBoundaryViolation):
        runner.run(s.make_request())
    assert LiveLooking.calls == 0 and not runner.store.exists()


def test_mock_transports_declare_themselves_offline():
    from scripts.orchestrator.adapters.openai_evidence_reviewer import DeterministicMockTransport, ScriptedTransport

    cfg = ReviewerConfig(model="m", price_in_per_mtok=1.0, price_out_per_mtok=1.0)
    assert OpenAIEvidenceReviewer(DeterministicMockTransport(), cfg).is_offline_mock
    assert OpenAIEvidenceReviewer(ScriptedTransport([]), cfg).is_offline_mock


def test_a1_owner_source_permission_check_is_unchanged(config, write_manifest):
    manifest = load(config, write_manifest)
    assert isinstance(manifest.assert_owner_source_permissions(enforce=False), list)


# --- CLI ---------------------------------------------------------------------------


def _cli(runtime_dir, approvals_dir, path, *extra):
    return [
        "--runtime-dir", str(runtime_dir), "--approvals-dir", str(approvals_dir),
        "a2a-review", "--manifest", str(path), "--fixture-dir", str(s.FIX),
        "--baseline-ids", str(s.FIX / "baseline_failed_ids.txt"),
        "--pr-number", str(s.PR), "--expected-head-sha", s.HEAD, *extra,
    ]


def test_cli_requires_an_explicit_guard_choice(write_manifest, runtime_dir, approvals_dir, capsys):
    path = write_manifest(**s.pr_overrides())
    assert cli.main(_cli(runtime_dir, approvals_dir, path)) == 2
    assert "APPROVAL_BOUNDARY_UNVERIFIABLE" in capsys.readouterr().err


def test_cli_offline_flag_cannot_be_combined_with_trusted_owner_flags(write_manifest, runtime_dir, approvals_dir, capsys):
    path = write_manifest(**s.pr_overrides())
    args = _cli(runtime_dir, approvals_dir, path, "--offline-fixtures", "--trusted-owner-sid", OWNER)
    assert cli.main(args) == 2
    assert "APPROVAL_BOUNDARY_VIOLATION" in capsys.readouterr().err


def test_cli_rejects_a_malformed_trusted_sid(write_manifest, runtime_dir, approvals_dir, capsys):
    path = write_manifest(**s.pr_overrides())
    assert cli.main(_cli(runtime_dir, approvals_dir, path, "--trusted-owner-sid", "not-a-sid")) == 2
    assert "APPROVAL_BOUNDARY_UNVERIFIABLE" in capsys.readouterr().err


def test_cli_enforced_mode_refuses_a_tmp_tree_owned_by_the_test_identity(write_manifest, runtime_dir, approvals_dir, capsys):
    """Real OS read: a pytest tmp tree is owned by the running identity, so the
    enforced guard must refuse (Windows and POSIX alike)."""

    path = write_manifest(**s.pr_overrides())
    flag = ("--trusted-owner-sid", g.SID_SYSTEM) if os.name == "nt" else ("--trusted-owner-uid", "0")
    assert cli.main(_cli(runtime_dir, approvals_dir, path, *flag)) == 2
    err = capsys.readouterr().err
    assert "APPROVAL_BOUNDARY_VIOLATION" in err or "APPROVAL_BOUNDARY_UNVERIFIABLE" in err
    assert not (runtime_dir / "a2a_checkpoint.json").exists()


# --- static safety of the new modules --------------------------------------------


GUARD_ALLOWED = {"__future__", "hashlib", "ntpath", "os", "posixpath", "re", "stat", "dataclasses", "typing"}
WIN_ALLOWED = {"__future__", "ctypes", "os", "stat", "struct"}
FORBIDDEN_ROOTS = {
    "socket", "ssl", "subprocess", "urllib", "http", "requests", "httpx", "aiohttp", "asyncio",
    "multiprocessing", "ftplib", "smtplib", "webbrowser", "openai", "boto3", "botocore", "win32api",
    "win32security", "win32net", "pywintypes",
}


def _roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_acl_guard_imports_are_a_tiny_stdlib_allowlist_without_ctypes():
    roots = _roots(PKG / "acl_guard.py")
    assert roots <= GUARD_ALLOWED, roots - GUARD_ALLOWED
    assert not roots & (FORBIDDEN_ROOTS | {"ctypes"})


def test_acl_windows_imports_only_ctypes_and_stdlib_basics():
    roots = _roots(PKG / "acl_windows.py")
    assert not roots & FORBIDDEN_ROOTS
    assert roots - {"scripts"} <= WIN_ALLOWED, roots - WIN_ALLOWED


WRITE_OR_AUTH_TOKENS = [
    "SetNamedSecurityInfo", "SetSecurityInfo", "SetEntriesInAcl", "SetSecurityDescriptor",
    "SetKernelObjectSecurity", "LogonUser", "CreateProcess", "ShellExecute", "WinExec",
    "AdjustTokenPrivileges", "ImpersonateLoggedOnUser", "ImpersonateSelf", "SetThreadToken",
    "DuplicateToken", "CreateProcessWithLogon", "CreateProcessAsUser", "LsaLogon", "NetUser",
    "SetFileSecurity", "icacls", "takeown", "net user", "runas", "os.system",
    "os.popen", "os.environ", "getenv", "password", "Password",
]


@pytest.mark.parametrize("name", ["acl_guard.py", "acl_windows.py"])
def test_new_modules_contain_no_write_auth_process_or_credential_surface(name):
    text = (PKG / name).read_text(encoding="utf-8")
    for token in WRITE_OR_AUTH_TOKENS:
        assert token not in text, f"{name} contains {token!r}"
    for token in ("socket.", "urlopen", "Authorization:", "Bearer ", "api_key"):
        assert token not in text


def test_acl_windows_only_calls_the_expected_read_apis():
    text = (PKG / "acl_windows.py").read_text(encoding="utf-8")
    called = set()
    import re as _re

    for m in _re.finditer(r"_(?:advapi32|kernel32)\.(\w+)", text):
        called.add(m.group(1))
    assert called <= {
        "GetNamedSecurityInfoW", "GetSecurityInfo", "OpenProcessToken", "GetTokenInformation",
        "LookupPrivilegeNameW", "GetCurrentProcess", "CloseHandle", "LocalFree",
        "CreateFileW", "ReadFile", "SetFilePointerEx", "GetFinalPathNameByHandleW", "GetFileInformationByHandle",
        "QueryDosDeviceW", "GetVolumePathNameW", "GetVolumeNameForVolumeMountPointW", "GetDriveTypeW",
        "GetVolumeInformationW", "DeviceIoControl",
    }, called
    # Read-only by construction: never a write/delete share or access right, and the
    # only IOCTL is the read-only storage property query.
    for token in ("GENERIC_WRITE", "GENERIC_ALL", "FILE_SHARE_DELETE", "WriteFile", "DeleteFile", "MoveFile",
                  "SetFileInformationByHandle", "FSCTL_"):
        assert token not in text, token
    assert text.count("_kernel32.DeviceIoControl(") == 1
    assert "_kernel32.DeviceIoControl(h, _IOCTL_STORAGE_QUERY_PROPERTY," in text
    assert "_IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400" in text


def test_acl_guard_defines_no_write_style_functions():
    forbidden = ("set_", "chmod", "chown", "grant", "rotate", "login", "logon", "impersonate", "merge", "deploy")
    for name in ("acl_guard.py", "acl_windows.py"):
        for node in ast.walk(ast.parse((PKG / name).read_text(encoding="utf-8"))):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                assert not node.name.lower().startswith(forbidden), node.name


def test_summary_json_still_serializes_with_the_boundary_block(config, write_manifest):
    manifest = load(config, write_manifest)
    runner, _ = s.make_runner(config, manifest)
    with pytest.raises(errors.MilestoneOwnerStop):
        runner.run(s.make_request())
    json.dumps(runner.summary())
