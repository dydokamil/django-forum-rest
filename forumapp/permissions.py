import datetime
from rest_framework import permissions

from forumapp.models import ForumUser


class IsNotBanned(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        forum_user = ForumUser.objects.get(user=request.user)

        return forum_user.banned_until.replace(
            tzinfo=None
        ) <= datetime.datetime.now()


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner of the snippet.
        return obj.creator == request.user


class CanPinThreads(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.has_perm('forumapp.can_pin_threads')
