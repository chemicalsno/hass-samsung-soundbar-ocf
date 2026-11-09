"""Synchronous OCF-over-DTLS(PSK) client for the Samsung soundbar.

Owner authentication uses the per-appliance OwnerPSK recovered from the
SmartThings app. The identity is carried as raw bytes (it can contain a NUL),
so the OpenSSL PSK path is unusable; the vendored pure-Python DTLS engine
carries the identity by length.

Each high-level operation opens a fresh DTLS session and closes it with a
close_notify. The appliance frees a peer entry only on close_notify and has no
idle timeout (measured upstream, QuiteYellow/SmartThings-Local #119), so a
long-lived or leaked session would eventually exhaust its peer slots. The
handshake is sub-second, so a session per poll cycle is cheap insurance.

Blocking by design: Home Assistant drives it through the executor.
"""

from __future__ import annotations

import logging
import os
import socket
import struct
import threading
import time
import uuid
from typing import Any

import cbor2

try:
    from .dtls_psk import DtlsError, DtlsPskClient, WantRead
except ImportError:  # run as a standalone script for validation
    from dtls_psk import DtlsError, DtlsPskClient, WantRead

_LOGGER = logging.getLogger(__name__)

UNSECURED_PORT = 5683
CONTENT_FORMAT_OCF_CBOR = 10000
_GET, _POST = 0x01, 0x02


class OcfError(Exception):
    """Any failure talking to the soundbar."""


def _token() -> bytes:
    tok = os.urandom(8)
    while 0xFF in tok:  # 0xFF collides with the CoAP payload marker when split
        tok = os.urandom(8)
    return tok


def _encode_option(buf: bytearray, last: int, number: int, value: bytes) -> int:
    delta = number - last
    length = len(value)
    buf.append((delta << 4) | length if length < 13 else (delta << 4) | 13)
    if length >= 13:
        buf.append(length - 13)
    buf += value
    return number


def _build(code: int, path: str, query: list[str] | None, payload: bytes | None) -> tuple[bytes, int, bytes]:
    mid = int.from_bytes(os.urandom(2), "big")
    tok = _token()
    out = bytearray([0x48, code, (mid >> 8) & 0xFF, mid & 0xFF]) + tok  # TKL=8, CON
    last = 0
    for seg in [s for s in path.split("/") if s]:
        last = _encode_option(out, last, 11, seg.encode())
    for q in query or []:
        last = _encode_option(out, last, 15, q.encode())
    if payload is not None:
        last = _encode_option(out, last, 12, struct.pack(">H", CONTENT_FORMAT_OCF_CBOR))
        out.append(0xFF)
        out += payload
    return bytes(out), mid, tok


def _parse(buf: bytes) -> tuple[int, int, int, bytes, bytes]:
    typ = (buf[0] >> 4) & 3
    tkl = buf[0] & 0x0F
    code = buf[1]
    mid = (buf[2] << 8) | buf[3]
    tok = buf[4 : 4 + tkl]
    i = 4 + tkl
    while i < len(buf):
        if buf[i] == 0xFF:
            i += 1
            break
        delta = buf[i] >> 4
        length = buf[i] & 0x0F
        i += 1
        if delta == 13:
            i += 1
        elif delta == 14:
            i += 2
        if length == 13:
            length = buf[i] + 13
            i += 1
        elif length == 14:
            length = struct.unpack(">H", buf[i : i + 2])[0] + 269
            i += 2
        i += length
    return typ, code, mid, tok, buf[i:]


def discover_secure_port(host: str, timeout: float = 5.0) -> int:
    """Read the ephemeral secure DTLS port from the unsecured /oic/res (p.port)."""
    msg, _, _ = _build(_GET, "/oic/res", ["rt=oic.r.doxm"], None)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(msg, (host, UNSECURED_PORT))
        resp, _ = sock.recvfrom(4096)
    except OSError as err:  # timeout / host unreachable: transient, let HA retry
        raise OcfError(f"cannot reach {host}: {err}") from err
    finally:
        sock.close()
    try:
        _, _, _, _, payload = _parse(resp)
        reps = cbor2.loads(payload)
    except (cbor2.CBORDecodeError, IndexError, struct.error) as err:
        raise OcfError(f"malformed /oic/res from {host}: {err}") from err
    for dev in reps:
        for link in dev.get("links", []):
            policy = link.get("p", {})
            if policy.get("sec") and policy.get("port"):
                return int(policy["port"])
    raise OcfError("no secure port advertised in /oic/res")


class _Session:
    """One open DTLS session; use via OcfPskClient as a context manager."""

    def __init__(self, sock: socket.socket, dtls: DtlsPskClient, port: int) -> None:
        self._sock = sock
        self._dtls = dtls
        self.port = port

    @staticmethod
    def _flush(dtls: DtlsPskClient, sock: socket.socket) -> None:
        while True:
            try:
                sock.send(dtls.bio_read(65535))
            except WantRead:
                return

    def request(self, code: int, path: str, payload: bytes | None, overall: float = 12.0) -> tuple[int, dict | None]:
        msg, mid, tok = _build(code, path, None, payload)
        self._dtls.send(msg)
        self._flush(self._dtls, self._sock)
        deadline = time.monotonic() + overall
        while time.monotonic() < deadline:
            try:
                self._dtls.bio_write(self._sock.recv(65535))
            except TimeoutError:
                try:
                    self._dtls.DTLSv1_handle_timeout()
                except Exception:  # noqa: BLE001 - best-effort retransmit
                    pass
                self._flush(self._dtls, self._sock)
                continue
            while True:
                try:
                    pl = self._dtls.recv(65535)
                except WantRead:
                    break
                typ, rcode, rmid, rtok, body = _parse(pl)
                if typ == 2 and rcode == 0 and rmid == mid:
                    continue  # empty ACK, response deferred to a separate CON
                if rtok == tok and rcode != 0:
                    if typ == 0:  # separate CON: acknowledge so retransmits stop
                        self._dtls.send(bytes([0x60, 0x00, (rmid >> 8) & 0xFF, rmid & 0xFF]))
                        self._flush(self._dtls, self._sock)
                    if not body:
                        return rcode, None
                    try:
                        return rcode, cbor2.loads(body)
                    except cbor2.CBORDecodeError as err:
                        # Oversized resources arrive blockwise; not handled here.
                        raise OcfError(f"{path}: undecodable body ({len(body)}B): {err}") from err
        raise OcfError(f"no response to {path}")

    def close(self) -> None:
        try:
            self._dtls.shutdown()  # queues close_notify so the bar frees the peer
            self._flush(self._dtls, self._sock)
        except Exception:  # noqa: BLE001 - closing is best-effort
            pass
        self._sock.close()


class OcfPskClient:
    """Owner-authenticated access to the bar, one short session per operation."""

    def __init__(self, host: str, identity: str | bytes, key: str | bytes) -> None:
        self._host = host
        self._identity = uuid.UUID(identity).bytes if isinstance(identity, str) else bytes(identity)
        self._key = bytes.fromhex(key) if isinstance(key, str) else bytes(key)
        self._lock = threading.Lock()

    def _open(self) -> _Session:
        port = discover_secure_port(self._host)  # rotates per boot, so read it every time
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect((self._host, port))
        except OSError as err:
            sock.close()
            raise OcfError(f"cannot connect to {self._host}:{port}: {err}") from err
        sock.settimeout(2.0)
        dtls = DtlsPskClient(self._identity, self._key)
        for _ in range(40):
            try:
                dtls.do_handshake()
                break
            except WantRead:
                pass
            except DtlsError as err:
                sock.close()
                raise OcfError(f"DTLS handshake failed: {err}") from err
            _Session._flush(dtls, sock)
            try:
                dtls.bio_write(sock.recv(65535))
            except TimeoutError:
                try:
                    dtls.DTLSv1_handle_timeout()
                except Exception:  # noqa: BLE001
                    pass
        else:
            sock.close()
            raise OcfError("DTLS handshake did not complete")
        _LOGGER.debug("connected to %s secure port %s", self._host, port)
        return _Session(sock, dtls, port)

    # -- public operations (each is one open/close cycle) ----------------

    def _one(self, code: int, path: str, payload: bytes | None) -> dict | None:
        with self._lock:
            session = self._open()
            try:
                rcode, rep = session.request(code, path, payload)
            finally:
                session.close()
        if rcode >> 5 != 2:
            raise OcfError(f"{'POST' if code == _POST else 'GET'} {path} -> {rcode >> 5}.{rcode & 0x1F:02d}")
        return rep

    def device(self) -> dict:
        rep = self._one(_GET, "/oic/d", None)
        if not rep:
            raise OcfError("empty /oic/d")
        return rep

    def write(self, path: str, properties: dict[str, Any]) -> dict | None:
        return self._one(_POST, path, cbor2.dumps(properties))

    def poll(self, paths: list[str] | tuple[str, ...]) -> dict[str, dict]:
        """One session, GET every path, close. Returns the ones that answered 2.xx."""
        out: dict[str, dict] = {}
        with self._lock:
            session = self._open()
            try:
                for path in paths:
                    try:
                        rcode, rep = session.request(_GET, path, None)
                    except OcfError as err:
                        _LOGGER.debug("poll %s: %s", path, err)
                        continue
                    if rcode >> 5 == 2 and isinstance(rep, dict):
                        out[path] = rep
            finally:
                session.close()
        return out

    def discover(self, resources: tuple[str, ...]) -> dict[str, dict]:
        return self.poll(resources)

    def close(self) -> None:
        """No persistent state; present for API symmetry."""


if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.INFO)
    host = sys.argv[1]
    if len(sys.argv) == 3:  # host, path to owner-psk.json
        secret = json.load(open(sys.argv[2]))
        identity, key = secret["psk_identity"], secret["psk_hex"]
    else:  # host, identity, key
        identity, key = sys.argv[2], sys.argv[3]

    print("secure port:", discover_secure_port(host))
    cli = OcfPskClient(host, identity, key)
    print("device:", json.dumps(cli.device()))
    try:
        from const import NETWORKAUDIO_RESOURCES  # type: ignore

        reps = cli.poll(NETWORKAUDIO_RESOURCES)
        print(f"reachable resources: {len(reps)}")
        for p, rep in reps.items():
            keys = [k for k in rep if k.startswith("x.com.samsung.networkaudio.")]
            print(f"  {p:42s} if={rep.get('if')} props={keys}")
    finally:
        cli.close()
