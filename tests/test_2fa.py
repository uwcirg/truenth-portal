import time
from portal.models.user import User, generate_random_secret


def test_2fa_tokens():
    """random failure, verify a large number all work

    Random failures seen in production, see TN-3097.
    Potential fix in place.  NB this would NEVER fail
    reliably despite large loop values.  Give the sleep
    a value greater than 1 sec and bump range to increase chances,
    but still unpredictable.
    """
    user = User()
    msg = "PASSED"
    for i in range(10):
        user.otp_secret = generate_random_secret()  # force new
        code = user.generate_otp()
        time.sleep(0.01)
        if not user.validate_otp(code):
            msg = f"FAILED {user.otp_secret}:{code}"
            break
    assert msg == "PASSED"


def test_expired_2FA():
    user = User()
    user.otp_secret = generate_random_secret()
    clock = int(time.time()) - user.TOTP_TOKEN_LIFE
    code = user.generate_otp(clock=clock)

    # since token life has passed, should fail
    assert not user.validate_otp(code)

    # give window to expand time
    assert user.validate_otp(code, window=1)
