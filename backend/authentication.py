from django.contrib.auth.models import User
from backend.models import Profile


def create_profile(backend, user, *args, **kwargs):
    """
    Create a profile for the user.
    """
    Profile.objects.get_or_create(user=user)

class EmailAuthBackend(object):
    """
    Authenticate using e-mail
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(email=username)
            if user.check_password(password):
                return user
            return None
        except User.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None