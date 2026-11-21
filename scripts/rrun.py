#!/usr/bin/env python3
"""Jalankan perintah di host remote via SSH password-auth (paramiko).

Password dibaca dari file yang ditunjuk env RSH_PASSFILE (default
~/.rsh_pass, harus mode 0600) atau dari env RSH_PASS. Password TIDAK
pernah ditulis ke stdout/stderr.

Pemakaian:
    python3 rrun.py 'perintah shell'
    python3 rrun.py -s <<'EOF'      # baca skrip dari stdin
    ...
    EOF

Opsi:
    -s            baca perintah dari stdin (bukan argumen)
    -t SECONDS    timeout (default 120)
    --sudo        jalankan perintah lewat `sudo -S` (password dikirim via stdin,
                  sehingga tidak muncul di argv/proses list remote)
    --put LOKAL REMOTE
                  unggah satu berkas lewat SFTP, lalu selesai (tanpa menjalankan
                  perintah shell)
    --get REMOTE LOKAL
                  unduh satu berkas lewat SFTP, lalu selesai
"""
import os
import shlex
import sys

import paramiko

HOST = os.environ.get("RSH_HOST", "192.168.18.222")
USER = os.environ.get("RSH_USER", "nms")


def load_password() -> str:
    pw = os.environ.get("RSH_PASS")
    if pw:
        return pw
    here = os.path.dirname(os.path.abspath(__file__))
    default = os.path.join(os.path.dirname(here), ".secrets", "rsh_pass")
    path = os.environ.get("RSH_PASSFILE", default)
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read().strip("\r\n")


def main() -> int:
    args = sys.argv[1:]
    from_stdin = False
    timeout = 120
    use_sudo = False
    upload = None
    download = None
    rest = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-s":
            from_stdin = True
        elif a == "--sudo":
            use_sudo = True
        elif a == "--put":
            upload = (args[i + 1], args[i + 2])
            i += 2
        elif a == "--get":
            download = (args[i + 1], args[i + 2])
            i += 2
        elif a == "-t":
            i += 1
            timeout = int(args[i])
        else:
            rest.append(a)
        i += 1

    command = sys.stdin.read() if from_stdin else " ".join(rest)
    if not upload and not download and not command.strip():
        print("tidak ada perintah", file=sys.stderr)
        return 2

    try:
        password = load_password()
    except OSError as exc:
        print(f"gagal membaca password: {exc}", file=sys.stderr)
        return 3

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            HOST,
            username=USER,
            password=password,
            timeout=15,
            allow_agent=False,
            look_for_keys=False,
        )
    except paramiko.AuthenticationException:
        print("AUTH_GAGAL: password ditolak", file=sys.stderr)
        return 4
    except Exception as exc:  # noqa: BLE001
        print(f"KONEKSI_GAGAL: {exc}", file=sys.stderr)
        return 5

    if use_sudo:
        command = "sudo -S -p '' bash -c " + shlex.quote(command)

    if upload:
        local, remote = upload
        size = os.path.getsize(local)
        try:
            sftp = client.open_sftp()
            sftp.put(local, remote)
            sftp.close()
        finally:
            client.close()
        print(f"unggah: {local} -> {remote} ({size:,} bytes)")
        return 0

    if download:
        remote, local = download
        try:
            sftp = client.open_sftp()
            sftp.get(remote, local)
            sftp.close()
        finally:
            client.close()
        print(f"unduh: {remote} -> {local} ({os.path.getsize(local):,} bytes)")
        return 0

    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        if use_sudo:
            stdin.write(password + "\n")
            stdin.flush()
        stdin.close()
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        rc = stdout.channel.recv_exit_status()
    finally:
        client.close()

    if out:
        sys.stdout.write(out)
        if not out.endswith("\n"):
            sys.stdout.write("\n")
    if err:
        sys.stderr.write(err)
        if not err.endswith("\n"):
            sys.stderr.write("\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
