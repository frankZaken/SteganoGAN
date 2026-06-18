import threading, time
from httpio.endpoint import HTTPEndpoint
from httpio.request  import HTTPRequest
from httpio.response import HTTPResponse
from security.secure_http import SecureHTTPServer, SecureHTTPClient
from security.asymmetric.rsa import rsa_keys, distant_random_primes

priv, pub = rsa_keys(distant_random_primes(2048))     # fresh matched pair

def echo(req):
    return HTTPResponse(status=200, message="OK", body=b"echo:" + req.body)

srv = SecureHTTPServer([HTTPEndpoint("/echo", "POST", echo)], server_private=priv)
threading.Thread(target=srv.serve_forever, args=(("127.0.0.1", 8771),), daemon=True).start()
time.sleep(0.5)

cli = SecureHTTPClient(("127.0.0.1", 8771), server_public=pub)
resp = cli.open(HTTPRequest(method="POST", uri="/echo", body=b"hi"))
print("RESULT:", resp.status, resp.body)