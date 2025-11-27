#!/usr/bin/env python3
"""
run_all.py — Orquestrador profissional para Mina_ATR_V2

Características principais:
- Construção opcional (cmake + make)
- Inicialização opcional do broker MQTT (mosquitto)
- Inicia várias instâncias do binário C++ (`atr_mina`) cada uma com `--truck-id` e `--route`
- Inicia a interface Python (usando `interface/venv` quando disponível)
- Monitora e registra processos, encerra limpo com Ctrl+C
- Faz checagens básicas de saúde (porta MQTT e processos ativos)

Este script permite rodar todo o sistema a partir de um único ponto de entrada,
útil para avaliação ou execução em container.
"""

from pathlib import Path
import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import json
import threading

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
BIN = BUILD_DIR / "atr_mina"
INTERFACE_DIR = ROOT / "interface"
INTERFACE_SCRIPT = INTERFACE_DIR / "painel_controle.py"
LOG_DIR = ROOT / "logs"
SOCKET_PATH = str(ROOT / "run_all.sock")

children = []
broker_proc = None


def info(msg):
    print(f"[run_all] {msg}")


def ensure_dirs():
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def run_process(cmd, cwd=None, env=None, logfile=None, tag=None):
    """Start process (no shell) and record it with logfile file handle.

    `tag` is an opaque identifier (e.g. truck id) stored alongside the process tuple.
    """
    info(f"starting: {' '.join(cmd)} (cwd={cwd})")
    if logfile:
        fh = open(logfile, "ab")
        p = subprocess.Popen(cmd, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT, env=env)
    else:
        fh = None
        p = subprocess.Popen(cmd, cwd=cwd, env=env)
    children.append((p, fh, tag))
    return p


def build_project():
    if not BUILD_DIR.exists():
        BUILD_DIR.mkdir(parents=True)
    info("running cmake ..")
    r = subprocess.run(["cmake", ".."], cwd=str(BUILD_DIR))
    if r.returncode != 0:
        raise RuntimeError("cmake failed")
    info("running make -j")
    r2 = subprocess.run(["make", "-j", str(os.cpu_count() or 2)], cwd=str(BUILD_DIR))
    if r2.returncode != 0:
        raise RuntimeError("make failed")


def start_broker():
    mosq = shutil.which("mosquitto")
    if not mosq:
        info("mosquitto not found; skipping broker start (use MQTT_BROKER=mock to run without broker)")
        return None
    logfile = LOG_DIR / "mosquitto.log"
    info("starting mosquitto (verbose)")
    p = subprocess.Popen([mosq, "-v"], stdout=open(logfile, "ab"), stderr=subprocess.STDOUT)
    # wait briefly and check port
    time.sleep(0.6)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(1.0)
        s.connect(("127.0.0.1", 1883))
        s.close()
        info("mosquitto listening on 127.0.0.1:1883")
    except Exception:
        info("mosquitto not responding on 127.0.0.1:1883 (continue anyway)")
    return p


def start_truck(truck_id: int, route: str, broker: str):
    if not BIN.exists():
        raise FileNotFoundError(f"binary not found at {BIN}; run with --build first")
    logfile = LOG_DIR / f"truck_{truck_id}.log"
    env = os.environ.copy()
    env["MQTT_BROKER"] = broker
    cmd = [str(BIN), f"--truck-id={truck_id}", f"--route={route}"]
    return run_process(cmd, cwd=str(BUILD_DIR), env=env, logfile=str(logfile), tag=f"truck:{truck_id}")


def start_interface(broker: str, use_venv=True):
    if not INTERFACE_SCRIPT.exists():
        info("interface script not found; skipping")
        return None
    python_exec = None
    venv_python = INTERFACE_DIR / "venv" / "bin" / "python"
    if use_venv and venv_python.exists():
        python_exec = str(venv_python)
    else:
        python_exec = shutil.which("python3") or shutil.which("python")
    if not python_exec:
        info("python not found; skipping interface")
        return None
    logfile = LOG_DIR / "interface.log"
    env = os.environ.copy()
    env["MQTT_BROKER"] = broker
    return run_process([python_exec, str(INTERFACE_SCRIPT)], cwd=str(INTERFACE_DIR), env=env, logfile=str(logfile), tag="interface")


def check_port(host: str, port: int, timeout=1.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


def stop_all(signum=None, frame=None):
    info("stopping all children...")
    for p, fh, tag in children:
        try:
            if p.poll() is None:
                info(f"terminating pid={p.pid}")
                p.terminate()
        except Exception:
            pass
    time.sleep(1.0)
    for p, fh, tag in children:
        try:
            if p.poll() is None:
                info(f"killing pid={p.pid}")
                p.kill()
        except Exception:
            pass
        try:
            if fh:
                fh.close()
        except Exception:
            pass
    global broker_proc
    if broker_proc:
        try:
            info(f"stopping broker pid={broker_proc.pid}")
            broker_proc.terminate()
            time.sleep(0.5)
            if broker_proc.poll() is None:
                broker_proc.kill()
        except Exception:
            pass
    info("all stopped")
    # remove ipc socket if exists
    try:
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)
    except Exception:
        pass
    sys.exit(0)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--build", action="store_true", help="Run cmake && make before starting")
    p.add_argument("--num-trucks", type=int, default=1, help="Number of truck instances to start")
    p.add_argument("--routes-dir", type=str, default="routes", help="Directory containing .route files")
    p.add_argument("--start-broker", action="store_true", help="Start local mosquitto broker")
    p.add_argument("--broker", type=str, default="localhost", help="MQTT broker address (default localhost). Use 'mock' to disable broker")
    p.add_argument("--no-interface", action="store_true", help="Do not start the Python interface")
    return p.parse_args()


def repl_loop(broker: str):
    """Simple REPL to control the orchestrator at runtime.

    Commands:
      - addtruck <id> <route>   : start a new truck process
      - list                    : list managed processes
      - help                    : show this help
      - exit|quit               : stop everything
    """
    info("REPL ready. Use 'addtruck <id> <route>' or 'help'.")
    while True:
        try:
            line = input("run_all> ")
        except EOFError:
            break
        except KeyboardInterrupt:
            break
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        cmd = parts[0].lower()
        if cmd in ("exit", "quit"):
            stop_all()
        elif cmd == "help":
            print("commands: addtruck <id> <route> | list | help | exit")
        elif cmd == "list":
            for p, fh, tag in children:
                status = "running" if p.poll() is None else f"exited({p.returncode})"
                print(f"pid={p.pid} tag={tag} status={status}")
        elif cmd == "addtruck":
            if len(parts) < 3:
                print("usage: addtruck <id> <route>")
                continue
            try:
                tid = int(parts[1])
            except ValueError:
                print("invalid id; must be integer")
                continue
            route = parts[2]
            # check if id already exists
            exists = any(tag == f"truck:{tid}" for _p, _fh, tag in children)
            if exists:
                print(f"truck id {tid} already managed")
                continue
            try:
                # validate route before starting
                ok, reason = validate_route_file(route)
                if not ok:
                    print(f"route validation failed: {reason}")
                    continue
                p = start_truck(tid, route, broker)
                print(f"started truck id={tid} pid={p.pid} route={route}")
                # publish ack (try paho-mqtt first, fallback to mosquitto_pub)
                if broker != "mock":
                    msg = json.dumps({"id": tid, "pid": p.pid, "route": route})
                    try:
                        publish_message(broker, "/mina/gerente/add_truck/ack", msg)
                    except Exception:
                        info("failed to publish ack")
            except Exception as e:
                print(f"failed to start truck: {e}")
        else:
            print("unknown command; type 'help'")


def handle_ipc_conn(conn):
    try:
        data = b""
        # read until newline or EOF
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in chunk:
                break
        line = data.decode("utf-8", errors="ignore").strip()
        if not line:
            resp = {"status": "error", "reason": "empty command"}
            conn.sendall((json.dumps(resp) + "\n").encode())
            return
        parts = line.split()
        cmd = parts[0].lower()
        if cmd == "addtruck":
            if len(parts) < 3:
                resp = {"status": "error", "reason": "usage: addtruck <id> <route>"}
                conn.sendall((json.dumps(resp) + "\n").encode())
                return
            try:
                tid = int(parts[1])
            except ValueError:
                resp = {"status": "error", "reason": "invalid id"}
                conn.sendall((json.dumps(resp) + "\n").encode())
                return
            route = parts[2]
            exists = any(tag == f"truck:{tid}" for _p, _fh, tag in children)
            if exists:
                resp = {"status": "error", "reason": "truck id already exists"}
                conn.sendall((json.dumps(resp) + "\n").encode())
                return
            ok, reason = validate_route_file(route)
            if not ok:
                resp = {"status": "error", "reason": f"route validation failed: {reason}"}
                conn.sendall((json.dumps(resp) + "\n").encode())
                return
            try:
                p = start_truck(tid, route, os.environ.get("MQTT_BROKER", "localhost"))
                resp = {"status": "ok", "id": tid, "pid": p.pid, "route": route}
                conn.sendall((json.dumps(resp) + "\n").encode())
                # publish ack as well
                try:
                    publish_message(os.environ.get("MQTT_BROKER", "localhost"), "/mina/gerente/add_truck/ack", json.dumps(resp))
                except Exception:
                    pass
            except Exception as e:
                resp = {"status": "error", "reason": str(e)}
                conn.sendall((json.dumps(resp) + "\n").encode())
        elif cmd == "list":
            lst = []
            for p, fh, tag in children:
                status = "running" if p.poll() is None else f"exited({p.returncode})"
                lst.append({"pid": p.pid, "tag": tag, "status": status})
            conn.sendall((json.dumps({"status": "ok", "procs": lst}) + "\n").encode())
        else:
            conn.sendall((json.dumps({"status": "error", "reason": "unknown command"}) + "\n").encode())
    finally:
        try:
            conn.close()
        except Exception:
            pass


def ipc_server():
    # remove stale socket
    try:
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)
    except Exception:
        pass
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCKET_PATH)
    srv.listen(5)
    os.chmod(SOCKET_PATH, 0o660)
    info(f"IPC socket listening on {SOCKET_PATH}")
    try:
        while True:
            conn, _ = srv.accept()
            t = threading.Thread(target=handle_ipc_conn, args=(conn,), daemon=True)
            t.start()
    except Exception:
        pass
    finally:
        try:
            srv.close()
        except Exception:
            pass


    def publish_message(broker: str, topic: str, message: str, qos: int = 0, retain: bool = False, timeout: float = 2.0):
        """Publish a message to `broker:1883` on `topic`.

        Attempts to use paho.mqtt.publish.single; if paho not available, falls back to `mosquitto_pub`.
        """
        # try paho
        try:
            import paho.mqtt.publish as publish
        except Exception:
            publish = None

        if publish:
            try:
                publish.single(topic, payload=message, hostname=broker, qos=qos, retain=retain, keepalive=int(timeout))
                return True
            except Exception as e:
                info(f"paho publish failed: {e}")

        # fallback to mosquitto_pub if available
        pub_cmd = shutil.which("mosquitto_pub")
        if pub_cmd:
            try:
                subprocess.run([pub_cmd, "-h", broker, "-t", topic, "-m", message], check=False)
                return True
            except Exception as e:
                info(f"mosquitto_pub publish failed: {e}")

        info("no mqtt publisher available (install paho-mqtt or mosquitto_pub)")
        return False


    def validate_route_file(route_path: str):
        """Validate that `route_path` exists and contains >=2 waypoints (lines with numeric coords).

        Returns (True, None) if ok, otherwise (False, reason).
        """
        p = Path(route_path)
        if not p.exists():
            return False, f"file not found: {route_path}"
        try:
            lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()]
        except Exception as e:
            return False, f"failed to read file: {e}"
        pts = []
        for ln in lines:
            if not ln or ln.startswith("#"):
                continue
            parts = ln.split()
            # expect at least two numeric columns (x y) optionally speed
            if len(parts) < 2:
                continue
            try:
                float(parts[0]); float(parts[1])
                pts.append((parts[0], parts[1]))
            except Exception:
                continue
        if len(pts) < 2:
            return False, f"route must contain at least 2 valid waypoints (found {len(pts)})"
        return True, None


def main():
    args = parse_args()
    ensure_dirs()
    signal.signal(signal.SIGINT, stop_all)
    signal.signal(signal.SIGTERM, stop_all)

    try:
        if args.build:
            build_project()

        global broker_proc
        broker = args.broker
        if args.start_broker:
            broker_proc = start_broker()
            time.sleep(0.8)
            if broker_proc and not check_port("127.0.0.1", 1883):
                info("broker appears not ready; continuing but some features may not work")

        if broker == "mock" and not broker_proc:
            info("Using MQTT mock mode (no broker) — processes will run with MQTT_BROKER=mock")

        # prepare route files
        routes_path = Path(args.routes_dir)
        route_files = []
        if routes_path.is_dir():
            for pth in sorted(routes_path.glob("*.route")):
                route_files.append(str(pth))
        elif routes_path.exists():
            # single file path
            for _ in range(args.num_trucks):
                route_files.append(str(routes_path))
        # fill with example.route if not enough
        while len(route_files) < args.num_trucks:
            route_files.append(str(ROOT / "routes" / "example.route"))

        # start trucks
        for i in range(1, args.num_trucks + 1):
            r = route_files[(i - 1) % len(route_files)]
            start_truck(i, r, broker)
            time.sleep(0.2)

        if not args.no_interface:
            start_interface(broker)

        info("all processes started — monitoring loop")
        # start interactive REPL in background
        repl = threading.Thread(target=repl_loop, args=(broker,), daemon=True)
        repl.start()
        # basic monitoring loop
        while True:
            # report status
            for p, fh, tag in list(children):
                if p.poll() is not None:
                    info(f"process pid={p.pid} exited (code={p.returncode}) tag={tag}")
                    try:
                        children.remove((p, fh, tag))
                    except ValueError:
                        pass
            time.sleep(1.0)

    except Exception as e:
        info(f"fatal error: {e}")
        stop_all()


if __name__ == "__main__":
    main()
