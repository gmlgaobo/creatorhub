from __future__ import annotations

import ipaddress
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def local_ipv4_addresses() -> list[str]:
    result = {"127.0.0.1"}
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            value = item[4][0]
            if value and not value.startswith("169.254."):
                result.add(value)
    except OSError:
        pass
    return sorted(result)


def ensure_certificate(directory: Path) -> tuple[Path, Path, str]:
    cert_path = directory / "creatorhub.crt"
    key_path = directory / "creatorhub.key"
    if cert_path.exists() and key_path.exists():
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        return cert_path, key_path, cert.fingerprint(hashes.SHA256()).hex().upper()

    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CreatorHub Local")])
    sans = [x509.DNSName("localhost"), x509.DNSName(socket.gethostname())]
    sans.extend(x509.IPAddress(ipaddress.ip_address(value))
                for value in local_ipv4_addresses())
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(sans), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(key, hashes.SHA256())
    )
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path, cert.fingerprint(hashes.SHA256()).hex().upper()
