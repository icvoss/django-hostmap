# Multi-host in ten minutes

This tutorial takes you from an empty Django project to a working two-host
project: a `www` site and an `api` site sharing one codebase, one database,
and one `manage.py`. You will install django-hostmap, declare the host map,
wire up the middleware, prove that `reverse()` behaves differently depending
on which host you are reversing from, add a redirect entry, and inspect the
resolved map with `manage.py hostmap`.

Follow the steps in order. Each one ends with a checkpoint so you know it
worked before moving on.

## What you will build

A single Django project with:

- A `www` host serving a home page and a blog.
- An `api` host serving a small JSON-free "user detail" view.
- An `apex` entry that redirects the bare domain to `www`.
- Proof that same-host links stay relative and cross-host links come back
  absolute, with zero changes to the views or templates involved.

You will run everything on `*.localhost`, which modern browsers and `curl`
resolve to loopback without any `/etc/hosts` editing (RFC 6761).

## Prerequisites

- Python 3.12 or newer.
- Comfort with Django projects, settings, and `manage.py`.
- No database preference: the default SQLite is fine for this tutorial.

## Step 1: Create the project and install hostmap

```bash
mkdir courts && cd courts
python -m venv .venv
source .venv/bin/activate
pip install django django-hostmap
django-admin startproject config .
```

**Checkpoint:** `pip show django-hostmap` prints the installed version, and
`ls` shows `manage.py` and `config/`.

## Step 2: Register the app and the middleware

Open `config/settings.py`. Add `hostmap` to `INSTALLED_APPS`, and add
`HostmapMiddleware` near the top of `MIDDLEWARE`, before `CommonMiddleware`
(its `APPEND_SLASH` handling resolves against the request's URLconf, so it
must run after hostmap has set it).

```python
# config/settings.py
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "hostmap",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "hostmap.middleware.HostmapMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

**Checkpoint:** `python manage.py check` still runs clean. `HOSTMAP` is unset
(defaults to `{}`), so hostmap is a transparent pass-through and there is
nothing to warn about yet.

## Step 3: Write two small URLconfs

Create `config/urls_www.py` for the `www` host:

```python
# config/urls_www.py
from django.http import HttpResponse
from django.urls import path


def home(request):
    return HttpResponse("www home")


def blog_index(request):
    return HttpResponse("blog")


urlpatterns = [
    path("", home, name="home"),
    path("blog/", blog_index, name="blog-index"),
]
```

Create `config/urls_api.py` for the `api` host:

```python
# config/urls_api.py
from django.http import HttpResponse
from django.urls import path


def user_detail(request, pk):
    return HttpResponse(f"user {pk}")


urlpatterns = [
    path("users/<int:pk>/", user_detail, name="user-detail"),
]
```

Note there is no `name` collision to worry about and no `host=` argument
anywhere: each URLconf is a completely ordinary Django URLconf.

**Checkpoint:** both files import without error:
`python -c "import config.urls_www, config.urls_api"`.

## Step 4: Declare the host map

Add the map to the bottom of `config/settings.py`. This is the one piece of
declarative configuration that replaces per-call-site host arguments.

```python
# config/settings.py

HOSTMAP = {
    "www": {"subdomain": "www", "urlconf": "config.urls_www"},
    "api": {"subdomain": "api", "urlconf": "config.urls_api"},
    "apex": {"host": "courts.localhost", "redirect_to": "www"},
}
HOSTMAP_PARENT_DOMAIN = "localhost"
HOSTMAP_DEFAULT = "www"
HOSTMAP_SCHEME = "http"
HOSTMAP_PORT = "8000"

ROOT_URLCONF = "config.urls_www"  # matches the default entry
ALLOWED_HOSTS = [".localhost"]
```

`ROOT_URLCONF` still has to point somewhere: Django needs it at startup, and
hostmap expects it to match the default entry's URLconf (`hostmap.W003` warns
if it does not). `HOSTMAP_SCHEME` and `HOSTMAP_PORT` are development-only
overrides; production uses the `https` and no-port defaults.

**Checkpoint:** `python manage.py check` passes with no errors. If you
mistype an entry (say, both `host` and `subdomain` on the same entry) you
will see a `hostmap.E00x` error naming exactly what is wrong.

## Step 5: Run the server and hit both hosts

```bash
python manage.py runserver
```

In another terminal:

```bash
curl http://www.courts.localhost:8000/
curl http://api.courts.localhost:8000/users/7/
```

**Checkpoint:** the first prints `www home`, the second prints `user 7`. Two
hosts, one process, one `runserver` invocation, no `/etc/hosts` edits.

## Step 6: Prove reversing is host-aware

Open a shell:

```bash
python manage.py shell
```

Reverse a same-host name and a cross-host name from the `www` URLconf's
perspective (the default, and therefore active outside a request):

```python
from django.urls import reverse

reverse("blog-index")
# -> '/blog/'                              (byte-identical to stock Django)

reverse("user-detail", args=[7])
# -> 'http://api.courts.localhost:8000/users/7/'   (cross-host, absolute)
```

Nothing here imports anything from `hostmap`. This is stock
`django.urls.reverse`, unmodified at the call site, behaving differently
depending on whether the name resolves on the active host or on another one.
See
[how host-aware reversing works](../explanation/how-host-aware-reversing-works.md)
for why this is safe even inside third-party apps.

**Checkpoint:** you saw a relative path for `blog-index` and an absolute URL
for `user-detail`.

### Confirm same-host stays relative even for a name that also exists elsewhere

If you add a `name="home"` view on the `api` host too, `reverse("home")` from
`www` still returns the `www` path: the active host is always tried first, so
a name declared on both hosts resolves to the active host's version. See
[resolution order](../explanation/resolution-order.md) for the exact rule.

## Step 7: Add a redirect entry

The `apex` entry above already answers `courts.localhost` (no subdomain) with
a redirect to `www`. Try it:

```bash
curl -i http://courts.localhost:8000/blog/
```

**Checkpoint:** you get a `301` (the default; see
`HOSTMAP_REDIRECT_PERMANENT`) with `Location:
http://www.courts.localhost:8000/blog/`. The path and query string are
preserved; only the host changes.

## Step 8: Inspect the resolved map

```bash
python manage.py hostmap
```

**Checkpoint:** you should see something close to:

```
Parent domain: localhost
Default entry: www
Scheme: http   Port: 8000

www *default*
    host:     www.localhost
    urlconf:  config.urls_www
api
    host:     api.localhost
    urlconf:  config.urls_api
apex
    host:     courts.localhost
    redirect: -> www
```

This is the single place to confirm what hostmap thinks your map resolves to,
useful when a host behaves unexpectedly in production.

## You did it

You now have a working multi-host Django project:

- Two hosts (`www`, `api`) served from one codebase.
- An `apex` redirect entry preserving path and query string.
- Proof that `reverse()`, unmodified, returns a relative path for same-host
  names and an absolute URL for cross-host names.
- A diagnostic command to inspect the resolved map.

## Where to go next

Now that the basics work, layer in the production concerns:

- [Route a subdomain to its own URLconf](../how-to/route-a-subdomain-to-its-own-urlconf.md)
  for the full range of entry options, including a full `host` instead of a
  `subdomain`.
- [Link across hosts in templates and Python](../how-to/link-across-hosts-in-templates-and-python.md)
  for `{% url %}` behaviour and the `NoReverseMatch` / silent-failure
  contract.
- [Reverse out of a request](../how-to/reverse-out-of-a-request.md) using
  `use_host()` for emails, Celery tasks, and webhooks.
- [Use wildcard subdomains](../how-to/use-wildcard-subdomains.md) for
  per-tenant subdomains.
- [Run behind a proxy](../how-to/run-behind-a-proxy.md) before you deploy:
  misrouted hosts behind nginx are the most common support issue.

For the complete settings and API surface, see the
[settings reference](../reference/settings.md) and the
[API reference](../reference/api.md).
