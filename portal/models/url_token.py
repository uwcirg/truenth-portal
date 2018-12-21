""" URL Tokens encrypt a user_id and timestamp

Typically used in unsafe formats such as email.  Should be coupled
with an identity check to verify holder is the intended target.

NB - sometimes referred to as `access_tokens` these tokens have
nothing to do with the OAuth access_token column in the tokens
table.

"""
from itsdangerous import BadSignature, SignatureExpired

from ..extensions import user_manager


def url_token(user_id):
    """Generate and return a token encrypting the given user_id

    Encrypts the user_id and the current time in a token safe to
    include in a URL string.

    :param user_id: the user_id (or any integer) to encrypt in a
      URL friendly base64 string
    :returns the token

    """
    return user_manager.token_manager.generate_token(user_id)


def verify_token(token, valid_seconds):
    """Confirm given token is well formed and no older than valid_seconds

    :param token: URL token to check
    :param valid_seconds: number of seconds since token generation defining
      the valid period.
    :return: user_id baked into the token
    :raises SignatureExpired if the token is older than valid_seconds
    :raises BadSignature if the token can't be parsed or validated

    """
    is_valid, has_expired, user_id = (
        user_manager.token_manager.verify_token(token, valid_seconds))
    if has_expired:
        raise SignatureExpired("Expired token {}".format(token))
    if not is_valid:
        raise BadSignature("Invalid token {}".format(token))
    return user_id
