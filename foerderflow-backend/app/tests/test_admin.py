"""Super-admin + org invites + setup parity tests."""

from __future__ import annotations

from app.models.auth import OrganizationMembership, User


# ── organisations ───────────────────────────────────────────────────────────
def test_org_crud(client, org):
    r = client.get("/api/admin/organisations")
    assert r.status_code == 200
    # the test org from the fixture
    assert any(o["id"] == org.id for o in r.json()["data"])

    r = client.post(
        "/api/admin/organisations",
        json={"name": "Neue Org", "rechtsform": "GGMBH", "regelarbeitszeit_stunden": 40},
    )
    assert r.status_code == 201, r.text
    new_id = r.json()["data"]["id"]

    r = client.get(f"/api/admin/organisations/{new_id}")
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "Neue Org"
    assert r.json()["data"]["members"] == []

    r = client.put(f"/api/admin/organisations/{new_id}", json={"name": "Geändert"})
    assert r.status_code == 200 and r.json()["data"]["name"] == "Geändert"

    # delete empty org
    r = client.delete(f"/api/admin/organisations/{new_id}")
    assert r.status_code == 200 and r.json()["message"] == "Organisation gelöscht."


def test_org_validation(client):
    r = client.post("/api/admin/organisations", json={"name": "X", "rechtsform": "GGMBH"})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_NAME"
    r = client.post("/api/admin/organisations", json={"name": "Gültig", "rechtsform": "BOGUS"})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_RECHTSFORM"


def test_org_delete_blocked_with_dependents(client, org, db_session, super_user):
    # add a membership -> blocks delete
    db_session.add(OrganizationMembership(org_id=org.id, user_id=super_user.id, role="ADMIN"))
    db_session.commit()
    r = client.delete(f"/api/admin/organisations/{org.id}")
    assert r.status_code == 409 and r.json()["code"] == "HAS_DEPENDENTS"


# ── members ─────────────────────────────────────────────────────────────────
def test_member_add_role_remove(client, org, db_session):
    # create a target user
    u = User(email="member@test.de", name="Member")
    db_session.add(u)
    db_session.commit()

    r = client.post(
        f"/api/admin/organisations/{org.id}/members",
        json={"email": "member@test.de", "role": "FINANCE"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["role"] == "FINANCE"

    # duplicate
    r = client.post(
        f"/api/admin/organisations/{org.id}/members",
        json={"email": "member@test.de", "role": "FINANCE"},
    )
    assert r.status_code == 409 and r.json()["code"] == "ALREADY_MEMBER"

    # unknown user
    r = client.post(
        f"/api/admin/organisations/{org.id}/members",
        json={"email": "ghost@test.de", "role": "FINANCE"},
    )
    assert r.status_code == 404 and r.json()["code"] == "USER_NOT_FOUND"

    # change role
    r = client.put(
        f"/api/admin/organisations/{org.id}/members/{u.id}", json={"role": "READONLY"}
    )
    assert r.status_code == 200 and r.json()["data"]["role"] == "READONLY"

    # remove
    r = client.request("DELETE", f"/api/admin/organisations/{org.id}/members/{u.id}")
    assert r.status_code == 200


def test_last_admin_guard(client, org, db_session):
    u = User(email="onlyadmin@test.de", name="Only Admin")
    db_session.add(u)
    db_session.commit()
    db_session.add(OrganizationMembership(org_id=org.id, user_id=u.id, role="ADMIN"))
    db_session.commit()
    # demote last admin -> LAST_ADMIN
    r = client.put(
        f"/api/admin/organisations/{org.id}/members/{u.id}", json={"role": "FINANCE"}
    )
    assert r.status_code == 409 and r.json()["code"] == "LAST_ADMIN"
    # force override works
    r = client.put(
        f"/api/admin/organisations/{org.id}/members/{u.id}?force=true", json={"role": "FINANCE"}
    )
    assert r.status_code == 200


# ── invites ─────────────────────────────────────────────────────────────────
def test_admin_invite(client, org):
    r = client.post(
        f"/api/admin/organisations/{org.id}/invite",
        json={"email": "invitee@test.de", "role": "FINANCE"},
    )
    assert r.status_code == 201, r.text
    invite_id = r.json()["data"]["id"]
    assert r.json()["data"]["email"] == "invitee@test.de"

    # revoke
    r = client.delete(f"/api/admin/organisations/{org.id}/invites/{invite_id}")
    assert r.status_code == 200 and r.json()["message"] == "Einladung widerrufen."


def test_admin_invite_bad_email(client, org):
    r = client.post(
        f"/api/admin/organisations/{org.id}/invite", json={"email": "notanemail", "role": "FINANCE"}
    )
    assert r.status_code == 400 and r.json()["code"] == "INVALID_EMAIL"


# ── users ───────────────────────────────────────────────────────────────────
def test_user_list_get_update(client, super_user):
    r = client.get("/api/admin/users")
    assert r.status_code == 200
    assert any(u["id"] == super_user.id for u in r.json()["data"])

    r = client.get(f"/api/admin/users/{super_user.id}")
    assert r.status_code == 200 and r.json()["data"]["is_super_admin"] is True

    # cannot self-revoke super-admin
    r = client.put(f"/api/admin/users/{super_user.id}", json={"is_super_admin": False})
    assert r.status_code == 409 and r.json()["code"] == "SELF_REVOKE_FORBIDDEN"


# ── org-admin invite (protected) ─────────────────────────────────────────────
def test_org_invite_protected(client, org):
    r = client.post("/api/protected/org/invite", json={"email": "team@test.de", "role": "FINANCE"})
    assert r.status_code == 201, r.text
    assert len(client.get("/api/protected/org/invite").json()["data"]) == 1


# ── setup ────────────────────────────────────────────────────────────────────
def test_setup_organisation(client):
    r = client.post(
        "/api/setup/organisation",
        json={"name": "Self Org", "rechtsform": "EV", "regelarbeitszeit_stunden": 39},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["name"] == "Self Org"
