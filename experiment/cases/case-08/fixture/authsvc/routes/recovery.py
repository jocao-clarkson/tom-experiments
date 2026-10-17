from fastapi import APIRouter, Depends, Request

from ..audit import AuditLog
from ..principal import Principal, current_principal
from ..security.hashing import hash_secret
from ..security.tokens import recovery_code

router = APIRouter()


@router.post("/me/recovery-codes", status_code=201)
def regenerate_recovery_codes(request: Request, principal: Principal = Depends(current_principal)):
    """Replace the user's recovery codes. Plaintext codes are returned once."""
    db = request.app.state.db
    codes = [recovery_code() for _ in range(10)]
    with db.transaction() as conn:
        conn.execute("DELETE FROM recovery_codes WHERE user_id = %s", (principal.subject,))
        for c in codes:
            conn.execute(
                "INSERT INTO recovery_codes (user_id, code_hash) VALUES (%s, %s)",
                (principal.subject, hash_secret(c)),
            )
        AuditLog(conn).record(
            actor=principal.subject,
            action="recovery_codes.regenerated",
            org_id=principal.org_id,
            target=principal.subject,
            metadata={"count": len(codes)},
        )
    return {"codes": codes}
