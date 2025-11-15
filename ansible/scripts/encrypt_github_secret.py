#!/usr/bin/env python3
import argparse
import base64
from nacl import encoding, public


def encrypt(public_key_b64: str, value: str) -> str:
    pk = public.PublicKey(public_key_b64, encoding.Base64Encoder())
    sealed = public.SealedBox(pk).encrypt(value.encode("utf-8"))
    return base64.b64encode(sealed).decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="Encrypt a GitHub secret value using repository public key")
    parser.add_argument("--public-key", required=True, help="Repository public key (base64)")
    parser.add_argument("--value", required=True, help="Plaintext secret value")
    args = parser.parse_args()

    print(encrypt(args.public_key, args.value))


if __name__ == "__main__":
    main()
