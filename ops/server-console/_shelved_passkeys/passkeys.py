"""Passkeys (WebAuthn): fingerprint / face unlock for the console.

A device is enrolled once from a signed-in session; afterwards it signs a
server challenge behind the phone's biometric prompt. Credentials live in S3
(server-console/passkeys/<credential id>.json). They are revoked by flag,
never deleted, so the console role needs no s3:DeleteObject.
"""
import datetime as dt
import json
import re
import secrets

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

import cloud

RP = cloud.CONFIG["passkeys"]
PREFIX = "passkeys"
CRED_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,512}$")


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _name(cred_id_b64):
    return f"{PREFIX}/{cred_id_b64}.json"


def all_credentials():
    return [c for c in cloud.list_json(PREFIX + "/") if not c.get("revoked")]


def registration_options(device_name):
    """Returns (options_json, challenge_bytes)."""
    opts = generate_registration_options(
        rp_id=RP["rp_id"],
        rp_name=RP["rp_name"],
        user_id=secrets.token_bytes(16),
        user_name=device_name,
        user_display_name=device_name,
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c["id"]))
                             for c in all_credentials()],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        timeout=120000,
    )
    return options_to_json(opts), opts.challenge


def register(credential, challenge, device_name):
    verified = verify_registration_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=RP["rp_id"],
        expected_origin=RP["origins"],
        require_user_verification=True,
    )
    cred_id = bytes_to_base64url(verified.credential_id)
    record = {
        "id": cred_id,
        "name": device_name,
        "public_key": bytes_to_base64url(verified.credential_public_key),
        "sign_count": verified.sign_count,
        "created": _now(),
        "last_used": None,
    }
    cloud.write_json(_name(cred_id), record)
    return record


def authentication_options():
    """Discoverable-credential login: the phone offers whichever console passkey it holds."""
    opts = generate_authentication_options(
        rp_id=RP["rp_id"],
        user_verification=UserVerificationRequirement.REQUIRED,
        timeout=120000,
    )
    return options_to_json(opts), opts.challenge


def authenticate(credential, challenge):
    """Returns the device record on success, None for an unknown or revoked passkey."""
    raw_id = json.loads(credential)["rawId"] if isinstance(credential, str) else credential["rawId"]
    if not CRED_ID_RE.match(str(raw_id)):
        return None
    record = cloud.read_json(_name(raw_id), None)
    if not record or record.get("revoked"):
        return None
    verified = verify_authentication_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=RP["rp_id"],
        expected_origin=RP["origins"],
        credential_public_key=base64url_to_bytes(record["public_key"]),
        credential_current_sign_count=record["sign_count"],
        require_user_verification=True,
    )
    record.update(sign_count=verified.new_sign_count, last_used=_now())
    cloud.write_json(_name(raw_id), record)
    return record


def revoke(cred_id):
    if not CRED_ID_RE.match(str(cred_id)):
        return False
    record = cloud.read_json(_name(cred_id), None)
    if not record:
        return False
    record.update(revoked=True, revoked_at=_now())
    cloud.write_json(_name(cred_id), record)
    return True
