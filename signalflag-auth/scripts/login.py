"""Log in to SignalFlag (device code flow). The SDK reuses the cached token after this."""
import sys

NOTICE = ("SignalFlag login: a URL will print below. Open it in a browser and approve; "
          "this finishes by itself. The token is cached in ~/.signalflag/token.json.")


def main(make_client=None) -> int:
    print(NOTICE, flush=True)
    if make_client is None:
        try:
            from signalflag.sdk.auth import DeviceCodeClient
        except ImportError:
            print("signalflag is not installed in this Python. Run login.py with the venv's "
                  "python: <venv>/bin/python login.py", file=sys.stderr)
            return 3
        make_client = DeviceCodeClient
    make_client()
    print("Logged in.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
