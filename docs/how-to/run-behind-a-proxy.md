# Run behind a proxy

## Goal

Deploy hostmap behind nginx (or any reverse proxy) so the Host header
Django sees is the one your users actually requested, not the proxy's own
internal hostname.

This is the single most common support issue with host-based routing of any
kind: everything works in `runserver` and breaks, silently misrouting every
request to the default entry, the moment a proxy sits in front of Django.

## Prerequisites

- A reverse proxy (nginx, Caddy, an load balancer) in front of Django.
- `HOSTMAP` configured and working under `runserver` or a direct WSGI/ASGI
  server, without a proxy.

## Steps

### 1. Understand the failure mode first

Host routing is only as good as the Host header that reaches Django.
`HostmapMiddleware` matches on `request.get_host()`, and
`request.get_host()` reads the `Host` header (or `X-Forwarded-Host`, if
configured; see step 3), never anything else. If the proxy rewrites or drops
that header before forwarding the request, every request looks like it came
in on whatever host the proxy used internally, usually the default entry or
an unmatched host.

### 2. Confirm the proxy passes the original Host header through unchanged

For nginx, this means the `proxy_pass` block explicitly forwards `Host`:

```nginx
location / {
    proxy_pass http://django_upstream;
    proxy_set_header Host $host;
}
```

Without `proxy_set_header Host $host;`, nginx defaults to forwarding the
value from `proxy_pass`'s own upstream definition in some configurations,
which is not what you want.

### 3. Or use `X-Forwarded-Host` with `USE_X_FORWARDED_HOST`

If your proxy sets `X-Forwarded-Host` instead of passing `Host` through
directly (common with some load balancers and CDNs), tell Django to trust it:

```python
# settings.py
USE_X_FORWARDED_HOST = True
```

`request.get_host()` then reads `X-Forwarded-Host` when present. Only enable
this if you have verified the proxy is the sole entry point and it always
sets this header itself; otherwise a client could forge it directly.

### 4. Confirm `ALLOWED_HOSTS` matches what the proxy forwards, not the upstream address

`ALLOWED_HOSTS` validates the same header hostmap routes on. If the proxy
forwards `www.example.com` but `ALLOWED_HOSTS` only lists an internal upstream
name, Django rejects the request with a 400 before hostmap ever runs.

### 5. Decide what happens to a host past `ALLOWED_HOSTS` but absent from the map

An allowed-but-unmapped host is served by the default entry under
`HOSTMAP_UNMATCHED = "default"` (the default setting). This is deliberate:
it means a typo'd or unexpected but otherwise valid host still gets a
response rather than a hard failure. For strict deployments where an
unmapped host should be rejected outright, set:

```python
HOSTMAP_UNMATCHED = "reject"
```

This raises `Http404` for any host that matches no entry at all.

## Verify it worked

From outside the proxy:

```bash
curl -H "Host: api.example.com" https://your-proxy/users/7/
```

Then confirm on the Django side (logging, or a temporary debug view) that
`request.get_host()` actually returns `api.example.com`, not the proxy's own
hostname. `manage.py hostmap` confirms what hostmap expects to see; it does
not confirm what the proxy is actually sending, so check both.

## Common pitfalls

- **Everything works locally, breaks in production.** This is almost always
  the proxy not forwarding the original Host header. Check
  `proxy_set_header Host $host;` (nginx) or the equivalent for your proxy
  first, before suspecting anything in hostmap itself.
- **Setting `USE_X_FORWARDED_HOST = True` without a proxy that actually sets
  the header, or without the proxy being the only entry point.** A client
  that can reach Django directly, bypassing the proxy, could then forge the
  header and control routing.
- **`ALLOWED_HOSTS` listing the proxy's internal address instead of the
  public hostname.** These are often different, and Django checks
  `ALLOWED_HOSTS` against whichever value `get_host()` resolves to.

## Related

- [Settings reference](../reference/settings.md): `HOSTMAP_UNMATCHED` and the
  `hostmap.W001` check for `ALLOWED_HOSTS` coverage.
- [Troubleshooting](../troubleshooting.md): the full symptom-first table,
  including this one.
