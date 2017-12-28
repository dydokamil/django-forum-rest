from django.urls import path

from forumapp import views

urlpatterns = [
    path(
        '',
        views.index,
        name='index'
    ),
    path(
        'forums',
        views.forums,
        name='forums'
    ),
    path(
        'forum/<int:pk>',
        views.forum,
        name='forum'
    ),
    path(
        'user/<int:pk>',
        views.user_view,
        name='user-view'
    ),
    path(
        'forum/<int:pk>/new-thread',
        views.new_thread,
        name='new-thread'
    ),
    path(
        'forum/<int:fpk>/thread/<int:tpk>',
        views.thread_view,
        # views.ThreadResponseListView.as_view(),
        name='thread-view'
    ),
    path(
        'forum/<int:fpk>/thread/<int:tpk>/respond',
        views.respond,
        name='respond-thread'
    ),
    path(
        'forum/<int:fpk>/thread/<int:tpk>/delete',
        views.delete_thread,
        name='thread-delete'
    ),
    path(
        'forum/<int:fpk>/thread/<int:tpk>/post/<int:ppk>/edit',
        views.edit_post,
        name='edit-post'
    ),
    path(
        'forum/<int:fpk>/thread/<int:tpk>/post/<int:ppk>/delete',
        views.delete_post,
        name='delete-post'
    ),
]
