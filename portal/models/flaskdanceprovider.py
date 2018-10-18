from abc import ABCMeta, abstractmethod

from flask import current_app


class FlaskDanceProvider:
    """base class for flask dance providers

    When a new provider is added to the protal's consumer oauth flow
    a descendent of this class needs to be created to get the user's
    information from the provider after a successful auth
    """
    __metaclass__ = ABCMeta

    def __init__(self, blueprint, token, standard_key_to_provider_key_map):
        """constructor

        :param blueprint: The provider blueprint
        :param token: The user's access token
        :param standard_key_to_provider_key_map: Each provider uses
            different keys to encode user values. This maps
            our standard keys, such as 'first_name' to provider keys,
            such as 'given_name' in Google's case
        """
        self.blueprint = blueprint
        self.token = token
        self.standard_key_to_provider_key_map = \
            standard_key_to_provider_key_map

    @property
    def name(self):
        return self.blueprint.name

    def get_user_info(self):
        """gets user info from the provider

        This function parses json returned from the provider
        and returns an instance of FlaskProviderUserInfo that is
        filled with the user's information

        :return FlaskProviderUserInfo with the user's info
        """

        # Ask the provider for details about the user
        resp = self.send_get_user_json_request()

        if not resp.ok:
            current_app.logger.error(
                'Failed to fetch user info from {}'.format(self.blueprint.name)
            )
            return None

        # Parse the json into a standard format
        user_json = resp.json()
        return self.parse_json(user_json)

    def parse_json(self, user_json):
        """parses the user's json and returns it in a standard format

        Providers encode user information in json. This function parses
        the json and stores values in an instance of FlaskProviderUserInfo

        :param user_json: info about the user encoded in json

        :return instance of FlaskProviderUserInfo with the user's info
        """

        def get_value_from_json(standard_key, required=True):
            """gets a value from the provider json

            Each provider returns json with different property values.
            For example, Facebook returns json that maps a user's first name to
            'first_name' while Google maps first names to 'given_name'.
            In addition, a value could be nested. For example, Facebook's
            profile picture is nested in json['picture']['data']['url'].
            self.standard_key_to_provider_key_map links standard keys to
            provider specific keys, including those that are nested, which
            allows our parsing code to stay as generic as possible.

            :param standard:key: the standard key
            :param required: is this property required?
            :return value from the user's json or None
            """

            # Get the key used by the provider
            user_json_key = \
                self.standard_key_to_provider_key_map[standard_key]

            # The key could have multiple nested parts
            # e.g. 'picture.data.url'
            # Which means we'll need to get each part
            # individually
            key_parts = user_json_key.split('.')

            try:
                # Loop over each key's part to get the value
                # from the user's json
                value = user_json
                for key_part in key_parts:
                    # Certain properties can be undefined
                    # Handle these cases gracefully
                    if not required and key_part not in value:
                        return None

                    value = value[key_part]

                return value
            except KeyError as err:
                current_app.logger.error(
                    'Unable to parse {} from user json. Error {}'.format(
                        user_json_key,
                        err,
                    )
                )
                raise err

        # Attempt to parse the user's json
        try:
            user_info = FlaskProviderUserInfo()
            user_info.id = get_value_from_json('id')
            user_info.first_name = get_value_from_json('first_name')
            user_info.last_name = get_value_from_json('last_name')
            user_info.email = get_value_from_json('email')
            user_info.image_url = get_value_from_json('image_url')

            # These properties may not be defined
            user_info.gender = get_value_from_json(
                'gender',
                required=False
            )
            user_info.birthdate = get_value_from_json(
                'birthdate',
                required=False
            )

            return user_info
        except Exception as err:
            current_app.logger.error(
                'Unable to parse user json for provider {}. Error {}'.format(
                    self.blueprint.name,
                    err
                )
            )
            return None

    @abstractmethod
    def send_get_user_json_request(self):
        """sends a request to the provider to get user json

        This function must be overriden in descendant classes
        to return a response with the user's json
        """
        pass


class FacebookFlaskDanceProvider(FlaskDanceProvider):
    """fetches user info from Facebook after successfull auth

    After the user successfully authenticates with Facebook
    this class fetches the user's info from Facebook
    """

    def __init__(self, blueprint, token):
        super(FacebookFlaskDanceProvider, self).__init__(
            blueprint,
            token,
            {
                'id': 'id',
                'first_name': 'first_name',
                'last_name': 'last_name',
                'email': 'email',
                'image_url': 'picture.data.url',
                'gender': 'gender',
                'birthdate': 'birthday',
            }
        )

    def send_get_user_json_request(self):
        """sends a GET request to Facebook for user data

        This function is used to get user information from
        Facebook that is encoded in json.

        :return Response
        """
        return self.blueprint.session.get(
            '/me',
            params={
                'fields':
                    'id,email,birthday,first_name,last_name,gender,picture'
            }
        )


class GoogleFlaskDanceProvider(FlaskDanceProvider):
    """fetches user info from Google after successfull auth

    After the user successfully authenticates with Google
    this class fetches the user's info from Google
    """

    def __init__(self, blueprint, token):
        super(GoogleFlaskDanceProvider, self).__init__(
            blueprint,
            token,
            {
                'id': 'id',
                'first_name': 'given_name',
                'last_name': 'family_name',
                'email': 'email',
                'image_url': 'picture',
                'gender': 'gender',
                'birthdate': 'birthday',
            }
        )

    def send_get_user_json_request(self):
        """sends a GET request to Google for user data

        This function is used to get user information from
        Google that is encoded in json.

        :return Response
        """
        return self.blueprint.session.get('/oauth2/v2/userinfo')


class MockFlaskDanceProvider(FlaskDanceProvider):
    """creates user info from test data to validate auth logic

    This class should only be used during testing.
    It simply mocks user json that is normally retrieved from
    a provider which allows us to granularly test auth logic
    """

    def __init__(self, provider_name, token, user_json, fail_to_get_user_json):
        blueprint = type(str('MockBlueprint'), (object,), {})
        blueprint.name = provider_name
        super(MockFlaskDanceProvider, self).__init__(
            blueprint,
            token,
            {
                'id': 'provider_id',
                'first_name': 'first_name',
                'last_name': 'last_name',
                'email': 'email',
                'image_url': 'picture.data.url',
                'gender': 'gender',
                'birthdate': 'birthdate',
            }
        )

        self.user_json = user_json
        self.fail_to_get_user_json = fail_to_get_user_json

        # Facebook embeds image urls in json.picture.data.url
        # Mimicing that behavior here so we can validate that
        # parsing it works properly
        if 'image_url' in self.user_json:
            url = self.user_json['image_url']
            self.user_json['picture'] = {'data': {'url': url}}

    def send_get_user_json_request(self):
        """return a mock request based on test data passed into the constructor

        Normally a request is sent to a provider and user json is returned.
        This function mocks out that request by returning a response
        with the user json passed through the test backdoor
        """

        if self.fail_to_get_user_json:
            current_app.logger.debug(
                'MockFlaskDanceProvider failed to get user info'
            )
            return MockJsonResponse(False, None)

        return MockJsonResponse(True, self.user_json)


class MockJsonResponse:
    """mocks a GET json response

    During auth we send a request to providers that returns
    user json. During tests we need to mock out providers
    so we can test our auth logic. This class is used to mock out
    requests that are normally sent to providers.
    """
    def __init__(self, ok, user_json):
        self.ok = ok
        self.user_json = user_json

    def json(self):
        """returns mock json"""
        return self.user_json


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
