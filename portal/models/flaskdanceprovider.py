from abc import ABCMeta, abstractmethod
from flask import current_app


class FlaskDanceProvider:
    """base class for flask dance providers

    When a new provider is added to the protal's consumer oauth flow
    a descendent of this class needs to be created to get the user's
    information from the provider after a successful auth
    """
    __metaclass__ = ABCMeta

    def __init__(self, blueprint, token):
        self.blueprint = blueprint
        self.token = token

    @property
    def name(self):
        return self.blueprint.name

    @abstractmethod
    def get_user_info(self):
        """gets user info from the provider

        This function must be overriden in descendant classes
        to return an instance of FlaskProviderUserInfo that is
        filled with user information fetched from the provider
        """
        pass


class FacebookFlaskDanceProvider(FlaskDanceProvider):
    """fetches user info from Facebook after successfull auth

    After the user successfully authenticates with Facebook
    this class fetches the user's info from Facebook and packages
    it in FlaskDanceProviderUserInfo
    """

    def get_user_info(self):
        """gets user info from Facebook

        After the user successfully authenticates with Facebook
        control enters this function which gets the user's info from
        Facebook and returns an instance of FlaskDanceProviderUserInfo
        """
        resp = self.blueprint.session.get(
            '/me',
            params={
                'fields':
                    'id,email,birthday,first_name,last_name,gender,picture'
            }
        )

        if not resp.ok:
            current_app.logger.debug('Failed to fetch user info from Facebook')
            return False

        facebook_info = resp.json()

        user_info = FlaskProviderUserInfo()
        user_info.id = facebook_info['id']
        user_info.first_name = facebook_info['first_name']
        user_info.last_name = facebook_info['last_name']
        user_info.email = facebook_info['email']
        user_info.gender = facebook_info['gender']
        user_info.image_url = facebook_info['picture']['data']['url']
        user_info.birthdate = facebook_info['birthday']

        return user_info


class GoogleFlaskDanceProvider(FlaskDanceProvider):
    """fetches user info from Google after successfull auth

    After the user successfully authenticates with Google
    this class fetches the user's info from Google and packages it
    in FlaskDanceProviderUserInfo
    """

    def get_user_info(self):
        """gets user info from Google

        After the user successfully authenticates with Google
        control enters this function which gets the user's info
        from Google and returns an instance of FlaskDanceProviderUserInfo
        """
        resp = self.blueprint.session.get('/oauth2/v2/userinfo')
        if not resp.ok:
            current_app.logger.debug('Failed to fetch user info from Google')
            return False

        google_info = resp.json()

        user_info = FlaskProviderUserInfo()
        user_info.id = google_info['id']
        user_info.first_name = google_info['given_name']
        user_info.last_name = google_info['family_name']
        user_info.email = google_info['email']
        user_info.image_url = google_info['picture']

        # Gender may not be available
        if 'gender' in google_info:
            user_info.gender = google_info['gender']

        # Birthday may not be available
        if 'birthday' in google_info:
            user_info.birthdate = google_info['birthday']

        return user_info


class MockFlaskDanceProvider(FlaskDanceProvider):
    """creates user info from test data to validate auth logic

    This class should only be used during testing.
    It simply returns the data passed into its constructor in
    get_user_info. This effectively mocks out the get_user_info
    request that's normally sent to a provider after successful oauth
    in non-test environments.
    """

    def __init__(self, provider_name, token, user_info, fail_to_get_user_info):
        blueprint = type(str('MockBlueprint'), (object,), {})
        blueprint.name = provider_name
        super(MockFlaskDanceProvider, self).__init__(
            blueprint,
            token
        )

        self.user_info = user_info
        self.fail_to_get_user_info = fail_to_get_user_info

    def get_user_info(self):
        """return the user info passed into the constructor

        This effectively mocks out the get_user_info
        request that's normally sent to a provider after successful oauth
        in non-test environments.
        """
        if self.fail_to_get_user_info:
            current_app.logger.debug(
                'MockFlaskDanceProvider failed to get user info'
            )
            return False

        return self.user_info


class FlaskProviderUserInfo(object):
    """a common format for user info fetched from providers

    Each provider packages user info a litle differently.
    Google, for example, uses "given_name" and the key for the user's
    first name, and Facebook uses "first_name". To make it easier for
    our code to parse responses in a common function this class provides a
    common format to store the results from each provider.
    """

    def __init__(self):
        self.id = None
        self.first_name = None
        self.last_name = None
        self.email = None
        self.birthdate = None
        self.gender = None
        self.image_url = None
