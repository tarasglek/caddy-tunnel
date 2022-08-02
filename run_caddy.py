#!/usr/bin/env python3
import sys
import random
import string
import os
import subprocess
# ./run_caddy.py summit.glek.net proxmox=https://192.168.3.1:8006

print(sys.argv)
domain_suffix = sys.argv[1]

N=256
random_string = ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(N))

caddyfile = f"""
{{
    https_port 4443
    http_port 8880
}}

(basic-auth) {{
  basicauth / {{
      {os.environ['CADDY_BASICAUTH']}
  }}
}}


# a snippet to check if a cookie token is set. if not, store the current page as the referer and redirect to auth site
(proxy-auth) {{
  # if cookie not = some-token-nonsense
  @no-auth {{
    not header_regexp mycookie Cookie myid={random_string}
    # https://github.com/caddyserver/caddy/issues/3916
  }}
   
  # store current time, page and redirect to auth
  route @no-auth {{
    header Set-Cookie "myreferer={{scheme}}://{{host}}{{uri}}; Domain=summit.glek.net; Path=/; Max-Age=30; HttpOnly; SameSite=Strict; Secure"
    redir https://auth.summit.glek.net
  }}
}}


# a pseudo site that only requires basic auth, sets cookie, and redirects back to original site
auth.summit.glek.net {{
  route / {{
    # require authentication
    import basic-auth
 
    # upon successful auth, set a client token
    header Set-Cookie "myid={random_string}; Domain=summit.glek.net; Path=/; Max-Age=3600; HttpOnly; SameSite=Strict; Secure"
     
    #delete the referer cookie
    header +Set-Cookie "myreferer=null; Domain=summit.glek.net; Path=/; Expires=Thu, 25 Sep 1971 12:00:00 GMT; HttpOnly; SameSite=Strict; Secure"
     
    # redirect back to the original site
    redir {{http.request.cookie.myreferer}}
  }}
 
  # fallback
  respond "Hi."
}}
"""

for arg in sys.argv[2:]:
    [domain, backend] = arg.split('=')
    extra = ''
    if backend[:8].lower() == "https://":
        extra = f"""
            {{
                transport http {{
                    tls
                    tls_insecure_skip_verify
                    read_buffer 8192
                }}
            }}
        """
    config = f"""
        {domain}.{domain_suffix} {{
            import proxy-auth
            reverse_proxy {backend} {extra.strip()}
}}"""
    caddyfile += config.strip() + "\n"

with open("Caddyfile", "w") as f:
    f.write(caddyfile)
subprocess.call(["/usr/bin/caddy", "run"])
