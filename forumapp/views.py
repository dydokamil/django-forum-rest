import datetime

from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.http import HttpResponseRedirect, \
    HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse

from forumapp.forms import ThreadCreateModelForm, ThreadResponseModelForm, \
    ThreadResponseDeleteForm, ThreadDeleteForm, LikeDislikeForm
from .models import Thread, ForumSection, ThreadResponse, Forum, LikeDislike, \
    ForumUser


def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(
                username=username,
                password=raw_password
            )
            ForumUser(user=user).save()
            login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(
        request,
        'registration/signup.html',
        {'form': form}
    )


def index(request):
    users_count = User.objects.count()
    threads_count = Thread.objects.count()

    responses_count = ThreadResponse.objects.exclude(
        thread__isnull=True
    ).count()

    responses_count -= threads_count

    return render(
        request,
        'forumapp/index.html',
        context={
            'users_count': users_count,
            'threads_count': threads_count,
            'responses_count': responses_count
        }
    )


def forums(request):
    sections = ForumSection.objects.all()
    return render(
        request,
        'forumapp/forums.html',
        context={
            'sections': sections,
        }
    )


def forum(request, pk):
    thread_list = Thread.objects.filter(forum=pk)
    thread_paginator = Paginator(
        thread_list,
        2
    )
    page = request.GET.get('page')
    thread_list = thread_paginator.get_page(page)

    return render(
        request,
        'forumapp/thread_list.html',
        context={
            'thread_list': thread_list,
            'forum': Forum.objects.get(id=pk)
        }
    )


def thread_view(request, fpk, tpk):
    thread = Thread.objects.get(id=tpk)
    parent_forum = Forum.objects.get(id=fpk)
    response_list = ThreadResponse.objects.filter(
        thread=tpk,
        thread__forum=fpk
    ).order_by(
        'created_datetime'
    )
    can_delete_thread = response_list[0].responder == request.user or \
                        request.user.has_perm("forumapp.can_remove_any_thread")

    response_paginator = Paginator(
        response_list,
        10
    )

    page = request.GET.get('page')
    response_list = response_paginator.get_page(page)

    return render(
        request,
        'forumapp/thread.html',
        context={
            'thread': thread,
            'response_list': response_list,
            'forum': parent_forum,
            'can_delete_thread': can_delete_thread,
            # 'like_dislike_forms': like_dislike_forms
        }
    )


@permission_required('forumapp.can_ban_users')
def ban_user(request, pk, datetime_until):
    pass


@login_required
def like_dislike_post(request, fpk, tpk, ppk, upvote):
    """
    This view is responsible for liking/disliking a response
    :param request request
    :param fpk: forum primary key
    :param tpk: thread primary key
    :param ppk: post primary key
    :param upvote: 0 or 1 - like or dislike
    """
    if request.method == "POST":
        form = LikeDislikeForm(request.POST)
        if form.is_valid():
            like_dislike_obj = LikeDislike.objects.get_or_create(
                response=ThreadResponse.objects.get(id=ppk),
                user=request.user
            )[0]
            like_dislike_obj.like = upvote
            like_dislike_obj.save()
            return HttpResponseRedirect(
                reverse(
                    'thread-view',
                    kwargs={
                        'fpk': fpk,
                        'tpk': tpk
                    }
                )
            )
    else:
        return HttpResponseForbidden()


@login_required
def respond(request, fpk, tpk):
    forum_user = ForumUser.objects.get(user=request.user)
    if forum_user.banned_until.replace(tzinfo=None) > datetime.datetime.now():
        return HttpResponseForbidden("You are banned! "
                                     "Check your profile for details.")

    if request.method == "POST":
        form = ThreadResponseModelForm(
            request.POST,
        )
        if form.is_valid():
            obj_response = form.save()

            obj_response.responder = request.user
            obj_response.created_datetime = datetime.datetime.now()
            obj_response.thread = Thread.objects.get(id=tpk)
            obj_response.order_in_thread = \
                obj_response.thread.threadresponse_set.count() + 1

            obj_response.save()

            return HttpResponseRedirect(
                reverse(
                    'thread-view',
                    kwargs={
                        'fpk': fpk,
                        'tpk': tpk
                    }
                )
            )
    else:
        form = ThreadResponseModelForm()
    return render(
        request,
        'forumapp/threadresponse_form.html',
        context={
            'form': form,
            'forum': Forum.objects.get(id=fpk),
            'thread': Thread.objects.get(id=tpk)
        }
    )


@login_required
def delete_thread(request, fpk, tpk):
    if request.method == "POST":
        form = ThreadDeleteForm(request.POST)
        if form.is_valid():
            thread = Thread.objects.get(id=tpk)

            creator = thread.threadresponse_set \
                .order_by('created_datetime') \
                .first() \
                .responder
            if creator == request.user or request.user.has_perm(
                    'forumapp.can_delete_any_thread'
            ):
                thread.delete()
            else:
                return HttpResponseForbidden(
                    "You are not allowed to remove this thread."
                )
            return HttpResponseRedirect(
                reverse('forum', kwargs={'pk': fpk})
            )
    else:
        form = ThreadDeleteForm()
        return render(
            request,
            'forumapp/thread_delete.html',
            context={
                'form': form
            }
        )


def enumerate_posts(thread_pk):
    responses = Thread.objects.get(
        id=thread_pk
    ).threadresponse_set.all().order_by(
        'created_datetime'
    )

    for i, response in enumerate(responses):
        response.order_in_thread = i + 1
        response.save()


@login_required
def delete_post(request, fpk, tpk, ppk):
    """
    :param request:
    :param fpk: forum primary key
    :param tpk: thread primary key
    :param ppk: post primary key
    """
    form = ThreadResponseDeleteForm()
    if request.method == "POST":
        form = ThreadResponseDeleteForm(request.POST)
        if form.is_valid():
            response = ThreadResponse.objects.get(id=ppk)
            first_thread_response = ThreadResponse.objects.filter(
                thread=response.thread
            ).order_by('created_datetime')[0]

            if first_thread_response == response:
                return HttpResponseForbidden(
                    "Can't delete the first response!"
                )

            if request.user == response.responder or \
                    request.user.has_perm('forumapp.can_remove_any_response'):
                response.delete()
            else:
                return HttpResponseForbidden(
                    "You are not allowed to delete this post.")

            enumerate_posts(tpk)

            return HttpResponseRedirect(
                reverse(
                    'thread-view',
                    kwargs={
                        'fpk': fpk,
                        'tpk': tpk
                    }
                )
            )

    return render(
        request,
        'forumapp/response_delete.html',
        context={
            'form': form
        }
    )


@login_required
def edit_post(request, fpk, tpk, ppk):
    if request.method == "POST":
        thread_response = ThreadResponse.objects.get(id=ppk)
        if request.user == thread_response.responder:
            form = ThreadResponseModelForm(request.POST)
            if form.is_valid():
                thread_response.message = form.cleaned_data['message']
                thread_response.edited = True
                thread_response.save()
                return HttpResponseRedirect(
                    reverse(
                        'thread-view',
                        kwargs={
                            'fpk': fpk,
                            'tpk': tpk
                        }
                    )
                )
        else:
            return HttpResponseForbidden(
                "You are not allowed to remove this post."
            )

    else:
        thread_response = ThreadResponse.objects.get(id=ppk)
        form = ThreadResponseModelForm(instance=thread_response)
        return render(
            request,
            'forumapp/threadresponse_form.html',
            context={
                'form': form,
                'thread': Thread.objects.get(id=tpk),
                'forum': Forum.objects.get(id=fpk)
            }
        )


def user_view(request, pk):
    user = User.objects.get(id=pk)
    user_responses = ThreadResponse.objects.filter(
        responder=pk
    ).exclude(thread__isnull=True)

    banned_until = None
    forum_user = ForumUser.objects.get(user=user)
    if forum_user.banned_until.replace(tzinfo=None) > datetime.datetime.now():
        banned_until = forum_user.banned_until

    return render(
        request,
        'forumapp/user_view.html',
        context={
            'user': user,
            'user_responses': user_responses,
            'banned_until': banned_until
        }
    )


@login_required
def new_thread(request, pk):
    forum_user = ForumUser.objects.get(user=request.user)
    if forum_user.banned_until.replace(tzinfo=None) > datetime.datetime.now():
        return HttpResponseForbidden("You are banned! "
                                     "Check your profile for details.")

    if request.method == "POST":
        form_thread = ThreadCreateModelForm(
            request.POST,
            prefix='form_thread'
        )
        if form_thread.is_valid():
            thread_obj = form_thread.save()
            form_response = ThreadResponseModelForm(
                request.POST,
                prefix='form_response',
            )

            if form_response.is_valid():
                obj_response = form_response.save()

                obj_response.thread = thread_obj
                obj_response.responder = request.user
                obj_response.created_datetime = datetime.datetime.now()

                obj_response.save()

                return HttpResponseRedirect(
                    reverse(
                        'thread-view',
                        kwargs={
                            'fpk': thread_obj.forum.id,
                            'tpk': thread_obj.id
                        }
                    )
                )
            else:  # response not valid
                thread_obj.delete()
    else:
        form_thread = ThreadCreateModelForm(prefix='form_thread')
        form_response = ThreadResponseModelForm(prefix='form_response')
        form_thread.initial['forum'] = pk
        return render(
            request,
            'forumapp/thread_form.html',
            context={
                'form_thread': form_thread,
                'form_response': form_response,
                'forum': pk
            }
        )
