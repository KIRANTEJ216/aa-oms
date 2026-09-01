def test_import():
    from app.core.security import hash_password, verify_password
    h = hash_password("password123")
    assert verify_password("password123", h)
    assert not verify_password("wrong", h)

def test_tenant_ctx():
    from app.core.tenant import tenant_ctx
    token = tenant_ctx.set("aarav-advisors")
    assert tenant_ctx.get() == "aarav-advisors"
    tenant_ctx.reset(token)
