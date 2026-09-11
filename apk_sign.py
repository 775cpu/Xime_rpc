#!/usr/bin/env python3
"""Sign APK files with a NIST256p PEM key or a secret exponent."""

import argparse
import datetime
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

try:
    import ecdsa
except ImportError:  # pragma: no cover - installed explicitly for deterministic ECDSA
    ecdsa = None

KEY_ALIAS = "apk_signer"
KEY_PASSWORD = "123456"
DEFAULT_PEM_PATH = Path.home() / ".ssh" / "NIST256p.pem"


def private_key_from_pem(pem_path: Path) -> ec.EllipticCurvePrivateKey:
    if not pem_path.is_file():
        raise FileNotFoundError(f"找不到 APK 签名私钥: {pem_path}")
    try:
        private_key = serialization.load_ssh_private_key(
            pem_path.read_bytes(), password=None
        )
    except ValueError:
        private_key = serialization.load_pem_private_key(
            pem_path.read_bytes(), password=None
        )
    if not isinstance(private_key, ec.EllipticCurvePrivateKey):
        raise ValueError("APK 签名私钥必须是 ECDSA 私钥")
    if not isinstance(private_key.curve, ec.SECP256R1):
        raise ValueError("APK 签名仅支持 NIST256p (secp256r1)")
    return private_key


def private_key_from_secexp(secexp: int) -> ec.EllipticCurvePrivateKey:
    curve = ec.SECP256R1()
    if not 1 <= secexp < 2**curve.key_size:
        raise ValueError(f"secexp 必须是 1 到 {2**curve.key_size - 1} 之间的整数")
    return ec.derive_private_key(secexp, curve)


def deterministic_ecdsa_sign_digest(
    private_key: ec.EllipticCurvePrivateKey, digest: bytes
) -> bytes:
    """使用 RFC6979 确定性 ECDSA 签名，确保相同 key+digest 必定得到相同签名。"""
    if ecdsa is None:
        raise RuntimeError(
            "缺少 ecdsa 依赖，无法进行确定性 ECDSA 签名。请执行: python3 -m pip install ecdsa"
        )
    if not isinstance(private_key.curve, ec.SECP256R1):
        raise ValueError("仅支持 secp256r1 / NIST256p 的确定性签名")

    private_value = private_key.private_numbers().private_value
    signing_key = ecdsa.SigningKey.from_secret_exponent(
        private_value, curve=ecdsa.NIST256p
    )
    return signing_key.sign_digest_deterministic(
        digest,
        hashfunc=hashlib.sha256,
        sigencode=ecdsa.util.sigencode_der,
    )


def deterministic_ecdsa_sign(private_key: ec.EllipticCurvePrivateKey, message: bytes) -> bytes:
    return deterministic_ecdsa_sign_digest(private_key, hashlib.sha256(message).digest())


def make_keystore(private_key: ec.EllipticCurvePrivateKey, output_dir: Path) -> dict:
    public_key_der = private_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    serial_number = int(hashlib.sha256(public_key_der).hexdigest(), 16) % (2**63 - 1)
    serial_number = serial_number or 1
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SELF"),
        x509.NameAttribute(NameOID.COMMON_NAME, "APK_SIGNER"),
    ])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(serial_number)
        .not_valid_before(datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc))
        .not_valid_after(datetime.datetime(2099, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc))
        .sign(private_key, hashes.SHA256())
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    key_path = output_dir / "apk_sign_key_NIST256p.pk8"
    cert_path = output_dir / "apk_sign_cert_NIST256p.der"

    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.DER))

    return {
        "key_path": str(key_path),
        "cert_path": str(cert_path),
    }


def find_apksigner(sdk_path: str | None = None) -> Path:
    sdk = sdk_path or os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk:
        raise FileNotFoundError(
            "未找到 Android SDK 路径，请先通过 build.sh 设置 ANDROID_HOME。"
        )
    build_tools_dir = Path(sdk) / "build-tools"
    candidates = []
    if build_tools_dir.is_dir():
        candidates = [
            path / "apksigner"
            for path in build_tools_dir.iterdir()
            if path.is_dir() and (path / "apksigner").is_file()
        ]
    candidates.sort(
        key=lambda path: tuple(int(part) for part in re.findall(r"\d+", path.parent.name)),
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"SDK 中未找到 apksigner: {build_tools_dir}")
    return candidates[0]


def signed_path(apk_path: Path) -> Path:
    if apk_path.name.endswith("-unsigned.apk"):
        return apk_path.with_name(
            apk_path.name[:-len("-unsigned.apk")] + "-signed.apk"
        )
    return apk_path.with_name(f"{apk_path.stem}-signed{apk_path.suffix}")


def sign_apk(apk_path: Path, keystore: dict, sdk_path: str | None = None) -> Path:
    if not apk_path.is_file():
        raise FileNotFoundError(f"找不到需要签名的 APK: {apk_path}")
    output_path = signed_path(apk_path)
    command = [
        str(find_apksigner(sdk_path)), "sign",
        "--key", keystore["key_path"],
        "--cert", keystore["cert_path"],
        "--out", str(output_path), str(apk_path),
    ]
    print(f"使用 apksigner: {command[0]}")
    subprocess.run(command, check=True)
    print(f"签名成功: {output_path.resolve()}")
    return output_path


def parse_secexp(value: str) -> int:
    if not value or not isinstance(value, str):
        raise ValueError("secexp 不能为空")
    allowed = {
        "__builtins__": {},
        "abs": abs,
        "bin": bin,
        "hex": hex,
        "int": int,
        "oct": oct,
        "pow": pow,
    }
    try:
        result = eval(value, allowed, {})
    except Exception as exc:  # pragma: no cover - exercised through CLI validation
        raise ValueError(f"secexp 表达式无效: {value!r} ({exc})") from exc
    if isinstance(result, bool) or not isinstance(result, int):
        raise ValueError(f"secexp 必须求值为整数，当前值为 {result!r}")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="使用 NIST256p 私钥签名 APK")
    parser.add_argument("apk", type=Path, nargs="?", help="待签名 APK 路径")
    parser.add_argument("--mode", choices=("pem", "secexp"), default=None)
    parser.add_argument("--pem", type=Path, default=DEFAULT_PEM_PATH)
    parser.add_argument("--secexp", help="Python 整数表达式，例如 2**64")
    parser.add_argument("--sdk", help="Android SDK 路径，默认读取 ANDROID_HOME")
    parser.add_argument(
        "--test-deterministic",
        action="store_true",
        help="验证同一 key + message 的确定性 ECDSA 输出是否完全一致",
    )
    parser.add_argument(
        "--message",
        default="deterministic-ecdsa-test-message",
        help="用于确定性签名测试的消息内容",
    )
    args = parser.parse_args()
    if args.secexp is not None and args.mode is None:
        args.mode = "secexp"
    if args.mode is None:
        args.mode = "pem"
    return args


def main() -> int:
    args = parse_args()
    if args.mode == "pem":
        private_key = private_key_from_pem(args.pem)
    else:
        if args.secexp is None:
            raise SystemExit("--mode secexp 必须同时提供 --secexp")
        private_key = private_key_from_secexp(parse_secexp(args.secexp))

    if args.test_deterministic:
        payload = args.message.encode("utf-8")
        sig1 = deterministic_ecdsa_sign(private_key, payload)
        sig2 = deterministic_ecdsa_sign(private_key, payload)
        print(f"message={args.message!r}")
        print(f"sig1={sig1.hex()}")
        print(f"sig2={sig2.hex()}")
        print(f"same={sig1 == sig2}")
        return 0

    if args.apk is None:
        raise SystemExit("必须提供 APK 路径，或使用 --test-deterministic 仅做确定性签名测试")
    keystore = make_keystore(private_key, Path.home() / ".ssh")
    sign_apk(args.apk, keystore, args.sdk)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as error:
        print(f"错误: {error}", file=sys.stderr)
        raise SystemExit(1)
